# llm-providers Specification

## Purpose

为 On-call Pilot 提供仅依赖本地 JSON 配置、可注入且可离线验证的 Qwen/Bailian 模型边界，统一 chat、embedding、rerank 的参数、顺序、就绪探测、资源生命周期和错误安全。

## Requirements

### Requirement: 三类可注入异步模型边界
系统 SHALL 提供 `LlmProvider` Protocol 与 `QwenOpenAIProvider`，通过注入 chat、embedding 和独立 rerank adapter 实现异步能力。生产 chat MUST 只使用 langchain-openai ChatOpenAI，embedding MUST 只使用 OpenAIEmbeddings，MUST NOT 引入 DashScope SDK。

#### Scenario: 离线替换边界
- **WHEN** 调用者注入 fake adapter 或 fake HTTP transport
- **THEN** 三类能力可独立执行和断言，不依赖真实配置或凭据

### Requirement: 明确 chat 参数与能力 profile
chat SHALL 默认使用可配置 `qwen3.7-max`、temperature=0.2、timeout=120 秒、retries=2；provider MUST 提供当前模型的正整数 contextWindowTokens。模型和能力 profile MUST 来自本地 JSON。

#### Scenario: 配置覆盖传到 client
- **WHEN** 用户 JSON 覆盖模型、temperature、timeout、retries 并提供模型 profile
- **THEN** ChatOpenAI 收到合并后的参数且 provider 返回对应 contextWindowTokens

### Requirement: embedding 分批与顺序
embedding MUST 使用 text-embedding-v4、dimensions=1024、check_embedding_ctx_length=false、chunk_size 不大于 10；每次请求 MUST 使用未经 tokenization 的原始字符串列表且最多 10 条。结果 MUST 保持与所有输入对应的顺序，不返回部分或错误维度的结果。

#### Scenario: 多批次文本
- **WHEN** 输入超过 10 条、包含中文和换行的字符串
- **THEN** 请求分批且原文保持不变，最终向量数量、1024 维和输入顺序一致

#### Scenario: 空输入及错误响应
- **WHEN** 输入为空或远端返回数量、维度不匹配的结果
- **THEN** 空输入返回空列表且不请求远端；错误响应明确失败

### Requirement: 独立 rerank 请求和真实分数
rerank SHALL 默认使用 qwen3-vl-rerank 和独立可配置 text-rerank endpoint；payload MUST 包含 model、input.query/documents 和 parameters.top_n/return_documents。返回值 MUST 使用真实 index/relevance_score，校验重复/越界索引及非有限分数，MUST NOT 生成 fallback 分数。

#### Scenario: 正常排序
- **WHEN** 远端返回按相关性排列的 results
- **THEN** provider 保留远端顺序、索引和分数，并可映射原始候选

#### Scenario: 失败与边界
- **WHEN** 输入为空、top_n 非法、远端失败或结果畸形
- **THEN** 空列表本地短路，非法输入与远端错误安全失败，不伪造排序

### Requirement: timeout 和有限重试
三类调用 MUST 显式使用配置 timeout/retries。rerank MUST 仅对超时、连接错误、408、429、5xx 重试，最多 retries 次额外尝试；取消 MUST 传播。

#### Scenario: 暂时失败与永久失败
- **WHEN** 远端暂时失败后恢复、持续超时或返回 401
- **THEN** 恢复调用成功，持续失败按配置耗尽，401 不重试，异常不泄密

### Requirement: 最小 readiness 与安全错误
readiness MUST 实际发起所选能力最小异步请求并返回 capability/provider/model/baseUrl/latency（毫秒）/ready；失败 MUST 标记未就绪并返回安全错误。任何已配置 apiKey MUST 在异常及元数据中替换为 `[redacted]`，MUST NOT 暴露原始异常链、请求对象或响应 body。

#### Scenario: 就绪探测成功
- **WHEN** 三种能力的最小请求成功
- **THEN** 每项结果包含对应模型、URL、非负 latency 和 ready=true

#### Scenario: 包含多个凭据的异常
- **WHEN** adapter 抛出的异常含任意能力的 apiKey
- **THEN** 所有匹配被替换为 `[redacted]`，readiness 为 false，公开 traceback 不含原始凭据

### Requirement: 导入安全和确定资源生命周期
模块 import MUST NOT 读取项目配置、创建外部 client 或联网。client MUST 只在 factory/显式调用中创建并确定关闭；项目值 MUST NOT 从 OS 环境获取。

#### Scenario: 隔离导入与受污染环境
- **WHEN** 禁止文件 I/O、网络和 client 构造后导入所有模块，或环境中存在其他 API key/URL/代理
- **THEN** import 成功，显式 factory 只采用注入 JSON 的项目值

#### Scenario: 关闭和取消
- **WHEN** factory 上下文正常退出、构造失败或调用取消
- **THEN** 已创建的自有 client 均关闭且取消不转化为 readiness 失败
