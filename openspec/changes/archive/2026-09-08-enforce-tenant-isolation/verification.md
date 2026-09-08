# enforce-tenant-isolation 验证报告

验证日期：2026-09-08。按 `openspec-verify-change` 对 proposal、两份 delta specs、design、tasks 与最终代码进行完整性、正确性、一致性核对。

## 结论

| 维度 | 结果 |
| --- | --- |
| 完整性 | 10/10 实现与验证任务完成，7/7 需求覆盖 |
| 正确性 | 14/14 场景有实现、测试或明确的后续接入约定证据 |
| 一致性 | 符合显式 scope、SQL 内过滤、认证引导例外、无新业务表/路由和无 Milvus 初始化的设计 |
| 待修复问题 | CRITICAL 0、WARNING 0、SUGGESTION 0 |

所有检查通过，可同步主规格并归档。用户本次请求已明确授权完整流程、验证问题修复、同步与归档。

## 逐场景证据

文件路径均相对于仓库根。测试专用 Repository 和 HTTP 探针只位于 tests，不是上线业务接口。

| 需求 / 场景 | 实现和验证证据 |
| --- | --- |
| 认证上下文 / 两个用户独立 | `memory/scope.py` 的不可变 CurrentUser/OwnerScope 与派生 tenant；`auth/api.py:40` 只从已认证 identity 派生。`test_tenant_api.py` 并发使用两个真实用户，伪造 query/header 的 owner 和 tenant 无法覆盖认证身份 |
| 认证上下文 / 无认证 | `protected_router` 默认装配认证 dependency；`test_protected_router_guards_handlers_without_identity_parameter` 验证 handler 无身份参数时缺失、无效、已撤销 bearer 仍返回 401，且不执行 handler |
| Repository / 双用户读写删除 | `memory/sqlite/scope.py:15` 起的 helper 绑定 owner；认证 adapter 复用。`test_two_owners_crud_parents_children_and_sql_scope` 验证双 owner 列表、同 ID、跨用户读取/更新/删除失败、合法更新/删除成功，并捕获实际 SQL 的 WHERE owner 条件及绑定值 |
| Repository / 参数失败 | `tests/scope_contract.py:12` 可复用断言；`test_auth_repository_parameters_fail_before_session_access` 和 `test_all_future_repository_parameters_fail_without_io` 覆盖共 15 个受保护方法，省略、空白、null、错误类型都在 session 操作前失败 |
| Repository / 创建归属 | `OwnerScope.require_owner` 和 `AuthRepository.add_session` 拒绝不同 owner；探针父资源由 scope 填充 owner，子资源 `INSERT ... SELECT` 校验父归属，复合外键拒绝跨 owner 关联 |
| 父子资源 / 缺失与越权等价 | `auth/api.py:58` 只将 scoped 缺失转换为 AUTH_FORBIDDEN。HTTP 测试逐项对比不存在父、他人父及子列表的完整 403 envelope，合法空父列表返回空集合 |
| 父子资源 / 子 ID 绕过 | SQLite/HTTP 测试覆盖自己的父配他人的子、同用户错误父、不存在父、不存在子；读取/更新/删除均失败且真实 owner 的数据保留。复合外键和 scoped 条件约束级联删除 |
| 向量 / 搜索范围 | `memory/vector_scope.py:30` 只输出 tenantId 和 knowledgeBaseId 集合；`test_vector_fields_and_exact_filters` 验证字段集合、去重、字面值转义。授权 KB 的来源在架构文档中强制要求为 scoped Repository 结果 |
| 向量 / 空 KB 与空 scope | `scoped_recall` 先构建 scope，空 KB 直接返回 []；`test_empty_kbs_short_circuit_and_post_filter_runs_after_recall` 证明召回/后过滤回调均未调用，参数化无效 scope 测试证明无法到达 adapter |
| 向量 / 删除与归属追溯 | `document_delete_filter` 同时包含 tenant、KB、document；每个维度的无效值被拒绝。`vector_ownership`/`vector_metadata` 保留 tenantId 与 ownerUserId，拒绝 metadata 覆盖归属。召回后过滤执行顺序有测试 |
| 登出 / 两用户切换及重登录 | `test_cross_tenant_http_contract_and_logout_persistence` 验证旧 bearer 401、重新登录可见原父子资源、另一用户资源不变；前端 `auth.test.ts` 使用不同 user id/email 验证清空可见数据和丢弃迟到结果，403 保留有效身份 |
| 全资源 / 后续接入 | `AGENTS.md` 的资源归属边界与 `apps/backend/persistence.md:43` 起的接入指南覆盖 chat、knowledge、index jobs、vector、MCP、AIOps、evidence、reports、cases、feedback、audit、background jobs；明确任务执行时重新校验归属和逐方法参数/双用户测试 |
| HTTP 合同 / 安全模式复用 | canonical OpenAPI 的 x-protected-operation、共享响应、公开例外；跨语言 generated 声明和 protected_router；contracts `tenant.test.ts` 与实际 OpenAPI 对齐测试覆盖 bearer、401、403 |
| HTTP 合同 / 漂移失败 | `scripts/tests/test_protected_contract.py` 验证缺失 bearer/401/403、新 path 未保护、错误共享响应、虚假公开例外、重复公开 operationId 均阻断生成；HTTP 门禁覆盖隐藏、重复、带前缀 include 路由 |

`memory/...` 与 `auth/...` 实现位于 `apps/backend/src/oncall_pilot/`；后端测试位于 `apps/backend/tests/`。

## 门禁结果

| 门禁 | 结果 |
| --- | --- |
| `npm run check` | 通过，退出码 0；涵盖下列仓库门禁 |
| backend Ruff / strict Pyright | 通过；追加 router 拦截测试后再次通过，0 errors/0 warnings |
| backend pytest | 全量 183 passed；追加独立 router 拦截回归 1 passed，共 184 个不同测试通过 |
| contracts TypeScript / 生成漂移 / Vitest | 通过，36 passed，生成物与 canonical OpenAPI 一致 |
| frontend ESLint / Prettier / vue-tsc | 通过 |
| frontend Vitest / production build | 49 passed；真实 Vite 构建通过 |
| repository tooling / WIKI tests | 34 passed |
| active WIKI include / 索引 / 导航 / VitePress | 同步和构建通过 |
| `openspec validate --all --strict` | 14 passed，0 failed（归档前含 1 个 active Change） |
| `git diff --check` | 通过 |

## 验证发现及修复

1. 新 protected router 触发现有平面路由检查不足：采用当前 FastAPI 的 `iter_route_contexts`，保留隐藏路由/重复路径失败检测，并补带前缀 include 的负向测试。
2. 共享响应头的 RequestId 引用在运行时没有独立 schema：生成时只展开响应头 schema，保留 ApiFailure 组件引用；实际 OpenAPI 深比较通过。
3. 新 path 可能复用公开 operationId 绕过默认保护：生成器拒绝重复 operationId，负向测试证明失败。
4. 首轮格式、严格类型及测试期望与错误目录不一致的问题均已修复，最终门禁无残留失败。

## 证据范围

本地真实证据：临时 JSON 配置、显式 Alembic 迁移、文件 SQLite、真实认证服务、ASGI HTTP 请求及实际 SQL 捕获。mock/纯函数证据：非法参数不访问 session、向量 filter 与延迟召回回调、前端 fetch 状态测试。

尚无 Milvus live、MCP live 或生产验收；本 Change 只定义未来 adapter 必须遵守的可执行边界。当前无业务 CRUD，父子表及接口为本地测试探针，不进入生产 metadata、迁移或 app。页面 UI 未修改，前端变更仅为认证状态回归测试。

## 同步与归档

已新增 tenant-isolation 主规格的 6 条需求，并向 api-protocol 追加 1 条复用安全需求；原主规格的其他需求完整保留。7 条需求和全部场景逐块回读一致后，Change 已移动至 `openspec/changes/archive/2026-09-08-enforce-tenant-isolation/`，保留 `.openspec.yaml`。

归档后结果：`openspec list --json` 返回空 active 集合；`openspec validate --all --strict` 为 14/14 主规格通过；WIKI 为 0 active / 8 archived，45 个 include 及索引/导航验证通过；VitePress 构建和 `git diff --check` 通过。更改保留在工作树，未提交、推送或创建 PR，用户已有 `.codex/config.toml` 未改动。
