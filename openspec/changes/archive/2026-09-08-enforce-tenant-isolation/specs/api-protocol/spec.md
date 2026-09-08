## ADDED Requirements

### Requirement: 受保护 path 的复用安全合同
contracts/OpenAPI MUST 提供 bearer、401、403 的复用操作模式；所有当前和未来受保护 path 必须引用该安全模式，保持真实路由与合同一致。公开认证引导和健康检查必须显式登记为公开例外；无效认证返回 AUTH_UNAUTHENTICATED 401，受保护资源缺失或越权返回 AUTH_FORBIDDEN 403。

#### Scenario: 新受保护操作复用合同
- **WHEN** 定义新的受保护 path 或生成现有认证操作的 OpenAPI
- **THEN** 操作包含 BearerAuth 安全要求以及复用的 401 和 403 响应，响应使用既有 ApiFailure envelope

#### Scenario: 安全模式漂移被门禁发现
- **WHEN** 受保护 path 缺失 bearer、401 或 403，或新增操作未经声明绕过安全模式
- **THEN** 合同生成或合同测试失败，不能将该 path 作为通过验证的受保护接口
