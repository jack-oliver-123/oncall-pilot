## Context

现有 `project_config.py` 返回深合并 JSON，基础应用可在没有 LLM section 时启动。P06 提供内部异步模型边界，不改变 `/health`、认证、Repository 和 HTTP/SSE contracts。

## Goals / Non-Goals

**Goals:** 配置可验证、三类能力可注入、每批 embedding 有界有序、真实 client 可用 fake transport 检验、错误安全、资源确定关闭。

**Non-Goals:** Agent 编排、流式聊天、工具调用封装、向量数据库、业务 endpoint、多模态 rerank、自动 live 验收。

## Decisions

1. 复用 P01 深合并。存在 `llm` 时 loader 验证 typed section；缺少整个 section 的旧配置继续支持基础应用，但显式加载 provider 配置必须失败。`llm` 包含 provider 与 chat/embedding/rerank，每项显式配置 baseUrl、apiKey；模型及 timeout/retries 具有模板一致的默认值。空凭据允许模板校验，factory 在创建 client 前拒绝空白凭据。`modelCapabilities` 按 chat 模型名称索引，必须含正整数 `contextWindowTokens`。使用 Pydantic SecretStr，验证错误只包含安全定位，不回显 input/ctx 或原始异常链。
2. `LlmProvider` 组合异步 chat、embed、rerank、readiness，生产实现通过构造参数接收三个窄 Protocol。chat 返回文本，embedding 返回与输入一一对应的向量，rerank 返回服务端 index/relevanceScore；不向业务暴露传输 payload。空 embedding/rerank 输入本地短路，无效输入和畸形响应明确失败。
3. 显式 async context manager factory 才导入 LangChain 并创建真实 client。chat 只使用 ChatOpenAI 的异步调用；embedding 只使用 OpenAIEmbeddings 的异步调用，禁用 tokenizer 路径，chunk_size <=10，逐批追加并验证数量、维度和有限数值。HTTP client 显式关闭环境代理读取；SDK 的 key、URL、组织等配置显式传入，禁用隐式 tracing。factory 拥有创建的 client 并确定关闭；直接注入的 adapter 由调用者管理。
4. rerank 使用独立 httpx 异步 client，请求为 model、input.query/documents、parameters.top_n/return_documents；解析 output.results 并校验索引唯一、范围和分数。timeout 使用每项配置；只重试超时/连接错误、408、429、5xx，最多 retries 次额外尝试；取消继续传播。chat/embedding 使用 SDK 内置同等 retry 配置，避免重复重试。
5. readiness 按能力发起最小异步请求：chat 限制输出、embedding 一个短字符串、rerank 一个短候选，返回 provider/model/baseUrl/latency（毫秒）、能力、ready 和可选安全 error。失败不冒充就绪。所有 API key（包括其他能力的 key）在异常文本中替换为 `[redacted]`；不转发服务端 body、请求对象或原始异常链，readiness 元数据也脱敏。
6. 提升 httpx、langchain-openai 到默认依赖，不安装 DashScope SDK。显式声明 openai>=2.26,<2.27，锁定已验证的无 OPENAI_CUSTOM_HEADERS 环境注入版本（2.26.0），与 langchain-openai 1.3.4 配合；升级需重跑环境污染与传输测试。新 SDK 在构造时无条件消费环境自定义 headers，可能覆盖 Authorization，当前通过版本约束避免该行为。模板补齐未来 section 但不初始化对应能力；保留 database，aiopsDemo 的 password 和全部凭据为空。本机配置只在不存在时复制。

## Risks / Trade-offs

- 地域与模型权限不同 → URL 可配置，手动 smoke 核实账户对应 endpoint；离线测试不代表线上可用。
- 批次串行增加大输入延迟 → 保证顺序、限制并发和请求体，后续吞吐优化另建 Change。
- 未来模型能力变化 → contextWindowTokens 由本地 profile 显式维护，切换模型必须提供对应 profile。
- 依赖可能隐式读取环境 → 用环境污染测试、真实 LangChain 配合 MockTransport、import-safety 和显式 client 参数检查。

## 外部依据（2026-09-08 核对）

- [百炼 embedding API](https://help.aliyun.com/en/model-studio/text-embedding-synchronous-api)：v4 支持 1024 维，每次最多 10 条。
- [百炼 rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)：qwen3-vl-rerank 使用独立 text-rerank 路径及 input/parameters 结构。
- [qwen3.7-max](https://help.aliyun.com/zh/model-studio/qwen3-7-max)：profile 模板使用 1000000 contextWindowTokens。模型权限和线上行为仍需 live smoke。

## Migration Plan

运行默认 uv sync，复制模板至不存在的本机 JSON；只在 ignored user 配置填写凭据。旧基础配置无 llm 时继续工作；启用 provider 前补齐 section。撤回此 Change 不涉及数据库迁移。
