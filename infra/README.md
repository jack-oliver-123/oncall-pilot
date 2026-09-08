# 基础设施边界

foundation Change 只记录进程归属，不创建 Compose file 或应用容器。

- backend、frontend 和官方 CLS MCP Server 在主机运行。
- 未来 Compose 只允许托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。
- 当前目录不包含应用 Dockerfile、应用 Compose service 或 `project.compose.json`。

改变此边界必须建立新 Change，并同步更新 ADR-0003。
