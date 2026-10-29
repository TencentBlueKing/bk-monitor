# P0 范围与目标

任务：[【日志前端】AI Native Web开发探索（AI Migration Engine）](https://tapd.woa.com/tapd_fe/10158081/story/detail/1010158081139460519)

- TAPD：`1010158081139460519`（短 ID `139460519`）
- 分支：`feat/ai-migration-engine/#139460519`
- 本轮阶段：P4 只迁移采集步骤里已从源码核对的状态。P0、P1、P3 已完成。P2 没有登录后截图。

## 优先级

1. 业务保真：已有行为、数据流、事件、校验、权限和异常处理不能在后续迁移中无故丢失。
2. UI 保真：以后以旧版真实运行效果为基准，不在本轮设计新 UI。
3. 可持续 AI 化：先把可复核的工程事实留下，再进入分析和迁移。

## 本轮做

- 确认 Vue2 源码、Vue3 目标目录、工具链和启动命令。
- 用 Node `26.12.1` 复核旧版开发构建能否编译。
- 记录另一分支上已有、但未并入本分支的 Vue3 成果。
- 留下可重复执行的路径检查：`node migration-project/check-baseline.mjs`。

## 本轮不做

- 不把登录后页面截图写成基线。P2 的运行时采集仍阻塞。
- 不迁移整页采集向导，不改 Vue 2 业务源码。
- 不把 `feat/ai-native-web-v3/#139386759` 的实现合并进本分支。该实现未在本单验收，不能当作正确基线。

## 仓库位置

同一 Git 仓库，不是两个独立仓库。

| 角色 | 路径 | 本分支事实 |
| --- | --- | --- |
| Vue2 源项目 | `bklog/web`，业务源码在 `bklog/web/src` | 与 `upstream/master` 一致 |
| Vue3 目标 | `bklog/web/packages/web-v3` | 独立 pnpm 包，Vue 3.5.44，含 TDesign 适配和采集步骤状态试点 |
| 已发布前端包 | `bklog/web/packages/web-v1` | 包名 `@blueking/log-web`，不是本次 Vue3 目标 |
| 迁移工作区 | `bklog/web/migration-project` | 本轮新建，不搬动业务源码 |

## 迁移范围

- 必须迁移的业务入口：检索、监控、仪表盘、管理。路由聚合在 `bklog/web/src/router/index.js`，默认路由名是 `retrieve`。
- 必须保留的自定义业务组件：具体清单留到 P1。本轮只确认它们位于 `bklog/web/src`，不能按组件名猜测行为。
- 计划替换的基础组件库：源为 `bk-magic-vue@2.5.10-beta.15`，目标为单据指定的 [TDesign Vue Next](https://tdesign.tencent.com/vue-next/getting-started)。TDesign 适配留到 P3。
- 包管理：`bklog/web` 使用 pnpm workspace，成员只有 `packages/web-v3`。该包依赖 Vue 3。根包继续使用 Vue 2。`packages/web-v1` 不加入 workspace，避免同名包 `@blueking/log-web` 覆盖根依赖。
- 可以保留、但尚未验收的成果：分支 `feat/ai-native-web-v3/#139386759`（TAPD `1010158081139386759`）相对主干的 `bklog/web/packages/web-v3` 有 211 个文件、约 17692 行新增，声明依赖 Vue `^3.5.13`、Vue Router `^4.5.0`、`tdesign-vue-next@^1.18.0`、Vite `^6`。
- 已知缺失：本分支没有可运行的 Vue3 应用；登录后的旧版页面访问本轮没有执行。

## 关键未知项

- 另一分支的 Vue3 页面哪些行为与旧版一致，尚未对照源码和运行结果。
- 旧版关键页面在登录态下的真实 UI，本轮没有打开。
- `bklog/web/src` 的组件、Vuex、接口和样式耦合清单属于 P1。
