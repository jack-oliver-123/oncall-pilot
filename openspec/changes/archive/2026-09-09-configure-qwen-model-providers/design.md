## Context

参见 proposal.md 的动机。现有 loader 返回 JSON object，认证与 Repository 测试使用无 llm 的最小配置；`langchain-openai` 已锁定在可选 ai 依赖。ADR-0002 要求 JSON 为唯一配置来源，浏览器公开投影保持不变。

## Goals / Non-Goals

目标是提供显式可组合的 Python 异步模型服务与稳定配置校验。provider 不持有租户数据、不访问 Repository；后续业务由已授权 OwnerScope 提供输入。本次不添加 HTTP readiness route、Agent 编排、向量数据库连接、MCP 或 UI。

## Decisions

1. `project_config` 保留 P01 深合并 API；有 llm 时调用纯 Pydantic 配置校验，无 llm 的旧基础配置仍可加载。显式 `load_llm_config` 要求完整 llm 和 profile。各模型有独立 model/baseUrl/apiKey/timeout/retries；SecretStr 隐藏凭据，生产 factory 校验非空。URL 禁止 userinfo、query 和 fragment，防止凭据混入报告。校验错误只给固定字段位置，丢弃原始输入及异常链。
2. `llm` 包包含配置、Protocol/结果记录、Qwen provider 和显式 smoke CLI。chat 使用 ChatOpenAI，embedding 使用 OpenAIEmbeddings；SDK 延迟导入 factory，HTTP client 显式注入，使用 trust_env=false，并明确覆盖 SDK 的 key/base/organization/project/proxy 等环境回退。HTTP hook 重建最小请求头（保留 chat 必需的 SDK raw-response 控制头），防止 OPENAI_CUSTOM_HEADERS 旁路注入。`httpx`、`langchain-openai`、`openai`、`langsmith` 为当前能力的运行依赖；后两者分别用于显式 SDK 装配和禁用环境驱动的远程 tracing，业务请求仍通过 LangChain。
3. `LlmProvider` 暴露异步 chat、embed_documents、rerank、readiness 与 context_window_tokens；提供注入 chat/embedding adapter 和独立 httpx AsyncClient。生产 factory 是 async context manager，拥有并关闭自建同步/异步 HTTP client；注入 rerank client 由调用方管理。
4. embedding 显式按 chunk_size（1..10）串行分批并验证数量、1024 维和有限数值，不返回部分成功。SDK 使用 check_embedding_ctx_length=false、encoding_format=float；利用 OpenAI response 的 index 恢复批内顺序，跨批按输入拼接。文本不分词、不裁剪。
5. rerank 使用专用 `/api/v1/services/rerank/text-rerank/text-rerank` endpoint 和文本 input/parameters payload，解析 output.results，检查索引范围/唯一性、有限分数和返回数量。独立 client 可替换；仅暂时 HTTP/网络故障重试，使用异步有界退避，失败不回退。
6. readiness 默认探测 chat，也可选择 embedding/rerank；chat 使用极短提示与 8 token 输出上限，embedding 单字符串，rerank 单候选。合法的 length completion 即使文本为空，也证明最小请求连通；不把预算耗尽误判为服务故障。报告以毫秒为 latency；失败保留固定错误类别和 `[redacted]`，不保留不可信上游消息或异常链。普通 provider 调用应用相同策略。
7. 不新增共享 HTTP contract；运行 contracts:check/typecheck/test 与现有 backend 协议测试防止边界回归。fake transport 经过真实 SDK 序列化验证请求参数；子进程 import-safety 阻断应用 I/O。

## Risks / Trade-offs

- 上游模型/地域/业务空间权限可能变化 → baseUrl、model 和 profile 由 JSON 配置；默认 qwen3.7-max profile 为 1,000,000 tokens，真实 smoke 单独记录。
- 只返回安全错误类别会减少上游诊断细节 → 可区分 timeout、认证/HTTP 与无效响应，但绝不输出响应体。
- 串行向量批次吞吐较低 → 当前优先确定顺序、单批限制和明确失败，未来性能 Change 再评估并发。
- 完整模板与 P01 的 foundation-only 测试冲突 → 更新该测试为 P06 section 与递归秘密检查，保留所有 ignore/公开投影断言。

## Migration Plan

补齐模板，从模板创建缺失本机文件；已有配置仅补缺失字段，保留现有值。真实 key 填 user.project.json。无凭据的普通应用仍可启动，只有显式 provider 创建要求 key；无数据库迁移。回滚本次代码与模板即可，不删除本机配置。

## 外部约束依据

核实日期：2026-09-09。阿里云文档目前给出业务空间域名，部署时按控制台配置覆盖默认兼容域名。

- [阿里云 rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)：qwen3-vl-rerank 的专用 endpoint、input/parameters、output.results。
- [阿里云 embedding API](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)：v4 的 1024 维与每批 10 条限制。
- [LangChain 原文输入开关](https://reference.langchain.com/python/langchain-openai/embeddings/base/OpenAIEmbeddings/check_embedding_ctx_length)：false 时直接发送字符串。
- [qwen3.7-max 模型信息](https://help.aliyun.com/zh/model-studio/qwen3-7-max)：模型 profile；可用性仍需要用户地域的真实 smoke。
- [Qwen OpenAI-compatible chat API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)：Qwen3.7-Max 支持 max_completion_tokens；锁定版 ChatOpenAI 会将 max_tokens 调用参数转换为该 wire 字段，限制推理与回答的总输出。
