# Pinia / Paraglide 升级交付记录

日期：2026-10-29。范围为活动 Vue3 `src`、独立 Monitor 构建及本地协议验证，不代表全业务重新验收完成。

## 状态架构

- Pinia 4.1.0 为唯一状态所有者；application、retrieve、collect、globals 四个业务域由 `app/state/application-runtime.ts` 组装，平台配置和上报也已改为 Pinia。
- 原有业务 getters、mutations、actions 保留函数体和参数。`platform/state/domain-store.ts` 将它们绑定为原生 Pinia computed 和具名方法；`state-runtime.ts` 提供旧调用协议适配。没有 Vuex 实例或私有字段依赖。
- 旧 Options 组件暂由 `map-helpers.ts` 读取同一份 Pinia 状态。新代码使用 `useApplicationStore` / `useRetrieveStore` / `useCollectionStore` / `useGlobalsStore`；不得重新创建影子 store。
- 测试覆盖根与模块上下文、跨模块更新、命名空间、对象式 payload 身份、请求配置、状态替换、异步失败、订阅顺序、原生 `$onAction` 和实例隔离。

## 国际化架构

采用 [Paraglide 官方 Vite 插件](https://paraglidejs.com/vite)，设置与编译策略在 `project.inlang/`。消息源为两份 JSON；编译产物 `.paraglide/` 忽略提交，开发、构建、测试和类型检查均可重新生成。插件从本地锁定依赖加载，不需要构建时下载 CDN 模块。

每种语言 2712 个消息键。原有中文键通过稳定 ASCII ID 注册表兼容，新代码可直接导入编译后的具名函数。ID 来自源键哈希和来源标识，避免中文/符号规范化造成的生成器标识符冲突。词条来源和哈希在 `ai-native/paraglide-catalog-origin.json`，原四份英文 TS 数据已合并进消息目录，来源台账保留原始分母。

`translator.ts` 负责旧参数重载及未知键回退；`rich-translation.ts` 使用插槽节点替换占位符，保留真实 Vue 节点、链接和事件，不使用 HTML 注入。TDesign ConfigProvider 与应用语言响应式同步。原用户语言 Cookie 读取及原应用切换流程保留，内存测试不修改用户偏好。

全词条对照保留三类明确修正：上传格式中的竖线、搜索提示中的竖线、含 `@蓝鲸监控上云` 的文字按原词典字面量展示，避免旧引擎将它们解释为复数或链接语法；数字键对象参数继续按 V2 使用方式插值。其余消息按冻结词典及旧引擎进行全量对照，缺少参数按原场景留空。

`vuex`、`vue-i18n` 仅为冻结基线和词条对照的开发依赖，活动源码无导入。第三方包的内部依赖不在此结论中。官方 `@blueking/date-picker` 保留。

## 验证

- 当前源码自动测试：154/154；历史对照：65/65。
- 主应用、APM、Trace 生产构建通过；Monitor 构建校验包含国际化配置和编译工具身份，已同步到两个本地交付目录，未发布、未变更版本号。
- AI 依赖与路由台账检查通过，92 条路由声明的来源契约继续保留。
- 真实检索索引 40678：只读验证字段、趋势、结果及中文富文本统计，无业务写入。
- `/__fixtures__/state-i18n`：使用真实 Pinia、Paraglide、TDesign 和官方时间选择器，仅查询数据为内存 fixture；验证中英文、查询、失败、重试及时间回填。独立测试页全部为 Vue3 控件，因此显式启用 MODE 3，修正嵌套 SDK 控件被兼容模式解释为旧插槽的问题。
- `/__fixtures__/monitor-host`：真实 Vue2 宿主挂载 Vue3，验证 props 替换、深层更新、组件 ref 方法、Pinia 状态、Paraglide 英文、路由参数保留及销毁清理；不等同完整实际 APM/Trace 业务验收。

截图：[英文运行时](../evidence/20261029-pinia-paraglide/runtime-en.png)、[Vue2 宿主协议](../evidence/20261029-pinia-paraglide/monitor-host.png)。截图为本地 fixture，不包含真实日志。

## 尚未完成

严格类型检查仍为失败：1404 条诊断；具体 getter 类型暴露后部分旧消费者新增诊断，不能将原 1241 条结果视为本批无回归。新状态与国际化核心文件无类型诊断，但全项目尚未达标。另有 19 个独立 JavaScript 文件及部分 Vue 脚本待升级。

完整业务和实际 APM/Trace 宿主仍需分模块验收；这批测试不能替代管理表单、权限、外部版和所有日期状态的全量回归。为承载全词条动态兼容表，构建已采用 8GB Node 堆上限；未来应逐模块迁为静态消息导入后再优化体积与构建内存。不得通过删减词条或业务场景降低分母。


## 后续批次：状态契约及客户端日志列表

本批将严格诊断由 1404 条降至 1355 条（净减少 49 条），未放宽编译选项、排除文件或添加忽略指令。

- 为 Pinia 根状态的空间、收藏分组、联合索引、显示字段及非文本字段声明实际业务类型，保留初始空对象/空数组。
- 路由 addition 解析显式接受重复参数中的 null；索引分组 reduce 使用双数组元组；检索 tab 修正函数改用索引元数据类型。运行分支不变。
- 客户端日志列表添加 Task / Pagination / Creator DTO，服务响应与轮询复用相同类型；表格 props、事件与单元格回调使用业务类型。移除 emits 数组的空位，保留全部事件名。
- 表格清空筛选工具的文档类型由错误的 HTMLElement 改为其实际读取的组件 ref 结构。侧栏空数据沿原默认 null 值处理。
- 客户端日志 collection-deploy 两个组件已无严格诊断；其他模块仍待继续处理，剩余独立 JS 数量仍为 19。

自动测试 155/155 通过。新增测试执行当前与冻结源码的真实 setup/事件处理器，比较实际请求参数、创建人标签、筛选、分页、查看/克隆弹层参数和轮询清理；接口与定时器在本地替换，无后端写入。本批主应用、APM、Trace 构建及产物校验通过；两个 Monitor 本地交付目录已同步，源码身份均为 `eb52889a1e6e941a11f0f3abb87cdb52cd3e577c160514e8043c0787ae0b1ee8`，未发布。完整剩余诊断分布记录在 `ai-native/typecheck-status.json`。


## 16176 真实应用回归更正

后续 16176 对照发现：早期独立测试页显式使用全局 MODE 3，未覆盖实际兼容宿主 MODE 2 下官方时间组件的私有子组件。当前已移除测试页全局模式覆盖，改为开发预打包与生产构建共同限定到 `@blueking/date-picker/vue3` 和 `bkui-vue` 的原生组件定义适配。主应用真实时间面板已复测；不能将早期独立页通过视为当时主应用全部时间流程通过。详见 `index-16176-parity-audit.md`。
