## MODIFIED Requirements

### Requirement: 策略参数校验与持久化
只有 fixed-character MUST 接受 `maxCharacters` 和 `overlap` 参数；fixed-character MUST 校验正数 maxCharacters 及 `overlap < maxCharacters`。其他策略传入这些参数 MUST 被拒绝。文档保存时 MUST 保存实际 strategy 和参数。工作区 MUST 显示 fixed-character 的长度和 overlap 输入，并在 markdown-heading、paragraph 请求中省略这两个字段。

#### Scenario: 非法 fixed-character 参数
- **WHEN** 用户提交 maxCharacters 非正数或 overlap 不小于 maxCharacters 的 fixed-character 配置
- **THEN** 前端即时提示或后端返回参数校验错误，且不保存文档

#### Scenario: 其他策略携带 fixed 参数
- **WHEN** markdown-heading 或 paragraph 请求携带 maxCharacters 或 overlap
- **THEN** 返回参数校验错误且不保存文档；正常工作区请求不会发送这些字段

### Requirement: 有界 chunk preview
系统 MUST 提供 chunk preview 响应，最多返回 12 个 chunk，每个 chunk 的 excerpt 最多 400 字，并包含顺序、策略和可追溯 metadata；preview MUST 不改变文档或索引状态。工作区 MUST 在文档上传并开始索引后通过对应 chunk-preview endpoint 读取实际切分结果，并在有界容器内展示服务端返回的策略和 metadata。

#### Scenario: 预览长文档
- **WHEN** 用户在工作区展开自己的长文档并请求 chunk preview
- **THEN** 客户端读取不超过 12 段且每段 excerpt 不超过 400 字的结果，并提供可滚动预览

#### Scenario: 预览不改变状态
- **WHEN** 用户重复展开同一文档并请求 chunk preview
- **THEN** 返回确定性结果，文档元数据和 index status 不发生变化
