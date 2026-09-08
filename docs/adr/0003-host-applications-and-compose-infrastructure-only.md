# ADR-0003：应用运行在主机，Compose 只托管基础设施

- 状态：已接受
- 日期：2026-08-28

On-call Pilot 的后端、前端和官方 CLS MCP Server 作为主机进程运行；未来 Compose 只托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。本项目因此不为应用创建 Dockerfile、Compose 服务或 `project.compose.json`。相比把所有进程容器化，这一选择减少了本地开发与真实 MCP 调试的边界错位，但要求主机工具链和跨平台 CI 明确验证运行兼容性。
