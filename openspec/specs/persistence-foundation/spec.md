# persistence-foundation Specification

## Purpose

为 On-call Pilot 的后续领域服务提供统一、可测试、可替换的持久化边界，明确配置来源、资源所有权、迁移权威、事务隔离和数据编码约定，避免领域逻辑绑定数据库对象或测试污染本机数据。

## Requirements

### Requirement: 配置注入和显式资源生命周期
持久化资源 MUST 使用显式注入的本地 JSON 深合并配置，只在显式初始化期间创建，MUST 提供确定的关闭路径；导入持久化模块 MUST 不读配置、不创建 engine/session、不连接数据库或执行迁移。

#### Scenario: 覆盖配置并改变工作目录
- **WHEN** 临时配置的用户文件覆盖数据库 URL 且调用方改变工作目录
- **THEN** 使用覆盖后的 URL，相对路径以配置目录的父目录解析，不读取环境变量或开发者数据库

#### Scenario: 无效配置
- **WHEN** URL 缺失、类型错误或不是受支持的本地 SQLite 文件 URL
- **THEN** 初始化清晰失败且错误信息不回显数据库凭据

#### Scenario: 导入与关闭
- **WHEN** 外部 I/O 和资源创建均被阻断时导入全部持久化模块
- **THEN** 导入成功；显式初始化后的资源则可由调用方确定关闭

### Requirement: 迁移是 schema 唯一权威
数据库 schema MUST 只由显式迁移命令管理，基础升级 MUST 可重复执行，持久化 metadata MUST 与迁移结果一致；基础 revision MUST 不包含领域业务表。

#### Scenario: 空数据库升级和重复升级
- **WHEN** 对临时空数据库执行 upgrade head 两次
- **THEN** 记录唯一当前 head，只有迁移管理表且 metadata 比较没有差异

#### Scenario: 不自动迁移
- **WHEN** 初始化运行时数据库边界或打开 session
- **THEN** 不自动建立或升级 schema，未迁移时读取 revision 清晰失败

### Requirement: 独立异步事务
每个工作单元 MUST 获得独立 async session；事务正常退出 SHALL 提交，异常或取消 SHALL 回滚并关闭 session；Repository MUST 不自行提交，多个 Repository 可共享调用方的同一事务。

#### Scenario: 并发工作单元
- **WHEN** 多个协程各自打开 session 并交错执行
- **THEN** 不共享 session 状态，提交数据可由后续 session 读取

#### Scenario: 回滚及取消
- **WHEN** 写入过程中抛出异常或协程被取消
- **THEN** 此事务的写入不可见，其他已提交事务不受影响，后续 session 仍可用

### Requirement: Repository 返回不可变记录
领域调用方 MUST 通过类型化 Repository Protocol 和不可变 record 访问持久化结果，不接收 ORM model 或 session；SQLite adapter MUST 封装数据库细节，同一 contract SHALL 可由测试 adapter 实现。

#### Scenario: 替换 Repository
- **WHEN** 同一 contract 测试分别运行于真实 SQLite adapter 和内存 fake
- **THEN** 二者提供一致的基础 revision record 语义，record 无法被修改且不包含 ORM 对象

### Requirement: 统一字段与规范化边界
持久化 MUST 使用标准 JSON、带时区的 UTC 时间和 UUID 字符串 ID；MUST 拒绝非有限 JSON 数值及无时区时间。后续需要查询、关联、唯一性或状态流转的数据 MUST 建规范化列和表，不得以通用大 JSON 容器代替。

#### Scenario: 字段往返
- **WHEN** 写入合法 JSON、非 UTC 时区时间和新生成 ID 后读取
- **THEN** JSON 值语义保持，时间归一为 UTC，ID 是可解析且互不相同的 UUID

#### Scenario: 非法字段
- **WHEN** 写入 NaN、Infinity、不支持的 JSON 对象或无时区时间
- **THEN** 写入被拒绝且事务不留下部分数据

### Requirement: 临时数据库验收隔离
测试 MUST 使用临时配置目录和独立 SQLite 文件，并提供可复用 migration helper，MUST 不依赖本机 var 数据库。

#### Scenario: 独立测试目录
- **WHEN** 两个测试目录分别升级并写入测试数据
- **THEN** 数据与迁移状态互不影响，测试结束后关闭所有数据库资源
