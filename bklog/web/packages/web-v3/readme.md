# BKLog Vue3

活动源码仅保留 `src`，按 `app / features / platform / shared` 组织。历史快照已退役，AI-Native 只校验当前源码。

从仓库根目录启动：

```sh
pnpm --dir bklog/web/packages/web-v3 --ignore-workspace dev
```

在 `bklog/web` 中运行 `pnpm dev` 也默认启动 V3。默认地址为 `http://localhost:4175`，主机名由本地 `bklog/web/.env.local` 的 `BKLOG_DEV_HOST` 决定。代理目标与登录 Cookie 只从本地环境变量和 `.cookie` 读取，依赖按本包隔离。

## 验证与定位

- `pnpm test`：当前源码的逻辑、组件及迁移契约测试。
- `pnpm typecheck`：完整严格类型检查；仍有待修复诊断，不能当作通过。
- `pnpm check:source`：检查重复源码目录和剩余 JavaScript；JS 转换尚未完成时保持失败。
- `pnpm ai:index`、`pnpm ai:check`：生成并验证依赖图、路由与来源台账。历史快照已退役，AI-Native 只校验当前源码。
- `pnpm build`：构建主应用到 `dist`。

不要重新建立活动 `src-native` 目录。验收以当前 `src` 的测试、类型门禁和 `ai:check` 为准。

## Monitor 包

`pnpm build:apm`、`pnpm build:trace` 分别输出 `dist-monitor/apm`、`dist-monitor/trace`，校验 CommonJS 导出、CSS、Worker 和资源完整性，并记录构建快照。构建中源码发生变化或产物过期时会拒绝交付。

`pnpm package:apm`、`pnpm package:trace` 将已验证产物写入 Web 根目录的对应交付目录，保留原包名和版本，不执行发布或自动升级版本，也不再保存替换前历史快照。

本地 `http://localhost:4175/__fixtures__/monitor-host` 提供 Vue2 宿主与 Vue3 嵌入的挂载、参数更新、路由和销毁协议验证；该页仅用于开发，不包含在生产入口中。

源码职责见 `src/README.md`，AI 工作协议见 `ai-native/README.md`。

## Pinia 与 Paraglide

应用状态由 `app/state/application-runtime.ts` 定义的原生 Pinia store 管理：`useApplicationStore`、`useRetrieveStore`、`useCollectionStore`、`useGlobalsStore`。新业务直接调用 store 的具名方法；保留的 `commit/dispatch/mapState/mapGetters` 仅是旧业务与 Monitor 协议适配，不维护第二份状态。

国际化采用官方 Paraglide Vite 插件，配置在 `project.inlang/`，中英文词条在 `src/platform/i18n/messages/`。`pnpm i18n:compile` 生成忽略提交的 `.paraglide/`；测试、类型检查及 Vite 构建会自动编译。新代码可静态导入 `#paraglide/messages.js` 中的具名消息函数；既有中文键通过 `legacy-message-keys.json` 映射到稳定消息 ID，富文本继续使用 `SourceTranslation` 保留 Vue 节点和事件。

`vuex`、`vue-i18n` 仅保留为开发依赖，活动源码不再导入。历史快照已退役，AI-Native 只校验当前源码；词条直接维护 `src/platform/i18n/messages/`，再运行 `i18n:compile`。生产构建使用 8GB Node 堆上限；当前动态兼容词条表保留全量消息，尚未完成体积优化。

开发测试页 `/__fixtures__/state-i18n` 仅操作内存，覆盖 Pinia 查询、错误恢复、双语富文本、TDesign 语言及官方时间选择器。
