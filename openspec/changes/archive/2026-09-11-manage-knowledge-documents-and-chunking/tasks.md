## 1. 合同

- [x] 1.1 扩展 OpenAPI DTO、policy、multipart、preview 和错误，生成跨语言合同与漂移测试。

## 2. 正文与切分

- [x] 2.1 实现文件 policy、Markdown/PDF 提取及边界测试。
- [x] 2.2 实现统一 splitter、参数规范化、metadata 和有界预览测试。

## 3. 持久化与 API

- [x] 3.1 实现默认知识库、owner-scoped Repository、迁移与隔离测试。
- [x] 3.2 实现冲突/覆盖、软删除和事务外向量清理及失败重试测试。
- [x] 3.3 实现认证 API、依赖注入及真实临时 SQLite HTTP、import-safety 测试。

## 4. 验证

- [x] 4.1 运行 backend/contracts 门禁、tooling tests、OpenSpec strict validate 和 git diff --check。
- [x] 4.2 核对规格、场景和设计一致性，记录 verify 证据，更新持久化文档和 WIKI 并验证 docs build。
