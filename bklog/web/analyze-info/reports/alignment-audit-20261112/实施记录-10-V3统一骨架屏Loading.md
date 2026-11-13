# 实施记录 10：V3 统一骨架屏 Loading

## 范围与约束

本批按“保留当前骨架屏、V3 其他 Loading 全部统一为骨架、V2 不变”实施。仅调整 V3 的加载显示入口及样式，不改变接口、查询参数、请求取消、重试、提交校验和任务状态判断。封版 V1 的 iframe 及 V2 源码不修改。

已有 `app/skeleton` 中检索页、原始日志、聚类表格、图表和 ItemSkeleton 的源码与布局全部保留；空间列表、JSON 和 Pattern 分析自己的骨架也保留。聚类表格外层保留透明阻挡层，关闭额外指示器，避免遮住内层原有 ClusteringLoader。

## 统一入口

- `packages/web-v3/src/shared/ui/loading/native.ts`：Loading 组件、LoadingPlugin 和 LoadingDirective。业务和应用初始化不再直接引入 TDesign 的这三个运行时接口。基础实现仍使用 TDesign 的延时显示、Teleport、层级和滚动锁，默认指示器改为骨架。
- `shared/ui/loading/skeleton.ts`：紧凑三行骨架。保留显式 `indicator=false` 及已有定制骨架/全屏骨架插槽。
- `shared/ui/loading/skeleton.scss`：面板、全屏、小按钮和下拉的尺寸；TDesign 内建 Table、Select、Button 等私有 Loading 的默认转圈改为骨架；Select 的传送弹层文字加载态也统一处理。
- `shared/ui/loading/_shimmer.scss`：与原有骨架相同的灰色渐变及 2.5s 动画，用于采集下发、采集状态、清洗、导出、提取、Grep 和上下文中手写的加载图标/图片/文字。
- 主应用及 Monitor 共同加载的 V3 主题引入骨架样式。SDK 桥接中的 Loading 也使用同一入口；不修改第三方包源码。样式不进入 V2 或封版 V1 iframe。

本次统一 22 个文件的运行时导入；163 处 `v-loading` 调用通过入口注册获得骨架，无需逐处改变请求状态。

指令为每个宿主保存独立实例。加载中参数变化前先销毁旧实例，false、卸载时释放实例，避免重复遮罩；继续支持布尔值、对象 `loading`、旧字段 `isLoading/title` 以及 fullscreen/inheritColor 修饰符。原有调用中的 delay、zIndex、attach、text 等保留。

## 后续新增或调整功能

1. 新增加载区使用 `@/shared/ui/loading/native`，禁止重新直接导入 TDesign Loading/LoadingPlugin/LoadingDirective。
2. 已有专用骨架优先复用；外层需要阻止点击时使用透明阻挡层及 `indicator=false`，避免再次叠加通用骨架。
3. 请求逻辑只控制原有 loading 状态；禁止为了视觉效果新增接口、改变成功/失败分支或延长业务请求。
4. 局部状态图标用公共 shimmer mixin 或 `bklog-loading-mark`；不能重新加入转圈图片、四色圆点和纯 loading 文案。
5. 小控件不扩大原有图标占位。加载下拉在 32/49px 等小容器中检查 scrollHeight，长列表仍需正常滚动。
6. 公共骨架动画支持 prefers-reduced-motion。新增弹层必须同时验证挂载、关闭、重试和卸载。

## 验证结果

- 浏览器隔离验证：公共面板、49px 高下拉区域、原生 TDesign Button/Select/Table、全屏 Loading。
- 加载区域 clientHeight=49、scrollHeight=49；不产生额外纵向滚动。连续关闭/开启后宿主只有一个遮罩。
- TDesign 默认旋转 SVG display=none，使用三条骨架；Select 弹层使用 12px 骨架，按钮保持原来的加载禁用语义。
- 加载结束后宿主遮罩=0、公共骨架=0；全屏定时关闭后全屏实例=0。
- 全量测试 414 项：408 通过，6 项失败。原来缺失的 loading-contract 测试已替换为实际新入口的生命周期测试。其余失败仍是 migration-engine 测试文件缺失及 V2 固定基线漂移，未跳过或伪造通过。
- 严格类型检查仍有 1566 条既有错误；本批公共 Loading 新入口没有类型错误。
- native-state 审计扫描 929 个文件，0 违规。
- 主应用生产构建及封版静态交付检查通过；APM、Trace 构建及 Monitor 产物检查均通过，最终两个 Monitor sourceDigest 一致。生成的 dist-monitor 文件已归档并还原，不混入源码变更。
- AI Native 依赖图已更新，检查通过（1395 文件、4582 依赖边）。
- 上述局部浏览器验证不代表全业务验收。

## 可重复执行

在 `bklog/web/packages/web-v3` 使用仓库配置的 Node 版本执行：

```sh
node --test tests/*loading*test.mjs
node --test tests/*.test.mjs
pnpm --ignore-workspace typecheck
node tools/native-state-audit.mjs
pnpm --ignore-workspace run build
pnpm --ignore-workspace run build:apm
pnpm --ignore-workspace run build:trace
```

`loading-contract.test.mjs` 同时扫描 V3 业务运行时导入，防止重新绕开公共骨架入口，检查旋转图片和四色圆点回流。其他 loading 用例继续核对原来的请求拥有者、finally 清理及状态分支。

截图、控制台/测试日志及隔离验证页只保存于仓库外本地目录 `/private/tmp/bklog-v3-loading-verification`；禁止提交截图、真实接口数据或浏览器快照。验证页已移出业务源码，生产构建不携带此页面。
