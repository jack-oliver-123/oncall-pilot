# On-call Pilot 前端

此 workspace 使用 Vue 3、Vite 6 和 TypeScript 5.6 strict 构建面向非技术值班人员的桌面 Web 壳。浏览器只通过 `virtual:public-config` 获取 allowlist 字段，不直接读取完整项目 JSON。

## 启动

从仓库根运行：

```powershell
npm run frontend:dev
```

## 验证

```powershell
npm run frontend:lint
npm run frontend:format:check
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
```

当前 foundation 不提供认证、聊天、知识库、AIOps 或 MCP 操作。桌面验收要求页面至多存在一个滚动容器，并检查键盘、reduced motion、console 和移动视口可读性。
