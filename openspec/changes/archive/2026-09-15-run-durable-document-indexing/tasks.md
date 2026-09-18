## 1. 合同与迁移

- [x] 1.1 扩展 canonical OpenAPI 的索引任务状态、DTO、创建/查询/重试/取消 path、统一 envelope 和 operation metadata。
- [x] 1.2 运行 `scripts/generate_contracts.py`，补充跨语言 contract/runtime 校验与 path 对齐测试。
- [x] 1.3 新增 Alembic revision 创建 `document_index_tasks`、owner/父子复合外键、状态约束、活动任务唯一索引和 resource 关联测试；更新 P10 文档状态迁移且不增加 `jobId`。

## 2. 领域任务与状态投影

- [x] 2.1 实现 owner-scoped task record、Repository、创建/查询/重建/重试/取消及安全 failureReason 持久化。
- [x] 2.2 将 task 与 P09 `background_jobs` 在同一短事务创建，使用 `resourceType=document_index_task` 和 `resourceId=taskId`，处理重复活动任务和 retry 来源。
- [x] 2.3 扩展 P09 claim/finish/cancel/recover 状态投影，保证 queued/pending、取消优先、lease fencing 和通用 retry 409 语义。
- [x] 2.4 在文档 repository/service 中同步五态并阻止活动索引期间删除/覆盖；保证旧 attempt 不能覆盖最新投影。

## 3. 索引 Handler 与向量边界

- [x] 3.1 增加 `insert_chunks` 单次全量写入能力，完整验证 chunk/归属/metadata/向量后调用一次底层 Milvus insert。
- [x] 3.2 实现 durable document index handler：owner-scoped 重读文档、P10 全量切分、P06 有序 embedding、取消检查和安全阶段错误。
- [x] 3.3 按固定顺序执行 `initialize -> delete_document(scope) -> insert_chunks(all)`，构造完整 metadata 和 UUID chunkId，并在线程池中执行有界同步 Milvus I/O。
- [x] 3.4 在 FastAPI lifespan 默认注册 handler，注入 provider/vector/config，覆盖重启恢复、超时、失败重试和客户端断开。

## 4. HTTP 与前端客户端

- [x] 4.1 实现 document-scoped index task API，复用认证、OwnerScope、API envelope 和统一错误映射。
- [x] 4.2 实现前端上传成功后显式创建首次任务、状态查询/重建/重试/取消客户端方法，处理第二步失败且不引入第二滚动容器。
- [x] 4.3 添加 UI-ready 状态 DTO 与中文状态展示数据，不添加假按钮、假向量或未实现导航。

## 5. 验证与文档

- [x] 5.1 添加专项 backend 测试：上传后显式建任务、手动重建、>10 embedding 分批且单次 Milvus insert、初始化顺序、旧向量清理、完整 metadata、失败/重试/取消、worker 重启、owner 隔离和 envelope。
- [x] 5.2 添加 contracts/frontend 测试及生成漂移检查，验证五态在 OpenAPI、Python、TypeScript、API 和 UI-ready DTO 一致。
- [x] 5.3 执行临时配置 migration 全流程、backend/contracts 全门禁、`openspec validate --all --strict`、`git diff --check`；可用时执行真实 Qwen+Milvus smoke，否则记录未执行原因。
- [x] 5.4 运行 `python scripts/sync_wiki.py active run-durable-document-indexing` 并构建 docs，完成 OpenSpec verify、修复缺口、同步主 specs 后准备归档。
