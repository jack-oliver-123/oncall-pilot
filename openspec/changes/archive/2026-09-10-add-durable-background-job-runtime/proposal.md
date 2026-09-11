## Why

文档索引和 AIOps 任务目前无法在客户端断开或进程重启后可靠恢复，临时 `asyncio.create_task` 会丢失状态、事件和租约。现在需要建立基于 SQLite 的持久后台任务运行时，统一承载任务生命周期、重试、取消和事件重放。

## What Changes

- 增加 `background_jobs` 与 `background_job_events` SQLite/Alembic 持久化模型。
- 增加按 `kind` 注册 handler 的 worker runtime，支持并发领取、租约、heartbeat、重启恢复、超时、指数退避和协作式取消。
- 增加 owner-scoped Repository 与 FastAPI lifespan 启停、后台任务查询/取消/重试 API。
- 在 `packages/api-contracts` 和 OpenAPI 中同步 schemas、错误码和路径合同；持久事件支持 AIOps 重连重放。

## Capabilities

### New Capabilities

- `durable-background-jobs`: 持久后台任务、事件、worker 生命周期、租约和 owner 隔离。
- `background-jobs-api`: 后台任务查询、取消、重试 HTTP 合同。

### Modified Capabilities

- `tenant-isolation`: 明确受信后台调度器的 owner 标识发现例外；所有业务读写仍强制 owner scope。

## Impact

影响 `apps/backend` 的 persistence、worker、FastAPI app factory/lifespan、Alembic migrations 与测试，`packages/api-contracts` 的 OpenAPI/TypeScript 合同，以及相关中文 WIKI。依赖现有 SQLite Repository、认证 `CurrentUser`/`OwnerScope` 和 tenant 隔离；不引入临时任务或生产数据库连接。
