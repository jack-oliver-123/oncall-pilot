## 1. 共享合同

- [x] 1.1 建立 foundation OpenAPI 入口，定义两类 envelope、四类稳定错误目录、health path 和八类 SSE/工具四态 schema。
- [x] 1.2 实现受控生成器、TS/Pydantic 生成声明、共享运行时 validator 与生成漂移检查。
- [x] 1.3 增加合同 fixtures 和类型/运行时测试，覆盖全错误目录、所有事件、工具四态和错误复用。

## 2. 后端协议适配

- [x] 2.1 实现 success/error helper、request-id middleware、HTTP/validation/unknown exception handler，并迁移 health。
- [x] 2.2 实现基于生成联合的 SSE serializer，增加 Pydantic/JSON Schema 跨语言一致性、字段路径、request ID、错误脱敏和 OpenAPI path/response 测试。

## 3. 前端传输

- [x] 3.1 实现 typed apiClient、envelope 解码、request ID/bearer/fetch/signal 注入，并增加成功/四类失败/协议异常测试。
- [x] 3.2 实现增量 SSE frame parser 与 sseClient，测试任意字节分块、换行、UTF-8、握手错误、取消和资源释放。

## 4. 防漂移与验收

- [x] 4.1 增加应用禁止临时事件结构的边界检查和负向用例，编写中文合同扩展指南并同步 WIKI；修复同日归档排序并增加回归测试。
- [x] 4.2 运行 contracts typecheck/test、backend pytest/Ruff/Pyright、frontend typecheck/test/build、OpenSpec strict、git diff --check 及必要 lint/文档检查，修复失败。
- [x] 4.3 执行 openspec-verify-change 与独立双轴审查，记录完整性、正确性、一致性和测试证据，关闭发现项。
- [x] 4.4 同步五组主规格、逐项验证合并结果，归档并重新验证 WIKI include、VitePress 与 OpenSpec。
