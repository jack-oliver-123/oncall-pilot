## MODIFIED Requirements

### Requirement: 状态、失败恢复与取消
领域状态 MUST 统一使用 `pending`、`running`、`succeeded`、`failed`、`cancelled`。底层 background job 的 `queued` MUST 映射为 `pending`；embedding、splitter 或 Milvus 错误 MUST 不被吞掉，安全 failureReason MUST 持久化，失败不得将文档标记为 succeeded。任务 MUST 支持有限自动重试、手动重建并保留 retryOfTaskId，以及 queued/running 取消。知识工作区 MUST 约每 2 秒读取活动任务，展示文字状态和 failureReason，并通过通用 background-job 取消能力提交取消请求。

#### Scenario: 依赖失败
- **WHEN** embedding、切分或 Milvus 任一步骤失败
- **THEN** 文档和领域 task 进入失败或可恢复状态，持久化原因不含凭据或原始异常，工作区显示安全失败原因且不返回成功状态

#### Scenario: 手动重建
- **WHEN** 用户在工作区对已失败、已取消或已完成的任务请求重建
- **THEN** 创建新的 attempt 和 durable job，旧 task 保留且新 task 的 retryOfTaskId 指向来源，工作区切换到新任务并继续跟踪

#### Scenario: 取消
- **WHEN** 用户从工作区取消 queued 或 running 索引任务
- **THEN** 客户端通过通用 background-job 能力发送取消请求，queued 任务直接成为 cancelled，running 任务最终成为 cancelled，客户端不需要保持连接
