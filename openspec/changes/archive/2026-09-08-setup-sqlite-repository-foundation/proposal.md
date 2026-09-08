## Why

P01、P02 已建立工程与协议基座，但持久化仍只有 Alembic 空入口。需要在领域功能之前统一数据库生命周期、迁移和事务边界，使后续认证、Chat、知识、任务、MCP、AIOps、反馈与审计能够独立测试并替换数据库实现。

## What Changes

- 建立 SQLAlchemy 2 async、aiosqlite 的显式初始化、session factory 与事务上下文。
- 建立声明式 Base、Alembic async 迁移环境和首个基础 revision；不提前添加业务表。
- 提供不暴露 ORM 的 Repository Protocol、不可变基础 record、统一 JSON、UTC 和 ID 约定。
- 数据库 URL 使用本地 JSON 深合并配置，提供独立临时数据库及迁移测试工具。
- 沿用当前 `oncall_pilot` namespace，将请求中的旧 `super_ai.memory` 名称映射为 `oncall_pilot.memory`；SQLite adapter 位于 `oncall_pilot.memory.sqlite`。

## Capabilities

### New Capabilities

- `persistence-foundation`: 无 import 副作用的持久化边界、迁移权威、事务隔离、类型约定与可替换 Repository 契约。

### Modified Capabilities

- `backend-foundation`: 将 P01 的空迁移入口约束推进为显式迁移与持久化初始化边界；既有 HTTP/SSE 合同、健康检查语义与本地配置来源不变。

## Impact

修改范围为后端 memory package、Alembic 环境、后端测试、持久化使用文档以及 OpenSpec/WIKI。复用已锁定依赖，不引入领域 CRUD、生产连接、前端 UI 或部署变更。用户本次请求明确授权在此范围内连续完成 artifact、实现、验证、spec 同步和归档；Git 提交、推送与 PR 不属于本次操作。
