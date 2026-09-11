## 1. 合同与规格
- [x] 在 `packages/api-contracts` 增加后台任务 DTO、状态枚举、错误码、四个 paths 和事件字段，并生成/同步 OpenAPI。
- [x] 将 delta spec 与现有认证、tenant、persistence 约定对齐，补充中文 WIKI 投影入口。

## 2. 持久化
- [x] 编写 Alembic migration 创建 `background_jobs`、`background_job_events`、索引和 sequence 约束。
- [x] 实现 owner-scoped repository：create/list/get/claim/heartbeat/recover/cancel/retry/append/list_events。
- [x] 使用临时 SQLite 测试覆盖 owner 隔离、并发唯一领取和事件顺序。

## 3. Runtime
- [x] 实现按 kind 的 handler registry 与脱敏日志。
- [x] 实现 worker polling、原子 lease、heartbeat、过期回收、restart 恢复、退避、maxAttempts、timeout 和协作式取消。
- [x] 在 FastAPI lifespan 启停 worker，验证停止时清理 lease 且不使用临时 create_task 作为最终运行时。

## 4. API 与验证
- [x] 实现四个认证 owner-scoped API 及错误映射，补充 API tests。
- [x] 运行 migration、backend lint/typecheck/test、contracts typecheck/test、frontend 受影响门禁、OpenSpec strict、git diff --check。
- [x] 执行 verify，修复 CRITICAL/WARNING，sync specs 与 WIKI，重新验证后归档。
