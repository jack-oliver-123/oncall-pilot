# P03 持久化基础验证报告

- Change：`setup-sqlite-repository-foundation`
- 日期：2026-09-08
- 环境：Windows，Python 3.12.10，后端 uv 环境，真实临时 SQLite 文件。
- 结论：实现与 artifact 一致，所有要求的检查通过，可同步 specs 并归档。

## 三维验证

| 维度 | 结果 |
| --- | --- |
| 完整性 | 8/8 任务完成；proposal、2 个 delta spec、design、tasks 完整 |
| 正确性 | 7/7 requirements、13/13 scenarios 有实现、测试或本次范围内的静态证据 |
| 一致性 | namespace、显式初始化、Alembic 唯一迁移权威、Repository/record、字段与事务约定符合设计 |

CRITICAL：0。WARNING：0。SUGGESTION：0。没有跳过本次 Change 的需求验证。

## 需求与证据映射

| Requirement / Scenario | 实现证据 | 测试证据 |
| --- | --- | --- |
| 配置注入：覆盖、cwd、环境变量、非法 URL | `apps/backend/src/oncall_pilot/memory/sqlite/database.py:26` | `tests/test_persistence.py:39`、`:46`、`:70` |
| 导入与关闭 | `memory/sqlite/database.py:85`、`:106`；package 无初始化调用 | `tests/test_import_safety.py:10`、`tests/test_persistence.py:206` |
| schema 权威：fresh、repeat、metadata、无自动迁移 | `migrations/env.py:15`、`migrations/versions/0001_persistence_foundation.py:3` | `tests/test_migrations.py:18`、`:28`；`tests/test_persistence.py:107` |
| 独立异步事务：并发、异常、取消 | `memory/sqlite/database.py:93` | `tests/test_persistence.py:127`、`:151`；adapter 读取后主动抛错证明没有隐式 commit |
| Repository 替换和不可变记录 | `memory/contracts.py:7`、`memory/sqlite/repository.py:10` | `tests/test_persistence.py:91`、`:107`，SQLite/fake 使用同一测试合同 |
| 字段往返与非法字段 | `memory/values.py`、`memory/sqlite/types.py:12` | `tests/test_persistence.py:223`、`:258`、`:273`、`:288` |
| 规范化数据边界 | `apps/backend/persistence.md`；生产 Base 无业务表或 JSON 业务容器 | 本次静态检查；未来领域 schema 必须在各自 Change 验收 |
| 临时数据库隔离 | `tests/migration_helpers.py`、`tests/conftest.py` | `tests/test_migrations.py:83` |
| 更新 backend-foundation 的导入与显式升级场景 | `migrations/env.py`、唯一基础 revision | import-safety、fresh upgrade 及单独 CLI 验收 |

表内简写 `memory/` 均相对 `apps/backend/src/oncall_pilot/`，`tests/` 与 `migrations/` 均相对 `apps/backend/`。

## 实际执行结果

| 检查 | 结果 |
| --- | --- |
| 显式 `alembic -c alembic.ini -x config-dir=<临时目录> upgrade head` | 退出码 0 |
| 同配置 `alembic current` | `0001_persistence_foundation (head)` |
| 同配置 `alembic check` | `No new upgrade operations detected.` |
| `npm run backend:test` | 128 passed，36.18 秒 |
| `npm run backend:lint` | All checks passed |
| `npm run backend:typecheck` | strict，0 errors / 0 warnings |
| `openspec validate --all --strict` | 归档前 11 passed / 0 failed |
| `git diff --check` | 退出码 0；Git 的 LF/CRLF 转换提示不属于 whitespace error |
| `npm run wiki:test` | 28 tests，OK，包含合同生成漂移与仓库边界检查 |
| active WIKI 同步 | 1 active / 5 archived，32 个 include 和导航验证通过 |
| `npm run docs:build` | VitePress 构建成功 |

独立 CLI 验收目录：`C:\Users\qianwen.cui\AppData\Local\Temp\oncall-pilot-p03-e4caf5c335fc4e7a82ff685fba8ff89b`。该目录只包含本次生成的测试 JSON 与 SQLite 数据库，没有使用开发者配置或数据库。

## 验收边界

- SQLite、并发、回滚、迁移和字段测试使用真实本地临时数据库；fake 仅用于 Repository 替换合同。
- 未执行生产操作、MCP/provider 验收、PostgreSQL 替换验收或后续领域 CRUD 验收。
- 没有前端 UI 变更，因此不需要浏览器 E2E 截图；文档站执行构建验证。
- 本次按已有 namespace 将请求中的 `super_ai.memory` 映射为 `oncall_pilot.memory`；未创建旧名称兼容包。
- 初次静态检查发现 import 排序和 async context manager 注解问题，以及不可变 record 负向测试的静态赋值问题；已修正并通过最终完整检查。
- 只读检查了改动范围、资源所有权和测试映射；没有启动额外独立审查代理，不将本报告描述为独立多代理 code review。

## 同步与归档

已新增 `persistence-foundation` 主规格，更新 `backend-foundation` 的显式迁移 requirement。同步后逐项核对两份 delta，7 条 requirement 的完整内容均已落入主规格，且主规格没有 delta operation 标题。

归档位置：`openspec/changes/archive/2026-09-08-setup-sqlite-repository-foundation/`，保留 `.openspec.yaml` 和全部 artifact。`openspec list --json` 返回空 active Change 列表。归档后 `openspec validate --all --strict` 为 11 passed / 0 failed，WIKI 为 0 active / 6 archived、32 个 include 与导航校验通过，VitePress 构建成功。

同步主规格后、P03 尚未归档的短暂阶段，WIKI 校验曾报告 P01 的旧迁移 requirement 内容未同步。检查同步器后确认其只折叠已归档 Change；完成本次已授权归档后，P03 的 MODIFIED 正常覆盖 P01，严格同步成功。没有使用 `--allow-unsynced`，没有修改历史 artifact 或 WIKI 校验器。
