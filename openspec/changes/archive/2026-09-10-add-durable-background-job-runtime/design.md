## Context

依赖现有 SQLite、认证与 OwnerScope。四个 HTTP endpoint 先登记 canonical OpenAPI，再生成 Python/TypeScript DTO。仅构建运行时基础，文档索引和 AIOps handler 由后续 Change 接入。

## Goals / Non-Goals

目标是进程或客户端断开后仍能恢复的持久任务和有序事件。当前不增加业务 SSE endpoint、HTTP Last-Event-ID、clock 构造参数或 heartbeatAt/result 列；不增加前端 UI。

## Decisions

- `background_jobs.py` 提供 immutable Job/JobEvent 和 owner-scoped SQLite Repository；JSON 以已验证文本存储，调用方取值时复制。时间使用固定 UTC RFC3339 微秒文本，便于 SQLite 比较且避免 naive datetime adapter。所有持久业务操作都要求 keyword-only owner，在 I/O 前验证。
- 写事务以限定 owner 的 no-op UPDATE 先取得 SQLite writer lock，避免 deferred SELECT 再写导致的锁升级死锁；领取与事件在同一事务提交。保留队列和 lease 索引、owner/parent 复合外键、attempt/status/lease CHECK。SQLite 单 writer 的短事务已足够，无需另建队列服务。
- `BackgroundWorker._owners` 仅用于受信调度器发现未完成任务的 owner 标识，不返回 payload、资源内容或 HTTP 结果；这一目录是明确的基础设施例外。随后回收、领取、续租、完成与事件操作全部使用该持久 owner 的显式 scope，不存在默认 owner 或全局 tenant 执行。
- 每次领取生成唯一 lease token，running 状态、token 和未过期时间共同授权写入；旧 worker 不得复活租约或写回结果。heartbeat 只续写 leaseExpiresAt。回收/失败/超时按 min(2 ** attempt, 30) 退避，达到 maxAttempts 转 failed。
- 按 kind 注册 async handler；未知类型保持 queued，不消耗 attempt。默认两个轮询槽、lease 30 秒、poll 0.2 秒，直接使用 `_utc_now()`/`asyncio.sleep()`。FastAPI lifespan 持有 worker 和 Database，关闭时取消并等待所有 handler/heartbeat，写回可恢复状态，再关闭数据库。create_task 只执行 SQLite 已持久的任务，不充当任务存储。
- `JobContext.cancelled` 是协作取消信号，queued 取消直接终止，running 请求由 heartbeat 通知；handler 退出后取消优先于成功。timeout 和关闭也清理 handler。handler 必须是遵守取消的 async 协程，业务 I/O 必须有界且不能阻塞事件循环。
- 手动 retry 创建全新任务并保留 retryOfJobId，原任务与事件留存。重复 cancel 对已请求/已取消状态幂等，其他终态冲突为 BUSINESS_CONFLICT 409；越权/缺失始终 AUTH_FORBIDDEN 403。
- `replay_events` 从持久事件快照重放，after_sequence 默认 0，消费者关闭不修改任务；未来 AIOps SSE 适配可复用。不声称已实现 HTTP 重连协议。
- 错误使用固定中文安全消息，日志只输出固定故障类别，不记录 payload、kind、异常原文或栈；事件业务 payload 由受信 handler 显式选择公开内容。

## Risks / Trade-offs

- 至少一次执行，崩溃窗口内外部副作用可能重复 → 后续 handler 按 job/resource ID 实现幂等，租约 fencing 仅保证本地状态与事件不会被旧执行写回。
- Python 无法强杀阻塞或吞掉 CancelledError 的 handler → handler 接入必须满足 async 协作取消和有界 I/O；本 Change 用 fake handler 验证约定。不承诺恶意/不合作 handler 的硬隔离。
- SQLite 单 writer 限制吞吐 → 事务不包围 handler I/O；并发槽默认 2，失败轮询保持有界间隔，租约最终回收。

## Migration Plan

显式使用临时配置执行 Alembic upgrade head、重复 upgrade、check、downgrade/re-upgrade。生产/开发真实数据库未操作。0003 增加两张表，降级删除后台任务与事件，必须先停止 worker 并备份需保留的数据。
