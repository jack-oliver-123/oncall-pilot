# P06 验证报告：configure-qwen-model-providers

验证日期：2026-09-09。范围为本次工作树相对基线 `b9802375efaf79afce604703711efb39136bdcf5` 的变更，包含新增未跟踪文件。真实凭据 smoke 未执行。

## 完整性、正确性、一致性

| 维度 | 结果 |
| --- | --- |
| 实现完整性 | 7/7 配置、模型和文档任务完成；所有 9 条 Requirement、13 个 Scenario 已映射证据 |
| 正确性 | backend 全量 259/259 通过；请求协议、分批、重试、readiness、异常与资源释放覆盖完整 |
| 一致性 | 实现遵循设计及 ADR-0002；不新增 HTTP、数据库、MCP 或 UI 行为 |
| 生命周期 | 9/9 tasks 完成；两个主规格逐条核对通过；已归档至 `2026-09-09-configure-qwen-model-providers`，实际 WIKI 同步和构建通过，active Change 为 0 |

没有未修复的 CRITICAL、WARNING 或 SUGGESTION。真实服务可用性属于明确未执行的手动 smoke，不计为自动验收通过。

## 需求与场景证据

| Requirement | 实现 | 场景验证 |
| --- | --- | --- |
| 最终配置模板覆盖模型和后续基础设施 | `config/project.template.json`、`config/user.project.template.json` | `scripts/tests/test_repository_foundation.py` 检查 section/aiopsDemo/空凭据；本次显式从模板补缺，已有本机值保留，git check-ignore 验证两个本机文件均 ignored |
| 模型配置必须显式验证 | `apps/backend/src/oncall_pilot/llm/config.py:18`、`:94` | `test_llm_config.py`：深合并、空值、缺失三类 endpoint 字段、无效 URL/port、profile、温度/超时/retries/向量参数；`test_llm_provider.py:302`：空 key 不读取环境补值 |
| 配置错误必须快速失败 | `apps/backend/src/oncall_pilot/project_config.py:17` | `test_project_config.py`：可选文件缺失、必需文件缺失、无效 JSON、非对象根、非 UTF-8、敏感路径与格式化 traceback 不泄密 |
| 三类模型边界可独立注入 | `llm/contracts.py:39`、`llm/qwen.py:90`、`:238` | `test_import_safety.py` 阻断应用 I/O 导入所有模块；provider tests 验证无请求创建、owned 释放、borrowed rerank 保留、body 异常传播、初始化/清理失败脱敏 |
| 对话参数与能力来自配置 | `llm/config.py:75`、`llm/qwen.py:271` | `test_llm_provider.py:41` 检查真实 SDK wire model/temperature/auth/baseUrl/timeout；config tests 检查所选 profile，SDK retry tests 检查尝试次数 |
| 向量分批保持原文和顺序 | `llm/qwen.py:60`、`:119` | `test_llm_provider.py:67`：23 条中文/空白/重复文本按 10/10/3 分批；fake 服务倒序返回 index，结果恢复输入顺序；空输入无请求，错误数量/维度/索引/数值拒绝 |
| 重排保留真实相关度 | `llm/qwen.py:140` | `test_llm_provider.py:102`、`:194`：专用 payload、真实索引/分数、空候选不请求；缺分数/非法结构/越界/重复拒绝且不重试无效响应 |
| 超时和重试有界 | `llm/qwen.py:140`、SDK 显式装配 | `test_llm_provider.py:137`、`:154`、`:320`：401 一次、408/429/503 最多三次、timeout 两次（retries=1）；`test_llm_readiness.py:157`：永不响应 fake transport 被总时限取消 |
| 就绪探测和故障不泄密 | `llm/qwen.py:201`、`:260`、`llm/smoke.py:17` | `test_llm_readiness.py`：三类最小请求、元数据、延迟、上游多 key 脱敏、取消传播、空凭据 smoke；`test_llm_provider.py:356`：合法预算耗尽响应；`:387`：清理异常无原始异常链 |

表中 `llm/` 指 `apps/backend/src/oncall_pilot/llm/`，测试短文件名指 `apps/backend/tests/`。

## 实际运行门禁

| 命令 | 最终结果 |
| --- | --- |
| `npm run backend:lint` | 通过 |
| `npm run backend:typecheck` | 0 errors、0 warnings |
| `npm run backend:test` | 259 passed，最终全量运行 143.40 秒，Python 3.12.10 |
| `uv lock --directory apps/backend --check` | 通过；未改变第三方锁定版本 |
| `npm run contracts:check` | 通过，无生成漂移 |
| `npm run contracts:typecheck` | 通过 |
| `npm run contracts:test` | 36 passed |
| `npm run frontend:test` | 49 passed，含真实生产构建的 sentinel secret 扫描 |
| `npm run wiki:test` | 34 passed |
| `python scripts/sync_wiki.py active configure-qwen-model-providers` | 通过，50 个 include 与导航一致 |
| `npm run docs:build` | 通过 |
| `openspec validate --all --strict` | 同步前 15/15、同步后 16/16、归档后 15/15 通过 |
| `python scripts/sync_wiki.py archive 2026-09-09-configure-qwen-model-providers` | 实际归档后通过：0 active、9 archived、50 include，导航一致；docs:build 通过 |
| `git diff --check` | 通过；新增源码、测试和 artifact 另做尾随空白检查 |

没有修改前端 UI，未执行浏览器视觉 E2E；前端已有公开配置/认证/transport 单测及构建秘密扫描已运行。未声明未运行的 frontend lint/typecheck 或真实服务验证通过。

主规格同步后、归档前，WIKI 同步器只读取已归档 Change，曾报告旧 P01 的同名配置错误 Requirement 内容不一致。已检查同步器的归档日期折叠逻辑，并在临时目录复制 OpenSpec 与 WIKI，模拟 P06 归档：0 active、9 archived、50 include 与导航全部通过。实际归档后再次执行真实同步及 docs:build，均通过。没有使用 `--allow-unsynced`，也没有修改旧归档或 WIKI 校验器。

## 独立 code review

Standards 与 Spec 两路只读复核基于同一工作树和 OpenSpec artifacts，包含锁定 SDK 源码检查。

- Standards：初审发现 1 个 P2——factory 的 client 清理异常可绕过脱敏。已先用 fake transport 复现，再增加 `test_factory_cleanup_error_does_not_disclose_transport_secrets` 并修复。复审分别验证正常清理、调用方异常、取消、body 与清理同时失败；最终无阻塞发现。
- Spec：未发现要求缺失、实质偏离或超范围功能；最终无发现。

过程中还修复了非 UTF-8/路径泄密、SDK 环境 header 旁路和极小预算 readiness 误判。最后一次 backend 全量运行已覆盖全部修复，早先 red 测试和中间失败不计作最终通过证据。

## 手动 smoke

真实 Qwen/Bailian 凭据 smoke：**未执行**。自动测试全部使用临时 JSON、fake adapter 或真实 SDK + fake HTTP transport，没有连接真实 Qwen、MCP、Milvus 或生产数据库。

配置好 ignored `user.project.json` 中的三类凭据及对应地域 endpoint 后，可显式执行：

```powershell
uv --directory apps/backend run python -m oncall_pilot.llm.smoke --config-dir ../../config
```

只记录 kind/provider/model/baseUrl/latency/ready 与安全 error；不要记录 key 或完整请求/响应。操作说明见 `apps/backend/llm.md`。
