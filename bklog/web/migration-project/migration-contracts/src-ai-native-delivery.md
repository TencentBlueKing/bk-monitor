# Vue3 主目录架构迁移交付

日期：2026-10-28。依据 [TAPD 139460519](https://tapd.woa.com/tapd_fe/10158081/story/detail/1010158081139460519) 及本项目既有迁移计划，完成 `src-native → src` 的责任域重组与默认运行入口切换。

## 实际变更

1315 个输入文件中，1310 个业务源码/资源有唯一目标位置；5 个 macOS Finder 元数据单独登记排除。`src-native` 原样保留。原 src 原型及未提交内容先完整归档，校验值见 `packages/web-v3/architecture-archive/manifest.json`。没有修改根 Vue2 业务源码。

目标分为 app、platform、shared 和 26 个业务域，共 29 个归属单元。页面、专用组件和领域 API 定义归入 features；应用层负责路由、全局状态、服务装配及插件注册。抽出 configure-app，将服务注册与 HTTP 传输层分离，避免传输层直接聚合业务域。已有全局 store 与跨域共享 hooks 的依赖不擅自改写，作为明确债务管理。

默认 `dev` / `build` / `dev:ui` / `build:ui` 使用 src。4175 已实际启动并确认加载 `src/main.js`；固定 SQL 查询返回 15 条结果。4177 保留 src-native 对照环境；临时 4176 已停止。生产输出为 dist；构建插件禁止任何 src-native 模块进入产物。

## AI Native 落地

`ai-native` 提供源码来源与摘要、29 个模块描述、3504 条静态依赖（含 263 条服务调用关系）、路由关联、任务格式、兼容依赖债务及失败记忆。

`ai:context` 提供入口优先的有界文件列表和契约位置；`ai:impact` 反向识别调用方与保守路由影响；`ai:index` 更新真实索引；`ai:check` 阻止丢文件、回引对照目录、源快照漂移、未经记录的新向上依赖、路由对象变化及图谱过期。已有 8 项静态缺失引用与源目录逐项一致，86 项动态请求/glob 需人工补充运行证据，不将其伪装为已解析。

## 验证结果

- `verify`：架构门禁、72 项测试、生产构建全部通过；最终构建 36.45 秒。测试实际加载新 src，包含原有 65 项业务/适配契约以及 7 项架构、服务定义、图谱与注册契约。
- 服务定义逐 token 对照源实现，仅规范化路径；路由源文件的 92 个 path 对象签名完全一致（包括导航目标，不等于 92 条业务路由）。业务路由台账仍为 90 条、88 条具名路由，验收状态原样保留。
- 严格 `typecheck` 未通过：相同配置下 src-native 和 src 均为 4934 条诊断。`typecheck:regression` 按来源文件及错误码比较，没有新增诊断；这不等于消除了类型债务。
- 浏览器验证检索深链、SQL/时间恢复、真实结果、历史弹层、表格模式、采集列表、归档新建表单、资源图标、取消与离开确认，补充 1280×800 检查。本轮没有提交新增、编辑或删除业务请求。
- 1440×900、同一绝对时间及 SQL 下，检索前后截图只在 x399..432、y208..231 的请求耗时文字附近不同；该比较没有遮罩。采集列表的导航展开状态不同，仅作布局/功能观察，不声称像素一致。

证据：[verification.json](../artifacts/verification/2026-10-28/src-architecture/verification.json)、[测试结果](../artifacts/verification/2026-10-28/src-architecture/tests.txt)、[类型对比](../artifacts/verification/2026-10-28/src-architecture/typecheck-regression.json)、[目标文件摘要](../artifacts/verification/2026-10-28/src-architecture/target-digests.json)。

## 后续维护

先通过 context/impact 定位原契约及影响范围，再按业务域推进类型收敛和兼容控件替换。共享组件修改须回归引用模块；动态请求关系需结合运行证据补充。独立 APM/Trace 发布、封版 V1/V2 退役及全量业务分支验收仍沿原计划执行，不能因本次目录迁移完成而自动标记通过。

启动和验证命令见 `packages/web-v3/README.md`；AI 工作协议见 `packages/web-v3/ai-native/README.md`。
