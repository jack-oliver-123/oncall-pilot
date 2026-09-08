# sse-protocol Specification

## Purpose

为 On-call Pilot 的聊天与 AIOps 流提供统一事件目录、公共关联字段和工具生命周期形状，使后续事件生产者与消费者可以共享判别联合，并通过同一错误模型解释 HTTP 与流式失败。

## Requirements

### Requirement: SSE 采用完整判别事件目录
SSE MUST 定义 content.delta、reasoning.delta、tool.call、reference.source、task.status、report、complete、error，公共字段 MUST 包含 id、type、channel(chat|aiops)、带时区 timestamp。

#### Scenario: 消费所有事件
- **WHEN** 任一目录事件在 chat 或 aiops channel 发出
- **THEN** 消费者按 type 收窄到对应 payload，拒绝未知事件、缺失公共字段和无效 channel

### Requirement: 工具事件覆盖四态生命周期
tool.call MUST 支持 started、delta、completed、failed，同一调用以 callId 关联；各状态 MUST 具有明确 payload，failed MUST 复用 ApiError。

#### Scenario: 工具运行与失败
- **WHEN** 工具分别开始、增量输出、完成或失败
- **THEN** started 包含调用标识和名称，delta 包含增量，completed 包含 output，failed 包含共享 error，缺少对应字段被拒绝

### Requirement: 流错误复用 HTTP 错误
error 事件和 tool.call failed MUST 使用与 HTTP failure 完全相同的 error 结构和错误目录，不能维护私有错误结构。

#### Scenario: 错误跨传输复用
- **WHEN** HTTP error 对象被用作 SSE error 或工具失败
- **THEN** code/category/httpStatus/message/details 不发生改名或语义变化

### Requirement: 应用不得自造事件 payload
生产端 MUST 使用合同声明构造和序列化事件，消费端 MUST 从 contracts 导入联合；应用中新增私有事件结构 MUST 被边界检查拒绝。

#### Scenario: 非合同事件回归
- **WHEN** 应用源码增加私有 event DTO 或手写事件字典
- **THEN** 自动化边界检查失败
