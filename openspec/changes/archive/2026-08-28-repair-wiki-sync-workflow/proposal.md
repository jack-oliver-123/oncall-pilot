## Why

归档后的 `wiki-sync` 当前无法执行：Skill 指向不存在的脚本位置，实际脚本依赖 Windows clone 不可靠的符号链接、误把合法 `skip_specs` Change 当作缺少规格，并缺少可构建的 VitePress 站点。需要把同步能力收敛为仓库级唯一实现并补齐自动验证，才能让 OpenSpec 变更 WIKI 真正保持同步。

## What Changes

- 建立仓库级 `scripts/sync_wiki.py` 作为 Claude、通用 Agent 和人工调用共享的唯一同步入口。
- 更新 `.claude/skills/wiki-sync/` 与 `.agents/skills/wiki-sync/` 的说明，使两份运行时入口调用同一仓库脚本；移除旧的运行时私有脚本实现。
- 直接从生成页面相对引用根级 `openspec/`，取消 `docs/openspec` 符号链接要求以支持 Windows clone。
- 根据归档 Change 的 `.openspec.yaml` 正确识别 `skip_specs: true`；仅对真正存在但尚未同步的 delta specs 阻断归档 WIKI 同步。
- 移除从其他项目带入的站点名称、生成器路径和 requirement evolution 特例。
- 增加最小 VitePress 文档站点、依赖锁文件和构建脚本，并排除生成缓存与构建输出。
- 增加同步模块测试，覆盖 active、archive、`skip_specs`、未同步阻断、include 路径与导航一致性。
- 运行修复后的同步器，补生成已归档 Change 的 WIKI 页面并通过 Python tests 与 VitePress build。
- 收敛实现审查发现：独立校验仅以 OpenSpec 为期望源并全文比较受管输出；空/畸形 delta operation 与非法同步参数在写盘前失败；Skill 收紧触发与 `--allow-unsynced` 一次性批准语义。
- 为 VitePress 1.6.4 增加已验证的 npm `overrides.vite=6.4.3`，消除默认 Vite 5 链 dev advisory，并保持 build/audit 门禁。

## Capabilities

### New Capabilities

- `wiki-sync`: 定义 OpenSpec active/archive Change 到可构建 WIKI 页面、索引和导航的确定性同步行为。

### Modified Capabilities

无。

## Impact

- 受影响区域：`scripts/`、`tests/`、两份 `wiki-sync` Skill、`docs/`、根级 npm 配置和 `.gitignore`。
- 新增 VitePress 开发依赖和可重复的文档构建命令。
- 开发依赖通过 override 固定 vite 6.4.3；不引入生产运行时依赖。
- 不修改任何已归档 OpenSpec artifact 或现有 main spec 内容。
