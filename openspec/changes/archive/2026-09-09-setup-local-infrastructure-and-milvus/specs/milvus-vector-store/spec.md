## Purpose

为 On-call Pilot 的后续知识库检索提供可显式管理且默认隔离租户的向量存储能力，确保配置、初始化、召回和删除的边界可以独立测试，并且不在模块导入时触发外部连接。

## ADDED Requirements

### Requirement: 显式且惰性的生命周期

向量存储 MUST 在导入与构造时不读取配置、不创建 client、不联网、不初始化 collection；SHALL 提供显式 connect、initialize、health、insert、search、delete-document，可注入 fake client，且不声明 public close API。配置 MUST 只来自本地 JSON 深合并后的 vectorStore。

#### Scenario: 导入与配置隔离
- **WHEN** 导入模块、构造 adapter 或设置冲突的环境变量
- **THEN** 导入与构造无应用 I/O；首次显式连接只采用注入目录中的 merged vectorStore uri/database/collection/token

#### Scenario: 幂等初始化和失败恢复
- **WHEN** 首次初始化、重复初始化或初始化中途失败后重试
- **THEN** 只有完整成功才进入 ready 状态，不重复建表，已有不兼容 schema/index 被拒绝且不破坏数据

#### Scenario: 独立健康探测
- **WHEN** 显式调用 health 且服务可用或故障
- **THEN** 返回真实探测成功或失败，不创建 collection，也不改变应用 /health 的存活语义

### Requirement: 固定向量与追溯字段

collection MUST 使用 chunkId 字符串主键、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt、metadata 和 1024 维 float vector；向量索引 MUST 为 HNSW/COSINE，M=16、efConstruction=200，搜索 ef=64；可过滤标量 MUST 有索引。

#### Scenario: 建表与索引
- **WHEN** 初始化空 collection
- **THEN** 创建全部字段、固定向量索引和标量索引后加载 collection

#### Scenario: 写入可信归属
- **WHEN** 插入合法 chunk 或试图覆盖归属、使用错误维度或非有限向量
- **THEN** 合法写入同时保留可信 ownerUserId/tenantId 标量和 metadata；非法输入在连接前拒绝

### Requirement: 结构化租户搜索与文档删除

搜索 MUST 只由经过验证的归属和 allowedKnowledgeBaseIds 生成 tenantId + knowledgeBaseId 条件；document/metadata 条件 MUST 由 retrieval tool 在 owner-scoped 粗召回后过滤。ownerUserId SHALL 用于追溯且不重复加入 Milvus filter。删除 MUST 同时限定 tenantId、knowledgeBaseId、documentId；禁止 raw expression 输入。

#### Scenario: 空授权范围
- **WHEN** 合法 tenant 使用空 KB 列表搜索
- **THEN** 返回 []，不读取连接配置、不创建 client、不连接或初始化 Milvus

#### Scenario: 非法范围
- **WHEN** tenant 为空，或删除缺少 KB/document scope
- **THEN** 在任何 I/O 前拒绝，包括空 KB 搜索时的空 tenant

#### Scenario: 转义与跨用户隔离
- **WHEN** 两个用户在相同 KB/document ID 下搜索或删除，或 ID 含引号、反斜杠和表达式字符
- **THEN** 值作为转义字符串处理，搜索只召回当前 tenant 的授权 KB，删除不影响其他 tenant 或其他 KB/document
