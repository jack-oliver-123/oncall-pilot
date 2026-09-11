# 持久化边界

`oncall_pilot.memory` 只导出数据库无关契约和不可变 record。SQLite 实现放在 `oncall_pilot.memory.sqlite`。本项目不提供旧 `super_ai` namespace，也不预建没有实际需求的 `extended_sqlite` 或领域 CRUD。

## 显式初始化与事务

先按 [迁移指南](migrations/README.md) 对目标数据库执行显式迁移，然后由组合层使用下面的调用方式。示例中的 `config_dir` 必须由 app factory、lifespan 或依赖 provider 注入；不要在 module scope 执行。

```python
from pathlib import Path

from oncall_pilot.memory import Repository, SchemaRevision
from oncall_pilot.memory.sqlite import SQLiteRepository, open_database


async def read_revision(repository: Repository) -> SchemaRevision:
    return await repository.schema_revision()


async def run(config_dir: Path) -> SchemaRevision:
    async with open_database(config_dir) as database:
        async with database.transaction() as session:
            return await read_revision(SQLiteRepository(session))
```

领域函数只接收 Repository，不接收 ORM model、engine 或 session。未来 PostgreSQL adapter 实现相同领域 Protocol，在组合层替换；基础层提供 schema revision contract；认证层另提供 AuthRepositoryPort，AuthService 通过 AuthTransactions 获取该 Protocol，组合层在事务内组装 SQLite adapter。

`open_database` 读取 `project.json` 与可选 `user.project.json` 的深合并结果。`database.url` 必须是 `sqlite+aiosqlite:///...` 文件 URL；相对数据库路径以配置目录的父目录解析，与进程 cwd 无关。支持绝对路径、空格与百分号文件名，不支持内存数据库、SQLite URI/query 模式或其他驱动。没有环境变量覆盖入口。

初始化只建立 engine/session factory 和所需父目录，首次连接才创建数据库文件；不会自动迁移或建表。未迁移数据库调用 `schema_revision()` 抛出 `SchemaNotInitialized`。FastAPI app factory 只读取配置；lifespan 显式持有并关闭数据库资源，`/health` 本身不查询数据库。

每个 `transaction()` 创建独立 async session，正常退出提交，异常或取消退出回滚并关闭。多个 Repository 通过同一个 session 组成原子工作单元；adapter 不调用 commit，不把 session 传入领域。不跨协程共享 session，不在事务中等待网络或 LLM。SQLite 同时只有一个 writer，忙等待上限 5 秒；NullPool 每次归还即关闭连接，不承诺无界并发吞吐。所有在途事务结束后再关闭 Database，关闭后拒绝新事务。

## 字段和 schema 约定

- `new_id()` 显式生成标准 UUID4 字符串；未来主键建议长度 36。ID 与时间在创建 record 时生成，禁止用 import 时求值作为默认参数。
- `utc_now()` / `as_utc()` 使用 aware datetime。ORM 层 `UTCDateTime` 存储无时区 UTC，读取恢复 UTC aware datetime，拒绝 naive datetime，保留微秒。
- SQLAlchemy `JSON` 字段统一经过 engine 的 serializer/deserializer，保留标准 JSON 值语义和中文；拒绝 NaN/Infinity、非字符串 key、tuple 与自定义对象。JSON 值按整值替换写入；不要依赖 ORM 自动发现嵌套原地修改。record 含集合时需在 adapter 边界转为深度不可变结构。
- 需要查询、关联、唯一约束或状态流转的数据必须使用规范化列和表。JSON 仅承载不参与这些操作的有限附加属性；不建立通用大 JSON 业务状态表。
- 未来 ORM model 继承 `sqlite.base.Base`，约束使用统一命名；CHECK 约束必须显式命名。新 model 要加入迁移 metadata 的显式导入，再生成、审查并测试 revision。
- tenant-scoped Repository 必须显式传入 `owner_user_id`，本地 tenant ID 从该值派生，并测试过滤，不使用默认或全局 tenant。

## 强制归属与租户上下文

`CurrentUser` 是已验证的最小用户身份；HTTP 层通过 `auth.api.current_user` 从认证会话派生，不能从 URL、请求 body、header 中的 owner/tenant 值构造。`OwnerScope` 是不可变的归属上下文，`owner_user_id` 必填，`tenant_id` 为只读派生属性。本地模型里二者都等于 `CurrentUser.user_id`，仍保留 owner 与 tenant 的不同语义。上下文按请求显式传递，不存入 module scope、默认参数或全局 tenant。

受保护 Repository 的 Protocol 和实现都采用 `async def get(resource_id: str, *, owner_user_id: str)` 这类签名；列表、创建、读取、更新、删除、批量操作、计数同样要求 keyword-only owner。`memory.scope.require_scope_id` 在访问 session 前拒绝空值、错误类型、首尾空白与控制字符。写入必须由 scope 填充 owner；如果入参 record 已含 owner，先调用 `OwnerScope.require_owner` 验证，更新 payload 不允许改变 owner 或父归属。

SQLite 的 `scoped_select`、`scoped_update`、`scoped_delete` 和 `owner_predicate` 在构造 SQL 时绑定 owner 值。用 `.where()` 追加资源 ID、父 ID、状态版本等条件，不允许替换或丢弃 owner 条件。避免 `session.get(Model, resource_id)`、无 scope 的全表读取和 service 层补检查；即使 identity map 已缓存其他用户对象，scoped SELECT 也必须重新执行 owner 查询。

```python
statement = scoped_select(
    DocumentRow, DocumentRow.owner_user_id, owner_user_id=owner_user_id
).where(DocumentRow.id == document_id, DocumentRow.knowledge_base_id == knowledge_base_id)
```

这里的 `DocumentRow` 仅说明未来接口用法，并非现有业务表。领域调用方只收到不可变记录或缺失结果，不收到 session/ORM。新 Repository 按实际领域定义 Protocol，不继承通用 CRUD 来隐藏 owner 参数。

受保护父资源查询必须带 owner。父列表入口先用 scoped 查询确认父存在于本用户 scope，再读取子列表；未找到父时不能返回空列表。父子创建可采用带 owner 的 `INSERT ... SELECT`，子资源读取和写入必须同时限定 owner、parent ID、child ID。未来 schema 以 `(owner_user_id, parent_id)` 复合外键关联父 `(owner_user_id, id)`，避免写入跨用户父子关系；迁移测试必须验证约束。可变父关系需要同事务验证且带条件写入，不得依赖早先单独查询的结果。

Repository 以 `None` 表示该 scope 中缺失，更新/删除返回可选资源 ID。使用布尔值或受影响行数的领域调用方必须将 false/零行显式转换为缺失，不能直接传给 `require_owned_resource`。HTTP 层用该 helper 统一将 `None` 转换成 `AUTH_FORBIDDEN` 403。父资源不存在、他人资源、子资源不存在或父子不匹配均不返回资源名、owner、查询细节，也不再做全局存在性查询；合法空父集合正常返回空列表。未知公开 URL 的既有 404 不属于受保护资源查询。

具名非受保护例外包括：基础设施 `schema_revision`；认证引导的 `add_user`（注册）、`find_user_by_email`（验证密码）、`resolve_token_hash`（按会话摘要恢复身份）。它们不提供通用业务查询能力，不向客户端暴露记录/凭据。`get_user` 只查当前 owner；`add_session`、`get_session`、`touch_session`、`revoke_session` 均显式带 owner。登出仅 revoke 当前 session，不删除 users 或业务资源，其他会话及其他用户资源保留。

## 向量边界

`memory.vector_scope` 是不连接 Milvus 的可执行约定。标量字段使用 `vector_ownership(owner_user_id=...)`，metadata 使用 `vector_metadata(extra, owner_user_id=...)`；两处都保留 `tenantId` 和 `ownerUserId`。附加 metadata 不能覆盖这两个归属字段。

`allowed_knowledge_base_ids` 必须来自当前 owner 的 scoped Repository 授权结果，不能直接传客户端提交的 KB 列表。`search_filter` 只生成 `tenantId == 当前用户 and knowledgeBaseId in 授权列表`；`ownerUserId` 用于追溯，不重复加入搜索条件。可选 document/metadata 条件由 retrieval tool 通过 `scoped_recall` 的 `post_filter` 在召回后执行，不能混进 Milvus 搜索 filter，也不提供原始表达式透传入口。

空 KB 列表的 `search_filter` 返回 `None`，这表示必须停止调用，不是可传给 Milvus 的“无过滤”。优先使用 `scoped_recall`：只有非空合法 scope 才调用 `recall`，未来 adapter 必须在该回调内部创建/获取 Milvus 客户端、读取连接配置和发起请求。空 KB 时不连接、不初始化客户端、不执行后过滤。即使 KB 为空，空 tenant 也应先失败。

`document_delete_filter` 只有在 owner、knowledge base、document 三个值全部有效时才返回删除条件；输出包含 `tenantId + knowledgeBaseId + documentId`，禁止无 scope delete 或省略某个维度。调用方先生成合法条件再连接。值通过 JSON 字符串转义，不能作为表达式拼接；ID 去重只影响授权集合的重复成员。

表达式中的相等、`in` 和逻辑 `and` 依据 [Milvus 标量过滤规则](https://milvus.io/docs/boolean.md)（2026-09-08 查阅）。P05 的纯 scope 合同由 P07 的实际 adapter 复用；fake、SDK 合同与 live 验证分别报告。

## Milvus adapter

`oncall_pilot.vector_store` 不在 import/构造时读取配置或连接。下面函数由主机组合层显式调用，config_dir 必须注入：

```python
from pathlib import Path
from oncall_pilot.memory.scope import CurrentUser
from oncall_pilot.vector_store import MilvusVectorStore, VectorChunk


def index_and_search(config_dir: Path, user: CurrentUser, chunk: VectorChunk):
    # chunk 的 KB/document 必须先通过 owner-scoped Repository 校验。
    store = MilvusVectorStore(config_dir)
    store.initialize()
    store.insert([chunk], owner_user_id=user.user_id)
    return store.search(
        chunk.vector,
        owner_user_id=user.user_id,
        allowed_knowledge_base_ids=[chunk.knowledge_base_id],
    )
```

collection 固定 1024 维 FLOAT_VECTOR、HNSW/COSINE（M=16、efConstruction=200、search ef=64）。chunkId 为调用方生成的全局唯一字符串主键，不提供 upsert；重复业务索引应由上层决定删除旧文档后重建。documentId、knowledgeBaseId、tenantId、ownerUserId、source、createdAt 建立 INVERTED 索引；content/metadata 不参与粗召回条件。createdAt 需要 aware datetime，存成 UTC ISO 字符串；向量必须是 1024 个有限数值。写入前验证整批数据并复制 metadata，归属投影不能被覆盖。

metadata 复用 `memory.values.serialize_json` 的标准 JSON 值约定，拒绝非字符串 key、tuple、自定义对象与非有限数值，不静默转换数据；任一记录无效时整批在连接前拒绝。

`search` 的 owner_user_id 必填，allowed_knowledge_base_ids 来自 scoped Repository；limit 为 1–64，空授权 KB 不读配置、不连接。结果是官方 hit 结构（id、distance、entity），retrieval 层在其上执行 document/metadata 后过滤。`delete_document(owner_user_id=..., knowledge_base_id=..., document_id=...)` 返回删除数且始终带完整 scope；不能通过 chunkId 单独删除。

`health()` 显式调用真实服务版本探测并返回 bool，不建表，不改变应用 `/health`。初始化有界超时，已有 schema/index 漂移失败关闭，缺失索引可补建。此同步 adapter 不公开 close，官方 SDK 负责客户端资源；未来异步调用方应卸载同步 I/O。服务配置与 smoke 操作见 [基础设施指南](../../infra/README.md)。

## 知识文档（P10）

`0004_knowledge_documents` 新增默认知识库与文档表。每个 user 的默认 KB 使用 UUID5 确定性派生，不能创建/删除额外 KB。Repository 的所有方法显式携带 keyword-only owner；文档读取与写入同时限定 owner/KB/document，复合外键阻止父子归属混用。首次访问使用幂等 INSERT，避免 SQLite 并发读锁升级。

`KnowledgeDocumentService` 通过 `KnowledgeTransactions` 获取 Repository Protocol，HTTP 组合层不持有事务。`create_app(..., document_vectors=...)` 可注入 adapter，默认使用 `MilvusVectorStore(config_dir)`；构造不连接，删除在工作线程执行。软删除先提交 `deleted_at`，事务外按 tenant/KB/document 清理向量，最后短事务写入 `vectors_cleaned`。未清理记录继续占用 owner/KB/hash partial unique index；失败返回安全 500，可重试同一 DELETE 或显式 overwrite。清理已完成的 DELETE 幂等成功。overwrite 只有清理成功后才创建新 ID；并发发布只允许一个相同 hash 的记录成功，其余返回 409。没有后台补偿或索引任务。

正文只保存 pypdf/UTF-8 提取后的文本，不把上传原文写入 MinIO。multipart 解析前累计请求流最多 10 MiB + 64 KiB（头部/字段预算），文件内容另按准确 10 MiB 校验；框架可能短暂使用系统临时文件，响应后关闭。`.md` 接受 text/markdown、text/plain，`.pdf` 接受 application/pdf；UTF-8 BOM 去除，加密/损坏/无文本 PDF、空白正文均拒绝，不提供 OCR。

`DocumentChunkingService.chunks` 和 `preview` 共用 `chunk_document_text`，固定字符默认 1200/200，另支持标题层级和空行段落。chunk metadata 的 start/end 为原正文字符偏移（end 不包含），保留 strategy、headings、documentId、knowledgeBaseId、ownerUserId、tenantId；preview 最多 12 段、每段最多 400 个 Unicode 字符，不改变 index status。文档 DTO 不暴露正文。


## 后续资源接入

以下资源全部继承上述边界：chat、knowledge、index jobs、vector、MCP、AIOps、evidence、reports、cases、feedback、audit、background jobs。

HTTP path 先扩展 canonical OpenAPI，再使用 `protected_router()` 和 `current_user` 接入；bearer、401/403 复用见 contracts README。MCP/tool 的执行上下文由后端注入 owner，LLM/tool arguments 不能选择 tenant。任务入队时保存发起用户 owner，执行时显式重建 `OwnerScope`、重新验证父资源归属，进度、结果、重试、取消和清理均使用同一 scope。任务的持久 owner 不因用户登出而丢失；是否继续执行按具体业务 Change 决定，不通过删除持久数据处理登出。

缓存 key、文件/对象路径、事件订阅、审计与向量归属必须含 owner/tenant；禁止用全局 key 或仅资源 ID 复用他人结果。删除、级联和后台清理同样带完整 scope。

新增 Repository 的必需验收：

1. 调用 `tests/scope_contract.py` 的 `assert_owner_parameter_contract`，逐方法覆盖必填 keyword-only owner、空值/类型失败，并断言 session 未调用。
2. 参照 `tests/tenant_probe.py` 与 `test_tenant_repository.py`，用两个 owner 验证列表、读、创建、更新、删除、相同资源 ID、父子 ID 混用、复合外键和真实 SQL owner 条件。探针使用独立 metadata，不能注册为生产表。
3. 参照 `test_tenant_api.py`，以真实本地认证和临时 SQLite 验证缺失/越权 HTTP 响应完全等价、无认证 401、并发上下文、登出保留资源和合法访问成功。
4. 前端受保护 store 注册清理回调，通过带版本隔离的认证客户端请求；登出、401、用户切换清空可见状态并丢弃迟到成功，403 保留有效认证。

## 测试

`tests/migration_helpers.py` 提供临时 JSON 配置与显式 Alembic 命令 helper；`migrated_config` / `database` fixture 使用每个测试独立的 `tmp_path`。禁止引用开发者真实配置或 `var/memory.sqlite3`。测试 fixture 会关闭资源，临时文件由 pytest 管理。

迁移测试在空数据库升级至当前 head 后比较 `Base.metadata`，另用未迁移表探针确认比较器能发现漂移。事务/字段测试的探针表只在测试内创建，不进入生产 metadata。`0001_persistence_foundation` 无领域表；`0002_user_authentication` 增加 `users` 和 `auth_sessions`，测试覆盖重复升级、降级再升级、唯一约束、外键及 token hash 格式。


## 持久后台任务运行时（P09）

`background_jobs.py` 的查询仍以 `None` 表示缺失，HTTP 通过 `require_owned_resource` 映射 403；任务状态变更及事件读取需要父任务存在，内部以 `JobNotFound` 终止事务，HTTP 统一映射同一 403。这一状态机异常不包含资源数据，不能用于全局存在性探测。

调度器 `BackgroundWorker._owners` 是新增的具名基础设施例外：仅从未完成任务发现 owner 标识，不返回 payload/资源内容、不暴露 HTTP endpoint。它只是调度目录；回收、领取、续租、事件、完成、取消和重试始终显式带同一持久 owner。`JobContext.scope` 由持久 owner 重建。新增具体业务 handler 仍须重新校验 resourceType/resourceId 对应的父归属。

0003 的两张表为 `background_jobs`、`background_job_events`；任务与事件及 retryOfJobId 采用 owner/parent 复合外键。队列与租约有索引，状态、attempt、lease 与 sequence 有 CHECK/唯一约束。此模块时间保存为固定 UTC RFC3339 微秒文本（40 字符列），在 SQL 中按同一格式比较，避免驱动 naive datetime 自动适配；不更改其他模块 UTCDateTime 约定。

启动前显式执行 Alembic upgrade head。应用可用 `create_app(config_dir, job_handlers=registry)` 注入按 kind 注册的 handler；默认没有业务 handler，未知类型保持 queued。worker 默认 concurrency=2、lease=30 秒、poll=0.2 秒；FastAPI lifespan 关闭时等待 handler 与 heartbeat 清理后关闭 Database。

handler 接收 `JobContext`，从 `context.job.payload_value()` 获取独立数据，观察 `context.cancelled` 协作退出，并通过 `context.emit` 写持久事件。handler 必须使用可取消、有界的 async I/O，不可阻塞事件循环或吞掉取消后无限运行。timeout/正常关闭取消并等待 handler；进程异常退出则由 lease 到期回收。至少一次执行不保证外部副作用 exactly-once；具体 handler 必须以 job/resource ID 实现幂等。

`replay_events(database, job_id, owner_user_id=..., after_sequence=0)` 重放有序事件快照，关闭迭代器不会取消任务。这里只提供后续 AIOps/SSE 的持久重放基础，没有新增业务 SSE endpoint 或 Last-Event-ID 协议。原始 payload 不记日志，错误仅用固定安全消息；handler 自行挑选可公开事件内容。
