# 业务组件原生 TDesign 迁移记录

目标：业务源码直接使用 TDesign 的组件、类型和事件协议；第三方 SDK 的兼容入口单独保留。不得以修改包名、导出别名或继续转接旧组件 API 认定迁移完成。官方 `@blueking/date-picker` 保持原组件。

当前结论：**实施中，未完成全量替换**。`pnpm --ignore-workspace check:tdesign` 在业务旧调用未归零前应返回失败，不允许按本批回归通过宣布旧库退役。

## 本批落地

- 505 处按钮用法直接使用 TDesign Button，转换 text/outline 变体、图标插槽、HTML 属性、主题及事件。提交按钮的业务处理函数显式调用，避免把 MouseEvent 误当作提交参数。
- 229 处选择类用法使用 Checkbox/CheckboxGroup、Radio/RadioButton/RadioGroup、Switch、Loading。保留组内选项值和独立勾选状态的区别；开关前置校验显式接收下一状态。事件按业务已有值类型收窄，没有放宽到 any。
- 120 处简单消息直接调用 MessagePlugin，保留内容、主题、持续时间和层级。17 处含结构化详情、操作按钮、截断等复杂消息契约暂未自动处理，见 `packages/web-v3/ai-native/button-feedback-migration.json`。
- 修复 76 个样式文件中的组件选择器，保留业务自定义类，避免旧按钮选择器失效或误改 `bk-button-group` 等业务类。真实检索页在 1440×900 下查询按钮为 74×50。
- 国际化移除旧控件 locale/lang 的空调用，TDesign 继续由现有 ConfigProvider 随 Paraglide 语言切换。
- 增加业务调用扫描和完成检查，包括模板/TSX、服务、指令和类型声明；仅排除明确列举的兼容文件，不排除整个目录。新增代码不得重新引入已迁移控件的旧调用。

## 运行对照

参考参数：`/retrieve/16176?spaceUid=bkcc__5000140&bizId=5000140&search_mode=ui&keyword=&addition=%5B%5D&pid=%5B%22%23%22%5D&h_12=10174228&f_11=20680`。

V2 使用 8001，V3 使用 4175。本轮 V3 初始化一度返回登录页；重启本轮启动的开发服务、重新读取当前代理配置后已恢复 JSON 初始化响应，没有新增对 V2 代理的依赖。真实 V3 查询可执行且显示结果。查询后两边均规范化移除空 addition，其他业务参数逐项相同。没有修改已有业务资源。

离线验证页仅验证控件契约：实际 LogButton 提交反馈及禁用、实际 GrokModeSwitch 开关，以及选择值和单选状态。不能替代全部业务流程验收。截图和机器记录保存在 `migration-project/evidence/20261102-native-tdesign`。

## 验证与剩余工作

本批自动测试、构建、类型诊断比较和调用余额以 `packages/web-v3/ai-native/tdesign-native-migration.json` 为准。严格类型仍未通过，不能把“无新增诊断”描述成类型检查通过。

后续依次处理输入/选择、表单校验、Dialog/Drawer、表格列/选择/排序/分页、树与搜索选择器、布局及指令，再移除无业务引用的旧导出和类型声明。复杂消息及确认服务必须保留完整操作、校验和关闭语义。每类组件都必须完成源码契约转换、类型回归和真实浏览器检查后才能签收。主应用、APM、Trace 的共享依赖均需回归。

## 第二批：展示组件与文本输入

源码依据：V2 `bk-magic-vue/lib/{alert,tag,progress,badge,input}.js` 的属性、事件、默认值及 `lib/ui/{alert,tag}.css`；业务分支保留原处理函数和 API。实际下载任务另外以封版 `views/retrieve-v2/result-comp/TaskItem.tsx` 做状态及重试载荷对照。

- 原生替换 Alert 34、Tag 22、Progress 5、Badge 2，共 63 处。显式转换进度比例和标签变体；提示标题进入 message 插槽，操作节点继续保留；隐藏角标不隐藏其包裹按钮。标签关闭事件转换为原 MouseEvent，零参数回调保留原调用。
- 原生替换 86 处文本输入。保留 model/trim、maxlength、禁用/只读、图标、回车及变更处理；TDesign 的 string/number 事件在已有 string 业务边界转回字符串。
- 输入器中的数值、文本域、emoji 过滤、分组插槽和常显清空按钮契约尚未迁移；233 处调用及各自原因保存在 `ai-native/text-inputs-migration.json`，不能计作完成。
- 更新业务样式选择器并对本批标签、提示使用独立 `data-v2-display` 主题范围；第三方 SDK 不继承这组业务尺寸覆盖。Trace 对已迁移控件按 TDesign 名注册，未迁移组件仍在台账内。

### 16176 对照发现与修复

真实业务中发现：V2 聚类 Pattern 展示文本和 `#DATETIME#` 等高亮，V3 同列为空。根因为 `vue-text-highlight` 的 Vue2 `beforeMount/beforeUpdate` 和 `$slots.default[0].text` 不适用于 Vue3 插槽。

新增 `shared/ui/text-highlight` 的 Vue3 渲染，8 个业务引用改用该组件。仅复用 `vue-text-highlight/dist/component.js` 无样式注入入口的纯 computed 匹配函数，没有挂载其 Vue2 组件，也没有重新制定匹配算法。保留正则、大小写、重音、重叠/相邻区间、自定义高亮组件、样式和属性转发；样式单独加载。该纯算法依赖仍然保留，不宣称第三方包退役。

16176 的 V3 Pattern 文本和高亮已在浏览器恢复；截图 `retrieve-16176-pattern-{v2,after}.png` 留存。离线页验证输入绑定/Enter、标签关闭、提示关闭、下载失败重试及 37% 进度；实际业务资源未被编辑或删除。

### 验收边界

本批源码替换不代表 149 处业务路径均完成浏览器验收。剩余旧调用由 2678 降至 2529，仍为实施中。严格类型由 1986 降至 1977，未新增诊断，检查仍失败。最终测试和构建结果以 `ai-native/tdesign-native-migration.json` 第二批记录为准。

本轮还观察到切换聚类页签后的 pid 编码表现与 V2 不同，待进一步定位；没有据此变更 URL 协议。后续优先补齐输入复杂契约，再处理 Select/Option、Form/FormItem、Dialog/Drawer 和 Table；必须保留源校验、排序、权限和事件载荷。
