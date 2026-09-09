# Qwen/Bailian 模型接入

项目只读取 `config/project.json` 与可选 `config/user.project.json` 的递归深合并结果。`load_project_config` 保留通用 JSON；存在 `llm` 时验证结构。`load_llm_config(config_dir)` 要求完整模型配置与所选 chat model 的 capability profile。

## 配置

首次使用可从两个 `.template.json` 复制本机文件；已有本机配置时只补齐缺失字段，不覆盖用户值。两个本机 JSON 都被 Git 忽略。模板中所有凭据为空，只在 `user.project.json` 填入实际值：

```json
{
  "llm": {
    "chat": { "apiKey": "" },
    "embedding": { "apiKey": "" },
    "rerank": { "apiKey": "" }
  }
}
```

此例的空字符串需要在本机替换成实际 key，不能原样运行模型请求。chat/embedding/rerank 可使用不同 key、baseUrl、timeout、retries。不要使用 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY` 或 OS 代理变量配置本项目。

| 配置 | 默认值与约束 |
| --- | --- |
| `llm.provider` | `qwen-openai` |
| `llm.chat.model` | `qwen3.7-max`，可覆盖；同时配置同名 profile |
| `llm.chat.temperature` | 0.2，范围 0..2 |
| `llm.*.timeout` | 120 秒；SDK 为每次 HTTP I/O 超时，rerank 同时有每次请求总时限 |
| `llm.*.retries` | 2，即最多三次尝试，允许 0..10 |
| `modelCapabilities.<chat-model>.contextWindowTokens` | 默认 profile 为 1000000，必须是正整数 |
| `llm.embedding.model` / `dimensions` | 固定 `text-embedding-v4` / 1024 |
| `llm.embedding.check_embedding_ctx_length` | 固定 false，原文直接发送，不自动分词或截断 |
| `llm.embedding.chunk_size` | 默认 10，可设 1..10 |
| `llm.rerank.model` | 默认 `qwen3-vl-rerank`；仅适用于相同 input/parameters 协议的模型 |
| `llm.rerank.baseUrl` | 完整 `/api/v1/services/rerank/text-rerank/text-rerank` URL，不是 OpenAI base URL |

模板采用北京地域的兼容域名。若控制台提供业务空间域名或其他地域，请在用户配置覆盖对应 URL；不能混用不同地域的 key 与 endpoint。URL 不接受 userinfo、query 或 fragment。空 key 允许普通配置加载，显式创建生产 provider 时才失败，因此 `/health` 和非模型功能不依赖模型凭据。

`app`、`backend`、`frontend`、`database`、`vectorStore`、`mcp`、`clsMcpServer`、`prometheusAlerts`、`clsLogUpload`、`aiopsDemo` 目前是对应阶段的配置骨架；此模块不会因此连接或启动后续基础设施。浏览器仍只能接收 P01 公开 allowlist。

## 调用与注入

```python
from pathlib import Path
from oncall_pilot.llm.config import load_llm_config
from oncall_pilot.llm.qwen import open_qwen_provider

async def example() -> None:
    config = load_llm_config(Path("config"))
    async with open_qwen_provider(config) as provider:
        answer = await provider.chat("解释这条告警", max_tokens=128)
        vectors = await provider.embed_documents(["日志一", "日志二"])
        ranked = await provider.rerank("超时", ["网络超时", "登录成功"], top_n=1)
        readiness = await provider.readiness("chat")
```

`LlmProvider` 是调用方使用的 Protocol；`QwenOpenAIProvider` 可显式注入 `ChatClient`、`EmbeddingClient` 和独立 `httpx.AsyncClient`。factory 的 `transport` 参数可替换 chat/embedding HTTP transport；`rerank_client` 可独立替换。factory 关闭自建 client，注入的 rerank client 由调用者关闭；直接构造 provider 时，所有注入依赖都由调用方管理。

生产 chat 由 `ChatOpenAI` 执行，embedding 由 `OpenAIEmbeddings` 执行。chat 的 `max_tokens` 参数由锁定版 LangChain 转换为 HTTP `max_completion_tokens`，限制推理与回答总量；覆盖为其他模型时需确认该模型支持此参数。底层 OpenAI resource 仅用于显式凭据和 transport 装配，以及按 embedding index 恢复顺序；不使用 DashScope SDK。23 条向量输入默认按 10/10/3 串行发送；空列表不调用网络，批次失败不返回部分结果。rerank 返回不可变 `index/relevance_score`，索引和分数无效时失败，绝无 fallback 分数。

所有外部依赖延迟到 factory；import 不读取配置或创建 client。SDK 环境回退被显式参数、关闭环境代理、最小请求头和关闭远程 tracing 隔离。上游异常转换为安全错误类别与 `[redacted]`，不会保留响应正文及异常链；不会记录 key 或模型输入输出。取消操作继续向调用方传播。

## 手动 smoke 与证据边界

仅当本机三类 key、地域 endpoint 和模型权限均已配置时，在仓库根目录执行：

```powershell
uv --directory apps/backend run python -m oncall_pilot.llm.smoke --config-dir ../../config
```

该命令会产生真实模型请求，可能计费。chat 使用短提示与 8 token 输出上限，embedding 发送单条文本，rerank 发送单候选。极小预算可能消耗在推理上，合法的 `finish_reason=length` 响应即使文本为空，也视为连通成功；readiness 不评价答案质量。每行 JSON 包含 kind、provider、model、baseUrl、latency（毫秒）、ready 与安全 error。三类均成功时退出码 0，否则为 1。无需建立数据库、启动 FastAPI 或连接 MCP/Milvus。

P06 自动验证使用临时 JSON、fake adapter 与真实 SDK + fake HTTP transport；它证明请求协议、分批、重试、脱敏和生命周期。**真实凭据 smoke 未执行，不能据此声称真实 Qwen/Bailian 连通性通过。** 手动执行后应单独记录日期、地域、三类 ready 和延迟，禁止粘贴 key、完整配置或请求正文。

协议依据（2026-09-09 核实）：[阿里云 rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)、[embedding API](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)、[LangChain 原文输入](https://reference.langchain.com/python/langchain-openai/embeddings/base/OpenAIEmbeddings/check_embedding_ctx_length)。服务端权限与可用性仍以实际 smoke 为准。
