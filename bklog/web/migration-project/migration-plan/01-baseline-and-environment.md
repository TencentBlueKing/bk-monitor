# P0 基线与环境

证据基准：分支 `feat/ai-migration-engine/#139460519`，起点 `upstream/master`（`5e1c8e820e8c`）。`bklog/web/src` 相对该提交没有差异。

## Git

- 创建前工作区干净。原分支是 `feat/ai-native-web-v3/#139386759`，短 ID 与本单 `139460519` 不一致，因此从 `upstream/master` 新建本分支。
- 切换后仍可见未跟踪目录 `bklog/web/packages/web-v3/.ai-native/`（49 个文件，主要是另一分支留下的本地截图）。`node_modules` 和 `dist` 也还在目标目录旁。这些文件不属于主干，本轮不删除、不纳入迁移基线。
- 用户在切换前没有未提交的业务修改。

## 工具链

命令在 `bklog/web` 下执行。Vue 2 根包继续用 npm 和 `package-lock.json`。pnpm workspace 清单是 `pnpm-workspace.yaml`，成员只有 `packages/web-v3`。不要在 `bklog/web` 执行 `pnpm install`：那会把根 `node_modules` 换成 pnpm 布局，并使 `vue-loader@15` 用上 Vue 3 的 `@vue/compiler-sfc`，旧版 webpack 会编译失败。V3 的安装命令是 `pnpm --dir packages/web-v3 --ignore-workspace install`。

| 项 | 声明 | 已安装 |
| --- | --- | --- |
| Node | `.nvmrc` / `engines.node` = `26.12.1` | 本机 nvm 有 `v26.12.1`；交互 shell 默认是 `v24.21.0` |
| npm | — | 配合 Node 26 时为 `11.20.0` |
| Vue | `v2-latest` | `2.7.16` |
| Vue Router | `3.6.5` | `3.6.5` |
| Vuex | `3.6.2` | `3.6.2` |
| bk-magic-vue | `2.5.10-beta.15` | `2.5.10-beta.15` |
| @blueking/bkui-library | `0.0.0-beta.5` | 未在本轮单独核验安装树 |
| @blueking/bkmonitor-cli | `^7.0.1` | `7.0.3` |
| 构建 | `webpack.config.js` + bkmonitor-cli | 开发编译见下方 |
| 目标组件库 | TDesign Vue Next | P3 再接入。V3 包当前依赖 Vue 3 与 Vue Router 4 |
| workspace | pnpm `10.32.1` | 只管理 `@bklog/web-v3`。根目录 Vue 仍由 npm 安装 |

根 `package.json` 没有 Jest、Vitest 或 Playwright 依赖。已有脚本包括 `npm run dev`、`npm run dev:e2e`、`npm run build`、`npm run lint`，以及 `.docs` 下的 smoke / e2e mock 脚本。

`bklog/web/src` 在主干上的文件约：178 个 `.vue`、311 个 `.tsx`、273 个 `.ts`、95 个 `.js`、346 个 `.scss`。路由名约 97 个，分布在 `router/retrieve.js`、`router/monitor.js`、`router/dashboard.js`、`router/manage.js`。这只是入口计数，不是 P1 依赖图。

## 旧版运行

2026-10-27 在本分支、Node `v26.12.1` 下执行：

```text
AAFE_E2E_PORT=8011 npm run dev:e2e
```

结果：

- webpack-dev-server 监听 `http://localhost:8011/`。
- 代理：`/apm`、`/rest`、`/fta`、`/api`、`/weixin`、`/version_log`、`/calendars`、`/alert`、`/query-api` → `https://bklog.bkop.woa.com`。
- `日志平台 Development模式` 在 2.39s 显示 `Compiled successfully`。
- 确认该行后已停止进程，8011 端口已释放。
- 未打开浏览器，未登录，未访问检索、监控、仪表盘或管理页面。

因此：旧版开发构建可以编译。登录后的页面可用性仍是阻塞项，见风险 `R-001`。

## 新版运行

`bklog/web/packages/web-v3` 是 workspace 包 `@bklog/web-v3`，声明 `vue@^3.5.13`，实际解析 `3.5.44`，Vue Router `4.6.4`。`pnpm --dir packages/web-v3 --ignore-workspace test` 3 项通过，`vite build` 通过。根包声明 `vue@v2-latest`，实际解析 `2.7.16`。恢复 npm 安装后，`AAFE_E2E_PORT=8011 npm run dev:e2e` 再次 `Compiled successfully`。另一分支上的完整页面实现仍未并入。

## P1 可直接使用的输入

- 源码根：`bklog/web/src`
- 路由入口：`bklog/web/src/router/index.js` 及其四个业务路由文件
- 组件库与状态：`bk-magic-vue`、Vuex `3.6.2`、Vue `2.7.16`
- 重复检查：在 `bklog/web` 执行 `node migration-project/check-baseline.mjs`
- 不要把 `.ai-native/ui-align/captures` 里的本地图片当作 P2 截图基线
