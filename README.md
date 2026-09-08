# On-call Pilot

On-call Pilot 当前正在建立产品工程基座。仓库包含 OpenSpec/WIKI、FastAPI 后端、Vue 前端 workspace、TypeScript API contracts、本地 JSON 配置、持久化、用户认证与 Qwen/Bailian 模型注入边界；聊天、知识库、AIOps、Agent/MCP 等完整产品流程尚未开放。模型配置与手动验证见 [模型指南](apps/backend/llm.md)。

## 安装

```powershell
npm install
Set-Location apps/backend
uv sync
Set-Location ../..
```

从 `config/project.template.json` 复制本机 `config/project.json` 后可运行应用命令。实际配置文件已被 Git 忽略，不得暂存。

## 验证

```powershell
npm run check
git diff --check
```

`npm run check` 统一执行 OpenSpec、backend、contracts、frontend、WIKI 和 VitePress 门禁。当前 Change 与任务状态以 `openspec list --json` 及对应 artifacts 为准。

## 项目规则

唯一项目指南见 `AGENTS.md`。所有项目维护文档使用简体中文，代码标识、命令、路径和标准技术名词保留原文。
