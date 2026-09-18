## MODIFIED Requirements

### Requirement: Worker 生命周期与租约
系统 SHALL 按 kind 注册 handler；FastAPI lifespan 启动并清理 worker，默认 concurrency=2、lease=30 秒、poll 约 0.2 秒。领取必须原子，heartbeat 续写 `leaseExpiresAt`，过期 lease 可回收。文档索引 kind MUST 使用 durable background job 执行，且 queued 状态对客户端映射为领域 `pending`。

#### Scenario: 文档索引重启后恢复
- **WHEN** worker 在文档索引期间退出并再次启动
- **THEN** 过期 lease 被回收，任务按剩余尝试次数重新排队或失败，领域状态不会永久停留在 running

#### Scenario: 并发唯一领取
- **WHEN** 多个 worker 同时轮询同一队列
- **THEN** 每个任务同一时刻最多被一个 worker 领取

#### Scenario: 客户端断开不影响 worker
- **WHEN** 索引 API 响应后客户端断开
- **THEN** 已持久化的 job 仍由 worker 执行，客户端稍后可 GET 任务状态
