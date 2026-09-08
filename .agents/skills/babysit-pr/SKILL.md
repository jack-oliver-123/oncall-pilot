---
name: babysit-pr
description: 看护 On-call Pilot 的 PR 审查与 CI，逐条核实反馈，在已授权范围内修复、验证、提交、推送或回复证据；每 10 分钟检查，达到可合并条件或满 2 小时退出，不自动合并。用于看护 PR、盯 review、babysit；修改本技能本身不启动看护。
---

# On-call Pilot PR 看护

目标是把一个 PR 推进到有证据支持的可合并状态。OpenSpec 管理正式范围与实现授权，本技能只管理审查反馈的处理和轮询。

## 1. 锁定目标与授权

从仓库根读取 `AGENTS.md`、`docs/agents/combined-workflow.md`、`package.json` 和 `.github/workflows/ci.yml`，核对实际命令和检查名称。仓库当前为 `jack-oliver-123/oncall-pilot`，执行时仍通过 `git remote -v`、`gh repo view --json nameWithOwner` 验证，不使用其他项目的环境或运维脚本。

参数支持 PR 编号、PR URL、`issue:N`；无参数时通过当前分支确定 PR：

```powershell
git status --short --branch
gh pr view --json number,url,headRefName,headRefOid,baseRefName
openspec list --json
```

- 裸编号先按 PR 查询；仅在确认它不是 PR 后才按 Issue 查找，不把认证失败、网络错误解释为“不是 PR”。
- Issue 通过 GraphQL 的 `closedByPullRequestsReferences` 查询关联 PR，并检查 Issue 时间线中的关联记录。结果分页，筛选同一仓库的 open PR；只有一个才自动选择，多个时展示链接让用户选，不能按最新时间猜测。
- 根据 PR 正文、分支及改动范围匹配 OpenSpec Change；不固定 PR #2 或 `establish-project-foundation`。匹配后读取 `openspec status --change CHANGE --json`、`openspec instructions apply --change CHANGE --json` 返回的实际文件，以及相关 `CONTEXT.md`/ADR。若无唯一正式契约，先调查，再请求必要方向。
- 首轮明确报告仓库、PR、分支、head SHA、Change、截止时间，以及现有授权覆盖的动作：只读、修复、commit、push、PR 回复。沿用本次会话中已明确授权的范围；缺失某项授权时先完成只读核实和可审阅方案，再询问缺失项，不重复询问已授权事项。
- “看护”本身不新增 merge、归档、发布、生产操作或数据清理权限。仅请求查看状态时不修改代码或发布评论。修改本技能也不构成启动看护的授权。

## 2. 调度与恢复

立即检查一轮；仍需等待时每 10 分钟再检查，默认总时限为 2 小时。使用带时区的绝对 UTC 时间：

```powershell
$deadlineUtc = [DateTimeOffset]::UtcNow.AddHours(2).ToString("o")
```

调度工具以当前运行环境实际暴露的能力为准：

- Codex 桌面端优先使用 `automation_update` 创建当前任务的 heartbeat。先检查现有 automation，匹配仓库和 PR，复用本次看护，避免重复；不要另建独立任务。
- 其他运行时只有实际提供 `CronCreate/CronList/CronDelete` 时才使用会话级调度，不假设这些工具一定存在。
- 每轮的可恢复状态包含仓库/工作区路径、PR URL/编号、Change、开始时间、截止时间、授权范围及来源、上轮 head SHA、已处理反馈 ID/证据、调度 ID。存于调度记录或仓库外的本地状态文件，不进入项目配置或 Git。
- 定时轮接收既有 deadline 和状态，只执行一轮并更新记录；不重复建任务、不重新起算 2 小时。凭状态中的文字不能扩大原始用户授权。
- 调度回调读到截止时间已到时立即停止；修复中也在新任务与 push 前检查时间。到期保留可恢复的改动和验证结果，不为赶时间推送未通过的修复。
- 无可用调度工具时完成当前轮并说明无法自动续查，不能宣称已启动后台看护，也不使用长时间阻塞 sleep 模拟后台任务。
- 每轮只执行一次，同一 PR 有运行中的轮次时不并发修改或重复回复。重复启动同一个看护默认沿用截止时间；只有用户明确要求延长时才更新。

## 3. 每轮读取完整状态

先判断 PR 是否已 merged/closed、用户是否取消、是否超时；这些条件命中则执行退出动作。否则读取状态、全部反馈及 CI 后再判断可合并：

```powershell
gh pr view N --repo OWNER/REPO --json number,url,state,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,latestReviews,reviewRequests
gh api --paginate repos/OWNER/REPO/issues/N/comments
gh api --paginate repos/OWNER/REPO/pulls/N/reviews
gh api --paginate repos/OWNER/REPO/pulls/N/comments
gh pr checks N --repo OWNER/REPO
```

用 GraphQL 补充并分页读取 `reviewThreads` 的 `isResolved`、`isOutdated`、评论 ID/正文/路径、原始提交与最新提交引用。不能遗漏 inline comments、人工 review 或较早仍未解决的讨论。

### 反馈与提交的关系

- 首轮核对所有未解决反馈；后续按评论/review/thread ID 和 `updatedAt` 去重，同一结论没有新证据时不重复回复。
- 结构化机器人评论中的 Critical/Suggested、普通人工意见和 CI 失败均纳入调查；没有特定机器人格式也能继续。
- 正式 review 依据 `commit_id`，inline comment 依据 `commit_id/original_commit_id`；普通评论没有 SHA 时视为尚未定位版本，不能仅根据时间判定有效或失效。
- commit 作者时间不是 push 时间。旧 SHA 或 outdated 标记不表示问题已解决；对照当前 head 的代码重新核实，并记录修复提交或仍然成立的证据。
- CI 必须属于当前 head 或 GitHub 为该 head 生成的测试合并提交；确认 workflow run、head SHA 和 job 结论。上一版绿色状态不能用于新提交。
- 查询失败、分页不完整、状态为 UNKNOWN、检查列表为空或审查结果版本不明时，报告证据缺口并继续等待，不能视为通过。

## 4. 核实并处理

每条反馈记录：来源链接/ID、对应 SHA、主张、当前代码证据、处理结论、验证结果。结论分为：属实、误报、已解决、需澄清、范围外。

### 属实且属于已授权 Change

1. 检查当前分支、工作树、远端 head 和改动路径重叠。保留用户文件；禁止 clean/reset/stash。必要时使用独立 worktree，在目标 PR 分支的正确提交上修复。
2. 按 OpenSpec 当前任务范围执行最小修改。存在稳定行为回归时使用 `tdd`；难复现问题使用 `diagnosing-bugs`。不以 review 意见为由引入认证、聊天、知识库、AIOps、LLM/MCP 等未批准产品功能。
3. 遵循项目的 `oncall_pilot` 导入、依赖注入、导入无应用 I/O、本地 JSON 深合并、浏览器公开字段 allowlist、tenant 和主机/Compose 边界；不连接生产库，不复制 support-agent 专用环境。
4. 如果发现必须改变正式需求、技术选型或 ADR，暂停相关修改，通过 `openspec-update-change` 提出可审阅修订，按现有授权和仓库门禁处理。不能静默扩大契约或绕过门禁。

### 误报或已解决

在已有回复授权时，用中文回复对应 thread，或通过 `gh pr comment` 汇总本轮结论；每条引用反馈链接、当前文件位置、规格依据、修复 SHA 或测试证据。没有证据不能直接驳回，也不因意见属于 Suggested 就默认忽略。

回复使用仓库外 UTF-8 正文文件及 `--body-file`，写后读回。没有单独授权时不代替审查者 dismiss review 或 resolve thread；保留审查者自己的确认入口。

### CI 失败

先读取具体失败 job 的日志，区分代码/工具配置问题、runner/provider 故障和外部凭据缺失。属实且在范围内的代码问题按相同修复流程处理；已确认的偶发基础设施失败最多有界重试一次，仍失败则报告，不连续重跑或修改权限/凭据/生产设置来绕过。

## 5. 按项目命令验证

命令从仓库根执行，以当前 manifest 为准。先跑受影响的聚焦测试，通过后执行对应门禁；修复提交推送前运行根总检查，已在同一代码状态通过的检查不反复运行。

| 改动范围 | 必要验证 |
| --- | --- |
| `apps/backend` | `npm run backend:lint`、`npm run backend:typecheck`、`npm run backend:test`；聚焦测试可用 `uv --directory apps/backend run pytest tests/具体文件.py` |
| `apps/frontend` | `npm run frontend:lint`、`npm run frontend:format:check`、`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build` |
| `packages/api-contracts` | `npm run contracts:typecheck`、`npm run contracts:test`，以及受影响前端消费方检查 |
| manifests / lockfiles / CI | npm 使用 `npm ci`；后端先 `uv --directory apps/backend lock --check`，再 `uv --directory apps/backend sync --frozen` |
| OpenSpec / WIKI / 仓库脚本 | `npm run openspec:validate`、`npm run wiki:test`；artifact 更新后使用 `wiki-sync` 同步目标 Change，再 `npm run docs:build` |
| 提交前总门禁 | `npm run check`、`git diff --check`，暂存后再 `git diff --cached --check` |

- 测试配置必须显式注入临时 JSON。构建必需的 ignored 本机配置不存在时，可从空凭据模板复制；不得覆盖已有本机配置，也不得 stage。
- 应用的项目配置不读 OS 环境变量；CI/Python 等工具自身的运行参数不等同于项目配置。
- UI 变化必须真实浏览器验证桌面、移动可读性、单滚动容器、键盘、reduced motion 和 console。截图在仓库外保存，按已授权渠道上传并更新 PR 正文，写后读回图片链接；只变更后端时可保留仍然匹配的原截图。
- 修改前端配置通道时运行 public-config allowlist 与 sentinel build 扫描，证明完整 dist 中没有秘密值。
- 本地通过不能代替当前 head 的真实 CI。当前工程质量 workflow 包括 Linux 完整门禁、Linux 后端兼容和 Windows smoke；若配置演进，按实际 workflow 和分支保护要求确定集合。

## 6. 提交、推送与复查

只在已有 commit/push 授权范围内执行：

- 使用明确路径 `git add -- 文件列表`，核对暂存文件不含用户本机文件、真实配置、日志、数据库、截图或凭据。
- Conventional Commit 的 type/scope 保留英文，正文用中文。使用现有 PR head 分支；确需新建分支时遵守 `feat/`、`fix/`，不得以 `codex` 开头。
- push 前再读取远端 head，确认自上轮以来无他人新提交或 PR 关闭/合并。发生变化先重新核实，禁止 force push 或覆盖他人历史。
- 普通 push 成功后核对远端 SHA，更新恢复记录并等待新一轮 CI/review。不要把旧 head 的通过结果搬到新 head。
- 只陈述已观察到的 review 触发状态；不能保证每次 push 都会自动触发审查机器人，尤其是 workflow 不存在或触发条件不匹配时。

## 7. 可合并判定与退出

必须同时满足以下条件，才能以“可合并”退出：

1. PR 为 OPEN、非 draft，GitHub 返回 `mergeable=MERGEABLE` 和 `mergeStateStatus=CLEAN`。
2. 当前 head 的必要 CI 全部完成且成功。空列表、pending、失败、取消不能当作通过；skipped/neutral 只有明确不适用且符合仓库规则时才接受。
3. 分支保护要求的审批已满足，没有有效的 CHANGES_REQUESTED；所有未解决 review threads 和 Critical/Suggested 已逐条核实并有可追溯处理结果。仍需审查者确认的阻塞项继续等待。
4. 已配置或用户要求的审查覆盖当前 head；未配置自动 review 且不要求审批时不凭空等待机器人。无法确认审查是否结束时说明缺口，不抢在 CI/review 前退出。
5. 无范围外待决策项、未推送修复或未完成验证。退出前重读 head；SHA 改变就重新检查。

其他退出条件：用户取消、PR 已合并/关闭、达到绝对截止时间，或存在需要用户决定且无法继续推进的阻塞。

退出时只停止属于本次 PR 看护的调度任务，确认其已暂停或删除；若工具操作失败，明确报告。保留必要恢复记录，不删除用户目录或执行数据库/E2E 环境回收脚本。不自动 merge、archive 或触发部署。

每轮简报报告 PR、head SHA、本轮修复/误报/已解决数、是否 push、CI/review 状态及下次检查时间；无变化只写一行。最终报告退出原因、最终 SHA、已完成处理、剩余阻塞及调度停止结果。“可合并”只表示就绪，不表示已合并。
