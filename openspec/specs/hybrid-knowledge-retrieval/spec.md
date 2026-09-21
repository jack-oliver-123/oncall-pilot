## Purpose

为 On-call Pilot 的 Agent 提供一个严格受当前 tenant scope 约束的最终知识检索能力，将向量、关键词、RRF 和真实 rerank 结果统一为可追溯引用，支持值班人员从中文与运维标识中获得稳定的知识片段。

## Requirements

### Requirement: Agent 可调用最终混合检索工具
系统 MUST 提供名为 `knowledge_retrieval` 的 LangChain Tool，输入包括非空 `query`、可选 `topK`、可选 knowledge base filter 和可选 document filter；`topK` 默认值为 5，允许范围为 1 到 5。工具 MUST 在执行开始时固定调用方当前 `CurrentUser` 派生的 owner/tenant scope，模型传入的 filter MUST 只能缩小该 scope，不能指定或扩大 tenant。

#### Scenario: 默认参数和合法过滤器
- **WHEN** 当前用户以非空 query 调用工具且未提供 `topK`，或提供当前用户已有的 knowledge base/document filter
- **THEN** 系统使用 `topK=5` 并只在该用户 scope 内检索，返回符合过滤器的结果

#### Scenario: 非法 query 或 topK
- **WHEN** query 为空白，或 topK 不是 1 到 5 的整数
- **THEN** 系统返回安全的输入校验错误，不调用 embedding、Milvus、BM25 或 rerank

#### Scenario: 模型尝试扩大权限
- **WHEN** 模型传入其他 tenant 的 knowledge base/document 标识，或试图省略当前 scope
- **THEN** 系统按当前用户 scope 过滤并返回空结果或安全的未授权错误，不读取其他 tenant 的数据

### Requirement: 向量和 BM25L 关键词召回必须并行且使用当前语料
系统 MUST 对 query 生成 embedding，并与 Milvus 向量召回、当前 tenant 已成功索引文档语料的内存 BM25L 关键词召回并行执行。BM25 tokenizer MUST 同时生成中文单字和相邻 bigram，并保留英文、数字、Java 类名以及 `trace`、`service` 等 ASCII 运维 token；不相交词项的 BM25 分数 MUST 为 0，BM25 分数 MUST 不为负。BM25 语料 MUST 只包含当前 scope、过滤器允许且已成功索引的 chunk。

#### Scenario: 中英文和运维 token
- **WHEN** query 或 chunk 同时包含中文、英文、数字、Java 类名或 trace/service 标识
- **THEN** tokenizer 产生中文单字、中文 bigram 和完整 ASCII 运维 token，关键词召回能按这些 token 计算 BM25L 分数

#### Scenario: 两路并行召回
- **WHEN** 当前用户执行合法检索且有可用文档
- **THEN** embedding/vector 分支和 BM25L 分支在同一检索阶段并行开始，两个分支的结果独立保留

#### Scenario: 单路未命中
- **WHEN** 某个 chunk 只被向量分支或只被 BM25L 分支命中
- **THEN** 该 chunk 仍可进入融合，未命中分支的 rank 和 score 为 `null`

### Requirement: 使用 RRF 融合并限制 rerank 候选
系统 MUST 使用 `RRF(k=60)` 融合向量和 BM25L 的原始排名，公式为每个命中分支的 `1 / (60 + rank)` 之和；融合排序 MUST 使用稳定且确定性的 tie-break。送入 rerank 的候选 MUST 不超过 20 条，最终结果 MUST 按请求 topK 截断且不设置最低相关性阈值。

#### Scenario: RRF 公式
- **WHEN** 一个 chunk 在两个分支分别以 rank 1 和 rank 3 命中
- **THEN** 其 rrfScore 等于 `1/(60+1) + 1/(60+3)`，并按融合分数排序

#### Scenario: 稳定 tie
- **WHEN** 两个 chunk 的 RRF 分数相同
- **THEN** 系统使用稳定的原始排名和稳定 chunk id 进行确定性排序，重复调用得到相同顺序

#### Scenario: rerank 候选和最终 topK
- **WHEN** 融合后候选多于 20 条且请求 topK 小于 5
- **THEN** 系统只向 Qwen rerank 发送前 20 条候选，并最终返回不多于请求 topK 的结果

### Requirement: 使用真实 Qwen rerank 并保留阶段审计信息
系统 MUST 调用配置的真实 Qwen rerank 对融合候选重新排序。每条结果和引用 MUST 包含稳定的 chunk、document、knowledge base id、source、excerpt、metadata，以及 `vectorRank`/`vectorScore`、`bm25Rank`/`bm25Score`、`rrfScore`、`rerankRank`/`rerankScore`；未命中某分支的 rank/score MUST 为 `null`。兼容字段 `score` MUST 等于 `rerankScore`。即使 rerank 改变顺序，也 MUST 保留每个阶段的原始排名。

#### Scenario: rerank 改变顺序
- **WHEN** Qwen rerank 返回顺序不同于 RRF 顺序
- **THEN** 返回结果按 rerankRank 排序，同时每条结果保留原 vectorRank、bm25Rank 和 RRF 信息

#### Scenario: 结果引用合同
- **WHEN** 工具返回命中结果
- **THEN** 每条 result 与 citation 都包含稳定标识、source、excerpt、metadata、全部阶段 rank/score 和与 rerankScore 相同的 score

### Requirement: 空结果和必需分支失败必须安全可观察
系统 MUST 在没有命中时返回 `results=[]`，不得生成兜底内容。embedding、Milvus vector、BM25L 或 Qwen rerank 任一必需分支失败时 MUST 返回安全明确的错误类别和消息，不能伪造分数、悄悄改用另一种算法或把部分成功伪装成完整成功。

#### Scenario: 无命中
- **WHEN** 合法 query 在当前 scope 和 filters 下没有向量或关键词命中
- **THEN** 系统返回空 results 和空 citations，不生成解释性或猜测性内容

#### Scenario: embedding 失败
- **WHEN** Qwen embedding 调用失败或返回无效向量
- **THEN** 系统返回 embedding 分支错误，不调用或伪装完成后续检索

#### Scenario: vector、BM25 或 rerank 失败
- **WHEN** Milvus vector、当前语料 BM25L 或真实 Qwen rerank 任一必需分支失败
- **THEN** 系统返回对应安全错误，错误不包含凭据、query 正文或上游敏感详情，也不静默切换算法
