## Purpose

为前端提供可注入、可取消且具备类型和运行时验证的 HTTP 与 SSE 基础传输能力，使调用者统一获取成功数据、服务错误及协议失败，并在任意网络分块下可靠消费共享事件合同。

## ADDED Requirements

### Requirement: HTTP client 解码共享 envelope
HTTP client MUST 按合同 operation 返回 typed data，校验响应 envelope 与状态一致性；失败 MUST 暴露共享 error 和 requestId，协议无效与网络异常 MUST 不伪装成服务端业务错误。

#### Scenario: 成功与错误解码
- **WHEN** 收到合法成功、合法四类失败、非法 JSON、非法 envelope 或状态矛盾
- **THEN** 分别返回 typed data、抛共享服务错误或协议异常

### Requirement: 传输身份与执行器可注入
HTTP/SSE client MUST 提供 request ID、bearer 和 fetch 注入点并支持 AbortSignal，不得自行读取本地秘密配置。

#### Scenario: 注入请求上下文
- **WHEN** 调用者提供 request ID、bearer 和 signal
- **THEN** 请求携带对应 header/signal，未提供 bearer 时不发送认证值

### Requirement: SSE 正确处理网络分块
SSE parser MUST 增量解码 UTF-8，处理跨 chunk 分隔符、LF/CRLF/CR、BOM、注释、多行 data 和单 chunk 多 frame；EOF MUST 不派发缺少终止空行的 frame。

#### Scenario: 任意字节切分
- **WHEN** 中文事件及 frame 分隔符在任意字节位置被拆分
- **THEN** 解码事件与未拆分一致，没有重复、丢失或乱码

#### Scenario: 无效或未结束 frame
- **WHEN** 流包含未知事件、无效 JSON、超限 frame 或 EOF 未结束内容
- **THEN** 无效和超限抛协议异常，未结束 frame 不作为完整事件发出

### Requirement: SSE client 校验握手并释放资源
SSE client MUST 校验 HTTP 成功及 text/event-stream，失败 envelope 复用 HTTP 错误解码；取消或消费者提前结束 MUST 释放流 reader，不自动重连。

#### Scenario: 握手与取消
- **WHEN** 握手失败、Content-Type 错误、请求取消或消费者提前结束
- **THEN** 提供对应错误或取消行为，关闭当前读取且不重试
