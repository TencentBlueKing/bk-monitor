# 业务 SDK 的 Vue3 入口迁移

## 分析范围与依据

核对 V3 源码、实际安装包的 package.json、exports、声明、ESM 实现及构建模块图。按安装版本判断入口，不以包名或文档中的通用示例推断 Vue 版本。不修改 node_modules，也不修改 V2 应用及封版 V1 产物。

运行日志、模块图明细和构建产物仅保存于仓库外。本文不记录环境参数、接口数据、业务截图或人员信息。测试使用从零构造的 synthetic 用户。

## 入口结论与实施

- `@blueking/ai-blueking`：安装版默认入口是 Vue3；业务原来显式引用 `/vue2`。改为默认入口及 `dist/vue3/style.css`，保留请求钩子、引用、快捷指令、打开关闭、尺寸和位置控制。
- `@blueking/bk-user-selector`：统一显式引用 `/vue3`。原租户人员选择器保留原有租户参数和接口。
- `@blueking/user-selector`：安装版没有 Vue3 入口，不能通过增加路径完成升级。八处旧调用改为项目内 `shared/ui/user-selector/legacy-contract.tsx`，底层使用官方 bk-user-selector Vue3 实现；移除 V3 的旧包依赖和对应锁记录。
- `@blueking/date-picker`：隔离入口及类型引用显式使用 `/vue3`；继续保留原生 Vue3 island 和原时间选择逻辑。
- `@blueking/login-userinfo`：显式使用 `/vue3`，保留原用户菜单行为。
- `@blueking/ip-selector`：删除项目复制的 Vue2 包装实现，调用官方 `dist/vue3.x` 工厂。保留其 props、事件、暴露方法、卸载处理和 dialog 高度处理。回调 ref 将真实根节点交给官方 setup，避免兼容运行时无法回填字符串 ref。
- `@blueking/notice-component`：默认 ESM 已为 Vue3，保持默认入口。
- `@blueking/bk-user-display-name`、`login-modal`、`open-telemetry`、`platform-config`：按各包现有工具函数或自定义元素入口使用，没有虚构 `/vue3` 子路径。
- `@blueking/bkui-library`：提供运行时能力，不是 `bkui-vue` UI 组件库；V3 业务没有需要切换的直接运行时引用。
- `@blueking/log-web`：当前主应用只使用清单信息，旧检索运行于封版 V1 静态入口。该安装版本没有可直接替换的 Vue3 检索实现；不破坏 V1 封版边界。

重要限制：IP 选择器官方 Vue3 工厂内部仍加载其 Vue2 实现及配套 CSS。这是安装包实现边界，不能据此声称消除了全部 Vue2 运行时。替换这部分需要上游提供原生实现或另立完整业务重写任务。

## 保留旧人员选择契约

旧业务采用用户名数组及目录 JSONP，新的组件默认接口和 change 载荷不同，不能直接修改 import 后交付。

边界组件保留：

- 原目录 API、非租户目录模式、多选默认值；单选仍回传旧数组形态。
- 受控 value/modelValue、input/change/update:modelValue、remove-selected；不直接修改父组件数组，不把用户对象作为用户名提交。
- 已选用户回填、原用户名与展示名顺序、域显示、头像、锁定标签及固定高度。
- Enter 校验、粘贴批量查人、每批最多一百个用户名、去重及顺序；卸载和后续输入取消过期校验。
- 外部聚焦、禁用时阻止键盘焦点与变更、失焦事件单次回传。新 SDK 的空搜索分支缺少外部失焦，使用容器 focusout 补齐，避免丢失原编辑保存触发。

目录请求不引入新的后端协议。批量限制通过限定于安装包 Vue3 入口的构建转换实现，并有基于实际包函数的回归测试；不修改安装包文件。升级 SDK 时需复核转换锚点和回归用例。

## Vue3 与兼容运行时边界

当前应用仍使用兼容运行时。全局启用的旧 v-model 转换即使遇到局部 MODE:3 仍可能生效，浏览器已复现 modelValue 被转成 value、已选用户无法回填。

统一在 `platform/compat/native-sdk-vue.ts` 显式关闭旧 model、render 和属性转换；构建转换覆盖官方 Vue3 SDK 的 defineComponent 与编译后的私有 SFC options。限定作用范围，不关闭旧业务组件所需的全局兼容能力。

AI Vue3 产物新增的 `bkui-vue/lib/form`、`lib/select` 默认导出和具名导出分别由专用 TDesign 边界承接；补齐 SDK 使用的 tooltip 指令。此举只服务第三方包内部的原名调用，不将业务组件改回旧组件库。

AI 声明与实际产物存在两个差异：自定义快捷指令方法声明要求持久化命令字段，而实际实现支持既有 components 指令；请求钩子声明使用 header，实际 fetch 使用 headers。项目边界按实际源码保留原契约，不补造后端字段。

## 验证与复验方式

1. 运行 SDK、DatePicker、IP、人员选择契约测试，覆盖受控值、事件、回填、批量限制、取消、禁用和编译 SFC 的兼容配置。
2. 启动 V3 后打开 `/__fixtures__/sdk-vue3-contract`，仅使用本地合成目录。验证首次回填、键盘输入及 Enter、删除标签、不可删除标签、外部失焦和禁用焦点保护；不向真实目录发送合成用户名。
3. 全量运行现有测试，失败项与本批开始前的基线逐项对照，不能将既有失败当作通过。
4. 严格类型检查按文件、错误类型和内容比较，排除行号位移，禁止仅凭错误总数下降判断通过。
5. 分别构建主应用、APM、Trace，使用构建校验工具检查入口、样式、worker、资源和源码摘要。
6. 检查主应用及 DatePicker island 的实际模块图：旧 user-selector 应为零，AI 不应出现 dist/vue2，不能包含原始 bkui-vue 或 bk-magic-vue 模块；IP 内部 Vue2 按上述例外单独记录。

浏览器已验证人员选择合成闭环；真实检索页面可挂载 AI 容器且无 Vite 错误遮罩。本批没有向真实 AI 服务发送日志或执行配置写入，不能将容器挂载等同于所有 SDK 业务链路验收通过。

本批验证结果：

- 主应用、APM、Trace 构建通过；两个 Monitor 产物均通过八项公开导出、样式资源、worker 和源码摘要校验。
- 主应用模块图中旧 user-selector 为零、AI Vue2 模块为零、AI Vue3 模块为 46；主应用及 DatePicker island 的原始 bkui-vue/bk-magic-vue 模块均为零。第三方内部原名调用仍经过 TDesign 适配边界，不能将此结论解释为已无适配层。
- 封版 V1 的 215 个静态文件交付校验通过；清单 runtimeAccepted 仍为 false，未升级为运行验收通过。
- 严格类型错误为 1566 条，对比本批之前的 1567 条，排除行号变化后无新增诊断；项目严格类型检查整体仍未通过。
- 全量测试仍存在六项基线失败：入口契约、端点基线、路由基线、全业务门禁、JSX 契约和原始日志时间列测试。四项与本地缺失入口相关，两项与基线漂移相关；本批没有掩盖这些失败。
- 第三方边界审计无违规；AI 源码索引校验通过。diff 空白检查通过。测试及构建没有改动 V2 目录。

本批状态：入口迁移和局部契约验证完成；全业务验收仍需逐入口验证，IP 原生化及封版 V1 保留明确边界。
