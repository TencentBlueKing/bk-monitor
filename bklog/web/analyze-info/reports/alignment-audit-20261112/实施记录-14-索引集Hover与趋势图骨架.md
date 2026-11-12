# 实施记录 14：索引集 Hover 与趋势图骨架

## 所属索引集 Hover 对照

本批对照两版的有值、空态及只读索引集标签；测试环境与资源记录仅保存在仓库外。

V2 的规则是：默认只显示灰色标签；悬停时在实际标签周围增加 4px 内容框，框色 #eaebf0、标签白色；展开后内容框为白色、蓝色边框 #3a84ff。单元格其余空白不应跟随变灰，只读仍为 not-allowed。

发现的适配差异：

- TDesign `t-select-input--borderless .t-input:hover:not(.t-input--focused)` 给整个输入区域加了 #f5f7fa 背景，超过了 V2 的实际标签内容框。
- TDesign 的多标签换行样式在有值时额外添加右侧 8px padding。V2 内容区域为 222px，V3 有值时缩成 214px，可能改变多标签换行和测量出的 Hover 范围。

修复仅落在 V3 `features/collection/current/components/common-comp/tag-more.scss` 的所属索引集自定义触发器范围：覆盖原生整格背景和额外 padding，继续由原有 TagMore 内容测量、hover/is-open 规则绘制背景及边框。其他表单选择框不受影响。

浏览器结果：

- 两版有值及空态内容区域均为 222px。
- 有值标签内容框使用 4px 包边；Hover 框 #eaebf0、标签 #fff。
- 打开后两版内容框均为白色、蓝色边框；关闭不更改选择。
- 两版只读光标均为 not-allowed。V3 不再出现整格灰底。
- 多标签原有测量/两行折叠代码不变，恢复了同等可用宽度；本批未修改已有资源来制造多标签样本。

## 趋势图独立骨架

原趋势图在页面骨架退出后使用通用 Loading：中间只有小号三条灰线，右上角另有一份 Loading，不能表达整个绘图区的布局。

在 V3 `features/retrieval/workbench/search-result-chart` 中改为复用现有 `app/skeleton/chart-skeleton`：

1. 独立加载时覆盖完整绘图区，保留原高度 dynamicHeight、标题与汇聚周期工具栏。
2. 使用柱状图骨架：40 根占位柱、原有 y 轴/网格、8 处 x 轴占位；限制密集刻度，避免形成连续灰条。
3. 取消旧中央通用指示器及右上角重复 Loading。
4. 保留真实 ECharts canvas 挂载，用绝对定位白色覆盖层承载骨架；完成后移除覆盖层，不重新创建 canvas。
5. loading/polling 复用原状态机；整页骨架覆盖期间不叠加独立图表骨架。取消、代次号、请求、轮询、空态和折叠规则不变。
6. 原 `app/skeleton/chart-skeleton` 源码不修改；本图表的间距与条宽仅在局部覆盖层中适配。

本段具体业务环境与运行记录已移至仓库外本地归档；复验须提供本地授权测试上下文。

## 测试与复验

新增 `trend-chart-skeleton-native.test.mjs`，执行真实视图状态表达式与 JSX 渲染函数，检查 loading/polling、页面骨架覆盖、动态高度、canvas 保留、ready、empty 和折叠。与原 Loading 队列、索引集单元格契约组合运行，针对性测试 7/7 通过。

全量测试 421 项中 415 通过，6 项为既有基线/缺失测试入口问题；严格类型仍为 1566 条既有错误，没有增加。主应用、APM、Trace 最终构建及对应产物检查均通过，Monitor 生成文件已归档并还原。AI Native 依赖图更新并检查通过。

复验顺序：

- 同数据、同视口比较两版索引集标签，鼠标移入标签及内容框边缘，再移到单元格空白，检查背景范围与光标。
- 打开后应为蓝色内容框，关闭后恢复；搜索/多选/只读沿实施记录 13 复验，不修改已有资源。
- 普通检索完成后再点击查询，观察独立图表 Loading，骨架应占满绘图区，标题和周期控件不跳动，不能再出现右上角迷你三条灰线。
- 等待查询完成，检查骨架退出和原图表恢复；折叠、空结果、页面级骨架覆盖分别检查。

```sh
node --test tests/trend-chart-skeleton-native.test.mjs tests/retrieve-loading-queue.test.mjs tests/collection-index-set-cell-native.test.mjs
node --test tests/*.test.mjs
pnpm --ignore-workspace typecheck
pnpm --ignore-workspace run build:apm
pnpm --ignore-workspace run build:trace
pnpm --ignore-workspace run build
```

截图和日志仅保存在仓库外 `/private/tmp/bklog-v3-hover-trend`，不提交截图、浏览器快照及真实接口数据。V2 应用源码不修改。
