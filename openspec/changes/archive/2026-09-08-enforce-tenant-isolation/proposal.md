## Why

用户认证已经归档，但后续资源仍缺少统一且不可省略的归属查询边界。第 05 个 Change 在业务资源出现前建立 owner scope，避免先按资源 ID 读取再补 service 检查导致跨用户泄漏。

## What Changes

- 定义认证派生的 CurrentUser、OwnerScope 和 tenant 上下文；本地模型中 tenant id 等于当前 user id。
- **BREAKING**：受保护 Repository 方法统一显式接收必填 `owner_user_id`，空值在数据库操作前失败，查询、更新、删除和父子关联均在 SQL 内限定归属。
- 在 `packages/api-contracts` 的 OpenAPI 中提供 bearer、401、403 的复用模式和生成声明；既有受保护认证 path 使用同一模式，未来业务 path 必须复用，不创建未实现业务 endpoint。
- 父资源不存在和越权统一返回无资源细节的 `AUTH_FORBIDDEN` 403；子资源也采用一致不可枚举语义。
- 提供 SQLite scope helper 与纯函数 Milvus filter builder；搜索仅 tenantId 和 allowedKnowledgeBaseIds，空 KB 集合在连接前短路，删除必须限定 tenant、KB、document。向量同时保留 tenantId 与 ownerUserId。
- 通过两个用户的本地 SQLite/HTTP 合同测试、向量边界测试和客户端状态测试验证隔离与登出数据保留。
- 更新 AGENTS、架构文档和 WIKI，覆盖所有未来资源与后台任务。

## Capabilities

### New Capabilities

- `tenant-isolation`：身份上下文、强制 scoped Repository、不可枚举访问、向量 scope 与登出边界。

### Modified Capabilities

- `api-protocol`：受保护 path 必须复用 bearer、401、403 安全模式。

## Impact

涉及后端认证与 memory 基础层、contracts/OpenAPI 和生成器、双用户测试、前端认证回归测试、AGENTS、持久化架构文档及 WIKI。无新依赖、无生产连接、无业务 schema 迁移、无页面 UI 修改；Milvus 只建立可执行约定，不初始化客户端。按用户本次明确授权执行提案、实现、修复验证、同步和归档；不包含 commit、push 或 PR。
