# 实施记录 12：条件联想 Loading 连续显示

## 复现与根因

常规检索 → 添加条件 → 选择 keyword 字段 → 骨架屏显示期间切换到另一个字段，原先可能出现 Loading、弹层短暂消失、结果重新出现。

字段行点击会先执行 `handleFieldItemClick`，随后冒泡到 `handlePanelClick`。前者更新字段并保留/打开条件值弹层，后者却将同一次字段点击当作面板空白点击，调用 `hide(100)`。异步请求成功的回调再重新打开弹层，形成中间断档。真正的请求耗时与 300ms 请求防抖并不是本次需要删除的逻辑。

## 实施

文件：`packages/web-v3/src/features/retrieval/workbench/search-bar/ui-mode/ui-input-option.vue`。

1. 面板点击与原有 document 点击采用相同的字段列表区域判断。字段列表点击不再触发空白关闭，条件值输入/下拉区域仍保持原来的判断；面板空白点击继续关闭。
2. 字段切换后的 nextTick 主动清理上一轮关闭定时器。已打开的弹层直接保留，仅更新 Loading 和结果内容。
3. 字段请求回调在 Vue nextTick 后更新弹层位置，避免按旧内容尺寸计算。
4. 保留请求防抖、接口及参数、数值/操作符校验、选择、输入、取消、Esc、外部关闭规则。V2 不修改；24px 骨架项、父级等宽和整行选中背景继续沿用实施记录 11。

## 验证

本段具体业务环境与运行记录已移至仓库外本地归档；复验须提供本地授权测试上下文。
- 在已有结果弹层开启时切换字段，连续进行 480 次 DOM 显示状态采样，覆盖约 1693ms。
- 状态变化：16ms 仍为旧结果，44ms 为 Loading，910ms 为新结果。Loading 出现后采到的 missing 状态为 0，未出现中间关闭。
- 回归测试新增“字段点击冒泡不关闭 Loading，面板空白仍关闭”：真实组件脚本在字段点击和 document 点击后均不得调用 hide，空白点击应调用 hide(100)。旧处理会在该用例中失败。
- UI 条件及 Loading 针对性测试 8/8；全量测试 416 项中 410 通过、6 项既有失败（migration-engine 入口缺失及 V2 固定基线漂移）。严格类型仍为 1566 条既有错误。
- 主应用生产构建及封版静态交付检查通过；APM、Trace 构建及产物核验通过。Monitor 生成文件已归档并还原。AI Native 依赖图已更新并检查通过。

## 后续快速复验

1. 添加条件，选择有联想接口的字段，等待首次结果。
2. 保持弹层开启，连续切换不同 keyword 字段；从骨架到结果不应发生 hide/show。
3. 保留输入焦点，输入筛选词；检查请求和结果转换，不能为了消除闪烁取消既有请求防抖。
4. 点击字段列表不应误关闭值列表；点击面板空白、取消及原有关闭入口仍应关闭。
5. 网络返回空值或失败时，骨架结束后展示原有空态，不永久保持 Loading。

```sh
node --test tests/ui-condition-parity.test.mjs tests/loading-contract.test.mjs
node --test tests/*.test.mjs
pnpm --ignore-workspace typecheck
pnpm --ignore-workspace run build
pnpm --ignore-workspace run build:apm
pnpm --ignore-workspace run build:trace
```

本批截图、DOM 状态采样和构建/测试日志仅保存于仓库外 `/private/tmp/bklog-v3-dropdown-continuity`。状态采样只记录相对时间及 loading/results/missing，不把真实接口数据加入仓库。
