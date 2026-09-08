## MODIFIED Requirements

### Requirement: OpenSpec-aware archive validation

同步器 SHALL 依据每个归档 Change 自身的 OpenSpec 状态判断 specs 是否需要同步，并 SHALL 区分合法跳过与未同步错误。存在 delta spec 时，同步器 SHALL 要求可识别且格式正确的 operation；空文件、空 operation 段落或无法解析的 RENAMED SHALL 在写入前失败。

#### Scenario: Change declares skip_specs
- **WHEN** 归档 Change 的 `.openspec.yaml` 声明 `skip_specs: true` 且没有 delta specs
- **THEN** 同步器 SHALL 将该 Change 视为合法无规格变更
- **AND** SHALL 继续生成其 WIKI 页面而不要求绕过标志

#### Scenario: Delta specs are synchronized
- **WHEN** 归档 Change 存在 delta specs 且其要求已反映在对应 main specs
- **THEN** 同步器 SHALL 通过 archive spec 校验并继续生成页面

#### Scenario: Delta specs are not synchronized
- **WHEN** 归档 Change 存在尚未反映到 main specs 的 delta spec 操作
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出未同步的 capability 或 requirement

#### Scenario: Delta specs contain no operations
- **WHEN** 归档 Change 存在 delta spec 文件，但未包含任何 ADDED、MODIFIED、REMOVED 或 RENAMED Requirements 段落
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出该 delta spec 缺少可识别 operation

#### Scenario: Operation section is empty or RENAMED is malformed
- **WHEN** delta spec 含有 ADDED、MODIFIED 或 REMOVED 段落但没有 requirement，或 RENAMED 段落无法解析出成对 FROM/TO
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出 capability、operation 与格式问题

#### Scenario: 同日归档覆盖遵循 OpenSpec 创建顺序
- **WHEN** 两个同日归档 Change 先后修改同一 requirement，且 OpenSpec created 日期能区分其创建先后
- **THEN** 校验器 SHALL 按归档日期、created 日期、目录名依次折叠 delta，以较晚创建的 Change 校验 main spec
- **AND** WIKI 页面导航顺序和幂等性 SHALL 保持不变
