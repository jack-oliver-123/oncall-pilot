## MODIFIED Requirements

### Requirement: Repository 参数与数据层强制归属
所有受保护 Repository 方法 MUST 显式接收必填 owner_user_id，在任何数据库操作前拒绝空值和错误类型；读取、列表、创建、更新、删除必须在数据层限定 owner，禁止先按资源 id 全局读取再在 service 补检查。认证引导的用户注册、邮箱查找、token 摘要解析和基础设施版本读取属于具名例外，不得用于业务资源访问。持久任务调度器的 owner 发现目录属于新增具名基础设施例外，只能发现未完成任务的 owner 标识，不得返回业务字段或开放 HTTP；后续业务操作仍必须显式限定该 owner。

#### Scenario: 双用户读写删除隔离
- **WHEN** 用户乙读取、更新或删除用户甲的资源，或者读取自己的资源列表
- **THEN** 资源条件同时包含 owner，乙不能读取或改变甲的数据，列表只返回乙的数据

#### Scenario: 参数级失败
- **WHEN** Repository 调用省略 owner_user_id 或传入空串、空白、null、错误类型
- **THEN** 调用在执行 SQL 前失败，不退化为无 scope 查询

#### Scenario: 创建归属不可伪造
- **WHEN** 创建记录携带不同于调用 scope 的 owner
- **THEN** 系统在持久化前拒绝该记录

#### Scenario: 后台调度发现归属
- **WHEN** 受信 worker 扫描未完成任务以安排执行
- **THEN** 目录只返回 owner 标识，领取、回收、续租、事件和完成操作恢复显式 owner scope，客户端不能调用目录扩大资源访问
