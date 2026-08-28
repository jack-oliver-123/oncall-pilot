## Context

参见 `proposal.md` 的问题描述。当前同步实现藏在 `.agents` 运行时副本中，但两份 Skill 都指向不存在的 `.codex` 路径；实现还依赖 `docs/openspec` 符号链接，而本 clone 的 `core.symlinks=false`。仓库没有 VitePress manifest，脚本包含其他项目的站点名称和 requirement evolution 特例，并把 OpenSpec 的合法 `skip_specs` 状态当作异常。

首轮实现已收敛到仓库级 `scripts/sync_wiki.py` 与可构建 WIKI。独立审查与依赖审计又确认：独立校验存在循环 oracle、delta operation 解析过宽、Python seam 输入校验不足、Skill 对 `--allow-unsynced` 约束偏弱，以及 VitePress 1.6.4 默认 Vite 5 链存在可经 override 消除的 dev advisory。

## Goals / Non-Goals

**Goals:**

- 用一个仓库级深模块隐藏 OpenSpec 发现、校验、渲染和输出一致性逻辑。
- 让运行时 Skill 成为相同 interface 的薄调用说明，不再各自拥有实现。
- 通过真实 CLI、临时仓库测试和 VitePress build 验证完整同步链路。
- 在不修改已归档 artifact 的前提下补生成所有当前 Change 的 WIKI 投影。
- 独立校验仅从 OpenSpec 源构造期望，并对受管输出做全文一致性比较。
- 对空/畸形 delta operation 与非法 mode/name 在写入前显式失败。
- 以已验证的 `vite@6.4.3` override 保持构建可重复且 audit 清洁。

**Non-Goals:**

- 不改变 OpenSpec archive/sync 的控制平面职责。
- 不把 WIKI 变成第二份可编辑规格；页面只引用 artifact。
- 不引入部署或托管流程。
- 不保留与本仓库无关的历史 requirement evolution 兼容表。
- 不在同步器内实现交互式批准流；`--allow-unsynced` 仍是显式 CLI 旗，批准语义由 Skill/操作者约束。

## Decisions

### 仓库级同步模块是唯一实现 seam

将实现放在 `scripts/sync_wiki.py`，外部 interface 为：

```text
python scripts/sync_wiki.py active <change-name>
python scripts/sync_wiki.py archive <change-name-or-archive-name>
python scripts/sync_wiki.py all
```

模块内部接收 `repo_root` 以便测试，CLI 默认从脚本位置解析仓库根目录。`.claude` 和 `.agents` 两份 Skill 只说明该 interface；旧 `.agents/.../scripts` 实现删除。

备选方案是把脚本复制到每个运行时目录或改为调用 `.agents` 路径。两者都会让某个兼容副本拥有事实源，增加漂移和运行时耦合，因此不采用。

### 直接相对引用根级 OpenSpec

归档页位于 `docs/changes/archive/<name>/index.md`，其 include 使用 `../../../../openspec/changes/archive/<name>/...`；active 页同理引用根级 `openspec/changes/<name>/...`。同步器使用解析后的文件路径逐一验证目标。

备选方案是维持 `docs/openspec` 符号链接。当前 Windows clone 不可靠支持受版本控制的 symlink，且链接只为缩短路径，不提供必要抽象，因此不采用。

### OpenSpec 元数据决定无规格状态

归档校验先读取 Change 的 `.openspec.yaml`。没有 delta specs 时：

- `skip_specs: true`：合法通过；
- 未声明 skip：报告缺少 delta specs；
- 有 delta specs：按 operation 与 main specs 比较。

存在 `specs/*/spec.md` 时必须解析出可识别 operation。下列情况在写入 WIKI 前失败，不得视为“无 delta”：

- 文件中没有任何 ADDED / MODIFIED / REMOVED / RENAMED Requirements 段落；
- ADDED / MODIFIED / REMOVED 段落存在但没有 requirement；
- RENAMED 段落无法解析出成对 FROM/TO。

`--allow-unsynced` 仅保留为用户显式批准**真正未同步**归档历史的逃生口，不用于合法 `skip_specs`，也不用于掩盖空/畸形 delta。Skill 要求该旗绑定**当前完整错误列表与仓库状态**的一次性批准，不得复用历史批准。

备选方案是根据 Change 名称或 artifact 内容猜测是否需要 specs；这会绕过 OpenSpec 的正式状态，因此不采用。

### 独立校验的期望只来自 OpenSpec 源

`verify_wiki` 与同步后的输出校验共用同一套期望构造：页面列表、frontmatter 日期、include 集合、索引与导航均只从当前 `openspec/changes` 与 Change 元数据推导。`created_date` 读取 `.openspec.yaml` 的 `created`、归档目录日期前缀等源字段，**禁止**从已有 WIKI frontmatter 回读作为 oracle。

对每个受管 Change 页、`docs/changes/index.md` 与 `docs/.vitepress/config.mts`，将磁盘内容与同一 render 函数的期望全文比较；仅比较链接顺序不足以捕获日期或正文漂移。

### Python seam 拒绝非法输入

公开 `sync_wiki(repo_root, mode, name=None, allow_unsynced=False)` 在任何仓库读取或写入前校验：

- `mode` 必须是 `active` / `archive` / `all`；
- `all` 时 `name` 必须为 `None`；
- `active` / `archive` 必须提供非空 `name`；
- `name` 不得为 `.` / `..`，不得包含 `/` 或 `\`，不得为空或仅空白。

CLI argparse 与 seam 双重守卫，测试直接打 Python interface 覆盖非法参数路径。

### 纯函数式渲染与显式仓库上下文形成测试 seam

同步实现用 `WikiRepository`（或等价上下文对象）持有根路径，收集/解析/渲染函数尽量返回值，最终写入集中在同步阶段。测试使用 `tempfile.TemporaryDirectory` 构造最小仓库，通过公开同步 interface 验证行为，不修改真实工作区。

不为文件系统引入抽象 Adapter：只有真实文件系统这一种实现，临时目录已提供足够 seam。

### 最小 VitePress 站点和锁定依赖

根级 `package.json` 使用 VitePress `1.6.4`，提供 `docs:dev`、`docs:build`、`docs:preview`；提交 `package-lock.json`。为消除默认 Vite 5 链上的 dev advisory，增加 npm override：

```json
"overrides": {
  "vite": "6.4.3"
}
```

该组合已在临时目录验证：与 `@vitejs/plugin-vue@5` peer 兼容、`npm audit` 为 0 vulnerabilities、完整 WIKI `docs:build` 通过。

`docs/index.md` 提供 On-call Pilot WIKI 首页，生成器负责 `docs/.vitepress/config.mts` 与 `docs/changes/`。`.gitignore` 排除 `node_modules/`、`docs/.vitepress/cache/` 和 `docs/.vitepress/dist/`。构建产物不进入 WIKI 正式内容。

### 生成内容使用本仓库身份

站点标题与描述使用 On-call Pilot；生成文件注释指向 `scripts/sync_wiki.py`。删除外部项目 capability 的 `REQUIREMENT_EVOLUTIONS`。若未来存在真实 rename/evolution，必须由 OpenSpec delta 的 RENAMED operation 表达，而不是在 WIKI 层隐藏修补。

## Risks / Trade-offs

- [VitePress include 可能限制 source root 外路径] → 在实现阶段先以最小生成页运行真实 `npm run docs:build`；若失败，暂停并通过 OpenSpec update 选择无 symlink 的替代（如构建时映射），不静默复制 artifact。
- [脚本重写引入回归] → 将现有确定性行为转为 interface 级 `unittest`，覆盖成功与失败路径后再删除旧实现。
- [生成器管理目录时可能删除人工页面] → 只管理 `docs/changes/active/` 与 `docs/changes/archive/` 的 Change 子目录；`docs/index.md` 和其他文档不在 stale 清理范围。
- [依赖引入扩大仓库安装成本] → 仅添加 VitePress 单一开发依赖并提交 lockfile，不增加运行时依赖。
- [全文比较对无关空白敏感] → 期望与生成共用同一 render 函数，避免手写第二套模板。
- [vite override 被上游将来收紧] → 版本锁在 lockfile；升级 VitePress 时重跑 audit 与 build。

## Migration Plan

1. 先添加 `scripts/sync_wiki.py` 与临时目录测试，迁移并修正现有行为。
2. 添加最小 VitePress manifest、首页和 ignore 规则，安装锁定依赖。
3. 更新两份 Skill 指向仓库级入口并确认正文完全一致；删除旧运行时脚本。
4. 运行 Python tests，再对真实仓库执行 `python scripts/sync_wiki.py all`。
5. 单独验证生成页 include 目标、目录集合、索引与导航一致性。
6. 执行 `npm run docs:build`；若 include 路径不被 VitePress 支持，停止并更新设计，不复制 OpenSpec artifact。
7. 修复 verify oracle、严格 delta 解析与 seam 输入校验；补充对应回归测试。
8. 应用 `vite@6.4.3` override，更新 lockfile，运行全项目 `npm audit` 与 `docs:build`。
9. 更新 Skill 触发描述与 `--allow-unsynced` 一次性批准约束。
10. 运行 OpenSpec validate 与 verify，确认没有修改归档 artifact 或 main specs。
11. 回滚时移除新增站点/脚本/测试/生成文件并恢复两份 Skill；OpenSpec 内容无需回滚。
