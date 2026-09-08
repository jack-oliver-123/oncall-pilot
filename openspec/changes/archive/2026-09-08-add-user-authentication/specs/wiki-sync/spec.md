## ADDED Requirements

### Requirement: 同日创建的归档校验顺序

同步器 SHALL 在 created 日期和归档日期完全相同且同一 requirement 的操作组仅含 ADDED/MODIFIED 时先折叠原始新增再折叠修改；含 REMOVED 的组 SHALL 保留原目录和解析顺序。排序不得修改导航或放过未同步主规格。

#### Scenario: 同日创建和归档时先新增后演进
- **WHEN** 同一 requirement 的原始 ADDED 与后续 MODIFIED 来自 created 日期及归档日期完全相同的 Change，该组仅含 ADDED/MODIFIED 且目录名字典序与演进顺序相反
- **THEN** 校验器 SHALL 先折叠 ADDED 再折叠 MODIFIED，按 MODIFIED 验证主规格，旧版主规格仍被拒绝
- **AND** 同类操作保持目录顺序，导航和重复同步输出 SHALL 保持确定

#### Scenario: 同日删除后重新添加
- **WHEN** 同一天的同一 requirement 先 REMOVED 再 ADDED，且目录顺序已表达该演进
- **THEN** 校验器 SHALL 保留原顺序，最终包含重新添加内容的主规格通过校验
