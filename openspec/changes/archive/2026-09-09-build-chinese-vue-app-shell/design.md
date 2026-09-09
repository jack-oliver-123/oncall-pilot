## Context

P04 的 createAuthState 已封装 token 持久化、清理登记与请求版本隔离；现有 apiClient 和 sseClient 已消费生成合同并验证运行时 payload。本次复用其行为，不复制传输协议。当前 App.vue 仅展示 foundation 文案。

## Goals / Non-Goals

**Goals:** 将认证、路由和共享 UI 组合成可测试的桌面工作台，避免模块导入阶段读取 Storage 或发请求。

**Non-Goals:** 不引入业务数据接口、持久化业务 store、移动抽屉/底部导航、跨标签页会话协调、自动 SSE 重连。

## Decisions

- 由 createApplication 组合根创建 Pinia、auth 和 router，通过注入使组件消费实例；不使用跨应用全局 auth 单例。auth store 包装现有状态，feedback 同样登记身份清理；publicOnly 页面遇到迟到登录成功也转至安全内部目标。protectedData 登记清理并在 scope dispose 注销，后续真实 store 复用同一登记接口。
- router guard 缓存首次 initialize Promise；失败保留认证错误并显示全局重试入口，只有显式重试调用 initialize。publicOnly 已认证回 /chat，redirect 通过 router.resolve 与受保护 route meta 验证，拒绝外站、认证页和未知路径。
- logout 首先增加版本、隐藏用户并取消流，尝试服务端撤销，finally 清理本地；新身份已建立时旧 logout 不清理新身份。HTTP 保留原有版本检查，SSE 包装相同版本与 AbortController 生命周期。
- WorkspaceLayout 使用 CSS grid：rail / Chat 会话列 / workspace，workspace 含顶栏与 edge-to-edge RouterView；只让 document 滚动，所有内部区域不建立滚动容器。保留窄屏同一结构并允许文字换行，不创建移动替代流程。
- 配色使用墨绿 #173f36、强调绿 #276653、冷灰 #f3f6f5、正文 #21332e、次要文字 #586961、边界 #dce5e0。中文正文使用 Microsoft YaHei UI/PingFang SC，品牌使用 Bahnschrift，主导航的纵向当前位置标记是唯一强调。避免业务画布卡片化。
- 服务状态调用 getHealth，使用有界取消与手动刷新；成功只显示“服务可连接”，辅助说明明确只检查应用进程。组件卸载取消请求。
- 共享 feedback store 只持有最新消息与递增 ID；AppFeedback watch ID 管理 3000ms timer，关闭与 unmount 均清 timer。可访问状态统一文字、role 与 aria-live，reduced motion 禁用非必要动画。

## Risks / Trade-offs

- [token 按 P04 保存在 localStorage] → 不增加其他凭据或领域持久化，不渲染未经净化的 HTML。
- [登出网络失败] → 无论结果均清本地，明确提示服务端撤销未确认，不误报成功。
- [恢复错误导致路由尚未认证] → 全局错误阻止受保护画布，显式重试成功后回到内部 redirect。
- [业务尚未实现] → 入口可导航至诚实占位，未开放操作不显示为可用按钮。
- [仅桌面验收] → 1440×900、1280×720 真浏览器检查；窄屏只做同一布局防溢出检查。

## Migration Plan

无需数据库或 contract 迁移。替换前端入口后运行独立质量门禁与本机隔离认证 E2E；回滚前端变更可恢复 foundation 页面，已持久化 session 不受业务删除影响。
