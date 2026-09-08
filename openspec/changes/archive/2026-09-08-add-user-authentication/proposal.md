## Why

P02 已提供统一 HTTP 合同，P03 已提供显式迁移和异步事务。P04 在这两个边界上建立真实用户身份与可撤销会话，为后续受保护业务和 P08 页面提供认证基础。

## What Changes

- 先扩展 `packages/api-contracts`：`POST /auth/register`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`，Auth DTO、请求/响应、bearer security scheme、401/409 错误及统一 envelope/requestId。
- 添加 users/auth_sessions migration、不可变记录、owner-safe Repository、AuthService 和 FastAPI dependency；密码使用 Argon2，opaque token 仅保存 SHA-256 hash。
- 实现邮箱规范化唯一、统一无效凭据错误、未知账号 dummy Argon2 校验、lastSeen 更新和登出撤销。
- 提供可复用前端 authClient/auth state，恢复时查询服务端，失效及登出清理本地受保护状态；localStorage 只保存 token。
- 先写各切片验收测试，执行受影响门禁、一致性验证、specs 同步、归档和 WIKI 同步。

## Capabilities

### New Capabilities
- `user-authentication`: 用户注册、登录、身份查询、会话保存和撤销。
- `frontend-auth-state`: 认证客户端、恢复与本地受保护状态清理。

### Modified Capabilities
- `api-protocol`: 在唯一机器合同中登记认证接口、DTO、错误和安全要求。
- `wiki-sync`: 修复同日创建且归档时原始 ADDED 与后续 MODIFIED 的校验顺序，保证本次归档可严格同步。
- `persistence-foundation`: 区分基础 revision 的空 schema 与后续领域 head，保持 migration/metadata 一致性。

## Impact

影响 backend、contracts、frontend 非 UI 模块、Alembic、合同生成器及测试；新增 `pwdlib[argon2]` 依赖。仅使用临时 SQLite 验收，不连接外部数据库。当前不实现 tenant、邮件验证、密码找回、自动过期、完整页面或业务数据删除；用户 ID 是当前 owner 边界。未来 tenant 接口仍须显式接收 tenant ID。本请求授权的范围不包括 Git 提交、推送或 PR。
