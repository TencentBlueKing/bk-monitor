# Architecture Decisions Memory

Record durable decisions, alternatives, tradeoffs and consequences here.

## 2026-05-21 retrieve-v2 字段设置收起态吸顶

- 背景：`field-filter.vue` 收起态入口在纵向滚动后定位不正确，原因是按钮模板内联 `position: absolute; top: 64px; transform: translate(-50%, -50%)` 覆盖样式，同时外层 `.field-list-sticky` 仅在展开态 `.is-show` 时 sticky。
- 决策：展开态继续使用 `.field-list-sticky.is-show { top: var(--offset-search-bar) }` 对齐字段设置面板；收起态新增 `.field-list-sticky.is-close { position: sticky; top: 0 }`，吸顶位置同步日志结果表头 `.bklog-row-container.row-header { top: 0; height: 32px }`。
- 实现：移除 `field-filter.vue` 内联定位，把默认按钮定位沉到 `field-filter.scss`；收起态按钮 `top: 16px; left: 0`，使 24px 按钮中心对齐 row-header 32px 高度中线。
- 约束：不要把展开态 `var(--offset-search-bar)` 复用于收起态，否则纵向滚动结果区时收起入口会和 row-header 错位。

## 2026-05-22 monitor/apm 独立包 timeRange 切换渲染防崩

- 背景：`src/views/retrieve-v3/monitor/apm.ts` 会通过 `build:apm` 将日志检索模块作为 NPM 包提供给外部项目；入口组件为 `src/views/retrieve-v3/monitor/monitor.tsx`。
- 问题：外部安装独立包后，`monitor.tsx` 的 `props.timeRange` 变化会触发 `LogRows` render 报错 `Cannot read properties of undefined (reading 'value')`，本项目内 `retrieve-v3/index.tsx` 入口不复现。
- 根因：`LogRows` 的行展开/行号状态存放在 `WeakMap<tableRow, Ref<RowConfig>>`，旧逻辑在 render/click 中直接 `tableRowConfig.get(row).value`。monitor 独立包的 timeRange 刷新时序下，结果列表可能已更新但行配置还没注册。
- 性能决策：保留原有基于 `tableDataSize` 和 `setRenderList(null)` 的已加载数据渲染模型；每次接口实际只追加约 50 条，但单条数据可能很大，不能监听/遍历大 list，也不能在 timeRange/list 替换时全量初始化或清理行配置。
- 实现决策：移除 eager `updateTableRowConfig`，改为 `ensureTableRowConfig(row, rowIndex)` 懒创建；render/click 路径都传入当前渲染行号，避免 `WeakMap` 未命中崩溃，同时避免 O(list.length) 扫描。
- 约束：不要监听 `indexSetQueryResult.value?.list` 引用来重置状态；不要把 `setRenderList` 默认值改为 `pageSize`，否则会破坏已加载结果的增量展示；不要在 `resetRowListState` 中重置 `pageIndex/hasMoreList`。
- 验证：`npm run build:apm` 构建通过；`git diff --check` 通过。


## 2026-05-22 LogRows monitor/apm 大数据性能约束复盘

- 背景：`retrieve-v3/monitor/apm.ts` 独立包中，`monitor.tsx` 的 `timeRange` 等 props 改变会触发 `requestIndexSetQuery`，`LogRows` 曾因 `tableRowConfig.get(row).value` 在新 row 未注册时崩溃。
- 覆盖要求：首次查询、timeRange/keyword/addition 等查询条件变更、滚动加载更多、Row Expand 都必须保持正确；同时日志单条和接口返回可能非常大，性能优先级最高。
- 决策：不监听 `indexSetQueryResult.value?.list`，不 deep watch，不枚举 query 条件；继续用 `tableDataSize` 作为轻量驱动。非分页查询在 store 中会先清空 list，因此 `tableDataSize === 0` 时 O(1) 调用 `resetPageState()`，覆盖所有查询条件变更。
- 决策：保留 `setRenderList(length ?? tableDataSize.value)` 的原有语义，滚动加载更多只按 pageSize 追加本地渲染窗口；不要强制缩回首屏，也不要全量初始化行状态。
- 决策：保留 WeakMap 作为 row 对象级状态缓存，但禁止裸访问 `.get(row).value`；统一用 `ensureTableRowConfig(row, rowIndex)` O(1) 懒初始化，Row Expand 渲染也必须显式传入 `rowIndex`。
