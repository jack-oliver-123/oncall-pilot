## Context

认证已由 add-user-authentication 归档，生产仅有 users/auth_sessions 和认证、health 路由。认证 session 修改已有 SQL owner 条件，但方法参数未统一校验。前端已提供受保护 store 清理与请求版本隔离。动机见 proposal.md。

## Goals / Non-Goals

建立可以在现有认证路径执行、供后续领域复用的最小边界。测试专用父子表和 HTTP 探针承担读写删除合同验收，不加入生产 metadata 或发布业务接口。此 Change 不实现业务 CRUD、真实 Milvus adapter、MCP 或新页面，也不连接生产系统。

## Decisions

1. `memory/scope.py` 提供不依赖框架的不可变 `CurrentUser`、`OwnerScope`、派生 tenant 属性及参数校验；HTTP dependency 从 `current_identity` 派生。显式传参比全局 ContextVar 更容易审查，也适用于后台任务。
2. `memory/sqlite/scope.py` 提供绑定参数的 owner predicate 与 scoped select/update/delete helper，并支持调用方添加父关系条件。认证 Repository 使用同一 predicate；用户自查只以 scope 查询。注册、邮箱查找、token 摘要解析为认证引导例外，不能成为通用无 scope CRUD。新增 session 必须验证记录 owner 与调用 scope 一致。
3. 资源缺失在 Repository 返回 None，由 HTTP 边界统一转换为 AUTH_FORBIDDEN；父列表先用 scoped 查询确认父资源。写操作返回可选资源 ID；使用布尔值或行数的领域调用方必须将 false/零行显式转换为缺失。只检查 scoped 查询结果，不二次全局查询存在性。父子写操作在同一事务中以 owner、父 ID 和子 ID 限定；未来 schema 应用复合外键防止跨 owner 关联。
4. `memory/vector_scope.py` 仅提供可执行 filter 与延迟召回回调约定。字符串使用 JSON 引号转义，拒绝无效 scope；不接受原始 filter 表达式。空 KB 在调用任何可连接 Milvus 的回调前返回空列表。可选结果过滤回调在召回后执行。归属字段固定由 scope 派生，保留 tenantId 和 ownerUserId；删除需三个维度。
5. OpenAPI 提供共享 components responses 与扩展操作模板，生成器校验所有非公开操作并导出安全声明。后端提供带身份 dependency 和失败响应的受保护 router 工厂，现有 me/logout 复用。保持 canonical contract 与运行时 OpenAPI 展开后等价，不增加虚构业务 paths。
6. 登出实现延用现有撤销与清理机制，用双用户持久资源回归和真实不同用户的前端切换/迟到响应测试锁定行为。

## Risks / Trade-offs

- helper 无法阻止未来作者手写无 scope SQL → AGENTS 明确硬边界，给出可复用参数与双用户合同测试，新 Repository 必须接入。
- SQLite 无数据库级 RLS → 每次受保护操作都显式 owner 条件，测试捕获实际 SQL，覆盖同事务内已缓存其他用户对象。
- Milvus 尚未实现 → 本次证据明确为纯函数和回调合同，不宣称 live 搜索验收；后续 adapter 在读取配置或连接前遵守空列表短路。
- 403 对不存在父资源统一 → 牺牲受保护资源 404 区分以避免枚举；公开未知 path 的既有 404 不变。

## Migration Plan

无 schema 迁移。统一内部 Repository 调用签名、再生成 contracts；完成全部质量与 OpenSpec 门禁后同步主规格并归档。回退代码时需一并回退调用方、contracts 生成物和新增约定，无数据删除步骤。
