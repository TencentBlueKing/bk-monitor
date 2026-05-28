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

## 2026-05-22 LogRows monitor 首屏骨架屏渲染门控

- 背景：monitor/apm 独立包挂载到外部项目时，timeRange 等新查询首屏数据返回后，父容器布局与列宽计算可能晚于真实行渲染，导致短暂出现第 2 列过窄、每行显示“更多”。本项目内入口布局稳定，不易复现。
- 决策：新查询首屏阶段先渲染 `src/skeleton/retrieve-loader.vue` 骨架屏，真实 `LogRows` header/rows/exception 在两帧列宽测量与 `columnLayoutVersion` reflow 后再显示。
- 约束：分页追加更多、列拖拽、字段设置展开/收起不触发首屏骨架屏；不能监听大 list、不能 deep watch、不能复制单条大日志对象。
- 验证：`npx eslint src/views/retrieve-v2/search-result-panel/log-result/log-rows.tsx`、`git diff --check`、`npm run build:apm` 通过。

## 2026-05-22 log-rows pagination response size fix
- 问题：首屏骨架屏修复后，monitor 包在 `total_count` 很大时只加载到 100 条即显示“已加载所有数据”。
- 根因：`loadMoreTableData` 对 `store.dispatch('requestIndexSetQuery', { isPagination: true })` 的返回值使用 `resp?.length !== pageSize` 判断是否还有更多；实际 store 返回对象 `{ length, size, ... }`，部分入口/构建下 `resp.length` 可能不可用或判断不兼容，导致错误将 `hasMoreList` 置为 `false`。
- 决策：新增 `getPaginationResponseSize(resp)`，兼容 `resp.length`、`resp.size`、数组返回与 `resp.data.list.length`；只有明确 `responseSize < pageSize` 时才关闭 `hasMoreList`，未知响应长度时保持可继续加载，避免大总量日志被误判为加载完成。
- 性能约束：该判断只读取响应元信息，不遍历当前大 list，不复制日志对象。

## 2026-05-28 retrieve-v2 日志排序后骨架屏不退出修复

- 背景：`src/views/retrieve-v2/components/result-storage/index.tsx` 的日志排序会执行 `requestIndexSetFieldInfo` 和 `requestIndexSetQuery`，查询完成后再触发 `RetrieveEvent.SORT_LIST_CHANGED`。
- 问题：`LogRows` 原先把 `SORT_LIST_CHANGED` 和搜索/时间变更事件一起无条件 `resetPageState()`。排序查询完成后 `tableDataSize` 已经更新，首屏 reveal 也已经调度/完成；此时再把 `isFirstPageLayoutPending` 置为 `true`，后续没有新的 `tableDataSize` 变化触发 `scheduleFirstPageTableReveal()`，导致骨架屏 loading 常驻。
- 决策：`SORT_LIST_CHANGED` 单独处理，只在仍处于请求中、页面 loading 中、requesting 中或当前无结果行时才重置首屏骨架状态；查询已完成且已有结果时不再重新进入 pending。
- 约束：搜索值、时间、趋势图搜索等真实查询起点仍可无条件 `resetPageState()`；分页加载更多仍不能触发首屏骨架屏。
- 验证：状态机静态验证、`git diff --check`、`npx eslint ... --quiet`、`npm run build` 通过。

## 2026-05-28 context-log 关闭后请求失效保护

- 背景：日志检索结果点击“查看上下文”后，快速上下滚动再 ESC 关闭弹窗，滚动防抖与异步 `getContentLog` 仍可能在弹窗关闭后继续执行。
- 问题：关闭流程会清空本地参数/列表，但旧滚动 timer 或旧请求回调仍可能继续使用已失效状态，导致请求参数出现 `None` 等非法值，后端报 `query_shard_exception`。
- 决策：`context-log/index.tsx` 增加弹窗可见态和 request sequence 保护；关闭、切换行、卸载时清理 scroll listener、所有 timer，并 cancel 固定 requestId 的上下文请求；旧请求返回后不再落地 UI，不再触发滚动定位/高亮初始化。
- 约束：上下文日志的滚动加载必须先判断弹窗仍可见、requestSeq 仍匹配、关键参数有效；ESC 关闭后禁止继续发起或落地 `retrieve/getContentLog`。
