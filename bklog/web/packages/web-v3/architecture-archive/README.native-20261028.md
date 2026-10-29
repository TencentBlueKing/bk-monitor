> 2026-10-28：本文件保留为 src-native 升级阶段的历史记录。当前主应用已按架构迁移到 src，默认 dev:ui 使用 src；对照请使用 dev:baseline（4177）。当前启动及验证以 [README.md](README.md) 为准。

# src-native 启动与测试

本阶段按用户最新要求，以本地 Dev 和 V2 浏览器对照完成 Vue3 页面主题及交互对齐；保留兼容宿主中的 Class 组件，无需先全量迁移 V2 class。业务依据仍为 `bklog/web/src`，目标目录为 `src-native`。

从仓库根目录启动当前 UI 测试入口：

```sh
pnpm --dir bklog/web/packages/web-v3 --ignore-workspace dev:ui
```

地址：http://appdev.woa.com:4175/#/retrieve/40676?spaceUid=bkcc__5000140&bizId=5000140

`dev:ui` 与 `dev:migration` 使用同一配置，基于 Vue3 的 `@vue/compat` 宿主运行现有组件。页面标题为“日志平台 · Vue3 UI 对齐”。4173 是此前原型，不属于本轮对照入口。

```sh
pnpm --dir bklog/web/packages/web-v3 --ignore-workspace test:native
NODE_OPTIONS=--max-old-space-size=6144 pnpm --dir bklog/web/packages/web-v3 --ignore-workspace build:ui
```

当前65项测试覆盖事件、状态、Worker、Loading、收藏/仪表盘/分级请求、排序和插值契约，不代表全量功能验收。主题集中在 `src-native/scss/theme/tdesign-bklog.scss`，映射 V2 调色、文字、尺寸、边框、圆角及加载指示器，避免复制整套 V2 控件 class。日期选择保持官方 `@blueking/date-picker` Vue3 版本。

`dev:native`（4174）、`build:native` 和 `check:native` 保留用于后续移除兼容层的检查；当前纯原生构建仍存在旧 class 装饰器问题，不作为本阶段 UI 对齐的准入条件。兼容宿主可用不等于全量业务已验收，尚不允许退役 V2。

修改 `migration-runtime` 后使用 `dev:ui --force` 更新预构建缓存。两套配置分别使用独立缓存，均以 `src-native` 为根目录。API代理保留 `/api/*.js` 源文件请求并包含公告 `/notice/` 路径。

组件替换记录见 `../../migration-project/TDesign组件替换分析与执行.md`。本批证据见 `../../migration-project/artifacts/verification/2026-10-28/ui-theme/`。Dev日志为 `/tmp/bklog-migration-vite-current.log`，构建和测试日志为 `/tmp/bklog-ui-build.log`、`/tmp/bklog-ui-tests.log`。

全业务对齐首轮记录见 `../../migration-project/migration-contracts/full-business-regression-20261028.md`。65项测试覆盖新增路由包装、槽位协议、旧表格元数据、函数组件上下文、Router4桥接和原生确认服务；真实Grok资源300已完成CRUD并清理。全量业务/视觉仍未验收。

补充回归：旧控件按需CSS由V2原构建插件的全局注册入口生成引用，共58项，仅引用依赖资产，不复制整套class或计为原生组件迁移完成。业务图标CSS保持在控件CSS之后，确认导航使用bklog字体。Vue3 ConfigProvider不输出原有DOM容器，已补充实际表格布局容器；操作区域宽度恢复90px，与V2实测一致。原生确认服务沿用现有OverlayRegistry层级分配，避免被旧侧栏遮挡。旧CJS弹层测试因缺少preset-env无法直接执行，将相同16个用例改为ESM纳入test:native后，合计65项全部通过。
