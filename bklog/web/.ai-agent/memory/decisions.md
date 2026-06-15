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

## 2026-05-29 Retrieve result render value truncation

Context: `src/store/index.js` `requestIndexSetQuery` receives `data.list` / `origin_log_list` from log search API. Individual field values can be extremely large and cause Vue render / JSON expand performance issues.

Decision:
- Before committing query results to `indexSetQueryResult`, normalize parsed rows with a render-safe truncation pass.
- Only truncate values whose runtime type is `string` and whose length exceeds `32 * 1024` chars.
- Preserve all non-string values unchanged.
- Preserve JSON rendering compatibility by recursively processing object / array values instead of stringifying entire objects.
- Apply to both `list` and `origin_log_list`, so table cells and expand JSON view share the same render-safe data.

Constraint:
- Do not deep-watch result lists.
- Do not clone or stringify whole rows for truncation.
- Keep row object structure stable for `parseTableRowData`, expand view and JSON rendering.

## 2026-06-01 Log Query Render Value Truncation Clarification

- `src/store/index.js` log query result truncation must treat `data.list` / `origin_log_list` as arrays of row objects.
- For each row object, every key's value must be processed independently.
- String values are truncated to `32 * 1024` characters; shorter strings and non-string values remain unchanged.
- Nested Object/Array values should preserve JSON structure and recursively truncate only string leaves.
- BigNumber-like values with `_isBigNumber` must not be expanded/rewritten by truncation logic.
- Do not stringify a whole row or nested JSON object before truncating, otherwise JSON rendering compatibility will be broken.

## 2026-06-01 Retrieve result frontend render performance

- For `requestIndexSetQuery`, avoid double traversal of large `data.list` payloads. Do not run `parseBigNumberList(list)` followed by a separate truncate pass.
- Use a single `normalizeLogRenderList` pass to convert BigNumber-like values and truncate string leaf values to max `32 * 1024` chars.
- Preserve unchanged row/object references when no value changes to reduce allocation pressure before Vuex commit.
- Do not persist heavy `origin_log_list` into `indexSetQueryResult` for the result list path; expand view should use the normalized `list` row data instead.
- In `expand-view.vue`, avoid `JSON.parse(JSON.stringify(result))` for JSON cache creation; it duplicates large row data and increases main-thread cost. Prefer `Object.freeze(result)` after values are already normalized.

## 2026-06-01 Retrieve dotted field rendering compatibility

- Context: Search API can return flattened dotted keys such as attributes.line and attributes.sampled without a parent attributes object.
- Decision: parseTableRowData must first read exact row keys before trying nested path parsing. This preserves display for flattened fields.
- Decision: When requesting a parent field such as attributes and no direct parent value exists, aggregate row keys with prefix attributes. into a JSON object for display, e.g. { line: ..., sampled: ... }.
- Rationale: OTel / flattened ES fields use dotted key names as real field keys. Treating all dotted names as nested paths causes table cells and JSON/KV expansion to render - incorrectly.
- Verification: Static dotted field parser test and npm run build passed.

## 2026-06-02 Retrieve UI fuzzy match mode

- Context: `retrieve-v2/search-bar/ui-mode/ui-input-option.vue` used a technical `使用通配符` checkbox for text/string contains filters. Users had to hand-write `*` / `?` and could not understand ES vs Doris behavior differences.
- Decision: Replace the checkbox with a standalone `fuzzy-match-mode.vue` component shown only for `包含` / `不包含` text/string conditions.
- Modes: exact, prefix, suffix, contains, custom. The input keeps the user keyword; submit transforms values to raw query strings only for fuzzy-enabled operators: `abc`, `abc*`, `*abc`, `*abc*`, or user custom input.
- Compatibility: Keep using existing wildcard operator mapping through `isInclude`; non-exact modes set `isInclude=true`, exact sets `false`. Preserve `fuzzy_match_mode` in front-end condition state so editing tags can restore the selected mode and strip auto-added wildcard wrappers back to the user keyword.
- Engine hint: `fuzzy-match-mode.vue` receives `engine` prop; current caller derives Doris when all selected index sets have `support_doris`, otherwise falls back to ES.
- Constraint: Other operators and field types must not show fuzzy mode UI and must keep existing condition logic unchanged.

## 2026-06-02 模糊匹配 UI 组件按设计稿分区渲染

- 文件：`src/views/retrieve-v2/search-bar/ui-mode/fuzzy-match-mode.vue`、`ui-input-option.vue`。
- 将模糊匹配组件拆为 `label` / `modes` / `preview` 三个 section，以适配设计稿：标题右侧显示“匹配模式 ?”，输入框上方显示分段模式按钮，输入框下方显示虚线预览说明卡片。
- 模式按钮文案拆分为主文案和示例：`精确 abc`、`前缀 abc*`、`后缀 *abc`、`包含 *abc*`、`自定义`。
- 只调整 UI 结构与样式，提交值转换逻辑保持不变：prefix/suffix/contains/custom/exact 仍由 `ui-input-option.vue` 在保存时统一转换。

## 2026-06-02 模糊匹配弹层宽度、模式点击与输入区优化

- 文件：`src/views/retrieve-v2/search-bar/ui-mode/ui-input-option.vue`、`ui-input-option.scss`、`fuzzy-match-mode.vue`。
- 模糊匹配模式下弹层父容器增加 `is-fuzzy-match` class，将内容宽度从 720px 扩展到 920px，左侧字段列表收敛到 320px，右侧配置区获得足够宽度承载 5 个匹配模式按钮。
- Vue2 环境中避免依赖 `v-model` 的 `update:modelValue` 语义；调用 `FuzzyMatchMode` 时显式传 `:value="condition.fuzzy_match_mode"` 并通过 `@input` 更新，确保 tab 点击立即生效。
- 模糊匹配输入区改为 `bk-input type="textarea"`，默认 3 行，高度可 `resize: vertical` 调整；键盘事件对该 textarea 放行普通 Enter/方向键，只保留 Cmd/Ctrl+Enter 提交和 Esc 收起。


## 2026-06-02 模糊匹配弹层 Vue2 响应式与宽度修复

- 场景：`src/views/retrieve-v2/search-bar/ui-mode/ui-input-option.vue` 的模糊匹配模式按钮点击后 active/preview 不刷新，且父级 tippy 宽度限制导致模式按钮区域显示异常。
- 根因：项目使用 Vue2，`condition.fuzzy_match_mode` 若作为动态新增属性直接赋值，不保证响应式；外层弹层宽度受 `PopInstanceUtil` 默认 `maxWidth: 800` 限制，内部 `.ui-query-option-content` 设置 920px 不足以生效。
- 决策：
  - `getInputQueryDefaultItem` 默认补齐 `fuzzy_match_mode: 'exact'`；
  - 模式变更使用 Vue2 `set(condition.value, 'fuzzy_match_mode', mode)`，并同步 `isInclude`；
  - `ui-input-option.vue` 暴露 `isFuzzyMatchAvailable`，由外层 `ui-input.vue` 在 tippy show 阶段设置 `maxWidth: 960/800`；
  - 保持内部模糊匹配内容宽度为 920px。
- 验证：静态脚本覆盖事件绑定、Vue2 set、默认字段、tippy maxWidth 链路和模式提交值；ESLint、`git diff --check`、`npm run build` 均通过。


## 2026-06-02 - 模糊匹配组件封闭化

- `src/views/retrieve-v2/search-bar/ui-mode/fuzzy-match-mode.vue` 必须作为封闭组件维护：props 仅使用 `{ value, type: 'es' | 'doris' }`，调用方只允许 `<FuzzyMatchMode v-model="..." :type="..." />`。
- 匹配模式到实际下发值的转换必须在组件内部完成：精确=`kw`，前缀=`kw*`，后缀=`*kw`，包含=`*kw*`，自定义=`原文`。
- 父组件不得维护 `fuzzy_match_mode`、不得上提匹配模式转换逻辑，只接收组件输出的最终 value。
- 搜索条件提交时，是否使用 wildcard operator 由最终 value 是否包含 `*` 或 `?` 判定，避免父组件感知模式。
- 模糊匹配弹层需要同步扩大 tippy `maxWidth` 与内部 `.ui-query-option-content` 宽度，避免 5 个模式按钮布局溢出或压缩。

## 2026-06-02 - 模糊匹配组件头部操作内聚

- `src/views/retrieve-v2/search-bar/ui-mode/fuzzy-match-mode.vue` 继续保持封闭组件：除 `value/type` 外，不向父组件暴露匹配模式状态或转换逻辑。
- 当 `ui-input-option.vue` 渲染 `FuzzyMatchMode` 时，外层原有“检索内容 / 批量输入 / 清空”标题行必须隐藏，避免双标题和职责重复。
- “检索内容”、`BatchInput`、`清空`、右侧“匹配模式 ?”统一迁移到 `fuzzy-match-mode.vue` 内部实现；批量输入结果由组件内合并为换行文本并按当前模式输出最终 value。
- 父组件仍只允许 `<FuzzyMatchMode v-model="fuzzyMatchValue" :type="fuzzyMatchEngine" />` 调用形态。


## 2026-06-03 编辑采集项稳定性排查

- 场景：`manage-v2/log-collection` 编辑采集项在生产偶现页面卡死/Chrome Error 5，接口数据量小，重点排查前端状态与副作用链路。
- 结论：编辑页多数操作在新标签页打开，不能依赖列表页通过 Vuex `collect.curCollect` 传入的内存态；各步骤应以路由 `collectorId` + `collect/details` 为权威数据源，并在详情返回后同步 `collect.curCollect`。
- 稳定性规则：
  1. 编辑页 Step3/Step4 进入时如存在 route collectorId，应主动拉详情并落地 store，避免新标签页 store 为空导致后续逻辑读取空对象。
  2. 轮询、延迟 tippy 初始化、异步详情请求必须在组件卸载时取消或通过 `isUnmounted/isDestroyed` 守卫，禁止卸载后继续落地 UI。
  3. `field-list` 这类会动态初始化 tippy 的组件必须集中调度 timer，重复触发前先清理旧 timer，避免实例和延迟任务堆积。
  4. 编辑页路由 query 应避免重复字段，减少异常导航状态。
- 已落地：`create-operation/index.tsx` 轮询卸载保护；`step3-clean.tsx` 详情请求卸载保护；`step4-storage.tsx` 详情回填同步 store 并 fallback formData；`field-list.tsx` tippy 初始化 timer 清理；`useCollectList.ts` 清理重复 `query.collectorId`。
## 2026-06-04 检索结果行操作改为 hover 浮层

- 文件：`src/views/retrieve-v2/search-result-panel/log-result/log-rows.tsx`、`log-rows.scss`、`log-row-attributes.ts`。
- 决策：移除日志检索结果右侧固定操作列，不再把操作列计入表格宽度、列宽分配、横向滚动 sticky/fixed right 占位或阴影计算。
- 实现：每行渲染 `bklog-row-hover-operator`，默认 `width: 0` 不参与表格 scrollWidth；hover/focus/AI active 时通过 sticky right + absolute content 从当前行右侧滑出，操作层 z-index 高于行内容，并在横向滚动时吸附可视区域最右侧。
- 约束：保留 `OperatorTools` 原操作能力和点击回调；Monitor Trace 环境仍不显示行操作。

## 2026-06-04 Retrieve V2 Row Hover Operator Style Refinement

- Scope: `src/views/retrieve-v2/search-result-panel/log-result/log-rows.scss`, `src/views/retrieve-v2/components/result-cell-element/operator-tools.vue`.
- Decision: row hover operator overlay should not use a fixed container width; it uses `width: max-content` and sizes by visible action count.
- Operator item sizing: each action is `20px x 20px`, with `gap: 2px` between actions.
- Overlay card: lightweight border/background/shadow is kept on the hover overlay, but previous 30px item sizing, 8px gap, and 40px action container height were removed.
- Tooltip UX: all operator tooltips use `delay: 500` to avoid immediate tooltip noise while moving across row actions.
- Verification: static assertions, `git diff --check`, `eslint operator-tools.vue --quiet`, and `npm run build` passed.

## 2026-06-04 Retrieve v2 row hover operator z-index fix

- Context: after removing the fixed right operation column, row actions are shown as `.bklog-row-hover-operator` on row hover.
- Issue: the hover operator was translated upward with `transform: translate(0, -32px)`, causing it to enter the sticky `.bklog-row-container.row-header` area and be covered by the header.
- Decision: keep the operator anchored inside the current row by using `transform: translateX(0)` on hover, and raise the hovered row/operator z-index above the sticky header (`row z-index: 120`, operator z-index: 130).
- Constraint: do not move row operators into the header layer; operators must stay aligned to the current row top/right padding and remain sticky to the visible right edge during horizontal scroll.

## 2026-06-04 Retrieve v2 row hover operator overlay clipping fix

- Context: `src/views/retrieve-v2/search-result-panel/log-result/log-rows.tsx` row hover action overlay must keep product-designed `transform: translate(0, -32px)`.
- Problem: rendering `.bklog-row-hover-operator` inside each row caused the first row overlay to enter sticky header area and be clipped by `.bklog-row-box { overflow: hidden; }`; changing/removing transform is not acceptable.
- Decision: render a single `.bklog-row-hover-operator` as a direct child of `.bklog-result-container`, position it absolutely from the hovered row's bounding rect, and keep `transform: translate(0, -32px)` in the overlay visible state. This escapes `.bklog-row-box` clipping while preserving the designed upward animation.
- Verification: browser test on `http://appdev.woa.com:8001` confirmed operator is direct child of `.bklog-result-container`, `handle-content` is visible (`76x28`, opacity 1), overlaps sticky header but has `z-index: 200` vs header `z-index: 2`, and is not clipped by row-box.
## 2026-06-04 Fuzzy Match tag relation/focus fixes

- Scope: `src/views/retrieve-v2/search-bar/ui-mode/fuzzy-match-mode.vue`.
- Keep fuzzy match relation row (`组间关系`, `AND`, `OR`) on one line with nowrap flex styles.
- Vue2 template refs inside `v-for` are not reliable for focusing the current edited tag; use a component root ref plus `data-fuzzy-edit-index` selector, then `focus()` and `select()` after `nextTick()`.
- Browser validation on `http://appdev.woa.com:8001`: select `log` field + `包含`, create two tags, relation row stays inline, double-click second tag focuses `.fuzzy-match-tag-edit[data-fuzzy-edit-index="1"]`.

## 2026-06-05 manage-collection basic-info 空条件防御

- 问题：采集项详情 `/manage/log-collection/collection-item/manage/:collectorId` 在部分采集配置下 `collectorData.params.conditions.separator_filters` 不存在，`basic-info.vue` 的 `isNotWinAndHaveFilter` 直接读取 `.length` 导致页面崩溃。
- 修复：`params` 默认 `{}`；`conditions` 默认补齐 `{ type: 'none', separator_filters: [] }`；`isNotWinAndHaveFilter` 基于补齐后的数组判断；同时 `winlog_event_id/winlog_level` 长度读取改为可选链。
- 验证：覆盖缺失 params/conditions/separator_filters 的静态 JS 场景；`npm run build` 通过。

Knowledge update: updated.

## 2026-06-04 检索结果原始模式首行 hover 操作浮层防裁剪

- 场景：`retrieve-v2` 日志检索结果切换到“原始”模式后，第一行 hover 操作浮层仍需保持产品设计的 `transform: translate(0, -32px)`，但不能被顶部工具栏/结果容器上边界裁剪。
- 根因：原始模式没有 table sticky row header，第一行 row 紧贴 `.bklog-result-container` 顶部；浮层 anchor top 使用 `rowTop + 4` 后再上移 32px，最终视觉 top 变成负数，受到 `.bklog-result-container { overflow: hidden }` 裁剪。
- 决策：不改动 `transform: translate(0, -32px)`；改为在 `updateHoverOperatorPosition` 中对 anchor top 做下限保护：`Math.max(rowTop, operatorTranslateY + rowPaddingTop)`，确保上移后视觉 top 不小于容器内 4px。
- 验证：浏览器访问 `http://appdev.woa.com:8001`，切换“原始”，hover 第一行；测得 `.bklog-row-hover-operator` transform 为 `matrix(1,0,0,1,0,-32)`、opacity=1、z-index=200、top/bottom=416/444，操作浮层完整可见未被裁剪。

## 2026-06-04 Hover operator first-row clipping fix

- Context: retrieve-v2 `log-rows.tsx` hover row operator in original display mode must keep product motion `translate(0, -32px)` but must not be clipped by the result container and must not cover row text/click/selection area.
- Decision: render `.bklog-row-hover-operator` as `position: fixed` and compute viewport-based `top/right` from the hovered row. Do not clamp anchor downward. This keeps the final visual operator above the first row while escaping `.bklog-result-container { overflow: hidden }`.
- Verification: browser E2E on `http://appdev.woa.com:8001` original mode, first row hover. Measured operator visible, transform matrix y=-32, operator rect top/bottom `384/412`, first row rect top/bottom `412/442`, root top `411`; no overlap with row text and no clipping.
