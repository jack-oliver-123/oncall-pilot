# Issue tracker: GitHub

本仓库的 issue 和 spec 存放在 GitHub Issues。所有操作使用 `gh` CLI。

## 约定

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 issue**：`gh issue view <number> --comments`，并同时读取评论和 labels。
- **列出 issue**：使用 `gh issue list`，按需要传入 `--label` 和 `--state` 过滤。
- **评论 issue**：`gh issue comment <number> --body "..."`
- **添加 / 移除 label**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 issue**：`gh issue close <number> --comment "..."`

从 `git remote -v` 推断仓库；在本 clone 中运行 `gh` 时会自动识别仓库。

## Pull request 是否作为 triage 请求入口

**否。** PR 不作为外部功能请求进入 triage 队列。如需启用，可将本节改为 `是`，并在此补充对应的 `gh pr` 操作约定。

## 当 skill 要求发布到 issue tracker

创建一个 GitHub issue。

## 当 skill 要求获取相关 ticket

运行 `gh issue view <number> --comments`。

## Wayfinder 约定

- **Map**：创建一个带 `wayfinder:map` label 的 issue，保存 Notes / Decisions-so-far / Fog。
- **Child ticket**：创建 GitHub 子 issue，使用 `wayfinder:<type>`（`research` / `prototype` / `grilling` / `task`）label。
- **Blocking**：优先使用 GitHub 原生 issue dependencies；不支持时，在子 issue 正文顶部写入 `Blocked by: #<n>`。
- **Frontier query**：列出 map 的开放子 issue，排除有开放 blocker 或已分配的 issue，按 map 顺序选择第一个。
- **Claim**：使用 `gh issue edit <n> --add-assignee @me`。
- **Resolve**：评论答案，关闭 issue，再向 map 的 Decisions-so-far 追加 context pointer。
