# 实施记录 09：场景联想 loading 滚动条闪动

日期：2026-11-12。用户反馈主机场景 IP 联想 loading 期间纵向滚动条反复出现、消失。运行截图、几何采样、临时复现源码及构建日志只存放在仓库外本地归档 `runs/implementation-20261112-09/`。

## 复现及根因

真实页面使用 TDesign LoadingDirective，挂载结构为 `.field-suggestion-dropdown > .t-loading--full > svg.t-icon-loading`。初始空下拉 clientHeight 约 49px，旋转 SVG 的尺寸约 36px。圆形 loading 处在旋转的方形 SVG 中，旋转后布局溢出边界会放大到对角线尺寸。

本地合成复现页直接复用实际业务 SCSS 和原生 LoadingDirective，不请求任何接口；持续 loading 采样 782 帧后，`scrollHeight - clientHeight` 最小 0、最大 1px。自动滚动条因这 1px 周期性溢出反复显示，与用户现象一致。没有证据表明这是请求反复触发，本批不改请求、防抖、取消、分页或选项业务。

## 局部修复

文件：`packages/web-v3/src/features/retrieval/workspace/search-bar/scene-filter/filter-panel.scss`。

仅在 `.field-suggestion-dropdown` 内，对直接子 loading 遮罩 `.t-loading--full` 设置 `overflow:hidden`，裁剪旋转 SVG 的布局溢出。保留外层列表的 `overflow-y:auto`、最大高度和全部滚动加载逻辑。没有隐藏整个下拉滚动条，没有停止动画，也没有调整接口参数或请求时序。

## 实测结果

- 持续 loading：3568 帧，clientHeight/scrollHeight 均为 49，溢出最小/最大均为 0。
- 空结果：clientHeight/scrollHeight 均为 49，无多余滚动。
- 两条合成结果：clientHeight/scrollHeight 均为 72，无多余滚动。
- 30 条合成结果：clientHeight=308、scrollHeight=968，溢出固定 660；浏览器滚轮实际滚到 scrollTop=660，正常滚动没有被禁用。

这些是相同样式和指令的隔离几何验证，不替代后端慢请求、真实空结果及真实分页接口全链路验收。真实页面的 host/IP 联想 DOM 已检查，与复现挂载结构一致。原始采样见本地 `geometry.json`，截图 `loading-stable.png`；临时 HTML/TS 已移出 src，保存在本地 `fixture/`，不进入生产源目录或 Git。

## 后续快速回归

1. 将本地 fixture 两个源文件临时放入 V3 src，使用本地 Dev 打开 `/scene-loading-local.html`。复现页只使用合成文本，不抓取或保存实际接口。
2. 在持续 loading 模式跨越多个完整动画周期观察几何采样，maxOverflow 必须为 0；不能用一张静态截图证明动画稳定。
3. 分别切换 empty、short、long。前两种无滚动，长列表应真实滚动到末项，防止通过隐藏整个列表滚动掩盖问题。
4. 在真实场景检索检查 loading 的实际挂载节点是否仍是该直接子级；Loading/Popup 或组件库版本升级后重新检查，不能只沿用旧选择器。
5. 验证完成后将临时复现源移回本地归档，再执行构建，避免临时测试页进入产物或影响源码摘要。

本批仅 CSS 溢出裁剪，不新增与实现相同的单元测试、不重复运行不覆盖动画布局的逻辑测试。主应用、APM、Trace 构建及资源检查均通过，结果及源摘要仅保存在本地 summary.json 和日志；此前全量测试与类型检查未通过项保持待处理，不因本次 UI 修复更改结论。
