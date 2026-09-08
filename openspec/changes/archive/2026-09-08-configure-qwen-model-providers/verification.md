# P06 验证报告

- Change：`configure-qwen-model-providers`
- 日期：2026-09-08
- 验证范围：完整 proposal、design、两份 delta specs、tasks 与本次代码。
- 结论：离线验收通过，specs 已同步且 Change 已归档。真实凭据 live smoke 未运行，不作为本次通过项。

## 验证摘要

| 维度 | 结果 |
| --- | --- |
| 完整性 | 8/8 任务完成；10 条需求均有实现 |
| 正确性 | 18 个场景逐项映射实现和测试；无遗漏场景 |
| 一致性 | P01 深合并、三类注入边界、显式资源生命周期与设计一致；无 HTTP/SSE 或 Repository 变更 |
| CRITICAL / WARNING / SUGGESTION | 0 / 0 / 0（不将已声明的 live 验收范围外事项计为实现缺陷） |

## 需求与场景证据

路径以仓库根目录为基准。

| 需求/场景 | 实现 | 测试证据 |
| --- | --- | --- |
| 安全文件错误；缺失用户配置；无效项目配置 | `apps/backend/src/oncall_pilot/project_config.py:17` | `tests/test_project_config.py` 的深合并、缺失、非对象测试；`tests/test_llm_config.py:151` 覆盖缺失、损坏 JSON、UTF-8、不可读目录和无原始异常链 |
| 合并后 typed validation；缺失字段；基础配置兼容 | `llm/config.py:84`、`project_config.py:51` | `tests/test_llm_config.py:25`、`:77`、`:95`；原 `tests/test_project_config.py` 不含 llm 的基础用例继续通过 |
| 完整模板与 ignored 本机配置 | `config/project.template.json`、`config/user.project.template.json` | `tests/test_llm_config.py:102`、仓库 template/ignore 测试；本机两份文件在不存在时复制，`git check-ignore` 均命中 |
| 三类可注入异步边界 | `llm/provider.py:40`、`:54`、`:99`；`llm/factory.py:48` | `tests/test_llm_provider.py:93` 的真实 LangChain + MockTransport；`:295` 的注入 fake |
| 默认/覆盖 chat 参数与能力 profile | `llm/config.py:42`、`:65`；`llm/factory.py` | `tests/test_llm_provider.py:93`、`:424`：默认值及自定义模型、温度、contextWindowTokens、timeout/retries 的真实请求 |
| embedding >10 分批、原文和顺序；空输入和错误结果 | `llm/provider.py` 的 `embed`；`llm/factory.py:36` | `tests/test_llm_provider.py:93`：25 条按 10/10/5，中文/换行原样、顺序/1024 维；`:424` 自定义 3/3/1；`:362`、`:494` 错误维度、数量、NaN、后批次失败 |
| rerank 正常排序、失败和边界 | `llm/rerank.py:29`；`llm/provider.py` 的 `rerank` | `tests/test_llm_provider.py:93` payload/独立 transport/真实分数；`:352`、`:474`、`:516` 缺失/畸形/重复/越界/非有限结果与非法输入，均不 fallback |
| timeout 与有限重试 | `llm/factory.py` 的 SDK 配置；`llm/rerank.py` 的有限 retry loop | `tests/test_llm_provider.py:193`：三类 429 恢复、500 耗尽、401 不重试、timeout 耗尽；`:424`：自定义 timeout=0.25、retries=0 |
| 最小 readiness 成功/失败和所有 key 脱敏 | `llm/provider.py:69`、`:86` 及 `readiness` | `tests/test_llm_provider.py:154`、`:295`、`:536`：最小请求、latency/元数据、多个 key、无原始异常链、URL/model 脱敏 |
| import 安全、受污染环境、正常关闭/构造失败/取消 | `llm/factory.py:48` 与惰性导入 | `tests/test_import_safety.py` 全 package 文件/网络/client 阻断并断言未导入模型库；`tests/test_llm_provider.py:229`、`:315`、`:324`、`:389`、`:405` |

表中 `llm/*` 相对 `apps/backend/src/oncall_pilot/`，`tests/*` 相对 `apps/backend/`。

## 已执行门禁

| 门禁 | 结果 |
| --- | --- |
| `uv sync --directory apps/backend --frozen` | 通过，lockfile 一致 |
| `npm run backend:lint` | 通过，Ruff 无错误 |
| `npm run backend:typecheck` | 通过，strict Pyright 0 errors / warnings |
| `npm run backend:test`（Python UTF-8 模式） | 261 passed，92.63 秒 |
| `npm run contracts:typecheck` | 通过 |
| `npm run contracts:test` | 36 passed，包含生成漂移检查 |
| `py -3 scripts/generate_contracts.py --check` | 通过 |
| `py -3 -m unittest discover -s scripts/tests -p test_*.py` | 34 passed |
| frontend `tests/public-config.test.ts` | 7 passed，包含真实生产 bundle 秘密扫描 |
| `openspec validate --all --strict` | 同步前 15 passed；同步后归档前 16 passed；归档后 15 passed |
| `git diff --check` | 通过；新增文件另外按 CRLF-aware whitespace 规则检查通过 |
| `py -3 scripts/sync_wiki.py active configure-qwen-model-providers` | 通过，1 active / 8 archived，50 include，导航一致 |
| `npm run docs:build` | 通过，Node 22 / npm 10.9.7 下重跑通过 |

## 初次失败与环境处理

- Windows `python` 命中 Store 别名，初次 WIKI 命令及 contracts test 未运行成功；使用 `py -3`，并在执行 npm 的 shell PATH 前置已安装 Python 目录后重新执行通过。未修改系统或项目配置。
- 初次 npm 安装使用系统 Node 24 / npm 11，安装成功但有 engine 警告；contracts、前端配置和文档验收改用 Node 22.23.2 / npm 10.9.7 执行。
- 首轮定向测试 67 passed / 1 failed：readiness 测试用旧参数名直接索引导致 KeyError；改为检查实际 `max_completion_tokens` 后完整套件通过。
- 首轮完整后端 260 passed / 1 failed：迁移子进程的系统编码输出被测试按 UTF-8 解码失败；执行 shell 设置 `PYTHONUTF8=1` 后完整重跑 261 passed，无 warning。该变量只控制解释器编码，不是项目配置来源。
- 附加 no-index 空白检查需把 CRLF 当作行尾；显式关闭 autocrlf 却未声明 CRLF 时的误报不代表源码存在尾随空格。最终按仓库正常 `git diff --check` 及新增文件 CRLF-aware 检查通过。

## 未执行与限制

- **live smoke：not-run**。未读取或使用真实凭据，未请求真实 Qwen/Bailian 服务。手动命令、成功标准和退出码见 `apps/backend/llm.md`；不能由 fake 请求推断账户权限、网络与线上模型可用性。
- 自动测试中的 provider failure 是预期注入结果，不是线上故障证据。
- 未修改前端 UI，不涉及浏览器 E2E 截图；只验证公开配置和 bundle 隔离。
- 未执行 commit、push、PR、merge 或发布。

## Specs 与归档

已按用户本次授权同步：新建 `llm-providers`（7 条新增需求）；更新 `project-configuration`（1 条修改、2 条新增），保留原有其他需求及场景。全部 10 个 delta Requirement 完整块均与 main specs 逐条比较一致，main specs 无 delta operation header。

已归档至 `openspec/changes/archive/2026-09-08-configure-qwen-model-providers/`，`.openspec.yaml` 随目录保留。归档后 `openspec list --json` 返回空 active 列表；WIKI 为 0 active / 9 archived，50 include 和导航验证通过，Node 22 / npm 10.9.7 下文档构建通过。两份本机配置在全套测试结束后仍与模板哈希一致，且保持 ignored。
