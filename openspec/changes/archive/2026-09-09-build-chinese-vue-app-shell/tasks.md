## 1. 认证与路由接入

- [x] 1.1 先建立路由保护、redirect、恢复与 Pinia 清理验收测试，确认现有合同生成无漂移和实际路径对齐
- [x] 1.2 实现应用组合根、Pinia auth/protectedData、路由守卫和安全 redirect
- [x] 1.3 接入认证 SSE 生命周期与服务端优先登出，验证 401、取消和迟到响应

## 2. 中文交互与工作台

- [x] 2.1 实现共享状态组件和 feedback 生命周期，覆盖可访问语义与 fake timer
- [x] 2.2 接入真实登录注册表单与恢复重试，覆盖校验、失败和重复提交
- [x] 2.3 实现桌面 WorkspaceLayout、Chat 插槽、四个诚实占位路由、真实服务状态与设计 tokens

## 3. 验证与交付

- [x] 3.1 运行 frontend lint/format/typecheck/test/build、contracts test/typecheck/check 和相关 backend tests，修复失败
- [x] 3.2 使用隔离本地配置和真实认证 API 完成桌面浏览器 E2E、焦点、reduced motion、console 与单滚动验收，截图存仓库外
- [x] 3.3 更新前端文档、核对需求场景及设计一致性，完成 verify，运行 openspec validate --all --strict 与 git diff --check
- [x] 3.4 同步 main specs、验证 delta 一致并准备归档后的 WIKI 验证

归档属于以上任务通过后的生命周期动作；归档后继续同步 WIKI、构建文档并复核 active Change 为空，证据记录在 verification.md。
