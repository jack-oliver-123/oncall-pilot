# Qwen/Bailian 模型边界

`oncall_pilot.llm.provider.LlmProvider` 提供异步 `chat`、`embed`、`rerank`、`readiness` 与 `chat_capability.contextWindowTokens`。它是后续业务的注入边界，本次没有聊天页面、Agent 或新增 HTTP endpoint。`/health` 仍只检查进程存活。

## 配置与生命周期

默认 `uv sync` 安装所需模型依赖，无需安装完整 `ai` extra。`langchain-openai` 负责 chat/embedding；rerank 使用独立 httpx client。未引入 DashScope SDK。当前限制 `openai>=2.26,<2.27`，因为后续版本增加了隐式 `OPENAI_CUSTOM_HEADERS`，会破坏仅从本地 JSON 配置请求的保证；升级时必须重跑环境污染和 MockTransport 测试。

项目配置只有必需 `project.json` 和可选 `user.project.json` 的递归深合并结果。首次复制两个模板；只在 ignored `user.project.json` 的 `llm.chat.apiKey`、`llm.embedding.apiKey`、`llm.rerank.apiKey` 填写真实 key。三种能力可使用同一个获授权 key，也可独立配置。已有本机文件不要覆盖；按模板补齐缺失 section。模板中的其余未来能力 section 仅预留配置，不会初始化服务。

没有 llm section 的旧配置仍支持基础应用；一旦存在 llm 就会校验三类 endpoint 和 `modelCapabilities`。空凭据允许保存模板，但创建 provider 会在创建 client 前失败。模型名与 `modelCapabilities` profile 必须匹配；默认 qwen3.7-max 的 contextWindowTokens 为 1000000，切换模型需在本地 JSON 增加对应 profile。

```python
from pathlib import Path

from oncall_pilot.llm.config import load_provider_settings
from oncall_pilot.llm.factory import create_qwen_provider

async def example():
    settings = load_provider_settings(Path("config"))
    async with create_qwen_provider(settings) as provider:
        answer = await provider.chat("请简要说明如何排查服务超时", max_tokens=128)
        vectors = await provider.embed(["候选日志一", "候选日志二"])
        ranked = await provider.rerank("服务超时", ["候选日志一", "候选日志二"], top_n=1)
        return answer, vectors, ranked
```

示例的 `config` 路径相对仓库根目录。factory 上下文拥有并关闭所创建的 HTTP client（包括注入 transport）；使用期间须保持上下文打开。直接构造 `QwenOpenAIProvider` 时，三个注入 adapter 的生命周期由调用者管理。

embedding 固定 text-embedding-v4、1024 维，`check_embedding_ctx_length=false`，保持原始字符串、串行分批且每批最多 10 条。不会截断长文本，远端超限以失败返回；数量或维度异常不返回部分结果。空输入本地返回空列表。rerank 保留服务端索引、分数和排序，top_n 必须在候选数量范围内，不提供 fallback。

timeout 单位为秒、retries 表示首次失败后的额外重试次数。chat/embedding 使用 SDK 重试；rerank 只重试连接错误、超时、408、429、5xx，采用有限退避。readiness latency 单位为毫秒，包含本次探测及重试耗时。chat readiness 只请求一个输出 token，不要求截断结果形成完整答案；正常 chat 要求非空文本。取消继续传播。

## 手动 live smoke（需要真实凭据）

1. 核对账户地域、模型权限与实际 endpoint，在 ignored user 配置填写上述三个 key，必要时覆盖三个 baseUrl。模板使用北京 DashScope 域名；新业务空间可按控制台提供的域名覆盖，rerank 必须使用完整 text-rerank 路径。
2. 从仓库根执行：

```powershell
uv --directory apps/backend run python -m oncall_pilot.llm.smoke --config-dir ../../config
```

3. 每类能力必须输出一条包含 capability/provider/model/baseUrl/latency/ready/error 的 JSON。仅三条 ready 均为 true 且退出码为 0 才记为 live smoke 通过。退出码 1 是 provider failure，2 是配置或构造失败；不要把这些情况写成通过。
4. 记录执行日期、地域、模型、脱敏结果和退出码。不要复制配置、Authorization、原始异常或响应 body 到报告。

本次自动验证使用临时 JSON、fake adapter 和真实 LangChain client + MockTransport；**未执行真实凭据 live smoke**。这证明本地合同与错误边界，不证明账户权限、网络或远端模型可用。

## 依据

- [百炼 embedding API](https://help.aliyun.com/en/model-studio/text-embedding-synchronous-api)
- [百炼 rerank API](https://help.aliyun.com/zh/model-studio/text-rerank-api)
- [qwen3.7-max 能力](https://help.aliyun.com/zh/model-studio/qwen3-7-max)

以上来源于 2026-09-08 核对，地域及模型实际可用性以 live smoke 为准。
