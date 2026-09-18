## Context

参见 `proposal.md` 与 delta specs。P09 已提供以 `kind` 注册的持久 worker；P10 文档 repository 与 splitter 已存在；P06 Qwen provider 和 P07 Milvus store 都是显式注入、可替换的边界。本 change 需要把这些边界组合为一个不在 SQLite 事务内执行网络 I/O 的 durable handler。

## Goals / Non-Goals

**Goals:**

- 领域 task 与 background job 通过 resourceType/resourceId 关联，并让领域状态可由 worker 生命周期安全更新。
- contract-first 增加索引任务 path/schema，生成 Python/TypeScript 类型后再实现 API。
- handler 完整执行切分、embedding、Milvus 初始化、精确删除和单次批量写入，失败可恢复且不泄露异常。
- 上传成功与首次建任务解耦，重试/重建保留来源，所有业务 I/O 使用显式 owner scope。

**Non-Goals:**

- 不增加 `background_jobs.job_id`、临时 asyncio 任务存储、跨系统分布式事务、全文检索或 MinIO 原文存储。
- 不自动为上传创建索引任务；不连接生产数据库；真实 smoke 只在可用凭据和服务下执行。

## Decisions

1. **领域表与 P09 关联。** 新 migration 创建 `document_index_tasks`，字段使用 snake_case 映射公开 camelCase；task repository 以 owner/KB/document 复合条件读写。创建 task 与 background job 在同一 SQLite 短事务中完成，job 只保存 task ID 和必要的 retry 参数，避免增加 jobId 冗余列。选择 resource association 而不是新增 FK 列，是因为 P09 已定义该稳定关联。
2. **状态以领域 task 为准。** queued 映射 pending，claim 时先写 running，handler 成功/失败/取消在 lease 仍有效时同步领域记录；worker recovery 将过期 running 按 job 结果恢复。领域状态不会写成 `indexed`，文档表 CHECK 与 DTO 一起升级。
3. **固定 handler 顺序。** handler 重新 owner-scoped 读取文档并调用 `DocumentChunkingService.chunks`；一次调用 provider 的接口让 P06 自身按最多 10 批次并按输入顺序返回；随后在线程池中按 `initialize -> delete_document -> insert_chunks` 调用向量 adapter。embedding 成功但 Milvus 删除/写入失败时只持久化失败并由重试再次重建，明确接受至少一次外部副作用。
4. **向量接口显式批量。** P07 `insert` 保持兼容但新增 `insert_chunks` 作为索引专用语义，先验证整批、只 initialize 一次，再向官方 client 单次 insert；fake adapter 记录调用顺序与全部 rows。`VectorChunk` metadata 由 chunk metadata 与归属字段合并，chunk ID 使用 task/document/index 的稳定组合或新 UUID，不能丢失顺序。
5. **API 与前端。** canonical OpenAPI 增加 task schema、create request、四条 document-scoped path 及统一错误 responses；运行生成脚本同步 generated contracts。前端上传成功后显式 POST create task，展示文档返回的五态和 task 查询/重试/取消，不创建第二滚动容器。
6. **错误与取消。** handler 只把固定类别映射到安全中文 failureReason，绝不写入上游异常原文；协作检查 `JobContext.cancelled`，取消优先于成功。SQLite 状态提交与 Milvus 网络操作分离，文档成功只在全部向量写入完成后设置。

## Risks / Trade-offs

- [SQLite 与 Milvus 没有跨系统原子事务] -> 精确 scope 删除、单次批写、失败状态和重试重建；不声称事务原子。
- [至少一次执行可能重复外部调用] -> 每次 handler 先删除当前文档旧向量，再一次批量写入；记录 task 来源和安全状态，避免旧 chunks 残留。
- [真实 Qwen/Milvus 需要服务与凭据] -> fake/local 测试与真实 smoke 分开报告，缺少条件时明确未执行。
- [前端任务请求可能在上传响应后失败] -> 文档保持 pending，用户可从文档工作流重新触发首次任务；API 不在上传端隐式补偿。

## Migration Plan

### 实现核对（2026-09-15）

本次前端范围为带认证版本隔离的上传客户端及五态中文展示数据，保留现有知识库占位页，不新增可见 UI。POST 创建和 retry 均创建新领域 attempt，已有终态时保留 retryOfTaskId。同一文档 pending/running 用 partial unique index 互斥，删除/覆盖遇到活动任务返回 409。通用 background retry 对索引关联任务返回 409，不能绕过领域 attempt。领域表没有 jobId；增加 cancelRequestedAt 以表示运行中的取消请求。

job 状态事件在同一 session 内投影到领域 task 与当前文档；claim、finish、cancel、timeout、shutdown、recover 都覆盖，不依靠 GET 修复。handler 不提前写 succeeded，由 worker 在 insert 完成并检查 lease/取消后提交终态。同步 SDK I/O 取消后等待有界线程结束；取消发生于已发送 insert 时外部副作用可能存在，但不标记成功，下一次重建精确清理。SQLite lease 不构成 Milvus 跨进程 fencing，不承诺异常网络分区时 exactly-once 或原子可见性。

chunkId 使用 UUID4，source 为 filename，createdAt 为本次 aware UTC，metadata 保留 index、start/end、strategy、headings、chunkingConfig 和 owner/tenant/document/KB。完整向量记录在删除旧 chunks 前预验证。旧 indexed 状态在 migration 映射 succeeded，降级时 running/cancelled 映射 pending。


1. 在临时测试配置目录执行 Alembic upgrade head、重复 upgrade、check、downgrade/re-upgrade，并验证既有数据表和新表约束。
2. 先部署 contracts/backend，再启用前端显式创建任务；旧文档可由用户手动重建，不自动扫描补任务。
3. 回滚应用代码前保留 task 表；需要回滚 schema 时停止 worker，并执行 Alembic downgrade，不能删除既有向量或文档数据作为隐式回滚。
