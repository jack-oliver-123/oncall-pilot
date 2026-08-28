# ADR-0001：以 OpenSpec 为控制平面、以 Matt Skills 为方法层

- 状态：已接受
- 日期：2026-08-26

## 背景

本仓库同时使用 OpenSpec 和 Matt Pocock Skills。OpenSpec 管理 Change 的 proposal、specs、design、tasks、实现、验证和归档；Matt Skills 提供 grilling、research、domain modeling、prototype、TDD、诊断和 code review 等工程方法。两者职责不同，但多个入口和重复副本会让它们看起来像可互换的工作流。

如果两套工具都维护计划，或辅助 Skill 可以直接改变已确认的规格，就会出现平行事实源、任务漂移和无法从中断状态恢复的问题。

## 决策

OpenSpec 作为正式 Change 的控制平面，拥有正式意图、artifact 依赖、实现授权、验证和归档状态。Matt Pocock Skills 作为方法层，按问题类型提供探索、分析、测试和审查能力；它们可以发现冲突和提出候选结论，但不能静默创建平行规格、覆盖确认过的 artifact 或接管 OpenSpec 生命周期。

新增组合路由只做适配，不复制或修改上游 Skill。方法层结论只有在用户确认后，才能按含义进入相应 OpenSpec artifact；若改变已确认目标，必须通过 OpenSpec 更新流程并重新授权。

## 备选方案

### 两套系统各自维护计划

不采用。实现者必须在两份任务和规格之间自行裁决，且恢复点不明确。

### 让 Matt Skills 覆盖 OpenSpec

不采用。工程建议可能很有价值，但它们不是当前 Change 的正式意图，静默覆盖会绕过范围和实现门禁。

### 修改上游 Skills 使其互相调用

不采用。会把项目专属协作规则混入上游内容，增加版本升级时的分叉和冲突面。

### 复制所有 Skill 内容到一个新总 Skill

不采用。复制提示词会产生第三份事实源，且无法安全跟随上游更新。

## 后果

- OpenSpec artifact 是实现者唯一需要遵循的正式契约。
- Matt Skills 可以按问题类型插入，而不必机械绑定每个 OpenSpec 阶段。
- 冲突和目标变化会增加一次更新及重新确认的成本，但换来可追踪性和可恢复性。
- 重复副本暂时保留；其清理或自动一致性检查应作为独立 Change 处理。
- 运行时入口可以不同，但必须共享同一组合规则和 OpenSpec 状态。
