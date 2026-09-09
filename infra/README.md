# 本地基础设施

backend、frontend 和官方 CLS MCP Server 在主机运行。`compose.yaml` 只托管 Alertmanager、etcd、MinIO、Milvus standalone 和 Attu；镜像版本仅由该文件维护。MinIO 是 Milvus 的内部依赖，不是应用文档对象存储，不向主机发布端口。

从仓库根目录执行：

```sh
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml up -d --wait --wait-timeout 180
docker compose -f infra/compose.yaml ps
```

主机连接地址：Milvus `http://127.0.0.1:19530`，Milvus 健康探测 `http://127.0.0.1:9091/healthz`，Attu `http://127.0.0.1:3000`，Alertmanager `http://127.0.0.1:9093`。这些端口只绑定 loopback。Attu 在容器内连接 `milvus:19530`。etcd 与 MinIO 仅由 Compose 内部网络访问。

MinIO 使用本地开发默认账号，与 Milvus 默认配置一致；该 Compose 仅用于本机开发。应用配置来自 ignored `config/project.json` 和 `config/user.project.json`，不使用 env_file 或环境变量替换。`vectorStore` 的 uri、database、collection、token 见项目模板；镜像字段不应复制进 JSON。Alertmanager 使用只读配置和本地无外部通知接收器，后续告警功能另行接入。

etcd、MinIO、Milvus、Alertmanager 各有持久卷；Attu 无独立持久数据。停止时保留数据：

```sh
docker compose -f infra/compose.yaml down
```

`down -v` 会删除数据，不作为日常停止命令。应用 `/health` 仍只表示进程存活；基础设施健康分别通过 Compose healthcheck 与 adapter 的显式 `health()` 检查。

## 向量操作

标准 `uv sync --directory apps/backend` 已安装官方 pymilvus。`MilvusVectorStore(config_dir)` 只保存参数，`connect()` 才加载 merged vectorStore 并连接；`initialize()` 建立或校验 collection/index 并加载。合法的 insert/search/delete 首次调用会 initialize。重复 initialize 在同一实例内幂等，新的实例也会校验并复用既有 collection；失败可重试。已有不兼容 schema/index 会抛出 `IncompatibleCollection`，不会自动重建或丢弃数据。

完整调用示例和归属约束见 [持久化边界](../apps/backend/persistence.md#milvus-adapter)。同步 SDK 不能直接阻塞异步事件循环；未来 async 组合层应在线程中调用。adapter 没有 public close API，客户端资源由官方 SDK 管理。

## 验证层级

```sh
python -m unittest discover -s scripts/tests -p test_local_infrastructure.py
uv --directory apps/backend run pytest tests/test_vector_store.py tests/test_vector_client.py tests/test_import_safety.py
uv --directory apps/backend run python ../../scripts/milvus_smoke.py
```

前两条分别验证 Compose 结构与 fake/真实 SDK builder 合同，不代表真实 Milvus 验收。最后一条只检查本机固定端口：不可用时输出 `SKIP`；可用时使用临时 JSON 与随机独立 collection，执行健康、两次初始化、双用户写入/搜索/删除隔离，最后仅删除本次创建的测试 collection。不会读取开发者配置或访问生产数据库。`SKIP` 必须记为未运行；服务可用但操作失败则以非零退出，不能记为通过。
