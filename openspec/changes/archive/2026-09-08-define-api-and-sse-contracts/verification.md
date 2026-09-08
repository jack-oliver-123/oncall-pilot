# 验证报告：define-api-and-sse-contracts

验证日期：2026-09-08。前置工程为用户明确确认的 `establish-project-foundation`，已先行归档。本次授权覆盖提案、实现、修复、验证、spec sync 与归档，不包含提交、推送或 PR。

## 三维检查

| 维度 | 结果 |
| --- | --- |
| 完整性 | 11/11 任务完成；五组 delta 含 14 条 requirement、22 个 scenario，全部实现、验证与生命周期收尾完成 |
| 正确性 | 33 个 Pydantic schema 与 canonical OpenAPI 逐项比较，包括 discriminator mapping；HTTP、SSE 和前端消费共享合同 |
| 一致性 | proposal/specs/design/tasks 与代码一致；Standards、Spec 独立审查的发现项全部修复并复核关闭 |

## 需求与证据映射

| 合同范围 | 实现与测试证据 |
| --- | --- |
| 成功 envelope、四类错误、安全目录 | `packages/api-contracts/openapi/foundation.openapi.json`、`src/generated.ts`、`tests/protocol.test.ts`；后端 `protocol.py` 与 `tests/test_protocol.py` |
| X-Request-ID 与验证字段路径 | `RequestIdMiddleware`、三个已知错误 handler 与未知异常适配；合法/缺失/非法 ID、body 数组索引和 query 路径、input/ctx 脱敏测试 |
| health、真实 path 与 response 对齐 | `app.py`；真实 APIRoute、响应模型、OpenAPI 路径、状态、header、schema 比较；隐藏路由与重复路由负向测试 |
| 八类 SSE、工具四态、错误复用 | `SseEvent`、`ToolCall` 及 `ApiError` 的生成判别联合；共享 fixtures、逐事件 serializer 和字段缺失/非法状态测试 |
| typed HTTP client | `apps/frontend/src/transport/apiClient.ts`；成功解码、目录全部错误、非法 JSON/envelope/status/request ID、bearer/fetch/signal 注入测试 |
| SSE parser 与资源释放 | `sseClient.ts`；三种换行逐字节切分、中文 UTF-8、BOM、注释、多行 data、EOF、未知事件、超限、握手失败、取消及缓存事件停止派发 |
| 禁止私有事件结构与生成漂移 | `scripts/check_contract_boundaries.mjs`、`scripts/tests/test_contract_boundaries.py`；TS interface/type/class/object、Python dict/class/TypedDict 负向探针；生成器不支持约束组合与 mapping 错误检查 |
| 同日归档 WIKI 覆盖 | `scripts/tests/test_sync_wiki.py` 的同日逆序名称回归先失败后通过；只调整 delta 校验折叠，不改变导航顺序 |

## 实测门禁

最终 Windows/Python 3.12 `npm run check` 整体退出 0，包含：

- 后端 pytest **95/95**，Ruff 通过，strict Pyright 0 errors / 0 warnings。
- contracts typecheck、生成漂移检查、Vitest **31/31**。
- 前端 lint、format、typecheck、Vitest **34/34**、生产 build；原有公开配置 sentinel 构建扫描继续通过。
- 仓库/WIKI unittest **27/27**，包括同日归档和私有协议结构负向回归。
- OpenSpec `validate --all --strict`、VitePress 构建和独立 `git diff --check` 通过。

HTTP 测试使用本地 ASGI app 和临时配置；SSE client 测试使用注入 fetch / ReadableStream，不代表新增业务 endpoint 的 live 验收。当前没有业务 SSE endpoint、认证实现或外部服务连接。

本次没有修改产品 UI，未新增浏览器 E2E 截图；前置工程的历史浏览器/CI 证据另见其归档验证记录。本次代码未提交或推送，因此新增协议及 CI 修复尚未在远端 GitHub Actions 运行。

## 审查与修复

Standards 原发现：schema 组合静默丢失约束、Python 常见事件构造绕过检查。Spec 原发现：隐藏/重复真实路由绕过 OpenAPI 检查、TS class 私有 DTO 绕过边界。上述项目均有负向回归且由原审查代理复核关闭。额外补齐 OpenAPI 显式 discriminator mapping 与非有限 JSON 数字拒绝。

没有未关闭的 CRITICAL、WARNING 或 SUGGESTION；未跳过实现需求核对。生成器是明确受控的 JSON Schema 子集，后续新增 schema 语义需同时扩展生成器与运行时 validator；工具调用状态的时间顺序由未来业务实现负责。

## 生命周期

实现 verify 与独立审查通过后，新增 api-protocol、frontend-transport、sse-protocol 三组主规格（12 条 requirement），修改 backend-foundation 与 wiki-sync 各一条，逐项比较 delta 与主规格并保留其余需求。随后归档到 `openspec/changes/archive/2026-09-08-define-api-and-sse-contracts/`，保留 `.openspec.yaml`。

归档后 `openspec list --json` 返回空 active 集合，`openspec validate --all --strict` 10/10 通过；WIKI 同步报告 0 active、5 archived、27 个 include 和导航验证通过，VitePress 构建成功；`git diff --check` 通过。最终所有 11 项任务均已勾选，不存在待实现或待归档步骤。

额外使用仓库外独立 Python 3.10.20 环境断言解释器版本，最终后端 pytest **95/95**、Ruff、Pyright 全部通过；这是 Windows 隔离实测，不能当作远端 Linux CI。
