## Context

动机见 proposal。前置主规格现已存在；唯一 endpoint 是 `/health`，前端尚无网络请求。沿用本地 JSON 配置和 import-safe factory，不初始化外部服务。

## Goals / Non-Goals

生成物由合同重建，运行时无需 Node/Python 互相导入。传输层可独立测试，不接入 UI、不新增业务路由、不实现自动重连或工具执行引擎。

## Decisions

1. `packages/api-contracts/openapi/foundation.openapi.json` 是 OpenAPI 3.1 入口；`components.schemas` 定义全部 wire 类型，`ApiError` 的各 code 分支记录固定 category、httpStatus 和 message 默认值。生成器读取受控 JSON Schema 子集，生成 TS 类型和 Python Pydantic 声明/目录；不支持的 schema 关键字直接失败。选择合同优先，避免 FastAPI 实现先决定协议；不另维护私有 TS union 或 Python event DTO。生成检查进入 contracts:test 与仓库测试。
2. success.data 为任意 JSON 值，health 以专门 schema 收窄为 status=ok。失败 error 为 code 判别联合；details 可选 JSON 对象，只由明确安全的业务信息填充。验证错误仅保留结构化 path（含 body/query/path 及数组索引）、type 和固定安全消息，禁止回传 input、ctx 或原始异常文本。四类 envelope 测试明确指四种错误 category，并额外覆盖成功 envelope。
3. 纯 ASGI request-id middleware 校验入站 ID 为 1–128 位 ASCII 字母数字及 `._:-`，无效/缺失时生成 UUID；response header 与 meta 一致。HTTPException/RequestValidationError 进入统一 handler，未知异常转换 SYSTEM_INTERNAL_ERROR。若响应已开始，不再发送第二个 HTTP envelope。协议 endpoint 的响应模型及生成的 OpenAPI paths 通过合同测试校验；框架文档 endpoint 不算业务路径。
4. SSE 共同字段 id/type/channel/timestamp；timestamp 是带时区的 RFC3339 字符串。delta 事件携带 delta；tool.call 携带 callId/name/status，started 不携带结果、delta 携带 delta、completed 携带 JSON output、failed 携带 ApiError。reference.source 携带 sourceId/title/url，task.status 携带 taskId/status，report 携带 reportId/title/content，complete 携带 finishReason，error 携带 ApiError。工具状态顺序由调用者执行，本 Change 检验每个生命周期 payload 的合法形状，不预建跨事件业务状态机。
5. SSE serializer 只接受生成联合，发送 id/event/data 和空行。frontend parser 使用增量 TextDecoder 与逐行状态，处理 UTF-8、BOM、LF/CRLF/CR、跨 chunk 分隔、注释、多行 data、多 frame 和空 frame；EOF 丢弃未以空行结束的 frame。事件 JSON 由共享 validator 校验，显式 wire id/event 必须与 JSON 一致，未知事件或无效结构抛协议异常。依据 [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)（2026-09-08 核查）。不自动重连，提前取消时释放 reader，限制未完成 frame 大小避免无界缓存。
6. apiClient 根据生成 operation 表推导成功 data 类型，严格验证 envelope、Content-Type、HTTP 状态和可见 request ID；错误抛 typed ApiClientError。sseClient 用 fetch 支持 bearer、request ID、AbortSignal，返回共享 SseEvent 的 AsyncIterable；HTTP 握手失败复用 apiClient 错误解析。网络/协议异常与服务端 ApiError 分开。注入值仅来自调用者，不读取环境变量或本机配置。当前没有业务 SSE path，sseClient 的 URL 仅为基础扩展点。
7. 后续提案先增加合同 path/schema/error/event，再运行生成命令，再实现 endpoint；现有协议语义不得静默修改。测试遍历真实业务路由/response model，拒绝未登记 endpoint；AST 边界检查拒绝应用中定义私有事件 DTO 或手写事件 payload。
8. 本次前置工程（创建于 2026-08-28）与合同 Change（创建于 2026-09-08）在同一天归档，名称字典序与创建顺序相反。复现测试证明 WIKI 原先仅按归档名称折叠会误报健康规格未同步；归档 delta 校验改按归档日期、OpenSpec created、目录名依次排序，不改变页面导航顺序，不使用文件修改时间或伪造日期。相同归档日和创建日仍保留原有名称顺序规则；更复杂依赖图不在本次范围。

## Risks / Trade-offs

- 自有生成器范围有限 → 只支持明确使用的 schema 子集，对未知关键字 fail closed，增加生成器失败测试及独立 JSON Schema 验证。
- 固定事件形状约束后续扩展 → 新字段和新事件先修改合同并补兼容测试；本次不猜测业务数据库字段。
- `/health` 响应不兼容旧调用方 → 同一工作树同步更新 contracts、后端和测试；回滚时整体回滚合同与消费者。
- 本次仅本地验证 → 不提交或推送，远端新 CI 明确标为未运行；不把单元测试或历史 CI 当作新增业务 live 验收。

## Migration Plan

先建立合同和生成检查，更新后端健康响应与错误适配，再增加前端 transport。所有指定门禁通过后执行 verify、同步五组 delta 并逐项比较，再归档和更新 WIKI。
