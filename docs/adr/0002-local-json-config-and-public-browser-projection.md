# ADR-0002：本地 JSON 配置与浏览器公开投影

- 状态：已接受
- 日期：2026-08-28

On-call Pilot 以必需的本地 `project.json` 和可选的 `user.project.json` 递归深合并结果作为唯一项目配置，不从 OS 环境变量读取项目值。浏览器只能通过明确 allowlist 获得 title、API base URL 和标记为 public 的 analytics key；其他配置默认私有。相比同时支持环境变量或把完整 JSON 暴露给前端，这一选择牺牲了通用云部署的灵活性，但换来可审计的单一事实源、确定的覆盖语义和可自动证明的秘密隔离。
