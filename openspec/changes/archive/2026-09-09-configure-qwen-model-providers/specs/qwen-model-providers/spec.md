## Purpose

为 On-call Pilot 后续对话、知识索引和检索建立可注入的 Qwen/Bailian 模型边界，统一异步请求、批次顺序、能力信息、故障脱敏和资源生命周期，允许在没有真实凭据时验证协议行为。

## ADDED Requirements

### Requirement: 三类模型边界可独立注入
系统 SHALL 提供 chat、embedding、rerank 三类可注入异步边界；生产 chat 与 embedding MUST 使用 OpenAI-compatible 协议，rerank MUST 使用独立 HTTP client。模块导入 MUST 不读取项目配置、不创建外部 client、不联网，client MUST 仅在 factory 或显式调用中创建并可释放。

#### Scenario: 隔离模型请求与导入
- **WHEN** 测试导入所有模块或以 fake transport 创建 provider
- **THEN** 导入没有应用 I/O，显式调用只使用注入依赖，关闭 provider 释放其拥有的 client，注入 client 仍由调用方管理

### Requirement: 对话参数与能力来自配置
chat SHALL 使用可配置 model，默认 `qwen3.7-max`、temperature=0.2、timeout=120 秒、retries=2；对应 capability profile MUST 提供正整数 `contextWindowTokens`，不得隐式套用其他模型的窗口。

#### Scenario: 指定模型参数
- **WHEN** 调用方提供 JSON 深合并后的模型参数与 profile
- **THEN** 请求使用该 model、temperature、timeout 和 retries，provider 暴露所选 profile 的 contextWindowTokens

### Requirement: 向量分批保持原文和顺序
embedding MUST 使用 `text-embedding-v4`、dimensions=1024、原始字符串输入、check_embedding_ctx_length=false、chunk_size 不大于 10；多批次结果 MUST 与原始输入顺序相同，不得生成 fallback 向量。

#### Scenario: 超过十条输入
- **WHEN** 输入 23 条包含中文、空白及重复内容的字符串
- **THEN** 请求按最多 10 条分批，原文不被分词或截断，返回 23 个对应顺序的 1024 维向量

#### Scenario: 空输入与异常结果
- **WHEN** 输入为空或上游返回数量、维度或数值无效的向量
- **THEN** 空输入不请求网络并返回空列表，无效结果明确失败且不返回部分或伪造结果

### Requirement: 重排保留真实相关度
rerank SHALL 默认使用 `qwen3-vl-rerank` 专用 endpoint，以 `model`、`input.query`、`input.documents` 和 `parameters.top_n` 发送文本请求，返回上游 index 与 relevance_score；不得伪造 fallback 分数。

#### Scenario: 正常重排
- **WHEN** 查询与候选文档通过独立注入 client 提交
- **THEN** 返回真实排序、原文索引和有限相关度分数，空候选不请求网络

#### Scenario: 重排响应不合法
- **WHEN** 响应缺少分数、索引越界、索引重复或返回错误结构
- **THEN** 明确失败且不生成替代分数

### Requirement: 超时和重试有界
各边界 MUST 使用配置 timeout 和 retries；重排仅重试连接故障、超时、408、429 和 5xx，不重试认证错误、无效响应或输入错误。

#### Scenario: 暂时故障与永久故障
- **WHEN** 上游超时或返回可重试状态
- **THEN** 总尝试最多 retries+1 次，耗尽后返回安全错误；401 只尝试一次

### Requirement: 就绪探测和故障不泄密
readiness SHALL 对所选 chat、embedding 或 rerank 发起最小异步请求，返回 provider/model/baseUrl/latency 和成功状态。任何 apiKey MUST 在错误中替换为 `[redacted]`，错误及其可见 traceback 不得包含原始上游响应或凭据；readiness 不得由 import 或 `/health` 隐式触发。

#### Scenario: 探测成功与错误脱敏
- **WHEN** readiness 收到成功响应或含任意已配置 apiKey 的异常
- **THEN** 成功返回可识别 provider、model、baseUrl 与非负延迟；失败报告脱敏信息，普通调用同样安全失败
