# 实施记录 03：根状态原生 Pinia 与 Monitor、聚类验证

日期：2026-11-12。继续执行《Vuex 移除与 Pinia 原生化核对》和《迁移对齐丢失根因与方案修订》。本批完成根状态拥有者及内部消费者的原生化，整体迁移仍在实施中。**这不是全业务、全视觉验收通过结论。**

## 1. 根状态及业务调用

实现位置以 `packages/web-v3/` 为基准：

- `src/app/state/domains/application-store.ts`：原生 `defineStore`，扁平 state，40 个具名同步 action、17 个具名异步 action，以及原业务派生值。保留 V2 方法名；`SET_APP_STATE` 现在是具名 Pinia action，不再通过字符串 commit 调用。
- `state.ts` 保留完整默认状态工厂；`mutations/index.js` 改为具名状态操作函数，不再导出 mutations 字典。40 个方法的参数和函数体与本批修改前逐项一致，包含缓存、localStorage、错误记录、字段、空间、Monitor 初始化及重置操作。
- `actions/*.js` 保留全部业务服务流程，以原生 store 作为参数，内部调用明确的字段、派生值及 action。API 参数、第三参 config、权限判断、缓存键、回填、异常和 finally 清理继续沿源实现执行。
- 原始 `visibleFields` 与原 getter 的派生 `resolvedVisibleFields` 分离；调用方按原 state/getter 的实际使用位置迁移，避免名称冲突。
- 请求池、字段请求合并、排序和搜索会话按拥有者隔离。主应用继续使用原默认请求池；独立 Pinia 实例互不取消请求。
- 根域和检索域缓存的是原生 store 定义，状态和实例由 Pinia 注册表拥有，`$dispose` 后可按 Pinia 语义重新创建实例。
- Options API 改用 Pinia `mapState`；组合式代码直接使用对应域 hook。迁移脚本初始处理了 290 个调用文件、1840 处访问，随后补齐 map selector、模板及以参数传递的 store；该数量仅作改动追踪，不是业务完成率。

主应用和 Monitor 的 Vue3 应用均安装 Pinia。业务组件不再读取 `$store`、`.state/.getters` 或调用 `.commit/.dispatch`。审计扫描脚本及 Vue 模板共 927 个文件，剩余违规 0；排除的发布协议文件逐一列在 `native-state-audit.json`，不是大目录豁免。

已经删除：通用 `platform/state/domain-store.ts`、`state-runtime.ts`、旧 context 类型、旧 action/getter 字典、旧 retrieve 定义、业务 `map-helpers.ts` 和 `use-store.ts`。collect/globals 原文件只保留状态类型，运行逻辑由原生 domain store 拥有。`url-resolver.ts` 也改为直接读取原生场景配置。

40 个函数体的逐项一致性证明针对**本批修改前工作区**，包含此前未提交的迁移修改；不能据此推断原迁移实现已经完整等价于 V2。V2 副作用对照测试、实际原生 store 测试及真实业务查询共同补充验证，未覆盖的 V2 场景仍须继续验收。

## 2. 发布边界与 APM/Trace

`monitor-store-compatibility.ts` 只服务已发布的 logStore 协议：字符串/对象调用、namespaced getter、第三参 config、返回 Promise 及 subscribeAction。所有行为直接转发到四个原生 store，没有第二份 state、旧 context 转换器或按字典执行的业务逻辑。`index.ts` 延迟解析该适配层，避免模块加载阶段创建根状态。

内部业务不得通过这一协议访问状态；只有发布入口可导入。已增加 `check:native-state` 并接入 `verify`，防止接口回流。

验证分三层记录：

1. APM/Trace 最终产物构建、发布导出及资源完整性验证，日志及源摘要在本批证据目录。
2. Vue2 2.7.16 宿主实际加载 Vue3 3.5.44 的浏览器夹具：断言组件注入的是同一个真实根 store，通过 `$refs` 调用适配层后原生状态计数从 0 变为 1；验证原数组修改、路由同步、未知参数保留，以及销毁后卸载清理。此夹具不请求或修改业务资源。
3. 独立 APM/Trace 产品宿主中的全后端业务回归仍为**待验证**，不以通用夹具替代。

补修打包脚本的回滚缺陷：打包前先归档上一版本及文件校验清单，校验成功后才替换目标目录；保留包版本。默认归档到 `analyze-info/monitor-package-archives/`。本批只在临时目录测试打包，没有替换仓库内的已发布包。

同时修复旧 Monitor 浏览器夹具错误地从根 Vue3 包查找 Vue2 runtime 的问题。Vue2 运行时仅由开发夹具从封版 V2 测试依赖解析；生产构建不依赖此夹具。构造器测试已按当前保留的消息反馈接口核对，未重新引入已移除的 `$bkMessage/$bkNotify`。

## 3. 本批真实运行发现的根因

以下问题是在源码替换后、真实运行验证中发现并修复，不能用构建成功掩盖：

- 根 store 在模块加载阶段被 Monitor/URL 工具提前实例化，引发循环初始化异常。URL 工具直接使用检索域，发布适配层延迟解析，主应用启动直接取得原生 store。
- Vue 模板中的 `store.state.showAlert/spaceUid` 没有被只处理 script 的变换覆盖。补齐模板访问，并将模板纳入后续审计。
- 原 `mapGetters({ globalsData: 'globals/globalsData' })` 不能直接变成 `mapState(useApplicationStore, {...})` 的字符串字段。17 个相关文件已改成明确的跨域函数 selector，修复聚类及管理页面的全局配置读取。
- Pinia Devtools 每次 action 都创建新的 receiver Proxy，按 `this` 做 WeakMap 的索引会失效。检索域使用显式 Pinia 闭包；搜索会话按原生 `$state` 的稳定对象标识。测试使用不同代理包装同一 store，验证去重、取消和过期响应仍有效。

## 4. 聚类剩余交互及样式

本段具体业务环境与运行记录已移至仓库外本地归档；复验须提供本地授权测试上下文。

- 表头只保留漏斗入口，责任人和备注继续使用草稿、明确确认/重置及数组值协议。本批进一步恢复 150px 弹层宽度、搜索图标/文案、底边框、勾选文字 6px 间距和 12px 字体。
- 模板解绑从 `bk-popconfirm` 改成原生 TDesign Popconfirm，保留 V2 完整提示内容与 `handleConfirmUnbindTemplate` 的事件顺序。取消不修改模式/规则；确认只改变本地草稿，真正持久化仍由原保存流程执行。
- 解绑弹层保留 380px 宽度、16px 内边距、无额外提示图标、右侧“解绑/取消”顺序。本批发现全局主题的 `row-reverse` 会反转局部 `order`，需显式恢复 `flex-direction: row`；自定义 `popupProps.overlayClassName` 也会覆盖 TDesign 默认的 `t-popconfirm` 类，现已保留原类名，避免默认容器样式失效。
- 浏览器实际打开聚类、筛选和设置/解绑提示后取消，没有保存、解绑或修改已有资源。确认后的业务事件链由真实组件测试覆盖。

截图必须结合 `browser-results.json` 中的实际视口阅读：V2 为 1440×900，V3 为 1280×720；本批视口能力未能改变 V3 尺寸。固定 1140px 的侧栏和固定宽度弹层可检查局部布局，但**不能将不同全页视口的截图算作像素对齐通过**。1440×900 和 1280×800 的同数据完整对照继续待验证。

## 5. 验证结果及未通过项

- 原生状态专项：20 项通过，覆盖状态归属、持久化、实例隔离、派生字段、请求合并、失败、取消、过期响应、分页恢复及释放后重建。
- Monitor 相关专项：8 项通过，含构造器、宿主路由、打包资源、归档和源快照校验。
- 聚类专项结果见 `clustering-tests.log`，包括新补的解绑取消/确认事件测试。
- 全量测试：388 项，364 项通过、24 项失败，无跳过。相对批次 02 的 379/353/26，新增 9 项并解决 2 项 Monitor 相关失败；没有删除原失败场景或缩小覆盖分母。
- 严格类型检查：仍有 1574 条错误；根原生 store、Monitor 适配层和运行时新文件无类型诊断，整体类型检查未通过。不得将错误数量下降当作迁移验收率。
- AI 依赖图/源清单检查通过；原生状态审计通过。
- 第三方边界检查仍失败：`features/collection/ip-selector/bk-ip-selector-vue3.js` 引用旧 IP Selector SDK 入口未登记为冻结 owner。本批未通过增加白名单掩盖该问题。
- source-layout 仍报告 22 个 JS 文件，JS→TS 全面清理未完成。
- APM/Trace 全产品链路、聚类其余弹层/导入导出/策略关联以及其余模块的完整验收，继续按原台账保留待验证，不能用本批通过项替代。

## 6. 后续维护与重复验证

1. 新增或调整根字段：修改 `state.ts` 与原生 domain 的具名 action/getter；沿 V2 源码核对调用参数、写入顺序及副作用。原始 visibleFields 和派生值必须分别验证。
2. 新增异步流程：传入明确的拥有者；异步 await 后不得重新取得不确定的全局 activePinia；测试两实例、Devtools 代理、取消/过期响应及 finally 清理。
3. 业务入口使用原生 hooks；Options API 的跨域映射使用函数。只要涉及模板或将 store 作为 helper 参数传递，必须覆盖这些位置。
4. 运行 `pnpm --ignore-workspace check:native-state`、状态/组件专项、全量测试和类型检查。保留失败名称，禁止静默刷新基线或忽略测试。
5. 共享状态/主题变更至少回归主应用初始化与查询、聚类、APM/Trace 构建及宿主夹具。TDesign 弹层必须检查 Teleport 后的 class、默认类合并、按钮顺序、宽度、层级、焦点与外部关闭。
6. 在相同数据、时间和视口下记录默认/打开/草稿/确认/取消/错误状态，分别登记业务和视觉结论。真实写入仅操作专门新建的测试资源。
7. 本批证据位于 `analyze-info/runs/implementation-20261112-03/`。可执行其中 `verify-state-operation-parity.mjs` 对当前状态操作与本批前快照重复核对；有意变更业务逻辑时需新增接受记录，不能直接覆盖历史快照。
