## 1. 建立长期词汇与架构记录

- [x] 1.1 创建根级 `CONTEXT.md`，仅记录 `Change`、`artifact`、控制平面、方法层和阶段门禁等跨 Change 稳定术语及关系。
- [x] 1.2 创建 `docs/adr/0001-openspec-control-plane-matt-method-layer.md`，记录 OpenSpec/Matt 分层、替代方案、冲突处理理由和不修改上游的边界。

## 2. 编写组合工作流规范

- [x] 2.1 创建 `docs/agents/combined-workflow.md`，定义 Change 边界、OpenSpec 与 Matt 的职责、规范入口、问题类型触发矩阵、产物映射和三处确认门禁。
- [x] 2.2 在 `combined-workflow.md` 中记录冲突、副作用、辅助 Skill 失败、多 Change、目标变化、中断恢复、Issue 隔离和上游升级规则。
- [x] 2.3 在 `combined-workflow.md` 中记录 `.claude/skills`、`.claude/commands/opsx`、`.codex/skills` 与 `.agents/skills` 的运行时映射，明确不把重复副本视为独立能力。
- [x] 2.4 更新根级 `CLAUDE.md`，加入指向组合规范的短版不变量；保留现有 Issue、triage 和领域文档约定。

## 3. 实现组合路由 Skill

- [x] 3.1 创建 `.claude/skills/openspec-with-matt-skills/SKILL.md`，声明其为交互式 Markdown 路由器，先读取组合规范和当前 OpenSpec 状态。
- [x] 3.2 在组合 Skill 中实现按问题类型选择 Matt 方法、按不确定性选择 `/opsx:new|continue` 或 `/opsx:propose|ff`，并将确认结论映射到唯一 OpenSpec artifact。
- [x] 3.3 在组合 Skill 中实现对冲突、重叠入口、失败、多个 Change、目标变化和重复副本的停止/提示规则；禁止静默覆盖、自动合并、代码修改、Issue、commit 和归档。
- [x] 3.4 在组合 Skill 中写明三个快照确认点：范围冻结、实现授权、验证后归档；内容变化后必须重新确认。

## 4. 建立场景回归材料

- [x] 4.1 创建 `docs/agents/combined-workflow-scenarios.md`，列出路由、边界、冲突、失败、恢复和归档场景，包含前置状态、输入、预期路由、禁止动作和确认点。
- [x] 4.2 在首次实现后按 Claude Code 主路径手工执行核心场景，逐项记录场景 ID、实际行为、日期、运行时和 `pass`/`fail`/`not-run` 结果及原因。
- [x] 4.3 对规则文档、组合 Skill 或上游入口的后续变化执行受影响场景，并在归档前处理所有失败项。

## 5. 接入稳定 OpenSpec 上下文并验证

- [x] 5.1 在不复制完整规则或动态批准状态的前提下，按当前 OpenSpec 配置格式将稳定组合规范和 `CONTEXT.md` 接入 `openspec/config.yaml` 的 `context`（若验证后格式支持）。
- [x] 5.2 运行 Markdown/YAML 检查和 `openspec validate`，修复 artifact、项目文档与配置之间的格式或引用问题。
- [x] 5.3 运行 OpenSpec verify，确认每条 requirement、场景、tasks、设计决策与实现保持一致。
- [x] 5.4 完成独立 code review，确认没有修改上游 Skill、删除重复副本、引入脚本路由器或产生第二份正式规格。
- [ ] 5.5 在获得明确归档确认后归档 `integrate-matt-skills-with-openspec`，并记录验证结果；遗留的副本治理另建 Change。
