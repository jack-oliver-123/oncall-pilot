## MODIFIED Requirements

### Requirement: 机器合同先于 endpoint
packages/api-contracts MUST 成为 response、错误、OpenAPI path 和 SSE 的单一事实来源；登记 foundation/health 和用户认证接口，后续提案 MUST 先增加合同再增加 endpoint。

#### Scenario: 检测跨语言或 path 漂移
- **WHEN** 应用增加未登记路径、私有响应或修改生成声明
- **THEN** 合同检查失败，必须先修正合同与实现一致性

## ADDED Requirements

### Requirement: 认证 HTTP 合同
合同 MUST 登记 POST /auth/register、POST /auth/login、POST /auth/logout、GET /auth/me 的 Auth DTO、请求和统一响应、401/409 错误及 HTTP bearer security scheme。认证响应 MUST 使用统一 envelope/error/requestId，公开用户 MUST 不含密码 hash 和会话 hash。

#### Scenario: 认证合同一致性
- **WHEN** 检查前后端生成声明和实际 OpenAPI
- **THEN** 请求、响应、path、错误及 logout/me bearer security 一致，缺失或额外字段被拒绝

### Requirement: 本机前端跨域认证
服务器 MUST 允许 http://127.0.0.1:5173 发起带 Authorization、Content-Type 和 X-Request-ID 的跨域请求，并暴露 X-Request-ID 响应头。

#### Scenario: CORS 预检
- **WHEN** 本机前端请求认证接口预检，或其他来源请求
- **THEN** 本机来源获得许可，其他来源不获得跨域许可
