## Why

P01、P05、P06 已分别提供主机应用边界、归属合同和 1024 维 embedding；当前仍缺少可运行的基础设施及真正消费租户过滤合同的 Milvus adapter。P07 将最终本地优先边界落地，使后续知识库接入有可验证的存储基础。

## What Changes

- 新增只含 alertmanager、etcd、minio、milvus、attu 的 Compose，版本仅在 Compose 定义，提供持久卷、健康检查及只读 Alertmanager 配置。
- 新增 `oncall_pilot.vector_store`：官方 pymilvus client、惰性连接、显式初始化与健康探测、1024 维 schema/index、tenant-safe insert/search/delete-document，以及可注入 fake client。
- 复用 P05 的 OwnerScope、JSON escaping 与授权 KB 过滤；document/metadata 条件保留在 retrieval 层后过滤。
- 确认配置模板不再含未消费的 docker.appImageTag/clsMcpServerVersion/milvusImage，添加防回归验证；连接配置只读取 merged vectorStore。
- 增加基础设施白名单/废资产黑名单、生命周期、跨用户和 import-safety 验证及本地操作文档。

## Capabilities

### New Capabilities

- `local-infrastructure`: 最终五服务 Compose 与主机应用运行边界。
- `milvus-vector-store`: 显式生命周期、固定 schema/index、结构化归属约束的向量存储。

### Modified Capabilities

无。沿用 project-configuration 与 tenant-isolation 现有合同。

## Impact

影响 infra、backend vector adapter/依赖/测试、repository tooling tests、持久化文档、OpenSpec 与 WIKI；无 HTTP/SSE 或前端 UI 改动。不会接入知识库业务、对象文档存储、日志上传、SOP seed 或应用容器；不提供旧 super_ai namespace 或 adapter public close API。用户已授权创建 feat 分支、实现并在验证通过后同步 specs 与归档；提交、推送和 PR 不在本次授权内。
