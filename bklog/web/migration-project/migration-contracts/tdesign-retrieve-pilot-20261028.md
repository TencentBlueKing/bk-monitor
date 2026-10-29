# 检索基础控件替换契约（2026-10-28）

本批使用 V2 `src` 中同路径文件作为唯一业务依据，修改落在 `packages/web-v3/src-native`。所有模块仍处于待完整验收状态；下列通过项仅代表相应用例。

## 新建收藏

依据：`views/retrieve-v2/search-bar/components/bookmark-pop.vue`。

保留全部 props：sql、addition、searchMode、extendParams、activeFavorite、matchSQLStr、commonFilterAddition。保留 refresh、save-current-active-favorite、instanceShow 事件及其载荷；保留私有/公共/未分组选择、组名/收藏名校验、创建分组、保存当前收藏、另存为、取消和打开时焦点恢复。

API 保持 favorite/createGroup、favorite/createFavorite。普通/联合索引、场景字段与表条件、IP chooser、公共筛选、SQL、图表扩展参数、APM scope 仍按原代码生成。对 V2 源脚本和新脚本执行同一组模拟输入，比较完整请求序列与载荷。

UI 使用 TDesign Popup、Form、FormItem、Input、Textarea、Select、Option、Button。手动打开与外部关闭独立控制，Select 的 panelBottomContent 承载原新增分组区域。原 validate 成功 Promise 转为 TDesign validate 结果必须为 true 才继续；错误列表不能当作成功。分组创建/收藏成功后的父事件和清理仍按源码执行。

已验证：五类请求载荷对照；非法表单不发出请求；未选组时使用未分组；取消清草稿和父通知；真实浏览器打开、输入、失焦必填反馈、分组列表、新增分组编辑区、取消。真实创建与保存未执行，保留待验证。

## 添加到仪表盘

依据：`views/retrieve-v2/search-result-tab/components/dashboard-dialog.vue`。

保留 isShow / update:isShow 协议、目录读取、目录切换时重置仪表盘、目录/仪表盘行内新增、并发保存保护、UI 查询编译、SQL 原文、保存图表和成功后的监控外链。保持原 API 与 dashboard_uids/index_set_id/bk_biz_id 等字段。

Dialog 的 header、visible、close-on-overlay-click、closed 对齐原标题、受控显隐、禁止遮罩关闭及关闭后清理。Select 搜索保留 tiny-pinyin 1.3.2 的全文拼音、首字母、大小写和空搜索语义；不能仅替换成默认文本过滤。输入与新增按钮保留原操作处理函数。

已验证：UI/SQL 两条保存请求与 V2 源脚本对照；目录/仪表盘创建请求与清理对照；错误列表阻止提交；中文/拼音/首字母过滤；浏览器打开标题、三项必填校验、取消。真实写入、成功外链与权限分支仍待隔离资源验证。

## 排序字段与结果选项

依据：`views/retrieve-v2/result-comp/update/table-sort.vue`、`views/retrieve-v2/components/result-storage/index.tsx`。

保留排序字段过滤、重复字段禁选、顺序、添加/移除、shadowSort 暴露协议及父级保存/取消。Vue3 Draggable 使用 item slot 和稳定 key，专用依赖别名 vuedraggable-vue3 指向官方 vuedraggable 4.1.0；其他尚未迁移的源组件继续使用原依赖，防止共享版本切换导致显示字段列表报错。该旧依赖仍需逐项退役，不能算完成。

保留显示行号、换行、联合索引来源、展开长字段、JSON解析/深度、空字段、时间格式化及场景采集项显示的原状态键和事件。Checkbox 显式映射 checked/change；更多选项改为 Popup content slot，避免旧 JSX slot 属性让全部菜单内容直接泄露到工具栏。排序切换仍使用原查询和事件链，未增删请求。

已验证：排序字段排除/禁选/顺序与 V2 源脚本对照；Vue3 proxy 初始值可复制且不会修改调用者；浏览器显示字段列表回归，行号开关可勾选并恢复原值。排序真实保存、拖拽、其余持久化选项仍待验证。

## 趋势与日志分级

依据：`views/retrieve-v2/search-result-chart/index.tsx`、`components/monitor-echarts/components/grade-option.tsx`。

保留趋势状态机、轮询、取消、过期响应保护、聚合周期、折叠、缩放与还原、分级数据读取和配置保存。周期选择改为 TDesign Select。分级的 Form、Select、Switch、RadioGroup、Radio、Input、Button 和消息服务改为 TDesign；可创建的字段值以原 fieldValue 数组为准，已有值仍进入选项集合。六级加 others 的全部默认配置和正则保留。

已验证：分级完整请求与 V2 源脚本对照，非法校验不提交，取消重置与事件载荷一致；趋势空态和标题在浏览器可见。原 FormItem 的 tooltips 错误展示与图标偏移尚未完整对齐；当前保留校验规则与提交阻断，视觉待修复。自定义字段值创建、分级真实保存、非空趋势及全部周期仍待验证。

## 全局基础与 JSX

- 应用/检索入口的异步组件工厂改为 defineAsyncComponent；路由工厂保持 Router 原有语义。
- 在索引选择、查询输入和导航等本批引用链上，将实际 JSX 节点的 scopedSlots、单属性插槽展开对象及 on-xxx 属性改为 Vue3 语法；保留回调表达式、字符串和注释。混合旧 props 展开不自动猜测，保留人工分析。
- 官方 Vue3 日期选择和 TDesign 控件在临时兼容宿主中明确原生组件语义，防止 modelValue/update:modelValue 被改成 value/input；原生 Vue3 环境不执行 TDesign 兼容宿主分支。
- Vue3 Translation 适配原 i18n/path、默认 span、locale 及 VNode 插值，恢复趋势标题等正文。SSR 验证中文、英文、VNode、缺省占位及标签。
- 顶部下拉菜单改为 TDesign Popup，用户信息改为官方 login-userinfo Vue3 发行入口。菜单、权限和原操作函数保持不变。
- fl/fr 来自 V2 基础样式，改为应用持有；只提取并固化原 bk-icon 字体资产，附 MIT 许可证和来源校验值，不引入旧组件代码和整套组件 CSS。
- 公告请求 /notice/announcements/ 补充后端代理，保持原 URL；已验证 HTTP 200 application/json，不再落入 Vite SPA HTML 回退。

## 验收边界

本批自动测试32项通过，涵盖源脚本差异对照、响应式/事件、Worker、加载时序、表单和插值。浏览器样例为40676真实空态；还未固定绝对时间/响应，所以截图仅用于布局定位，不能作为完整视觉门禁。非空38131、权限、写入、APM/Trace/场景端到端均未完整验收。

4175 仍是 @vue/compat 诊断入口。原生 build:native 仍被 masking-setting.tsx 的 Vue2 class 装饰器阻塞。最新静态检查303项候选、170个文件、0解析错误；候选数量不是功能完成率。所有完整模块 businessAccepted/visualAccepted 继续为 false，禁止 V2 退役。
