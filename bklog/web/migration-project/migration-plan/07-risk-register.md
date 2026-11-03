# P0 风险登记

| ID | 风险 | 证据 | 处置 |
| --- | --- | --- | --- |
| R-001 | 检索页打不开可交互界面 | 登录态打开 `appdev.woa.com:8001` 的检索路由后，页面停在初始化文案。webpack 因 `@blueking/bkui-library` 缺少 `h`、`reactive` 阻止刷新 | BLOCKED。不能把这次访问写成检索或采集页视觉通过 |
| R-002 | 交互 shell 的 Node 不是项目要求版本 | `.nvmrc` 为 `26.12.1`，默认 `node -v` 为 `v24.21.0`。用 `v24` 时今天更早一次 `dev:e2e` 也能编译 | 迁移命令固定使用 nvm `26.12.1`。`check-baseline.mjs` 会报告 `nodeMatches` |
| R-003 | 把另一分支的 Vue3 实现当成已完成迁移 | `feat/ai-native-web-v3/#139386759` 有 211 个文件的 `web-v3`；本分支目标目录只有 `readme.md` | 不合并。P1 只把它列为待核验成果，逐项对照旧版源码和运行行为后再决定保留 |
| R-004 | 本地截图被误当成 UI 基线 | 未跟踪目录 `bklog/web/packages/web-v3/.ai-native/` 有 49 个文件，含 v2/v3 截图 | 不删除、不提交、不作为 P2 基线。正式截图必须在本分支可重复的运行环境里重新采集 |
| R-005 | 目标组件库只安装在 V3 包 | `packages/web-v3` 依赖 `tdesign-vue-next@1.20.10`，根包没有该依赖 | 继续用 `pnpm --dir packages/web-v3 --ignore-workspace`。不要装进根包 |
| R-006 | 旧版测试不能覆盖迁移回归 | 根包没有 Jest / Vitest / Playwright；存在 smoke 与 e2e mock 脚本 | P2 单独确认哪些脚本能对关键路径复用，不把「没有单测框架」写成「没有行为」 |
| R-007 | 同仓库里的 `web-v1` 被误认为目标工程 | `packages/web-v1` 是 `@blueking/log-web` | 目标只认 `packages/web-v3` |
| R-008 | `web-v1` 进入 workspace 后覆盖根依赖 | 根依赖 `@blueking/log-web@0.0.13`，`packages/web-v1` 同名 | workspace 成员只写 `packages/web-v3` |
| R-009 | 在 `bklog/web` 执行 `pnpm install` 会破坏 Vue 2 编译 | 一次过滤安装把 `vue-loader@15` 接到 `@vue/compiler-sfc@3.5.44`，webpack 报 144 个错误。随后用 `npm ci` 恢复，编译再次成功 | V3 只用 `pnpm --dir packages/web-v3 --ignore-workspace install`。根依赖继续走 `npm ci` |
| R-010 | 把源码状态试点写成整页迁移完成 | P4 只覆盖 `label-target-dialog.vue` 与 `container-target-item.vue` 中已核对的状态；树、弹层和登录后页面没有运行时证据 | 状态是 `NEEDS_REVIEW`。整页采集向导和视觉回归都不算通过 |
