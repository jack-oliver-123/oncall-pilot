## MODIFIED Requirements

### Requirement: 迁移是 schema 唯一权威
数据库 schema MUST 只由显式迁移命令管理，升级 MUST 可重复执行，持久化 metadata MUST 与当前 head 迁移结果一致；基础 revision MUST 不包含领域业务表，后续 revision SHALL 引入规范化领域表。

#### Scenario: 空数据库升级和重复升级
- **WHEN** 对临时空数据库执行 upgrade head 两次
- **THEN** 记录唯一当前 head，包含该版本的领域表且 metadata 比较没有差异；升级到基础 revision 时只有迁移管理表

#### Scenario: 不自动迁移
- **WHEN** 初始化运行时数据库边界或打开 session
- **THEN** 不自动建立或升级 schema，未迁移时读取 revision 清晰失败

#### Scenario: 认证迁移往返
- **WHEN** 从基础 revision 升级认证 revision、降级到基础 revision 再升级
- **THEN** users 和 auth_sessions 表按版本存在，邮箱与 token hash 唯一、会话 owner 外键和时间列约束有效
