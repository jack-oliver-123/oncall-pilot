## Why

On-call Pilot 目前只有 OpenSpec 与 WIKI 基础设施，产品前后端尚无可运行入口、确定技术栈或统一质量门禁。首个产品工程基座需要先建立可复现、安全且可验证的工程契约，避免后续认证、聊天、知识库、AIOps 和 MCP 等能力各自引入不兼容的目录、配置与依赖边界。

## What Changes

- 建立 npm workspaces monorepo，形成 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config`、`infra`、`scripts`、`openspec` 和 `docs` 的最终顶层骨架。
- **BREAKING**：移除旧的根级 `backend`、`frontend` 空目录；Python 包统一使用 `oncall_pilot`，项目与产品统一使用 On-call Pilot，不再使用 `super_ai`。
- 建立 Python/FastAPI 后端、Vue/Vite 前端和 TypeScript API contracts 的最小可运行、可测试骨架，并锁定已确认的运行时、依赖与工具版本线。
- 建立本地 JSON 配置深合并和浏览器 public allowlist，提交脱敏模板，阻止秘密字段进入前端 bundle。
- 建立 import-safety、目录、包导入、脚本、ignore、public-config 和构建产物秘密扫描等自动化验证。
- 建立 Windows/Linux CI、统一根命令、中文项目指南与 workspace README，并将 `AGENTS.md` 设为代理规则唯一事实源。
- 只记录未来 Compose 与主机进程的基础设施边界，不创建应用容器或任何产品功能。

## Capabilities

### New Capabilities

- `workspace-foundation`: 定义最终目录、npm workspace、共享 contracts、项目命名、依赖方向、基础设施边界和仓库级命令入口。
- `backend-foundation`: 定义 Python/FastAPI src-layout 包、app factory、启动 interface、`/health`、import safety 和后端质量工具链。
- `frontend-foundation`: 定义面向值班人员的 Vue 桌面 Web 壳、严格 TypeScript、单滚动容器、可访问性和前端质量工具链。
- `project-configuration`: 定义本地 JSON 深合并、模板安全、显式测试注入、浏览器 public allowlist 和秘密扫描。
- `engineering-quality`: 定义跨 workspace 验证命令、Windows/Linux CI、锁文件可复现性和归档前质量门禁。

### Modified Capabilities

无。现有 `combined-agent-workflow` 与 `wiki-sync` 的可观察要求保持不变。

## Impact

- 影响根 package manifest、lockfile、ignore、项目指南、README、OpenSpec 配置、WIKI 工具测试位置和 CI。
- 新增后端 Python workspace、前端 Vue workspace、TypeScript contracts workspace、配置模板、基础设施说明和对应测试。
- 新增并锁定 Python、AI optional group、Vue/TypeScript、质量工具与 OpenSpec CLI 依赖；首次实现需要执行根 `npm install` 与后端 `uv sync`。
- 不包含认证、聊天、知识库、AIOps、LLM provider、CLS、MCP、Milvus 业务接入、数据库模型或其他产品能力。
