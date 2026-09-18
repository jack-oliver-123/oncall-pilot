## Why

P10 已保存可索引正文并提供统一切分入口，但上传后没有可恢复的 embedding 与向量写入流程；进程退出、客户端断开或外部服务失败都会让文档状态无法可靠追踪。现在把文档索引作为 P09 的持久任务接入 P06 Qwen 与 P07 Milvus，为值班人员提供可观察、可重试、可重建的索引生命周期。

## What Changes

- 新增 `document_index_tasks` SQLite/Alembic 领域表，保存 owner、知识库、文档、状态、失败原因、来源任务和时间戳；不向 `background_jobs` 增加 `jobId` 列。
- 上传 API 只创建文档；客户端上传成功后显式创建首次索引任务，新增任务状态、重建/重试和取消接口，全部使用统一 API envelope。
- 注册 durable `document_index` handler：owner-scoped 重新读取文档，复用 P10 splitter，使用 P06 embedding，显式初始化并清理/批量写入 P07 Milvus，最后更新领域状态。
- 失败安全持久化并支持重启恢复、有限重试、手动重建和协作取消；SQLite 与 Milvus 之间不宣称跨系统原子事务。
- 扩展 contracts、Python DTO、前端知识文档工作流和专项测试，覆盖归属隔离、完整 metadata、批处理顺序及 API envelope。

## Capabilities

### New Capabilities

- `durable-document-indexing`: 文档索引领域任务、handler 顺序、状态恢复、重试、重建、取消和向量写入语义。
- `document-indexing-api`: 首次任务创建、状态查询、重试/重建与取消的认证 owner-scoped HTTP contract。

### Modified Capabilities

- `knowledge-documents`: 文档 index status 从旧状态集合升级为与索引任务一致的 `pending/running/succeeded/failed/cancelled`，上传不再隐式启动索引。
- `milvus-vector-store`: 增加显式初始化、旧文档向量精确清理和一次性批量写入全部 chunk records 的 handler-facing contract。
- `durable-background-jobs`: 注册文档索引 kind，并将底层 queued 状态映射为领域 pending。

## Impact

影响 `packages/api-contracts` OpenAPI/生成类型、`apps/backend` migration、文档 repository/service、durable worker 注册、Qwen/Milvus adapter 与测试，以及 `apps/frontend` 知识文档上传后的显式建任务和状态展示。需要运行 Alembic、backend/contracts/frontend 质量门禁；真实 Qwen+Milvus smoke 仅在本机存在凭据和服务时执行。
