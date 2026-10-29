# bk-magic-vue → TDesign Vue Next 替换分析与执行

本记录基于 V2 `bklog/web/src`，实施目录为 `packages/web-v3/src-native`。不能以已有 `packages/web-v3/src` 原型作为功能依据。目标是原生 Vue3 + `tdesign-vue-next`；兼容运行时仅用于定位迁移问题，不能计入最终验收。时间选择保持 `@blueking/date-picker` 的 Vue3 发行入口。

## 已接入的官方依据

已通过 MCP SDK 实际连接官方内网服务 `http://mcp.tdesign.woa.com/mcp`，成功调用 `get-component-docs` 获取 Loading、Table、Form、Select、Dialog、Drawer、Popup、Input、Button、Pagination、Tabs 文档。原始结果保存在 `artifacts/tdesign/`，带获取时间和来源。

参考：[官方快速开始](https://tdesign.tencent.com/vue-next/getting-started)、[官方 MCP 接入说明](https://tdesign.tencent.com/vue-next/mcp)。本次使用一次性文档客户端，没有修改全局 IDE 配置。客户端只发送技术栈和组件名称，不上传业务代码、Cookie 或业务数据。

从 `bklog/web` 执行，可重复获取资料：

```sh
node migration-project/migration-engine/tdesign-mcp.mjs docs loading
node migration-project/migration-engine/tdesign-mcp.mjs docs table form select dialog drawer
node migration-project/migration-engine/tdesign-mcp.mjs dom table dialog drawer
node migration-project/migration-engine/inventory-tdesign.mjs
```

内网 MCP 曾对一批查询返回 HTTP 433，随后单组件和批量查询成功。查询失败会退出并报告错误，不伪造文档结果。

## 源码覆盖范围

首轮静态扫描发现 79 个文件直接导入 `bk-magic-vue`；模板、JSX、指令和导入合计形成 86 类候选名称，其中包含业务自定义组件、注释及条件编译入口，不能直接解释为 86 个基础组件。完整文件清单、候选属性、事件及映射方向见 `artifacts/tdesign/source-inventory.json`。正则扫描用于定位，必须结合源码 AST、实际引用和运行验证复核。

按涉及文件数，优先关注 Button（191）、Input（152）、Loading（151）、Select/Option（各98）、Form（73）/FormItem（74）、Table（68）/TableColumn（66）、Dialog（64）。这些数字是静态涉及文件数，含注册文件，不能当作功能完成率。

## 替换规则与关键差异

- 基础控件使用 TDesign。业务页面按 V2 源码重写，保留原 API、权限、条件分支和副作用。不能通过全局字符串别名把 `bk-*` 标签直接映射为 TDesign 后宣布完成。
- Loading：旧指令的 `isLoading` 对应受控显示；`title` 对应 `text`。V2 的 `delay` 延迟隐藏，TDesign 原生 `delay` 延迟显示，因此由适配层处理取消和隐藏时序。保留初始 `immediate`、标题/尺寸更新、颜色、透明度和层级；卸载释放挂载节点及计时器。指示器外观仍需 V2 截图复核。
- Table：V2 的子列组件、selection 列、过滤器、`renderHeader`、单元格插槽和实例方法必须逐项转换为 TDesign `columns`、`rowKey`、`selectedRowKeys`、`cell/title` 等契约。TDesign 分页、排序、过滤的 `change` 事件带上下文，不能直接转发为旧回调。必须保留全选前校验、跨页选择、禁选、行展开、空态和设置列。当前旧表格使用 Vue2 `_renderProxy`，需要随表格实现移除该内部依赖。
- Form：旧 `validate()` 的成功/拒绝分支要与 TDesign 返回 `true` 或错误列表对齐，不能把返回 Promise 成功执行当成校验成功。逐字段核对触发方式、异步规则、错误展示、`clearValidate`、重置，以及步骤切换后表单状态。
- Select：核对原始值类型、空值、多选、分组、远程检索、创建项、键盘、弹层宽度和焦点恢复。TDesign `change(value, context)` 的第二参数不是旧事件参数；`filterable`、`valueType`、选项插槽需显式转换。
- Dialog/Drawer：TDesign `visible` 是受控状态；`close` 的 `trigger` 区分 ESC、取消、遮罩和关闭按钮。逐项核对 V2 的异步确认、关闭前校验、取消副作用、销毁策略、底部操作区、附着节点、宽度、层级和滚动。不能统一成无条件关闭。
- Input：按源码区分单行、数值和多行；保留输入事件参数、组合输入、失焦校验、清空、前后缀和焦点实例方法。
- SearchSelect、TableSetting、ResizeLayout、Exception、虚拟滚动等没有可靠的一对一替代，必须组合基础控件并升级原业务逻辑。用户选择器与用户展示组件仍按真实包来源处理，不因 `bk-` 前缀而误替换。
- Popup/Tooltip：保留受控显隐、点击外部、延时、触发器、插槽、挂载和边界处理。必须更新依赖 `.bk-*` DOM 的样式和查询逻辑，使用 MCP DOM 资料核对结构。
- Message、Notify、InfoBox 等服务入口最后统一到原生应用上下文；Promise、确认/取消和错误反馈保持原行为。

## 实施顺序与验收

1. 共享启动基础：Loading、Button、Icon、Message、Tooltip/Popup；每项先固定 V2 契约和调用点。停止为旧库增加长期兼容实现。
2. 检索工具栏：时间组件保持官方 Vue3 版本；逐个升级历史、自动刷新、索引选择与查询编辑器所需控件。验证完整回填字段、键盘和外部关闭。
3. 检索结果：先将表格、字段设置、分页、排序、详情侧栏组合成完整结果闭环；覆盖空、加载、失败、无权限、展开和选中。
4. 表单和弹层：以一条采集新增/编辑闭环验证 Form、Select、Drawer、Dialog 后，再扩展管理页面。不能用通用表单和列表替代原业务组件。
5. 聚类、收藏、其他管理、外部嵌入和 APM/Trace：沿条件编译入口分别完成，不能只统计默认日志页面。
6. 原生清理：移除 `common/*import*` 中的 `Vue.use`、旧组件库样式、旧 `tdesign-vue`、Vue2 class 依赖和实例私有 API；原生构建、类型检查、组件测试、浏览器与视觉验收通过后才能删除依赖。

每个模块产出源码依据、属性/事件/插槽/实例方法契约、实现、测试、浏览器截图和剩余差异。逻辑通过与视觉通过分开记录。未对齐项目保持待验证，不从覆盖分母中移除。

## 首批接入状态（后续进展见下方）

- 已实现：`src-native/adapters/tdesign/loading-contract.js`、`loading.js`；在 `main.js` 注册 Vue3 指令，调用 TDesign Loading，沿用 V2 `v-bkloading` 参数契约，减少业务调用点的改动。
- 自动测试：8 项 native 单元测试通过，其中 Loading 新增2项覆盖重试取消、延迟隐藏、初始 immediate 和卸载清理。未据此宣称 UI 或检索业务通过。
- 兼容构建：包含本批 Loading 替换的 `build:migration` 成功（35.56秒）。该产物仍包含旧库，不能作为原生 Vue3 交付。
- 原生构建：失败。当前首个阻塞为 `components/log-masking/masking-setting.tsx` 仍使用 Vue2 class 装饰器；大量组件尚未按源代码升级。
- 浏览器：4175 已初始化导航，但检索界面尚未通过，仍有原生函数组件与兼容运行时交互错误，以及旧组件契约未迁移导致的渲染失败。4174 原生入口也未达到业务可用。
- 全量 `bk-magic-vue` 替换尚未完成；当前属于共享基础首批实施。

## 后续检索修复批次

已进一步升级收藏、仪表盘弹层、排序/结果选项、趋势/分级与顶部菜单，并修复日期绑定、索引名插槽、插值正文、布局、字体资产和公告代理。当前32项测试通过、兼容构建成功；40676只读查询及部分弹层已真实验证。详细证据与未完成项见 `migration-contracts/tdesign-retrieve-pilot-20261028.md` 和 `artifacts/verification/2026-10-28/verification.json`。这些进展不等于原生构建或全量业务验收通过。

## 最新阶段调整：本地 Dev UI 主题对齐

按用户最新要求，当前不再以全量迁移V2 class作为阻塞，保留Class在Vue3兼容宿主中运行，通过4175 Dev与V2浏览器对照优化主题。使用 `dev:ui` / `build:ui`，集中主题文件为 `packages/web-v3/src-native/scss/theme/tdesign-bklog.scss`。本批映射颜色、尺寸、文字、边框、圆角及四色Loading，并对齐收藏弹层按钮64px宽度；无需整体复制旧组件库class。主题与小范围交互的证据见 `artifacts/verification/2026-10-28/ui-theme/verification.json`。历史原生构建失败保留为后续技术事项，完整业务与全量视觉验收仍未完成。
