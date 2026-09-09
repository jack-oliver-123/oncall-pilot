## Context

见 proposal.md。P05 已提供 `memory.vector_scope` 的 escaping 和 OwnerScope，P06 embedding 固定 1024 维。当前模板已无 docker 段，故仅补防回归合同，不改写 ignored 本地配置。Python 包只使用 `oncall_pilot`，用户提到的旧 `super_ai.vector_store` 对应本项目 `oncall_pilot.vector_store` 的 import-safety。

## Goals / Non-Goals

**Goals:** 用官方同步 MilvusClient 实现小而明确的 adapter，客户端 factory 作为唯一测试 seam；操作范围在任何配置读取或网络访问之前验证。

**Non-Goals:** 不初始化应用级全局 client，不接入 FastAPI lifespan，不添加 HTTP endpoint、不实现 retrieval tool、不提供 public close、不创建业务表或应用对象存储。

## Decisions

1. Compose 固定用户指定的五个镜像版本，etcd/MinIO/Milvus/Alertmanager 使用 named volumes。端口绑定 loopback，etcd/MinIO 只在容器网络访问；健康检查使用镜像已有工具，Attu 使用 Node HTTP 探测。Alertmanager 路由到无外部动作的本地接收器，不预置未实现 webhook。
2. `MilvusVectorStore(config_dir, client_factory=...)` 构造只保存参数；connect 才读取 merged vectorStore 并构造 client。官方包在 factory 内导入，避免其 import 副作用扩散到应用。同步操作由未来 async 调用方在线程中执行，本 Change 不额外建设 async 抽象。
3. 生产包装层把官方 SDK 不完整类型隔离在单独模块；端口只暴露 adapter 实际消费的方法。initialize 在锁内检查 collection、创建或校验 schema/index、加载，最后标记 ready；失败保持可重试，不 drop/recreate 既有 collection。已有 collection 缺索引可补建，冲突索引/schema 明确拒绝。
4. 数据记录使用不可变入口模型，写入前校验 ID、1024 维有限数值和 metadata 归属。chunkId 使用调用方全局唯一 ID；insert 而非 upsert，归属不接受 payload 覆盖。createdAt 保存 UTC ISO 字符串。标量索引覆盖 documentId、knowledgeBaseId、ownerUserId、tenantId、source、createdAt，metadata/content 不参与粗召回过滤。
5. search/delete 复用 P05 纯过滤器且 owner 必填 keyword-only；授权 KB 来源由上层 scoped Repository 保证。空 KB 在 connect 前短路。返回粗召回 hit 供后续 retrieval 层后过滤，不增加任意 filter 参数。
6. pymilvus 从 ai optional 移至 runtime dependency，以保证标准 uv sync 后显式连接可用；不提前初始化其他 AI 能力。

## Risks / Trade-offs

- [beta 镜像与 SDK/Attu 兼容性] → 保持用户指定版本；结构与 fake 验证不能替代 live，服务不可用时明确记录未运行。
- [已有 collection 漂移] → 失败关闭并提示显式迁移，不隐式删表；索引补建可重复执行。
- [本地同步 I/O] → SDK 每次请求使用有界 timeout；未来 async 集成需卸载阻塞操作。
- [测试隔离] → fake 验证实际过滤行为，真实 smoke 仅使用固定 loopback 和随机独立 collection，不读取开发者配置，不连接生产库。

## Migration Plan

新增资产无需数据库迁移。开发者显式执行 Compose up 与 adapter initialize；停止服务使用 Compose down 保留卷。回退代码不自动删除 Milvus collection/volume。验证通过后同步两个新主规格并归档，WIKI 由同步器生成。

## 事实来源

2026-09-09 查阅：[官方 standalone Compose](https://github.com/milvus-io/milvus/blob/master/deployments/docker/standalone/docker-compose.yml)、[MilvusClient create_index](https://milvus.io/api-reference/pymilvus/v3.0.x/MilvusClient/Management/create_index.md)、[官方 PyMilvus 实现](https://github.com/milvus-io/pymilvus/blob/master/pymilvus/milvus_client/milvus_client.py)。具体接口还需以本地已锁定 SDK 源码和测试核对。
