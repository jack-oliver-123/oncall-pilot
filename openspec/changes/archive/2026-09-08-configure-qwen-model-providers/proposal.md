## Why

P01 已建立本地 JSON 配置来源，Repository 基础和共享 contracts 已具备，但后续对话与检索还缺少可注入、可离线测试的模型边界。P06 将 Qwen/Bailian 接入约束集中在配置和 provider 中，避免业务代码处理凭据、批次限制和外部异常。

## What Changes

- 完善现有 loader 的安全文件错误，在深合并后按需验证 LLM section 与模型能力 profile；不引入环境变量配置来源。
- 补齐最终配置 section 模板，所有凭据为空；仅在本机文件不存在时从模板复制，保留已有 ignored 配置。
- 增加 `LlmProvider` Protocol、`QwenOpenAIProvider`、chat/embedding/rerank 注入边界和显式 factory。chat 使用 `ChatOpenAI`，embedding 使用 `OpenAIEmbeddings`，rerank 使用独立 HTTP client。
- 固定 embedding 为 `text-embedding-v4`、1024 维、原始字符串、每批最多 10，保持顺序；chat 默认 `qwen3.7-max`、temperature 0.2、timeout 120、retries 2。
- 提供最小异步 readiness、统一安全错误和 API key 脱敏；不提供伪造 rerank fallback。
- 增加离线合同测试、完整后端门禁和手动 live smoke 说明；验证通过后同步 specs、归档并重建 WIKI。

## Capabilities

### New Capabilities
- `llm-providers`: 三类模型调用、能力元数据、显式资源生命周期、readiness 与错误安全。

### Modified Capabilities
- `project-configuration`: 安全错误细节、完整模板与按需 typed LLM validation。

## Impact

- 涉及 `apps/backend` 配置、模型适配器与测试，`config` 模板、依赖 lockfile、OpenSpec 与 WIKI。
- 依赖 P01 配置、Repository 与共享 contracts 基础；不新增 Repository、受保护 path、HTTP/SSE 合同、Agent、索引任务或基础设施。
- 不使用 DashScope SDK，不自动使用真实凭据，不提交、推送或发布 PR。
- 本次用户已明确授权按上述范围连续提案、实现、验证、同步 specs 和归档。
