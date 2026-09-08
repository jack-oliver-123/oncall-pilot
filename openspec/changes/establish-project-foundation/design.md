## 背景

变更动机见 `proposal.md`。当前仓库只有 OpenSpec/WIKI 基础设施、根级 VitePress manifest，以及两个空的根级应用目录；尚无产品 manifest、应用入口、CI workflow 或产品质量命令。现有 `CONTEXT.md` 已将 On-call Pilot 和值班人员确立为稳定词汇，ADR-0001 规定 OpenSpec 是 Change 控制平面。

本 Change 横跨多个 workspace，并刻意在产品能力出现前建立最终工程形态。它必须兼容当前 Windows 开发环境和 Linux CI，同时保证本地凭据及项目专属值不会进入 Git 或浏览器 bundle。

## 目标 / 非目标

**目标：**

- 提供可在主机运行的最小后端、桌面 Web 前端及一份共享 TypeScript contract。
- 让仓库目录、依赖方向、配置投影和质量门禁都可被机械验证。
- 在 manifest 中锁定约定的技术版本线，在 lockfile 中锁定实际解析版本。
- 为非技术值班人员提供诚实、可访问且不虚构产品行为的首屏。
- 在迁移仓库工具测试的同时保持现有 OpenSpec/WIKI 行为不变。

**非目标：**

- 认证、聊天、知识库、AIOps、LLM provider、CLS、MCP、Milvus 应用接入、tenant 实现或其他产品能力。
- 业务数据模型、repository、数据库 revision 或应用侧基础设施 adapter。
- 除手写 foundation 健康响应外的 API 类型生成。
- 应用容器、应用 Compose 服务、生产部署或 Git 历史重写。
- 移动端产品验收；移动端渲染需保持可读，但正式验收目标是桌面 Web。

## 决策

### 1. 使用 npm workspaces 仓库和独立 uv 后端 workspace

最终受跟踪目录如下：

```text
/
├── apps/
│   ├── backend/
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── src/oncall_pilot/
│   │   ├── tests/
│   │   └── README.md
│   └── frontend/
│       ├── src/
│       ├── tests/
│       ├── package.json
│       └── README.md
├── packages/
│   └── api-contracts/
├── config/
├── infra/
├── scripts/
│   └── tests/
├── openspec/
├── docs/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── package.json
└── package-lock.json
```

根 npm workspace 包含 `apps/frontend` 和 `packages/api-contracts`；根 manifest 继续负责 VitePress 与仓库级命令编排。Python 独立放在 `apps/backend`，避免 npm 成为第二套 Python task runner 或依赖管理器。

唯一允许的应用级依赖方向是 `apps/frontend -> packages/api-contracts`。contracts 不依赖任何应用，backend 不依赖 npm workspace，也不导入 frontend 文件。跨应用通信使用 HTTP；共享 JSON 配置属于数据 seam，不是源码依赖。

未采用的方案：

- 全栈 JavaScript 应用与已冻结的 Python/Agent 技术栈冲突。
- 过早拆成多个仓库会增加 contract 和质量基线的原子变更成本。
- 当前 workspace 数量不足以证明引入 monorepo orchestrator 的复杂度是合理的。

### 2. 所有项目命名统一到 On-call Pilot

面向人员的产品和文档名称使用 `On-call Pilot`；仓库及根 npm package 使用 `oncall-pilot`；npm workspaces 使用 `@oncall-pilot/frontend` 和 `@oncall-pilot/api-contracts`；Python distribution 使用 `oncall-pilot-backend`；合法 Python import namespace 使用 `oncall_pilot`。

此前提出的 `super_ai` 已被替代。自动化测试检查 manifests、README 和 Python imports，防止旧命名重新进入项目。

### 3. manifest 锁定技术版本线，lockfile 锁定实际版本

项目支持 Python `>=3.10`，将 Python 3.12 记录为标准本地开发版本，并以 Python 3.10 作为静态语义基线。Node 使用 22 系列，npm 固定为 10.9.7。根 `packageManager` 使用精确版本，lockfile 是实际依赖图的事实源。

后端运行依赖：

- FastAPI、Pydantic v2 和 Uvicorn。
- SQLAlchemy 2 async、aiosqlite 和 Alembic。
- hatchling 作为 PEP 517 build backend，uv 作为唯一 Python 依赖工作流。

后端开发依赖组：

- pytest、pytest-asyncio、Ruff、Pyright，以及用于 ASGI 测试的 httpx。

后端 optional `ai` 依赖组会解析进 `uv.lock`，但默认 runtime sync 不安装：

- 使用 `create_agent` 的 LangChain 1.x、LangGraph、langchain-openai、langchain-mcp-adapters 和 MCP。
- pymilvus 3、rank-bm25、pypdf、langchain-text-splitters 和 httpx。

前端运行依赖：

- Vue 3.5、Pinia 3、Vue Router 4、marked、DOMPurify 和 lucide-vue-next。

前端开发依赖：

- Vite 6、TypeScript 5.6、Vitest 2、`@vitejs/plugin-vue`、vue-tsc、Vue Test Utils 和 jsdom。
- ESLint 9 flat config、typescript-eslint、eslint-plugin-vue 和 Prettier 3。

根工具固定 `@fission-ai/openspec` 1.7.0，因为当前 artifacts 和 skills 都基于 1.7.0 生成。升级 OpenSpec，或让 Vite、TypeScript、Vitest 跨出已冻结版本线，都必须建立独立兼容性 Change。

manifest 使用有上下界的兼容版本线；`package-lock.json` 和 `uv.lock` 固定具体依赖图。实现阶段只有在 npm manifests 完成后才运行 `npm install`，只有在 `pyproject.toml` 完成后才运行 `uv sync`。CI 使用 `npm ci` 和 `uv sync --frozen`。

未采用的方案：

- 在每个 manifest 中精确固定所有版本会重复 lockfile 职责，也无法表达兼容性意图。
- 默认安装 AI 依赖会让一个禁止初始化 AI 的骨架承担额外环境和启动成本。
- 只在文档中列出 AI package 无法验证它们能否共同解析。

### 4. 后端 package 保持小而且 import-safe

初始 package 只包含拥有真实行为的 module：

```text
src/oncall_pilot/
├── __init__.py
├── __main__.py
├── app.py
└── project_config.py
```

`project_config.py` 在单一 interface 后负责 JSON 加载与深合并；`app.py` 负责 `create_app(config_dir: Path | None = None)`；`__main__.py` 接收 `--config-dir`、`--host`、`--port` 等主机进程参数，再把已创建的 app 交给 Uvicorn。根 `backend:dev` 命令显式传入仓库 `config` 目录。

module import 只做声明，不读取配置、不执行应用级文件 I/O、不创建 engine、不构造 network client，也不连接依赖。Python 导入机制自身读取 module 文件不属于本规则。测试在监控项目配置、应用文件 I/O、socket 和数据库入口时导入所有可发现的 `oncall_pilot` module。

app factory 在被调用时读取配置；必需配置缺失或无效时，在开始服务前失败。`/health` 只表示进程存活，固定返回 HTTP 200 和 `{"status":"ok"}`，不探测任何依赖。

本 Change 刻意不创建空的 `domain`、`application`、`infrastructure`、`agent`、`auth` 等 package。只有当未来 Change 出现真实 interface，且至少存在生产和测试 adapter 时，才建立对应 seam，避免形成 pass-through module。

未采用的方案：

- module-level 全局 app/config 会让 import 依赖环境状态，并让测试依赖开发者本机配置。
- 完整 clean architecture 空目录会在产品行为出现前冻结假想 seam。

### 5. 初始化 Alembic，但不创建 persistence module

`alembic.ini` 和 async `migrations/env.py` 用于确认迁移工具链。当前不创建 revision、model metadata、session module 或 repository。只有显式运行 Alembic 命令时，才加载本地合并配置并创建 async engine；安装、import、lint 和普通测试收集都不得创建 SQLite 文件。

项目模板包含指向 `apps/backend/var/oncall-pilot.db` 的本地 `sqlite+aiosqlite` URL，`apps/backend/var` 被忽略。未来 persistence Change 将同时引入 typed 数据库配置、engine/session 所有权和第一份 migration。

未采用 unused engine/session factory，因为它目前没有 caller，也没有可替换 adapter，只会形成浅 interface。

### 6. 使用一套通用 JSON 深合并语义和显式注入

受跟踪模板为：

```json
// config/project.template.json（示意；实际 JSON 不包含注释）
{
  "frontend": {
    "title": "On-call Pilot",
    "apiBaseUrl": "http://127.0.0.1:8000",
    "analytics": { "publicKey": "" }
  },
  "database": {
    "url": "sqlite+aiosqlite:///apps/backend/var/oncall-pilot.db"
  }
}
```

`config/user.project.template.json` 固定为 `{}`，复制后不会清空项目默认值。模板中任何名为 key、secret 或 password 的字段值必须为空。foundation 不预声明 LLM、CLS、MCP 和 MinIO section；它们各自的 Change 增加字段与 typed validation，但不改变通用 loader。

运行时必须存在 `project.json`，`user.project.json` 可选；后者递归覆盖前者。对象按 key 深合并，数组、标量和 `null` 整体替换。JSON 无效、根节点不是对象或必需项目文件缺失时，错误必须指出对应文件并快速失败；缺失用户配置等价于 `{}`。

根命令向应用 interface 显式传入配置目录。测试始终创建并注入临时目录。项目配置值不从 OS 环境变量读取；host、port、config-dir 是进程参数，不属于项目配置。

SQLite URL 等相对文件值基于显式配置目录推导出的仓库根解析，而不是基于偶然的 process working directory。这保证根命令、Alembic 和测试在 Windows/Linux 上一致。

未采用的方案：

- 环境变量会形成第二份项目配置事实源，嵌套配置也难以检查。
- 测试期间改写 ignored 本机文件会破坏开发者设置，也不支持并发测试。

### 7. 通过 Vite virtual module 投影浏览器配置

`vite.config.ts` 按同一深合并语义读取两份本地 JSON，然后只投影：

- `frontend.title`
- `frontend.apiBaseUrl`
- `frontend.analytics.publicKey`

一个小型 Vite plugin 把冻结且 typed 的结果暴露为 `virtual:public-config`，`src/config.ts` 是唯一应用消费入口。应用 module 不直接 import 任一完整 JSON。virtual module 的 interface 由类型声明定义。

投影使用 allowlist，而不是 denylist：任何新增字段默认私有，只有被明确加入公开投影才可进入浏览器。Vitest integration test 创建临时 JSON，在 LLM、CLS、MCP、MinIO 形状字段中放入唯一 sentinel，使用临时配置目录调用 Vite programmatic production build，再按 bytes/text 扫描全部输出文件。sentinel 必须完全不存在；测试不使用环境变量，也不读取或覆盖开发者文件。

未采用全局 `define` 常量，因为它会让公开面更难发现，也更容易绕过唯一 typed interface。

本地 JSON 与浏览器公开投影边界已记录为 accepted ADR-0002，后续配置工作不得静默增加第二个配置来源或扩大浏览器暴露范围。

### 8. API contract 保持最小

`packages/api-contracts` 只通过一个 typed entrypoint 暴露 foundation `HealthResponse` 类型，并提供独立 typecheck/test scripts。contracts 测试进行类型断言并检查代表值，后端健康测试断言同一 wire shape。

本 Change 不把它声明为永久的跨语言生成方案。第一个真实业务 interface 出现前，必须由独立 Change 决定 FastAPI OpenAPI 是否成为生成 TypeScript 类型的事实源。

取舍：手写健康类型可能漂移，但它只有一个 literal response，并由两侧测试保护，因此在 foundation 阶段可接受。

### 9. 构建安静、面向非技术值班人员的桌面工作台

页面的唯一工作是标识 On-call Pilot、建立值班工作台语境，并如实说明业务操作尚未开放。页面不包含假指标、无效按钮、假路由、功能卡片或 API request。

视觉 token：

| 角色 | 值 | 用途 |
| --- | --- | --- |
| 画布 | `#F5F7F6` | 安静的页面背景 |
| 表面 | `#FFFFFF` | header 和文字表面 |
| 墨色 | `#17211D` | 主要文字 |
| 信号色 | `#19704F` | 品牌标记、focus 和交接线 |
| 提醒色 | `#C77D12` | 为未来 warning 状态保留 |
| 严重色 | `#B93B36` | 为未来 critical 状态保留 |

Latin 品牌字使用克制的 `Bahnschrift SemiCondensed`，fallback 为 `Arial Narrow`。中文正文使用 `Microsoft YaHei UI`、`PingFang SC` 和系统 sans-serif fallback。utility text 可使用 `Cascadia Mono` 和 monospace fallback。页面不发起 remote font request。

唯一 signature element 是从 Lucide `RadioTower` 品牌标记对齐到工作区标题的窄交接线，用来表达班次之间的连续性，而不是无意义装饰。其他布局保持无框且克制：

```text
┌──────────────────────────────────────────────┐
│  [RadioTower]  On-call Pilot                 │
├──────┬───────────────────────────────────────┤
│  │   │  值班工作台                           │
│  │   │                                       │
│  │   │  工作台正在准备中                     │
│  │   │  当前版本暂未开放业务操作。           │
│  │   │                                       │
└──────┴───────────────────────────────────────┘
```

页面使用单一 document scroll context、稳定 responsive 约束、语义化 header/main、可见 keyboard focus 和足够对比度。若使用一次 entrance transition，持续时间必须短，并在 `prefers-reduced-motion` 下禁用。桌面浏览器验收覆盖典型 Windows 尺寸，确认无重叠和第二滚动条；移动视口只检查 fallback 可读性，不作为正式产品验收目标。

未采用的方案：

- marketing hero 不适合需要反复使用的工作型产品。
- sidebar navigation 和 status card 会错误暗示已有路由和数据。
- dark navy、purple gradient、beige editorial 样式和装饰动画都是与值班人员无关的通用默认答案。

### 10. 提供唯一根命令面

根 manifest 保留现有 `docs:*` 命令，并增加：

```text
backend:dev
backend:lint
backend:typecheck
backend:test
frontend:dev
frontend:lint
frontend:format:check
frontend:typecheck
frontend:test
frontend:build
contracts:typecheck
contracts:test
wiki:test
openspec:validate
check
```

各 workspace script 负责直接调用自己的工具；根 script 通过 npm workspace selector 或 uv backend directory option 委派。`check` 顺序执行 OpenSpec strict validation、backend lint/typecheck/test、contracts typecheck/test、frontend lint/format/typecheck/test/build、WIKI unittest discovery 和 VitePress build。public-config sentinel build 属于 frontend tests。`git diff --check` 保持为独立 CI/最终验收步骤，因为它检查当前 Git patch，而不是某个 workspace。

在 `apps/backend` 中仍可直接运行：

```text
uv run ruff check .
uv run pyright
uv run pytest
```

Ruff 使用 line length 100、`target-version = "py310"` 和 B/E/F/I/UP；Pyright 使用 strict；pytest 使用 `asyncio_mode = "auto"`。TypeScript 使用 strict，并启用 `exactOptionalPropertyTypes`、`noUncheckedIndexedAccess`、`isolatedModules`、ES2022 target 和 Bundler module resolution。

### 11. 在 Linux 和 Windows CI 强制执行质量基线

GitHub Actions 包含三类逻辑 job：

1. Linux/Python 3.12 完整门禁：冻结 npm/Python 安装、根 `check`、public-config sentinel scan 和 `git diff --check`。
2. Linux/Python 3.10 后端兼容：冻结 backend sync 和 backend lint/typecheck/test。
3. Windows/Python 3.12 smoke：在 Node 22 上执行 npm/Python install、backend tests、contracts typecheck/test 和 frontend typecheck/test/build。

代码库目前只有骨架，CI 暂不设置 coverage 百分比；coverage 输出进入 ignore，为未来使用保留。仓库不引入 Git hook，CI 是 merge quality gate。

### 12. 让 AGENTS.md 成为唯一代理指南入口

根 `AGENTS.md` 成为 authoritative project guide，内联会改变 Agent 行为的高影响 invariant，并通过条件式 pointer 指向 OpenSpec/WIKI 详细流程。`CLAUDE.md` 改为指向 `AGENTS.md` 的短 compatibility pointer；应用目录不复制根规则。

项目指南覆盖：

- 最终目录和允许的依赖方向；
- canonical install、start 和 quality commands；
- `oncall_pilot` imports、import safety 和 dependency injection；
- 本地 JSON 配置、credential handling 和禁止直接连接生产数据库；
- 未来 tenant-scoped interface 必须显式提供 tenant identity；
- unit test 可使用 fake adapter，但未来 MCP 验收必须连接官方真实 MCP；
- 项目维护的文档、OpenSpec artifacts、ADRs、README、Issue/PR 文本和面向用户文案统一使用简体中文；
- 代码标识、命令、路径、文件名、配置键、标准、协议、框架、库、产品专名、OpenSpec 结构关键字、日志/错误原文和必要引用可保留原文，并在需要处提供中文说明；
- 桌面 frontend/browser acceptance、one-scroll rule，以及保存在仓库外的 UI PR screenshots；
- feature 使用 `feat/`、defect 使用 `fix/`，branch 不得以 `codex` 开头；
- Conventional Commits，以及外部 support-agent 仓库禁止自动 merge 的既有规则。

README 只描述已实现骨架及其命令，明确区分已锁定的未来依赖和当前可用产品行为。详细技术版本保留在 manifests 和本 design 中，不复制到每个 README。生成文件、lockfile 和第三方/上游原文不做机械翻译，以免破坏可执行内容或标准术语；所有项目自行编写的叙述性内容坚持中文优先。

### 13. 本 Change 中 Compose 只记录边界

`infra/README.md` 记录未来 Compose 可托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。backend、frontend 和官方 CLS MCP Server 作为主机进程运行。本 Change 不创建 Compose file、Dockerfile、`project.compose.json`、deployment environment 或 remote connection。

该分离策略已记录为 ADR-0003，因为它是持久且不明显的约束，未来维护者很可能误以为把应用容器化是在“修正”项目。

### 14. 通过可观察 interface 测试

- `scripts/tests` 保存现有 WIKI sync unittest 及新的仓库结构/import/script/ignore tests，仓库工具测试不归入 backend tests。
- backend pytest 覆盖配置合并/错误、app factory、`/health`、允许的 imports，以及阻断外部副作用后的 import safety。
- contracts Vitest 覆盖 typed entrypoint 和代表性 `HealthResponse`。
- frontend Vitest 覆盖 public projection、无效配置、应用渲染和 sentinel production build。
- browser acceptance 检查桌面 framing、文案、keyboard focus、reduced motion、console error、非空 pixels 和 single-scroll invariant；screenshot 只作为仓库外的 UI PR evidence。

测试只使用临时配置。实现阶段可为当前 workspace 从项目模板复制 ignored 的本地 `project.json`，但必须先验证 ignore 命中，并且永远不得 stage。

## 风险 / 取舍

- [已锁定的旧前端版本线未来失去支持] -> 现在固定实际解析版本，Vite/TypeScript/Vitest 升级必须单独建立兼容性 Change。
- [未使用的未来依赖增大 lockfile 和 resolver 时间] -> AI packages 保持 optional 且不 import；前端 libraries 仅因技术栈已明确冻结而保留。
- [手写健康 contract 可能漂移] -> 只保留一个 literal response、两侧分别测试，并在首个业务 contract 前决定 OpenAPI generation。
- [JSON-only 项目配置降低通用 cloud deployment 灵活性] -> 当前目标是 host-run local files；process arguments 与项目配置分离，只有新 Change 才能重审。
- [Python 与 Vite allowlist 实现可能漂移] -> 各 runtime 保留自己的小 adapter，但共享深合并 fixture 和 security property tests。
- [跨平台 CI 增加运行时间] -> Linux 只运行一次全套，再增加 minimum-Python backend job 和聚焦的 Windows smoke，避免完整 Cartesian matrix。
- [独特视觉可能暗示不存在的产品能力] -> signature 只放在品牌和布局，不展示数据、导航或操作。

## 迁移计划

1. 创建最终应用/workspace 目录和 manifests，再运行根 `npm install` 与 backend `uv sync` 生成精确 lockfile。
2. 增加配置模板和 ignore 规则；只为当前 workspace build 验证复制 ignored 本机项目配置。
3. 建立 contracts、backend、migration environment、frontend skeleton 及各自 focused tests。
4. 迁移根 frontend/backend guidance 和 WIKI tests，再删除旧空目录。
5. 更新项目指南、README、OpenSpec context 和 CI，并验证实现与两份 accepted ADR 一致。
6. 运行全部本地 gate、browser acceptance、Windows/Linux CI-equivalent checks 和 WIKI sync，再请求 implementation verification。

回滚使用普通 revert 撤销受跟踪 foundation 文件；ignored 本机配置和 runtime data 保持不变。不使用 filter-repo、force push 或历史重写。
