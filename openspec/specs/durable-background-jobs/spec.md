# durable-background-jobs Specification

## Purpose

为 On-call Pilot 的文档索引和 AIOps 提供可在客户端断开或进程重启后恢复的后台任务基础，持久保存生命周期与有序事件，并统一保证任务归属、租约、重试、超时和取消的可观察行为。

## Requirements

### Requirement: 持久后台任务模型
系统 SHALL 在 SQLite 持久化 `background_jobs` 和 `background_job_events`。任务包含 owner、kind、resourceType、resourceId、status、payload、attempt、maxAttempts、timeoutSeconds、availableAt、leaseOwner、leaseExpiresAt、cancelRequestedAt、retryOfJobId、errorMessage 及 created/updated/started/completed 时间戳；不得增加虚构的 heartbeatAt/result 列。

#### Scenario: 重启后可恢复
- **WHEN** 进程在任务运行期间退出并再次启动
- **THEN** 未完成任务可被新 worker 领取，过期 lease 不会永久悬挂

### Requirement: Owner-scoped Repository
所有任务 list/get/cancel/retry/event 操作 SHALL 显式接收无默认值的 owner scope，并在 SQL 层同时限定 owner 与资源关系；越权视为不存在或统一 `AUTH_FORBIDDEN`。

#### Scenario: 两个用户隔离
- **WHEN** 用户 B 读取、取消、重试或读取用户 A 的任务/事件
- **THEN** 操作失败且不泄露任务存在性

### Requirement: Worker 生命周期与租约
系统 SHALL 按 kind 注册 handler；FastAPI lifespan 启动并清理 worker，默认 concurrency=2、lease=30 秒、poll 约 0.2 秒。领取必须原子，heartbeat 续写 `leaseExpiresAt`，过期 lease 可回收。

#### Scenario: 并发唯一领取
- **WHEN** 多个 worker 同时轮询同一队列
- **THEN** 每个任务同一时刻最多被一个 worker 领取

### Requirement: 重试、超时与取消
worker SHALL 使用最大 30 秒的指数退避、尊重 `maxAttempts`、执行 timeout，并对取消请求进行协作式处理；handler crash 或 timeout 必须释放/更新 lease。

#### Scenario: 失败重试
- **WHEN** handler 失败且仍有剩余尝试次数
- **THEN** 任务回到 queued，`availableAt` 使用指数退避且不超过 30 秒，并追加事件

### Requirement: 有序持久事件
每次状态变化 SHALL 追加单调递增 sequence 的事件；Repository 支持 `list_events(after_sequence=...)`。客户端断开不得取消任务，重连可从 sequence=0 重放持久事件。

#### Scenario: 断连后重放
- **WHEN** AIOps 客户端断开后重新连接并请求 sequence=0 之后的事件
- **THEN** worker 继续运行，客户端收到断开期间已持久化的有序事件

### Requirement: 失租写入隔离与安全错误
系统 SHALL 拒绝过期或旧租约执行的续租、事件与完成写回。任务异常 SHALL 保存安全错误信息，日志不得输出任务 payload 或异常中的凭据。

#### Scenario: 旧 worker 写回
- **WHEN** 任务租约到期并已被另一个执行领取
- **THEN** 旧执行不能续租、追加事件或覆盖当前状态

#### Scenario: 含凭据的执行异常
- **WHEN** handler 抛出包含 token 或 password 的异常
- **THEN** 持久错误与运行日志仅包含安全消息

### Requirement: 有界执行与生命周期清理
任务运行时 SHALL 在 timeout、取消或进程正常关闭时清理遵守 async 协作取消约定的 handler 和 heartbeat，未知 kind 不得消耗尝试次数；资源释放后不得再访问已关闭数据库。

#### Scenario: 超时清理
- **WHEN** handler 超过任务 timeout
- **THEN** handler 被取消并完成清理，任务进入重试或失败且释放租约

#### Scenario: 运行中协作取消
- **WHEN** 用户取消 running 任务
- **THEN** handler 收到取消信号并退出，持久状态最终为 cancelled

#### Scenario: 正常关闭再恢复
- **WHEN** FastAPI lifespan 在任务运行中结束后再次启动
- **THEN** handler 和 heartbeat 已清理，未完成任务按剩余尝试次数恢复

#### Scenario: 未注册类型
- **WHEN** 队列任务的 kind 没有已注册 handler
- **THEN** 任务保持 queued 且 attempt 不增加
