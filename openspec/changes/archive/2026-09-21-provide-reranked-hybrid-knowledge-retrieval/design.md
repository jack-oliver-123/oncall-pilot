## Context

详见 `proposal.md` 的 Why 和 Impact。本 Change 建立在 P10/P11 已成功索引的文档 chunk、现有 `QwenOpenAIProvider`、tenant-safe `MilvusVectorStore`、`CurrentUser`/`OwnerScope` 和默认知识库约束之上。当前系统没有 retrieval tool，也没有可用于关键词分支的运行时 chunk 语料读取接口。

## Goals / Non-Goals

**Goals:**

- 在一个后端 domain/service 中封装输入校验、scope 固定、文档语料读取、双路并行召回、RRF 和真实 Qwen rerank。
- 保留每个阶段的 rank/score，提供 contracts 可验证的 Tool input/output/citation 数据结构。
- 让 provider、Milvus、语料加载和 scope 都可显式注入，支持隔离的 fake 测试与真实 smoke。
- 失败时维持“必需分支完整成功”语义，避免部分结果被当作最终结果。

**Non-Goals:**

- 不新增独立搜索 HTTP path、前端搜索页面、持久化检索结果或新的知识库管理 API。
- 不修改文档上传、切分、索引 worker、embedding 模型或 Milvus collection schema。
- 不实现仅向量、BM25Okapi 或 provider 不可用时的 fallback 算法。

## Decisions

### 1. Retrieval domain 与 LangChain Tool 分层

新增检索 domain 负责纯 tokenization、BM25L、RRF、阶段记录和结果合同；组合层创建带有当前 `OwnerScope` 的 LangChain Tool。Tool schema 只接收模型可提供的 query/topK/filters，owner 和 tenant 由组合层闭包注入，避免模型参数成为授权边界。

备选方案是新增 HTTP 搜索 endpoint，但这会扩大产品 surface，且 Agent tool 已是目标调用界面，因此不采用。

### 2. 使用内存 BM25L 语料快照

每次工具调用由 owner-scoped repository 读取允许的、`index_status=succeeded` 文档并展开其 chunk 文本，构建仅在本次调用存活的 BM25L 语料快照。tokenizer 先提取连续 ASCII token，再对中文字符产生单字和相邻 bigram；ASCII token 保留大小写归一化后的可检索形式，并保留 Java 类名等包含点号的标识。

BM25L 使用正向 IDF 保护小语料：采用 `log(1 + (N-df+0.5)/(df+0.5))`，并将任何数值误差后的负分截为 0。语料快照不跨调用缓存，避免 owner、文档删除和索引状态变化导致泄漏或陈旧结果。

备选方案是 `rank-bm25` 的 BM25Okapi 或全局缓存。两者都不满足目标算法/隔离要求，且全局缓存会增加租户数据生命周期风险。

### 3. 向量召回与 BM25L 并行

先用当前 scope 的授权知识库和可选 document filter生成安全语料范围；随后用 `asyncio.gather` 并行等待 embedding+Milvus vector recall 与 BM25L recall。Milvus 的 scalar expression 只使用已授权 tenant/KB 集合，document filter 在检索 domain 中基于返回 chunk 做精确后过滤。任一必需分支抛错时取消并收束另一分支，统一为不带上游详情的 `RetrievalProviderError`。

这样保留了两路独立失败证据，并避免 SQLite/网络 I/O 处于同一事务。同步 Milvus 调用沿用现有 `bounded_thread` 边界。

### 4. RRF 与审计记录不可变

将两路结果映射到稳定 chunk id，分别按分支 score 降序并以 chunk id 稳定 tie-break 赋 rank。RRF 只累加存在的 rank；融合 tie-break 依次使用最高已知原始 rank、chunk id，保证重复运行顺序稳定。截取前 20 条后调用 provider.rerank，按 provider 返回的顺序赋 rerankRank；未返回的候选视为 provider 合同错误，不生成缺失分数。

最终内部 record 同时承载 `vectorRank/vectorScore`、`bm25Rank/bm25Score`、`rrfScore`、`rerankRank/rerankScore`，序列化时 rank/score 缺失用 JSON null，`score` 映射为 rerankScore。citation 复用相同稳定数据，避免返回另一套无法核对的引用。

### 5. Contracts 是共享类型事实源

在 `foundation.openapi.json` 的 components.schemas 增加 `KnowledgeRetrievalInput`、`KnowledgeRetrievalOutput`、`KnowledgeRetrievalResult`、`KnowledgeRetrievalCitation` 和阶段字段 schema，不添加 path。使用现有 `scripts/generate_contracts.py` 生成 TypeScript/Python 类型，并为 generated drift 加入 contracts 测试。

## Risks / Trade-offs

- [风险] 每次调用重建 BM25L 语料会增加 CPU 和内存开销 → [缓解] 只读取当前 scope、只处理成功索引 chunk、限制检索候选和 topK，并保持 chunk 读取接口可替换；后续若需缓存另建 Change。
- [风险] Qwen/Milvus 同步或网络失败使整个检索失败 → [缓解] 明确返回分支错误并保留安全类别，符合必需分支完整成功合同；监控和重试由上层 Agent/后续 Change 决定。
- [风险] rerank provider 返回重复或越界 index → [缓解] 复用 provider 的严格响应校验，检索层再验证候选映射和完整结果，拒绝伪造阶段数据。
- [风险] 当前索引数据缺少可直接查询的 chunk repository → [缓解] 定义 owner-scoped `IndexedChunkSource` Protocol，在生产组合层通过现有 Milvus metadata/文档 chunk 展开 adapter 注入，测试使用内存 fake；不在模块 import 时连接外部服务。
- [风险] OpenAPI generator 的 schema 命名和 Python 生成物需要同步 → [缓解] 只修改 canonical OpenAPI，运行生成器 check、contracts typecheck/test 和 backend 相关导入测试。

## Migration Plan

1. 发布后先部署代码与 contracts；没有新 migration，也没有独立 HTTP endpoint。
2. 启用 Agent tool 时由应用组合层注入现有 Qwen/Milvus/owner-scoped chunk source；历史未成功索引文档自然不进入语料。
3. 回滚时移除 tool 注册并回退生成 contracts；现有文档与向量索引不受影响。
