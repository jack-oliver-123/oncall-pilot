## Purpose

为 On-call Pilot 提供可重复启动的本地基础设施，并明确基础设施容器与主机应用的责任边界，使开发人员能够验证服务健康、保留持久数据并避免重新引入早期全栈容器方案。

## ADDED Requirements

### Requirement: 五服务本地运行边界

基础设施 SHALL 只包含 alertmanager、etcd、minio、milvus、attu；backend、frontend 和官方 CLS MCP Server MUST 在主机运行。MinIO MUST 仅作为 Milvus 依赖，不能作为应用文档对象存储。

#### Scenario: 渲染 Compose
- **WHEN** 执行 docker compose config
- **THEN** 只得到五个允许服务，standalone Milvus 依赖健康的 etcd/MinIO，Attu 依赖健康的 Milvus，持久数据使用 named volumes，每个服务有 healthcheck，Alertmanager 只读挂载配置并暴露本机 9093

#### Scenario: 阻止废资产回归
- **WHEN** 检查仓库应用和基础设施资产
- **THEN** 不存在应用 Dockerfile、project.compose.json、应用镜像、Compose env_file 或变量插值，也没有日志上传和 SOP seed 服务

### Requirement: 镜像版本单一事实源

Compose SHALL 固定 etcd v3.5.18、MinIO RELEASE.2024-12-18T13-15-44Z、Milvus v3.0-beta、Attu v2.5.12、Alertmanager v0.28.1，并作为镜像版本唯一配置来源；项目配置模板 MUST 不包含 docker 版本遗留段。

#### Scenario: 配置版本无冲突
- **WHEN** 读取 Compose 和配置模板
- **THEN** 镜像版本来自 Compose，模板不含 docker.appImageTag、clsMcpServerVersion 或 milvusImage
