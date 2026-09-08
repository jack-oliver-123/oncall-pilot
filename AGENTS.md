# On-call Pilot 项目指南

本文件是仓库代理规则的唯一事实源。开始任务先检查 active OpenSpec Change、工作树状态和本文件；`CLAUDE.md` 仅作为兼容入口指向这里。

## 语言与文档

- 项目维护的文档、OpenSpec artifact、ADR、README、Issue/PR 文本和面向用户的文案统一使用简体中文。
- 代码标识、命令、路径、文件名、配置键、标准、协议、框架、库、产品专名、OpenSpec 结构关键字、日志与错误原文及必要引用保留原文。
- 保留原文时在需要处提供中文说明，不得为了全中文而改写可执行内容或改变技术词义。
- 生成文件、lockfile 以及第三方或上游原文不做机械翻译。

## OpenSpec 门禁

- OpenSpec 是 Change 控制平面；范围、需求、设计、任务和验证状态以 active Change artifacts 为准。
- 涉及行为、interface、跨文件或设计取舍的工作必须建立 Change。范围冻结、实现授权和验证后归档都需要用户对当前快照明确确认。
- 开始前运行 `openspec list --json`；选定 Change 后运行 `openspec status --change <id> --json` 和对应 instructions。
- artifact、规格和 Change 文档使用简体中文；`ADDED Requirements`、`Requirement`、`Scenario`、`WHEN`、`THEN` 等 schema 结构词可保留原文。
- 完整组合规则见 `docs/agents/combined-workflow.md`，领域词汇规则见 `docs/agents/domain.md`，WIKI 同步规则见 `.agents/skills/wiki-sync/SKILL.md`。

## 技术栈

- 后端：Python >=3.10、FastAPI、Pydantic v2、Uvicorn、uv、hatchling、SQLAlchemy 2 async、aiosqlite、Alembic。
- 后端质量：pytest、pytest-asyncio、Ruff、strict Pyright；pytest `asyncio_mode=auto`；Ruff line length 100、target py310、规则 B/E/F/I/UP。
- Agent/AI：LangChain 1.x `create_agent`、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters、httpx。未有对应 Change 时只锁依赖，不实现或初始化能力。
- 前端：Vue 3.5、Vite 6、TypeScript 5.6 strict、Pinia 3、Vue Router 4、Vitest 2、marked、DOMPurify、lucide-vue-next、ESLint 9、Prettier 3。
- 仓库：npm workspaces、Node 22、npm 10.9.7、OpenSpec 1.7.0 spec-driven、VitePress、Conventional Commits。

## 目录与依赖方向

```text
apps/backend
apps/frontend
packages/api-contracts
config
infra
scripts
openspec
docs
```

- 唯一应用级 workspace 依赖方向是 `apps/frontend -> packages/api-contracts`。
- backend 不依赖 npm workspace；contracts 不依赖应用；前后端不通过相对路径导入彼此源码，只通过 HTTP contract 通信。
- repository tooling tests 放在 `scripts/tests`，backend tests 放在 `apps/backend/tests`，frontend/contracts tests 放在各自 workspace。
- 不预建没有真实 interface 的空业务 module；出现生产和测试 adapter 后再建立 seam。

## 常用命令

```text
npm install
uv sync --directory apps/backend
npm run backend:dev
npm run backend:lint
npm run backend:typecheck
npm run backend:test
npm run contracts:typecheck
npm run contracts:test
npm run frontend:dev
npm run frontend:lint
npm run frontend:format:check
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
npm run docs:build
npm run check
openspec validate --all --strict
```

CI 使用 `npm ci` 和 `uv sync --frozen`。失败、未运行、provider failure 和真实验收必须分别报告，不得把缺失证据写成通过。

## Python、import 与依赖注入

- Python package 使用 src layout 和 `oncall_pilot` namespace；只允许 `from oncall_pilot...`，禁止 `from src.oncall_pilot...` 或 `super_ai`。
- module import 只做声明，不读取项目配置、不执行应用级文件 I/O，也不连接 SQLite、Milvus、LLM 或 MCP。
- app factory、配置目录、外部 client 和未来 tenant context 通过参数显式注入；禁止在 module scope 创建运行时依赖。
- `/health` 只表示进程存活，不探测数据库或外部依赖。

## 配置、凭据与 tenant

- 项目配置只来自本地 `config/project.json` 与可选 `config/user.project.json` 深合并结果，不从 OS 环境变量读取项目值。
- 只提交 `config/project.template.json` 和 `config/user.project.template.json`；本地配置、`.env*`、数据库、日志和凭据始终 ignored。
- 测试使用临时配置目录，不读取、改写或暂存开发者真实配置。
- 浏览器只允许接收 `frontend.title`、`frontend.apiBaseUrl` 和明确 public 的 analytics key；秘密字段默认不公开。
- Agent 不直接连接生产数据库。未来 tenant-scoped interface 必须显式接收 tenant ID，禁止默认 tenant、全局 tenant 和跨 tenant 查询。

## 资源归属边界

- chat、knowledge、index jobs、vector、MCP、AIOps、evidence、reports、cases、feedback、audit、background jobs 的受保护访问统一从已验证 `CurrentUser` 派生 `OwnerScope`；本地 `tenant_id == user_id`。
- 所有受保护 Repository 方法必须显式接收无默认值的 keyword-only `owner_user_id`，空 scope 在 I/O 前失败；SQL 同时限定 owner、资源 ID 和父子关系。禁止先按资源 ID 全局查询，再在 service 层检查 owner。
- 受保护父资源不存在或越权统一 `AUTH_FORBIDDEN` 403，不披露存在性或资源细节；子资源 ID 不能绕过 owner/父关系。登出仅撤销当前认证并清客户端可见状态，保留持久数据。
- 新增 Repository、受保护 path、向量或后台任务时，先读取 [持久化架构中的归属接入约定](apps/backend/persistence.md#强制归属与租户上下文)，复用参数失败及双用户合同测试。向量保留 `tenantId`/`ownerUserId`，搜索只用 tenant 与授权 KB，空 KB 在连接前短路，文档删除必须带 tenant、KB、document 三个维度。

## MCP 与基础设施

- unit test 可使用 fake adapter；声明 MCP 功能验收通过时，必须额外连接主机上的官方真实 MCP Server，并把 mock、local 和 live evidence 分开报告。
- backend、frontend 和官方 CLS MCP Server 在主机运行。未来 Compose 只托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。
- 不创建应用 Dockerfile、应用 Compose service 或 `project.compose.json`，除非新 Change 明确修改该 ADR。

## 前端验收

- 面向非技术值班人员使用简体中文和可识别的工作语言，不暴露实现术语，不用假数据、死按钮或未实现导航伪装功能。
- 页面最多只有一个滚动容器；桌面和移动视口都不得出现内容重叠、裁切、横向溢出或不可读文本。
- 检查 keyboard focus、颜色对比、reduced motion、loading/error/empty state，以及浏览器 console。
- 修改前端 UI 的 PR 必须提供真实浏览器 E2E 截图；截图和临时 QA artifact 保存在仓库外。

## Git 与外部操作

- 新功能 branch 使用 `feat/`，缺陷修复使用 `fix/`；branch 不得以 `codex` 开头。
- commit 使用 Conventional Commits。提交、推送、PR、merge、release、生产操作和归档分别需要明确授权。
- 保留用户已有 tracked/untracked 文件，不擅自 clean、reset、stash 或覆盖。
- 禁止自动合并 `https://github.com/HaoYan-A/support-agent`。
- 不为从零项目设计 filter-repo、force push 或历史重写步骤。
