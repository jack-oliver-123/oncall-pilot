# frontend-auth-state Specification

## Purpose

为后续认证页面与受保护业务提供可复用的认证状态和服务端身份恢复能力，限制浏览器持久化凭据范围，并确保认证失效、账号切换和退出后不会残留前一用户的本地受保护信息。

## Requirements

### Requirement: 认证客户端与最小持久化
前端 MUST 使用共享认证合同调用注册、登录、登出和当前用户查询；localStorage MUST 只保存 raw token 这一种认证凭据，用户和密码 MUST 不持久化。

#### Scenario: 注册和登录
- **WHEN** 调用注册后登录
- **THEN** 使用登记的请求合同，注册不隐式登录，登录后持久化 token 并在内存保存公开用户

### Requirement: 服务端身份恢复
initialize MUST 在存在 token 时调用 /auth/me 验证后恢复用户，MUST 不仅凭本地 token 判定已认证。网络错误 MUST 与认证失效区分。

#### Scenario: 有效、失效及无 token
- **WHEN** initialize 分别遇到有效 token、401 和无 token
- **THEN** 有效时恢复用户；401 清理 token 和受保护状态；无 token 不发送查询且保持未认证

#### Scenario: 恢复期间网络失败
- **WHEN** /auth/me 网络失败或返回服务端错误
- **THEN** 不显示已认证用户，保留 token 供重试并向调用方报告错误

### Requirement: 清理与异步竞态隔离
登出、认证失效及账号切换 MUST 清除已登记的本地受保护 store，MUST 不调用服务端业务删除。旧请求完成后 MUST 不能恢复已清理身份或清除新会话。登出 MUST 先尝试撤销捕获的服务端 session，随后清除本地状态；撤销期间不接收旧身份请求结果，失败也必须清理本地并报告错误。

#### Scenario: 登出和撤销失败
- **WHEN** 用户登出且服务端成功或网络失败
- **THEN** 本地 token、用户和受保护状态均清理；失败向调用方报告，不能声称服务端已撤销

#### Scenario: 迟到响应
- **WHEN** 旧 initialize 或登录请求在登出或新登录之后才完成
- **THEN** 旧结果不覆盖新的认证状态

### Requirement: 认证流生命周期
认证 SSE MUST 复用共享事件合同、携带捕获的身份并支持取消；当前身份收到握手 401 MUST 清理认证与受保护数据，身份改变 MUST 取消旧流且不派发旧事件；旧身份的失败不得清除新会话。

#### Scenario: SSE 失效与取消
- **WHEN** 当前流握手返回 401，或登出与账号切换发生在流读取期间
- **THEN** 401 清理当前身份，身份改变取消旧流并释放 reader；迟到结果不能污染新账号
