# P07 验证报告

- Change：`setup-local-infrastructure-and-milvus`
- 日期：2026-09-09
- 分支：`feat/setup-local-infrastructure-and-milvus`
- 起始提交：`25eefab`；P01/P05/P06 归档与当前代码均已核对。
- 最终结论：10/10 任务完成，代码、规格和必要本地门禁通过，已同步 specs 并归档；无 CRITICAL/WARNING 未解决项。真实服务条件性未运行单独记录，不等同于 live 验收。

## 验证维度

| 维度 | 结果 |
| --- | --- |
| Completeness | 4 类 artifacts 完整；5 项 requirements、11 个 scenarios 均映射到实现和测试 |
| Correctness | tenant/KB 搜索、三维删除、schema/index、lazy lifecycle 与 JSON 合同有本地证据 |
| Coherence | 使用 oncall_pilot namespace、P05 scope、P06 1024 维与官方 SDK 窄端口；与 ADR-0002/0003 一致 |

## 需求和场景证据

| 需求 / 场景 | 实现 | 验证 |
| --- | --- | --- |
| 五服务边界 / 渲染 Compose | `infra/compose.yaml`、`infra/alertmanager.yml` | `test_docker_compose_config_dependencies_mounts_and_ports`：服务、依赖健康条件、持久卷、只读挂载、loopback 端口 |
| 五服务边界 / 废资产回归 | 同上、config templates | `test_compose_services_versions_and_no_interpolation`、`test_no_legacy_assets_or_image_config` |
| 镜像唯一事实源 / 无冲突 | Compose 中固定指定镜像；模板原已无 docker 段 | 白名单版本与遗留字段黑名单测试 |
| 显式生命周期 / 导入与配置隔离 | `vector_store/store.py:83`、`config.py:51`、`client.py:26` | 无配置目录构造/空搜索、merged JSON 覆盖、环境变量不生效、全包 import-safety 禁止 I/O/SDK 构造 |
| 显式生命周期 / 幂等与失败恢复 | `store.py:108`、`schema.py:42` | 同实例并发和重复初始化、新实例复用、失败重试、缺失索引补建、6 类 schema/index 漂移拒绝 |
| 显式生命周期 / 健康 | `store.py:125`、`client.py:95` | health 成功/失败/恢复、未创建 collection、SDK get_server_version 有界调用；原应用 health 回归 |
| 固定字段 / schema/index | `schema.py:15`、`client.py:43` | fake 字段/索引精确检查，加真实 pymilvus schema.verify、IndexParams builder 和 search ef=64 调用合同 |
| 固定字段 / 可信归属 | `store.py:55`、`memory/vector_scope.py` | 标量和 metadata 双重归属、覆盖拒绝、错误维度/非有限向量、无时区时间、非法 JSON 整批 I/O 前拒绝 |
| 结构化 scope / 空授权 KB | `store.py:142` | 不存在配置目录也直接返回 []，不连接、不初始化；空 owner 仍先拒绝 |
| 结构化 scope / 非法范围 | `store.py:133/142/166` | owner 必填 keyword-only，None/空白/错误类型拒绝；删除 KB/document 不完整拒绝 |
| 结构化 scope / escaping 与跨用户 | P05 filters、`store.py:142/166` | fake 独立解析表达式并存取数据，两个用户相同 KB/document、引号/反斜杠/中文/注入片段，删除保留其他 owner/KB/document；retrieval 后过滤合同 |

以上路径相对仓库根；`vector_store/` 的完整目录为 `apps/backend/src/oncall_pilot/vector_store/`，测试位于 `apps/backend/tests/test_vector_store.py`、`test_vector_client.py`、`test_import_safety.py` 和 `scripts/tests/test_local_infrastructure.py`。

## 本地门禁

| 检查 | 结果 |
| --- | --- |
| 初始验收 red | Compose 缺失触发错误及失败，adapter 缺失触发 ModuleNotFoundError，确认测试能够发现未实现 |
| 后端全量基线 | Windows / Python 3.12.10：290 passed；随后增加 JSON 修复与 6 个回归 case |
| 修复后定向测试 | 38 passed（vector store、官方 SDK 合同、import-safety） |
| 修复后 backend lint/typecheck/test | Ruff 通过；strict Pyright 0 errors / 0 warnings；pytest 296 passed（218.52s）；最后仅补测试的类型标注，另行通过 Pyright 和该参数合同测试 |
| `npm run wiki:test` | 37 passed，包括 3 项基础设施合同；无 skipped |
| `docker compose -f infra/compose.yaml config --quiet` | 通过；不等于容器启动或服务健康通过 |
| `uv lock --directory apps/backend --check` | 通过；pymilvus 3.0.1 从 optional 移到运行依赖，没有依赖版本漂移 |
| `openspec validate --all --strict` | 同步前 16 passed；同步后 18 passed；归档后 17 passed，0 failed（active Change 已移出计数） |
| `git diff --check` | 归档后通过；另按仓库原有行尾设置检查新增文件，无补丁空白错误 |
| WIKI | 归档后同步完成：0 active、10 archived、55 includes，目录/索引/导航验证通过；最终 VitePress 构建通过（9.91s） |

## 独立 code review

按照 code-review 的 Standards / Spec 两轴进行只读独立检查，基线为 `25eefab`，包含本次 tracked 和 untracked 新文件，排除用户 `.codex/config.toml`。

- **Standards**：发现 1 项 metadata 非标准 JSON 静默转换问题；补充回归后先得到 4 failed / 1 passed，再复用 `memory.values.serialize_json` 修复。复核确认关闭，无残留发现。
- **Spec**：0 项可操作问题；另以锁定 pymilvus 3.0.1 源码核对调用签名、collection/index 返回形状和 delete_count。

两轴最终均为 0 项未解决问题。未将 adapter 的必要 fake/SDK 类型隔离视为多余转发层。

## 真实服务与未运行边界

执行 `uv --directory apps/backend run python ../../scripts/milvus_smoke.py` 返回：

```text
SKIP: 本机 127.0.0.1:19530 不可用，真实 Milvus smoke 未运行。
```

Docker daemon 可用，但检查时没有运行中的 Milvus；没有启动/修改已有其他项目容器。真实 Milvus CRUD、指定 beta 镜像运行健康、Attu 与 beta 的实际连接均未验证，不以 fake 或 config 渲染代替 live。用户要求仅在服务可用时执行 smoke，因此该条件性未运行不阻塞本次代码与规格归档。提供的 smoke 只用临时 JSON、固定 loopback 和随机独立 collection，清理仅针对该测试 collection。

没有前端 UI、HTTP/SSE 合同改动，未重新运行 frontend/contracts 门禁或浏览器 E2E；未声称这些本次通过。未执行远程 CI、提交、推送、PR、merge 或生产操作。

## 同步与归档

两个 ADDED delta 已合并到 `openspec/specs/local-infrastructure/spec.md` 和 `openspec/specs/milvus-vector-store/spec.md`，合计 5 requirements、11 scenarios。主规格保留完整 Purpose，将 delta operation 改为标准 Requirements；写入后 readback 和移动前再次逐字比较所有内容一致，无残余差异。

已在验证完成后归档至 `openspec/changes/archive/2026-09-09-setup-local-infrastructure-and-milvus/`，保留 `.openspec.yaml`。归档前验证全部 artifacts done、10/10 tasks 完成、目标不存在且 source/target 都位于当前 workspace。归档后 `openspec list --json` 返回空 active 列表；WIKI、docs build、OpenSpec 和补丁后置门禁均通过。

全部更改留在 `feat/setup-local-infrastructure-and-milvus` 工作树，未暂存或提交；用户已有 `.codex/config.toml` 保留。此报告不将此前 P05/P06 的记忆结果当作当前验证，本次代码与依赖状态均已重新检查。
