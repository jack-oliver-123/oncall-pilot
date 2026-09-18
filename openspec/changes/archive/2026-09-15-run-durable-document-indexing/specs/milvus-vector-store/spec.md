## ADDED Requirements

### Requirement: 文档全量索引批写
Milvus 向量记录 MUST 保留 chunkId、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt、chunking metadata 和 1024 维向量；写入 MUST 只接受已验证的完整记录。索引 handler MUST 显式 initialize collection，在删除旧文档向量时同时限定 tenant、knowledge base、document 和 owner scope，并通过一次 insert_chunks 写入本次文档的全部 records；不得通过 chunkId 单独删除或分批写入造成部分成功假象。

#### Scenario: 完整记录写入
- **WHEN** handler 写入一个或多个 chunk
- **THEN** 每条记录包含全部归属、正文、来源、创建时间和切分 metadata，向量维度和有限数值校验失败时拒绝整批

#### Scenario: 精确删除
- **WHEN** handler 重建文档
- **THEN** 只删除当前 owner/tenant/KB/document 的旧向量，不影响其他用户或文档
