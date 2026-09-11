# 验证报告

日期：2026-09-11。Change：`manage-knowledge-documents-and-chunking`。

## 总结

| 维度 | 结果 |
| --- | --- |
| 完整性 | 7 条需求、16 个场景均有实现及测试；8 项任务完成 |
| 正确性 | 文件 policy、参数、生命周期、并发冲突、双用户隔离和预览边界通过 |
| 一致性 | 符合 canonical contracts、显式注入、无 import I/O、事务外向量清理和本 change 范围 |

CRITICAL：0。WARNING：0。未遗留阻止归档的问题。实现自检覆盖标准和规格两个维度；当前工具无独立 sub-agent review 能力，本报告不宣称独立代理审查。

## 需求与场景证据

| 需求 | 实现 | 测试证据 |
| --- | --- | --- |
| 隐式默认知识库与 owner-scoped API（自己的 KB、跨用户、未认证） | `knowledge.py` 的 UUID5 默认 ID、Repository owner/KB SQL、`knowledge_api.py` 受保护路由 | `test_all_routes_auth_owner_parent_isolation_and_logout`、`test_repository_owner_parameter_contract`、`test_repository_scope_unique_and_concurrent_uploads` |
| 文件 policy 与正文保存（有效 Markdown/PDF、拒绝无效文件） | `knowledge_documents.extract_document`、multipart 累计流上限及准确文件大小校验 | `test_markdown_and_size_boundary`、`test_pdf_real_text_and_rejections`、`test_invalid_upload_policy`、`test_http_file_policy_boundaries_and_unknown_fields` |
| hash、覆盖和删除（默认冲突、显式覆盖、普通删除） | `knowledge_models` partial unique index，`KnowledgeDocumentService` 短事务软删除、事务外清理、确认释放 hash | `test_lifecycle_conflict_overwrite_pdf_and_preview`、`test_vector_failure_retry_hash_reservation`、并发上传唯一性测试 |
| 文档 DTO（详情及不返回正文） | canonical KnowledgeDocument DTO、不可变 Document 记录与 public 投影 | lifecycle HTTP 测试、`packages/api-contracts/tests/knowledge.test.ts` |
| 统一切分与三策略（fixed、heading、paragraph） | `chunk_document_text`、`DocumentChunkingService.chunks/preview` | fixed overlap/offset、heading 层级/前言/代码围栏、paragraph CRLF/尾部空白测试 |
| 参数校验与持久化（非法 fixed 参数、其他策略带 fixed 参数） | 不可变 ChunkingConfig 与 strict normalize、持久化实际配置 | `test_invalid_chunking_config`、`test_invalid_multipart_config_has_no_side_effects`、overwrite 后配置读回 |
| 有界 preview（长文档、状态不变） | limit=12 提前结束统一 splitter，excerpt 最多 400 字，返回准确偏移和 owner/KB/document metadata | lifecycle 重复 preview/详情不变、三策略有界前缀一致、跨语言 12/400 负向测试 |

## 执行记录

- 后端完整 `uv --directory apps/backend run pytest -q`：386 passed。
- 最后预览优化及 import-safety 修改后，运行 knowledge core/API、protocol、migrations、import-safety 定向回归：176 passed。
- multipart 超限异常改为框架清理路径后，重跑 HTTP policy 边界测试：1 passed。
- `npm run backend:lint`：通过。
- `npm run backend:typecheck`：0 errors、0 warnings。
- `npm run contracts:typecheck`：通过。
- `npm run contracts:test`：42 passed，包含生成物漂移检查。
- `python -m unittest discover -s scripts/tests`：37 passed。
- `openspec validate --all --strict`：21 passed（归档前 20 个主规格加本 change）。
- `git diff --check`：通过；Git 的 CRLF 提示不是空白错误。
- active WIKI 同步：1 active、12 archived、71 includes 验证通过。
- `npm run docs:build`：通过。

## 实现自检

- SQLite 新迁移与 metadata 对比一致；复合 owner/KB 外键和 partial unique hash 索引生效。活动及待清理记录持有同一个 hash 占位。
- 所有受保护 Repository 方法 owner 必填、keyword-only；非法 owner 在 session I/O 前失败，读写同时限定父子归属。
- 向量 fake 使用独立 SQLite 写连接验证软删除已提交且服务未持有写事务；失败不发布替换文档、重复 hash 不释放、同一 DELETE/overwrite 可重试。
- 应用默认组合真实 MilvusVectorStore，测试显式注入 fake，不把缺失 adapter 当成功。provider 异常转换为安全固定 500，不泄露底层内容。
- PDF 使用 pypdf 生成真实文本 PDF fixture 验证提取，不仅测试损坏文件；测试均使用 tmp SQLite/config，不读取真实配置或密钥。
- import-safety 遍历全部应用模块，并阻断 pypdf PdfReader、数据库、网络、配置及应用文件 I/O。
- 只新增知识文档与切分，没有 UI、embedding、完整检索、索引 worker 或 MinIO 原文存储。未改动用户 `.codex/config.toml`。

## 验收边界

本次证据为真实本地 SQLite/认证 HTTP、pypdf fixture、向量 fake 和既有向量 adapter 离线测试；未连接真实 Milvus/MinIO、未执行 live 基础设施验收。默认 adapter 的实际删除需要可用的 Milvus 配置与服务；不可用时返回可重试错误。未修改前端 UI，因此无 UI E2E 截图要求。扫描 PDF 不提供 OCR；跨存储不宣称分布式原子事务，不提供后台自动补偿。

验证通过后按用户授权同步 `knowledge-documents`、`document-chunking` 主规格并归档，归档后再次执行 WIKI 同步、OpenSpec strict 校验、docs build 与 diff check。
