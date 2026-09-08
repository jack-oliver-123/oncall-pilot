## Purpose

为值班人员建立可验证的用户身份和可撤销会话，保证密码与认证令牌不会以明文进入持久化或日志，并为后续受保护业务提供可靠的当前用户边界及一致的失败语义。

## ADDED Requirements

### Requirement: 注册与邮箱唯一
系统 MUST 将邮箱去除首尾空白并按不区分大小写规范化后唯一保存；注册只返回公开用户信息，密码 MUST 使用 Argon2 哈希且不得持久化或记录明文。

#### Scenario: 注册与重复邮箱
- **WHEN** 注册合法邮箱和密码，再使用大小写或首尾空格变体注册
- **THEN** 首次成功，重复返回 BUSINESS_EMAIL_ALREADY_EXISTS；数据库仅存在一个规范邮箱和非明文密码 hash

#### Scenario: 无效输入不泄露密码
- **WHEN** 请求包含无效邮箱、短密码或额外私有字段
- **THEN** 返回统一 422，响应和日志不包含输入密码

### Requirement: 登录避免明显账号枚举
正确凭据 MUST 获得独立高熵 opaque bearer token；不存在账号与密码错误 MUST 使用相同 AUTH_INVALID_CREDENTIALS，未知账号 MUST 执行 dummy Argon2 校验。

#### Scenario: 正确与错误登录
- **WHEN** 分别使用正确密码、错误密码和未知邮箱登录
- **THEN** 正确登录成功；后两者返回相同 401 错误，均执行密码校验

#### Scenario: token 持久化保护
- **WHEN** 同一用户登录两次
- **THEN** 获得不同的高熵 token，数据库仅存各自 64 位 SHA-256 hash，不保存 raw token

### Requirement: 当前身份与会话撤销
系统 MUST 通过有效 bearer 查询当前用户，记录 createdAt、lastSeenAt、revokedAt；成功认证 MUST 更新 lastSeenAt；登出 MUST 撤销当前会话且保留用户及业务数据。当前版本 MUST 不声明自动过期。

#### Scenario: 身份恢复及最后访问时间
- **WHEN** 使用登录 token 调用 /auth/me
- **THEN** 返回对应公开用户并更新 lastSeenAt，createdAt 保持不变

#### Scenario: 撤销和无效 token
- **WHEN** 登出后再次使用同一 token，或使用缺失、畸形、未知 token
- **THEN** 受保护接口返回 AUTH_UNAUTHENTICATED；其他独立会话和服务端数据仍存在

### Requirement: owner 安全的持久化边界
会话读取、touch、revoke MUST 受服务端认证得到的 owner ID 限制；认证引导仅能用 token hash 解析身份，客户端 MUST 不能指定身份或修改他人会话。Repository MUST 返回不可变记录，不自行提交。

#### Scenario: 跨 owner 操作
- **WHEN** 以其他用户 ID 读取、touch 或撤销某会话
- **THEN** 返回未找到或无修改，原会话仍可使用

#### Scenario: 回滚
- **WHEN** 会话写入事务失败
- **THEN** 不留下部分会话，后续事务仍可用
