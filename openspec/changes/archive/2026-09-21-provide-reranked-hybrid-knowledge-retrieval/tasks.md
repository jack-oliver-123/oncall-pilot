## 1. 合同与 OpenSpec 对齐

- [x] 1.1 在 canonical OpenAPI components 中增加 `KnowledgeRetrievalInput`、过滤器、结果、阶段分数和 citation/output schemas，并保持不新增 HTTP path。
- [x] 1.2 运行 contract generator，审查生成的 TypeScript/Python 类型，补充 contracts schema/typecheck/test 的回归覆盖。

## 2. 检索核心算法

- [x] 2.1 新增 tenant-scoped chunk source Protocol 和不可变检索模型，校验 query、topK、KB/document filters 和稳定 ID。
- [x] 2.2 实现中英文与 ASCII 运维 tokenizer，覆盖中文单字/bigram、英文、数字、Java 类名、trace/service token；实现 BM25L 正 IDF、非负分和不相交词项零分。
- [x] 2.3 实现向量/BM25L 双路召回、过滤、稳定分支排名、RRF(k=60) 和最多 20 条候选裁剪。
- [x] 2.4 接入真实 Qwen embedding/rerank 与现有 Milvus adapter，保留各阶段 rank/score、兼容 `score` 字段和 citation；任一必需分支错误都返回安全明确错误。

## 3. Agent Tool 组合

- [x] 3.1 创建 `knowledge_retrieval` LangChain Tool，闭包注入当前 `CurrentUser`/`OwnerScope`，禁止模型 filter 扩大权限，并在 Agent 组合层注册。
- [x] 3.2 实现空 query/空结果、单路未命中、错误收束和 no-fallback 行为，保证无命中不生成兜底内容。

## 4. 测试与验证

- [x] 4.1 增加后端单元/组合测试：中文英文 token、正 IDF、双路并行、单路未命中、RRF 公式和稳定 tie、rerank 改序、topK、全部 rank/score、空结果。
- [x] 4.2 增加 embedding/vector/BM25/rerank provider failure 及跨 tenant/filter 扩权测试，验证安全错误和无数据泄漏。
- [x] 4.3 运行 backend、contracts 及受影响 frontend contract tests；运行 `openspec validate --all --strict` 和 `git diff --check`，修复所有失败。
- [x] 4.4 检查本机配置：fake/local 测试证据已通过；因 Qwen API key 与 Milvus token 均不可用，live smoke 记为 `not-run`，未将其报告为通过。

## 5. 验证、同步与归档

- [x] 5.1 执行 `openspec-verify-change` 检查任务、需求场景、设计和代码一致性，修复 CRITICAL/WARNING；当前 CLI 不提供 `verify` 子命令，已按 verify skill 完成手工检查，无 CRITICAL/WARNING。
- [x] 5.2 按 delta spec 与主 spec 的差异同步 `openspec/specs/hybrid-knowledge-retrieval/spec.md`，重新验证并运行严格 OpenSpec 校验。
- [x] 5.3 在验证结果通过后归档 Change，保留 `.openspec.yaml` 并记录归档位置与 spec sync 结果。
