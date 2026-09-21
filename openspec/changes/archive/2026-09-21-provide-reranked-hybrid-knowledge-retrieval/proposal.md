## Why

On-call Pilot 已能将知识文档切分、向量化并写入 tenant-scoped Milvus，但 Agent 还没有可以直接调用的最终知识检索工具。仅依赖向量会漏掉中文关键词、类名和 trace/service 等运维标识，旧式 BM25Okapi 方案也不符合本 Change 要求；现在需要把当前 tenant 的向量召回、内存 BM25L 召回、RRF 融合和真实 Qwen rerank 组织成一个可审计、可失败的 LangChain Tool。

## What Changes

- 新增 `knowledge_retrieval` LangChain Tool，接收非空 query、受限 `topK` 和可选 knowledge base/document filters，工具上下文始终注入当前 user/tenant scope。
- 对同一查询并行执行 Qwen embedding、Milvus 向量召回和当前 tenant 文档语料的内存 BM25L 关键词召回；BM25 tokenizer 同时保留中文单字、bigram 以及英文、数字和 Java 类名、trace/service 等 ASCII 运维 token。
- 使用 `RRF(k=60)` 融合两个分支，候选上限为 20，再调用真实 Qwen rerank；最终结果最多 5 条，不设置最低相关性阈值。
- 每个结果和引用返回稳定的 chunk/document/knowledge base 标识、source、excerpt、metadata，以及 vector、BM25L、RRF、rerank 各阶段的排名和分数；未命中分支使用 `null`，兼容的 `score` 等于 `rerankScore`。
- 任何必需的 embedding、vector、BM25 或 rerank 分支失败都返回安全明确的错误，禁止伪造分数、静默切换算法或生成兜底内容；空命中返回空 `results`。
- 在 `packages/api-contracts` 增加 Tool input/output/citation 类型，不暴露独立搜索产品 API。
- 增加中英文 token、正 IDF、并行、单路未命中、RRF 稳定排序、重排改序、topK、分数和排名、空结果、各类 provider 失败及跨 tenant 的测试。

## Capabilities

### New Capabilities

- `hybrid-knowledge-retrieval`: 为 Agent 提供 tenant-scoped、可审计的向量与 BM25L 混合召回、RRF 融合和 Qwen rerank 工具。

### Modified Capabilities

- 无。

## Impact

- 后端新增检索 domain/tool、中文和 ASCII 运维 tokenization、BM25L/RRF 排序及组合层依赖注入，并复用现有 Qwen provider、Milvus adapter、文档 repository 和 `CurrentUser`/`OwnerScope`。
- `packages/api-contracts/openapi/foundation.openapi.json` 及生成的 TypeScript/Python contracts 增加工具输入、输出、引用和阶段分数类型；不新增 path。
- 后端测试和 contracts 测试增加覆盖；前端只消费共享类型，不发生 UI 或路由修改。
- 真实 Qwen rerank、Qwen embedding 和 Milvus smoke 依赖本机有效配置；无可用真实服务时将明确记录未执行，不把 fake 测试当作 live 验收。
