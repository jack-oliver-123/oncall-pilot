# P04 用户认证验证记录

日期：2026-09-08。Change：`add-user-authentication`，schema：`spec-driven`。

## 结论

| 维度 | 结果 |
| --- | --- |
| 完整性 | 12/12 tasks；12/12 requirements；21/21 scenarios 已核对 |
| 正确性 | 真实临时 SQLite、HTTP ASGI、共享合同与前端状态验收通过 |
| 一致性 | P02 单一机器合同、P03 Repository Protocol 和显式事务边界一致 |
| CRITICAL | 0 个未解决问题 |
| WARNING | 0 个未解决问题 |
| SUGGESTION | 0 个待处理建议 |

## 测试先行证据

- 合同：新增 3 个认证验收首先全部失败（缺少 operation、RegisterRequest、AuthUser），增加 OpenAPI 并生成声明后通过。
- 持久化：首先因认证模块缺失失败；实现后 migration/Repository 共 7 项验收通过。修复了命名约定重复添加 check constraint 前缀导致的 Alembic metadata 漂移。
- HTTP：首先因 PasswordManager 缺失失败；实现后对失效 token 的测试发现未登记错误码，修正为 P02 已有 AUTH_UNAUTHENTICATED。注册、登录、恢复、撤销及安全验收通过。
- 前端：首先因 authClient 模块不存在失败，实现后 9 项通过；审查新增迟到成功/切换账号回归先出现 2 个失败，修复后认证测试合计 13 项通过。
- Unicode：4 个 emoji 密码的合同回归先失败；启用 Unicode 正则语义后通过，Python 另覆盖 4/8/65/128/129 字符边界。
- WIKI：同日创建和归档的新增/修改先出现错误的未同步报告；修复后通过。审查补充删除后重加回归先失败，再限制特殊排序仅适用于纯 ADDED/MODIFIED 组，全部工具测试通过。

## 需求与场景映射

| Requirement | 场景数 | 实现与验收证据 |
| --- | --- | --- |
| 注册与邮箱唯一 | 2 | `auth/service.py`、`auth/repository.py`；`test_register_login_restore_revoke_and_secret_storage`、`test_validation_never_echoes_password`、并发注册测试 |
| 登录避免明显账号枚举 | 2 | `auth/passwords.py`、`auth/service.py`；`test_unknown_and_wrong_password_both_run_argon2` 实际调用 pwdlib verify，确认两条路径均使用不同但同参数的 Argon2 hash；完整流程检查 SQLite 文件不含 raw token/密码 |
| 当前身份与会话撤销 | 2 | `auth/api.py` dependency、service authenticate/logout；完整流程检查 createdAt/lastSeen/revokedAt、其他会话和探针业务数据保留；缺失/畸形 token 与无隐式过期测试 |
| owner 安全的持久化边界 | 2 | `auth/records.py`、`auth/repository.py`；`test_records_owner_safety_and_revocation`、`test_constraints_and_rollback` |
| 认证客户端与最小持久化 | 1 | `auth/authClient.ts`、`auth/authState.ts`；注册不隐式登录、token 唯一认证持久化、用户内存化验收 |
| 服务端身份恢复 | 2 | `initialize`；无 token、me 成功、401 清理、网络失败保留 token 测试；非 401 服务端错误沿同一异常分支报告 |
| 清理与异步竞态隔离 | 2 | `clearIdentity`、version/token 检查；登出成功/失败、迟到 me/login、旧 401、迟到受保护 200 和账号切换测试 |
| 机器合同先于 endpoint | 1 | `foundation.openapi.json`、生成的 Python/TS；生成漂移、实际 route、隐藏/重复路径负向检查 |
| 认证 HTTP 合同 | 1 | `test_protocol.py::assert_openapi_matches` 比较请求、响应、security、requestId headers；所有 Pydantic schema 与 canonical JSON Schema 对齐 |
| 本机前端跨域认证 | 1 | app CORS allowlist；`test_cors_and_actual_auth_openapi` 接受本机来源、拒绝其他来源 |
| 迁移是 schema 唯一权威 | 3 | `0002_user_authentication.py`、metadata；重复升级、降级再升级、offline 不建文件、未迁移失败、约束/外键/回滚验收 |
| 同日创建的归档校验顺序 | 2 | `scripts/tests/test_sync_wiki.py` 覆盖 skip_specs、已同步/未同步、无 operation、空 operation/畸形重命名、created 日期排序、同日新增后演进、同日删除后重加 |

## 最终门禁

| 门禁 | 结果 |
| --- | --- |
| backend:lint | 通过 |
| backend:typecheck | 0 errors、0 warnings |
| backend:test | 161 passed |
| contracts:typecheck | 通过 |
| contracts:test（包含 contracts:check） | 34 passed，生成物无漂移 |
| frontend:lint / frontend:format:check / frontend:typecheck | 通过 |
| frontend:test | 47 passed，其中 auth 13 项 |
| frontend:build | 通过 |
| wiki:test | 30 passed |
| openspec validate --all --strict | 通过；归档前后分别复核 |
| git diff --check | 通过；归档前后分别复核 |
| WIKI include、目录、导航及 docs:build | 通过；归档后重建最终投影 |

## 独立审查

Standards 轴检查标准和回归风险，Spec 轴检查正式 artifact 一致性，均为独立只读子代理。

- Standards：迟到成功重填受保护 store 已以回归修复并复核关闭；AuthService 不再接触 ORM session，以注入的 AuthTransactions 获取 Repository Protocol；WIKI 删除后重加排序回归已修复并复核关闭。
- Spec：JavaScript/Python Unicode 密码长度差异已修复并复核关闭；迟到登录和旧请求 401 的测试缺口已补齐。
- 所有发现均已关闭；未将静态复核作为重新运行测试的证据。

## 验收边界

后端使用真实临时 SQLite、真实 Argon2 和进程内 ASGI HTTP；前端使用 Vitest/jsdom 和可控 HTTP 边界。没有使用本机开发数据库或生产数据库。本次没有改动可见 UI，完整页面留在 P08，因此未运行完整页面浏览器 E2E，也未产生 UI 截图。当前没有自动过期、邮箱验证、密码找回、tenant 或权限管理功能；登出网络失败仅保证本地清理并报告错误。

## 最终投影校验修正

首次归档后 WIKI 严格校验因 P04/P02 同日 MODIFIED 同一 WIKI requirement 而失败，未将该失败报告为通过。本次新增同日排序规则改为独立 ADDED requirement，原 OpenSpec-aware archive validation 需求保持 P02 内容；再次逐项比较 delta/main 并运行严格 WIKI 同步、构建及 OpenSpec 校验。未使用 allow-unsynced。

最终归档位置为 `openspec/changes/archive/2026-09-08-add-user-authentication/`，`.openspec.yaml` 完整保留。五份 delta 与主规格所有 requirement 均一致；归档后 `openspec list --json` 返回空 changes，`openspec validate --all --strict` 为 13 passed / 0 failed。WIKI 同步结果为 0 active、7 archived、40 个 include，目录与导航校验通过；最终 `docs:build` 和 `git diff --check` 通过。未执行 Git 提交、推送、PR 或生产操作，用户已有 `.codex/config.toml` 保持原样。
