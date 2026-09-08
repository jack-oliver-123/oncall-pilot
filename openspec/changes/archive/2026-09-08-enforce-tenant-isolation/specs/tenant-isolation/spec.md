## Purpose

为 On-call Pilot 的本地用户建立强制归属边界，使当前用户只能访问自己的持久资源，并为后续关系数据、向量检索、工具调用和后台任务提供一致且可验证的隔离合同，避免资源枚举和跨用户数据泄漏。

## ADDED Requirements

### Requirement: 认证派生的不可变归属上下文
系统 MUST 从已验证认证会话派生当前用户和 owner scope；本地 tenant id SHALL 等于当前 user id，不接受客户端 owner 或 tenant 覆盖，不使用默认或全局 tenant。

#### Scenario: 两个用户的上下文独立
- **WHEN** 两个有效用户分别或并发请求受保护资源，并提交另一个用户的 owner 或 tenant 参数
- **THEN** 每个请求的 user、owner 和 tenant 均来自自身认证，客户端参数不能扩大访问范围

#### Scenario: 无认证不创建上下文
- **WHEN** 请求缺少有效 bearer 或会话已撤销
- **THEN** 系统返回 AUTH_UNAUTHENTICATED 401 且不执行受保护资源操作

### Requirement: Repository 参数与数据层强制归属
所有受保护 Repository 方法 MUST 显式接收必填 owner_user_id，在任何数据库操作前拒绝空值和错误类型；读取、列表、创建、更新、删除必须在数据层限定 owner，禁止先按资源 id 全局读取再在 service 补检查。认证引导的用户注册、邮箱查找、token 摘要解析和基础设施版本读取属于具名例外，不得用于业务资源访问。

#### Scenario: 双用户读写删除隔离
- **WHEN** 用户乙读取、更新或删除用户甲的资源，或者读取自己的资源列表
- **THEN** 资源条件同时包含 owner，乙不能读取或改变甲的数据，列表只返回乙的数据

#### Scenario: 参数级失败
- **WHEN** Repository 调用省略 owner_user_id 或传入空串、空白、null、错误类型
- **THEN** 调用在执行 SQL 前失败，不退化为无 scope 查询

#### Scenario: 创建归属不可伪造
- **WHEN** 创建记录携带不同于调用 scope 的 owner
- **THEN** 系统在持久化前拒绝该记录

### Requirement: 父子资源与不可枚举错误
受保护父资源不存在或不属于当前用户时 MUST 统一返回 AUTH_FORBIDDEN 403，不包含资源内容、owner、存在性或内部查询细节。子资源操作 MUST 同时限定 owner 和父资源关系；不存在、跨用户或不属于指定父资源的子资源采用相同错误语义。

#### Scenario: 父资源不存在与越权等价
- **WHEN** 用户读取不存在的父资源或另一用户的父资源，包括其子列表和子资源操作
- **THEN** 均返回相同错误码、状态与无资源细节的响应，不能通过空列表或 404 推断父资源存在

#### Scenario: 子资源 ID 不能绕过父 scope
- **WHEN** 用户使用自己的父资源 ID 配上其他父资源或其他用户的子资源 ID
- **THEN** 读取、更新、删除均失败且不改变子资源

### Requirement: 向量归属与检索删除边界
向量标量和 metadata MUST 同时保留 tenantId 与 ownerUserId，二者均等于当前 user id。Milvus 搜索 filter MUST 仅包含 tenantId 与经 owner 校验的 allowedKnowledgeBaseIds；可选 document/metadata 过滤在 retrieval tool 召回后执行。空 KB 集合必须直接返回空结果且不连接 Milvus。文档向量删除 MUST 同时包含 tenantId、knowledgeBaseId、documentId，空 tenant 或任一空删除维度禁止操作。

#### Scenario: 搜索只在已授权知识库内
- **WHEN** 当前用户在一组已验证归属的 KB 内搜索并有可选文档条件
- **THEN** 搜索 filter 只限定 tenantId 和 KB 集合，文档及 metadata 条件仅作用于召回结果

#### Scenario: 空 KB 与空 scope
- **WHEN** KB 集合为空，或 tenant/delete scope 无效
- **THEN** 空 KB 返回空结果且不建立客户端；无效 scope 在连接或删除前失败

#### Scenario: 精确删除与归属追溯
- **WHEN** 删除指定文档向量或生成向量归属字段
- **THEN** 删除 filter 同时限定 tenant、KB、document，归属字段保留 tenantId 和 ownerUserId 且无法被附加 metadata 覆盖

### Requirement: 登出保留持久数据并清理客户端状态
登出 MUST 只撤销当前认证会话、清除客户端可见的身份与受保护状态，不删除任何用户持久数据；旧身份请求的迟到响应不能填充新用户状态。

#### Scenario: 双用户切换与重新登录
- **WHEN** 用户甲登出后用户乙登录，随后甲重新登录
- **THEN** 客户端不残留甲的数据，迟到请求被丢弃，甲乙的持久资源均保留并分别可访问

### Requirement: 全资源和后台任务统一边界
chat、knowledge、index jobs、vector、MCP、AIOps、evidence、reports、cases、feedback、audit、background jobs MUST 遵守同一 owner/tenant 边界，后台工作必须显式携带发起用户 scope 并在执行时校验资源归属。

#### Scenario: 后续资源接入
- **WHEN** 增加任一受保护 Repository、工具或后台任务
- **THEN** 实现遵循架构文档中的必填参数、数据层过滤、父子关系和不可枚举错误合同，并复用双用户与参数失败测试
