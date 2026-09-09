## Why

P01 的 JSON 配置和 P03/P05 的持久化边界已建立，但后续对话、索引和检索尚无统一、可测试的模型入口。P06 建立 Qwen/Bailian 适配器，确保配置错误和上游故障不泄露凭据，模块导入不触发外部依赖。

## What Changes

- 完善本地 JSON loader 的安全错误；增加显式 LLM typed validation 和 chat capability profile。
- 补齐最终配置 section 的脱敏模板；缺失的本机配置从模板复制，已有本机值保留且始终 ignored。
- 新增 `LlmProvider` Protocol 与 `QwenOpenAIProvider`，分别注入 chat、embedding 和独立 rerank HTTP 边界。
- chat 使用 `ChatOpenAI`；embedding 使用 `OpenAIEmbeddings`、1024 维、原始字符串且每批最多 10 条；rerank 严格使用真实返回分数。
- 提供显式异步 readiness 与手动 smoke 入口，报告 provider/model/baseUrl/latency 并脱敏错误。
- 使用 fake transport/config 验证，不依赖本机凭据；验证通过后同步 specs、WIKI 并归档。

## Capabilities

### New Capabilities

- `qwen-model-providers`：可注入模型边界、分批向量、重排、readiness、脱敏与生命周期。

### Modified Capabilities

- `project-configuration`：完整脱敏模板、LLM typed validation 与安全配置错误。

## Impact

涉及 `apps/backend` 配置/provider/测试/文档、`config` 模板、OpenSpec 与生成 WIKI。将已锁定的 `langchain-openai`、`httpx`、`openai` 和 `langsmith` 声明为运行依赖，后两者用于显式 SDK 装配与关闭远程 tracing；不升级锁定版本、不引入 DashScope SDK、不初始化其他 AI 能力。不新增 HTTP endpoint、SSE、数据库或 UI；共享 contracts 保持现有边界并运行生成一致性、类型及测试检查。提交、推送、PR 和生产操作不属于本 Change。
