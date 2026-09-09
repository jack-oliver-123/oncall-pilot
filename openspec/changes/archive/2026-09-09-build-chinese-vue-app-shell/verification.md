# P08 验证记录

日期：2026-09-09。Change：build-chinese-vue-app-shell，schema：spec-driven。

## 结论

实现任务 10/10 完成；7 条 Requirement、13 个 Scenario 均有实现及验证证据。完整性、正确性、一致性检查通过，无未解决 CRITICAL、WARNING 或 SUGGESTION。main specs 已逐项同步，Change 已归档为 2026-09-09-build-chinese-vue-app-shell。归档后 WIKI 同步、60 个 include、导航与 VitePress 构建通过；active Change 为空。

## 需求与证据

| 需求 | 实现 | 测试与验收 |
| --- | --- | --- |
| 路由与首次身份恢复 | src/router.ts、src/application.ts、src/App.vue | workspace.test.ts：首次初始化、publicOnly、根/未知路径、redirect、401/网络恢复；app.test.ts：恢复重试；浏览器刷新仅一次 /auth/me |
| 真实认证表单 | src/views/AuthView.vue、src/auth/authClient.ts | app.test.ts：校验、注册返回登录、失败、重复提交；浏览器真实注册→登录→回到 /knowledge?tab=recent |
| 桌面工作台结构 | src/layouts/WorkspaceLayout.vue、src/views/PlaceholderView.vue、src/styles.css | app.test.ts：四路由、Chat slot、服务成功/失败；桌面浏览器四路由布局检查 |
| 受保护状态生命周期 | src/stores/protectedData.ts、src/application.ts | workspace.test.ts：多回调、注销、dispose、HTTP 401、反馈清理；auth.test.ts：旧用户结果隔离 |
| 共享可访问交互状态 | src/components/*、src/stores/feedback.ts | states.test.ts：三种反馈、3000ms 重置、关闭与卸载 timer、ARIA、retry；浏览器键盘 3px 焦点与 reduced motion |
| 清理与异步竞态隔离 | src/auth/authState.ts | auth.test.ts、workspace.test.ts：先撤销后清理、失败清理、迟到 login/me/logout；浏览器登出后旧 token /auth/me 返回 401 |
| 认证流生命周期 | src/auth/authClient.ts、src/auth/authState.ts | auth.test.ts：SSE 401、取消、旧握手隔离；transport.test.ts：共享事件、UTF-8 分块、取消和 reader 释放 |

表中 src 与 tests 路径均相对 apps/frontend。已检查应用实例隔离、localStorage 仅 token、无虚构领域数据、无业务删除、中文文案、焦点与单滚动约定。原有 typed HTTP/SSE transport 继续复用，无新增 endpoint 或 contract。

## 独立质量门禁

- frontend：67 tests passed；lint、format check、typecheck、build 全部通过。
- contracts：36 tests passed；typecheck、生成漂移检查通过。
- backend：认证 API、认证 repository、protocol 共 115 passed；tenant API、tenant repository、OwnerScope 共 21 passed，合计 136 passed。未运行 backend 全量测试；未修改 backend。
- openspec validate --all --strict：归档前 19 passed，0 failed。
- git diff --check：通过。
- 归档后 openspec validate --all --strict：18 passed，0 failed；openspec list --json 返回空 changes。
- 归档后 WIKI：0 active、11 archived、60 个 include 与导航检查通过，docs:build 通过；仓库工具测试 37 passed。

## 浏览器证据

真实本地主机 FastAPI + 临时 SQLite 迁移，前端 http://127.0.0.1:5173，后端 http://127.0.0.1:18008。配置、数据库、浏览器脚本、截图全部位于仓库外目录：

`C:/Users/qianwen.cui/.codex/visualizations/2026/09/09/01a0848a-91c7-7ac3-bde8-e9897e1b5614/p08-qa`

- `login-1440.png`：真实登录页。
- `knowledge-1440.png`、`chat-1440.png`、`chat-1280.png`：不同路由及桌面工作区。
- `keyboard-focus-1440.png`：键盘焦点。
- `chat-320.png`：窄屏同一结构的防溢出补充检查。
- `browser-results.txt`、`browser-console.json`：最终浏览器几何与流程断言、console 结果。

桌面 1440×900、1280×720，附加 390×844、320×844，合计 16 个 route/viewport 组合：document 宽度等于 viewport、内部滚动容器为 0、顶栏与画布不重叠且等宽。真实注册不自动登录、登录回 redirect、刷新恢复、导航、退出后本地清理与服务端撤销均验证通过。最终浏览器 console 0 error/0 warning、pageerror 0，页面标题正确，无空白或框架错误 overlay。

## 过程问题与修复

- 测试先于实现，首次路由测试因 application 模块缺失变红；实现后转绿。
- 后端第一次命令引用不存在的 test_tenant_isolation.py，未运行测试；改为实际存在的文件后上述 136 项通过。
- QA 临时配置遗漏 frontend.analytics 导致 Vite overlay；补齐临时公开配置后重载正常，不改开发者真实配置。
- Browser plugin not available。已有 Playwright CLI 完成初始交互后，run-code 的后台会话报 Session closed；后续使用同一缓存 Playwright 库启动独立 Chrome 完成全链路复核，没有安装或修改项目依赖。
- 补充修复提交期间切换 publicOnly 页的迟到登录导航，并清除前一账号反馈；对应新增回归均通过。
- main spec 同步后、P08 尚未归档时，WIKI 以旧 P04 archived delta 严格比较而报告清理需求不一致。代码确认其按归档日期折叠最新 operation；不使用 --allow-unsynced，不修改同步器或旧归档，归档后重跑同步已通过。

- 额外仓库 tooling 测试发现前端 README 漏掉既有“桌面 Web”约定文字，补齐文档后重跑；未修改测试规则。

## 证据边界

本机真实认证 API 验收通过；SSE 为共享协议及模拟网络流的单元验证，不声明真实业务 SSE、MCP、LLM 或知识库验收通过。四个业务页仍为“尚未开放”，无移动专用抽屉、底部导航或替代流程。不涉及生产数据库、部署、commit、push 或 PR。
