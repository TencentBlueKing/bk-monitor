# Vue3 主应用源码

实际入口为 `src/index.html → main.js`。默认 `dev`、`build`、`dev:ui`、`build:ui` 均使用此目录；不通过别名、软链接或回退加载 `src-native`。

- `app/bootstrap`：先注册业务服务定义，再启动应用；`configure-app.js` 统一安装现存控件、指令和插件，保留顺序。
- `app/router`、`app/state`、`app/shell`：应用级路由、全局状态与根视图。
- `features/<domain>`：业务页面、专用组件和后端服务定义。`retrieval/classic`、`workbench`、`workspace` 是业务实现代际，运行时都采用本包 Vue3 升级链路；不能用文件夹名称推断 Vue 版本。
- `platform/http`：认证、空间头、请求队列、错误与服务查找；领域服务由 `app/bootstrap/service-definitions.js` 装配，传输层不直接依赖业务页面或聚合领域服务。
- `platform/compat`：集中放置 Vue 兼容运行时与控件契约适配。`@blueking/date-picker` 保持官方 Vue3 组件；剩余 `bk-magic-vue`/Class 组件兼容是显式债务，不能据目录归档声称完成原生改写。
- `platform/persistence`、`i18n`、`observability`：缓存/Worker、语言与监控协议。
- `shared`：暂无法归属单一业务域的 UI、hooks、样式、资源和公共工具。现存跨域依赖记录于 `ai-native/boundary-debt.json`，新增依赖需评估，不能扩大耦合后直接更新基线。

业务行为以原组件源码、现有测试和真实页面为准。来源对应关系见 `../ai-native/source-map.json`。

维护前先从包目录运行 `pnpm --ignore-workspace ai:context --module=retrieval --limit=30`；变更后运行 `ai:impact`、`ai:index`、`ai:check`、`test`、`build`，并验证相关页面。命令及限制见 `../ai-native/README.md`。
