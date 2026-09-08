## 1. 建立 workspace 与锁文件

- [x] 1.1 创建 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config` 和 `infra` 骨架，更新根 `package.json` 为 npm workspaces，并锁定 Node 22、npm 10.9.7 与 OpenSpec 1.7.0。
- [x] 1.2 创建后端 `pyproject.toml`、Python 3.12 开发版本文件、hatchling 构建配置、默认/开发/AI optional 依赖组，以及前端和 contracts manifests；确认版本约束覆盖 design 中的全部技术栈。
- [x] 1.3 在 manifests 完成后立即从根运行 `npm install`，再在后端运行 `uv sync`；提交更新后的 `package-lock.json` 和 `apps/backend/uv.lock`，并记录任何解析冲突而不静默更换技术线。
- [x] 1.4 增加仓库结构、workspace 依赖方向、包命名、根脚本存在性和禁止 `super_ai`/跨应用源码导入的自动化测试。

## 2. 建立安全配置基线

- [x] 2.1 扩展根 `.gitignore`，覆盖本地 JSON、`.env*`、`.idea`、`.venv`、`node_modules`、dist、coverage、缓存、VitePress 产物、backend var、SQLite 和日志文件，并用测试验证关键模式。
- [x] 2.2 创建 `config/project.template.json` 和空对象 `config/user.project.template.json`；验证所有 key/secret/password 模板值为空，且未来产品配置字段未被预声明。
- [x] 2.3 实现后端通用 JSON 加载与递归深合并 interface，覆盖必需/可选文件、对象递归、非对象替换、相对路径基于配置目录解析、错误消息和显式临时目录注入测试。
- [x] 2.4 从模板为当前 workspace 创建 ignored 的本机 `project.json`，先验证 ignore 命中且保持未跟踪；所有自动化测试继续使用临时配置，不读取或改写该文件。

## 3. 建立 API contracts workspace

- [x] 3.1 创建 `@oncall-pilot/api-contracts` typed entrypoint、严格 TypeScript 配置和最小 `HealthResponse` 类型，不引入前后端应用依赖。
- [x] 3.2 增加 contracts typecheck/test scripts 与类型测试，并从根 `contracts:typecheck`、`contracts:test` 验证包入口。

## 4. 建立后端 foundation

- [x] 4.1 创建 import-safe 的 `oncall_pilot` src-layout 包、`create_app` factory、主机 CLI 参数入口和 `/health`，只使用 `from oncall_pilot...` 导入。
- [x] 4.2 创建 async Alembic 空环境；确保只有显式迁移命令读取数据库配置和创建 engine，且不存在业务模型、revision、session module 或自动 SQLite 文件。
- [x] 4.3 配置 pytest `asyncio_mode=auto`、Ruff 100/py310/B-E-F-I-UP 和 strict Pyright，提供后端 dev/lint/typecheck/test 根命令。
- [x] 4.4 增加 app factory、配置失败、健康响应、禁止导入形式和全包 import-safety 测试；监控配置加载、应用级文件 I/O、socket、SQLite、Milvus、LLM 与 MCP 初始化后导入全部 module。
- [x] 4.5 从后端 workspace 运行 `uv run ruff check .`、`uv run pyright` 和 `uv run pytest`，确认安装、检查和测试均不创建 SQLite 或连接外部依赖。

## 5. 建立前端配置投影与质量工具链

- [x] 5.1 创建 Vue/Vite/TypeScript workspace、ES2022/Bundler strict TS 配置及 exact optional、unchecked index、isolated modules 约束；配置 ESLint 9、Vue/TypeScript lint 和 Prettier 3。
- [x] 5.2 实现 Vite JSON 深合并与 `virtual:public-config` allowlist，只暴露 title、apiBaseUrl 和 public analytics key；`src/config.ts` 作为唯一应用消费入口。
- [x] 5.3 增加公开投影、配置错误和本机配置隔离测试；使用临时 LLM/CLS/MCP/MinIO sentinel 执行真实 Vite build 并扫描完整 dist，证明秘密不存在。
- [x] 5.4 提供前端 dev/lint/format/typecheck/test/build scripts，并从根逐项验证其失败传播与 workspace 选择正确。

## 6. 实现面向值班人员的桌面 Web 壳

- [x] 6.1 按 design 的冷白/墨色/信号色 token、系统字体、Lucide RadioTower 和交接线实现 On-call Pilot 首屏，不添加假指标、按钮、路由、卡片或 API 请求。
- [x] 6.2 使用简体中文呈现“值班工作台”“工作台正在准备中”和当前无业务操作状态，增加语义结构、可见键盘焦点、对比度和 reduced-motion 处理。
- [x] 6.3 增加渲染与可访问性测试，确保桌面视口内容不重叠且页面只有一个滚动容器，移动视口保持可读但不作为产品验收目标。
- [x] 6.4 启动本地开发服务，通过浏览器在桌面和移动视口检查页面、控制台、资源、键盘、reduced motion、滚动容器和非空像素；截图保存在仓库外作为未来 UI PR 证据。

## 7. 完成仓库指南、文档与 CI

- [x] 7.1 将根 `AGENTS.md` 改为唯一项目指南，覆盖目录、命令、导入/依赖注入、配置/凭据、生产数据库、tenant、真实 MCP、项目文档简中及原文例外、桌面验收、分支、Conventional Commits 和 UI PR 截图规则；将 `CLAUDE.md` 改为兼容指针。
- [x] 7.2 创建简体中文根 README、backend/frontend/contracts workspace README 和 `infra/README.md`，只说明真实骨架、启动、验证和未来进程边界；检查项目维护文档的叙述内容为中文、必要技术原文获得中文说明，且不声称产品功能已实现。
- [x] 7.3 将 `tests/test_sync_wiki.py` 迁移到 `scripts/tests/test_sync_wiki.py`，更新相关命令/文档并删除被替代的根级 `backend`、`frontend` 和 `tests` 目录。
- [x] 7.4 更新 `openspec/config.yaml` 项目上下文，记录已冻结技术栈、目录、配置安全、主机/Compose 边界和简体中文要求，同时保留 `spec-driven` schema。
- [x] 7.5 建立 Linux Python 3.12 完整门禁、Linux Python 3.10 后端兼容和 Windows Python 3.12 smoke 三类 GitHub Actions job，统一使用 Node 22 与冻结安装。
- [x] 7.6 完成根 `wiki:test`、`openspec:validate` 和 `check` 编排，确保任一后端、contracts、前端、WIKI 或文档子门禁失败都会返回非零状态。

## 8. 完整验证与交付门禁

- [x] 8.1 运行 `openspec validate --all --strict`、根 `npm run check`、后端三个直接质量命令、contracts typecheck/test、前端 lint/format/typecheck/test/build、WIKI 测试和 VitePress build，并分别记录结果。
- [x] 8.2 运行配置模板/ignore/import-safety/目录/脚本/public-config/sentinel 专项测试，确认 ignored 本机配置未改变、未跟踪且未暂存。
- [x] 8.3 运行 `git diff --check`，复核没有应用 Dockerfile、应用 Compose 服务、`project.compose.json`、产品功能模块、环境变量项目配置或历史重写步骤。
- [x] 8.4 执行 OpenSpec verify 和独立 code review，核对 proposal、五组 specs、design、tasks、ADRs、指南、代码和测试一致；任何未运行的真实 CI/浏览器门禁必须明确标为未验证。
- [x] 8.5 同步 active Change 到 WIKI 并验证 VitePress build；只有本地门禁、真实 CI、浏览器证据和 verify 全部通过后，才展示归档快照并单独请求归档授权。
