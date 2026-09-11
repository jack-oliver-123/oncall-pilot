## Why

值班人员需要把 Markdown 和 PDF 纳入个人知识库，但当前没有可追踪的文档元数据、正文提取和统一切分入口。现在建立 owner-scoped 文档管理与可复用 splitter，可为后续索引和检索提供稳定、可审计的基础，同时避免把原文写入 MinIO 或越过既有 tenant 边界。

## What Changes

- 在 `packages/api-contracts` 先定义知识库、文档 DTO、上传 policy、multipart 配置、chunk preview、冲突/覆盖及认证授权错误合同。
- 为每个用户提供稳定的隐式默认知识库，增加文档列表、上传、详情、删除和 chunk preview API；本范围不支持创建或删除多个知识库。
- 后端只接受 UTF-8 `.md`/`.pdf`，限制 10 MiB，由后端权威校验扩展名、MIME 和大小，并用 `pypdf` 提取 PDF 文本。
- 在 SQLite 保存 owner-scoped 文档元数据、可索引正文、哈希、索引状态和实际切分配置；原文不写入 MinIO。
- 以 SHA-256 处理重复文档：默认返回 `BUSINESS_CONFLICT`，显式 overwrite 时软删除旧文档并按 owner/KB 清理旧向量；普通删除也清理向量。
- 实现 fixed-character、markdown-heading、paragraph 三种策略，preview 与未来 indexing 共用 `chunk_document_text` 入口，并限制 preview 为最多 12 段、每段最多 400 字。
- 增加 md/pdf 提取、策略边界、冲突覆盖、owner 隔离、向量清理和 import-safety 测试。

## Capabilities

### New Capabilities

- `knowledge-documents`: 隐式默认知识库、owner-scoped 文档生命周期、文件 policy、正文提取、哈希冲突与向量清理。
- `document-chunking`: 统一文档切分入口、三种策略、参数校验、持久化配置和有界预览。

### Modified Capabilities

- 无。

## Impact

- `packages/api-contracts/openapi/foundation.openapi.json`、生成的 TypeScript/Python contracts 和 contracts tests。
- `apps/backend` 的 FastAPI 路由、Pydantic DTO、SQLite migration/repository/service、文本提取与 splitter、Milvus 删除 adapter 及测试。
- 新增或锁定 `pypdf` 依赖；不实现完整检索、索引后台任务或前端 UI。
