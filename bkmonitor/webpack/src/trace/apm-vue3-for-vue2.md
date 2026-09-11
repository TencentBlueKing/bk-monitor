# @blueking/apm-vue3-for-vue2

> 把蓝鲸监控的**告警中心**与 **Trace 检索**（`src/trace`，Vue3 + TSX 工程）打成可嵌入的 Vue3 子应用，
> 供 **Vue2 宿主**（APM 等）在自己的页面里挂载，无需整站迁移到 Vue3。
>
> 如果你的工程本身是 Vue3、只想复用单个组件（检索筛选、PromQL 编辑器、图表等），
> 请改用 [`@blueking/monitor-vue3-components`](https://www.npmjs.com/package/@blueking/monitor-vue3-components)。

---

## 1. 安装与使用

```bash
npm install @blueking/apm-vue3-for-vue2
```

产物：`index.js`（ESM 入口，代码按需拆成同目录若干 chunk）、`index.css`（样式）、`readme.md`。

```ts
// 样式需要引入一次（建议放在宿主组件或应用入口）
import '@blueking/apm-vue3-for-vue2/index.css';

// 入口较大，建议按需动态加载
const { mountAlarmCenter } = await import('@blueking/apm-vue3-for-vue2');

const handle = mountAlarmCenter(el, {
  props: { timeRange, refreshInterval, timezone, queryString },
  onEvent: (event, ...args) => {
    /* 子应用事件回传宿主，例如 conditionChange / queryStringChange */
  },
});

handle.update({ timeRange: next }); // 增量推送 props，触发子应用响应式更新
handle.unmount(); // 宿主销毁前必须调用，否则内存泄漏
```

`mountTraceExplore` 用法完全一致。子应用的 Vue3 实例（router / pinia / i18n）由包内自行创建，
宿主只需提供一个挂载节点。

## 2. 导出

| 导出名 | 说明 |
| --- | --- |
| `mountAlarmCenter(el, options)` | 挂载告警中心，返回 `{ update, unmount }` |
| `mountTraceExplore(el, options)` | 挂载 Trace 检索，返回 `{ update, unmount }` |
| `AlarmCenterApm` / `TraceExploreApm` | 两块能力的根组件，供已有 Vue3 应用直接渲染（需自备 router / pinia / i18n） |
| 类型 | `MountOptions` / `MountHandle` / `BridgeProps` / `BridgeEmit` |

## 3. 运行环境与依赖

以下依赖被声明为 `external`，需可从宿主工程解析到（已列在本包 `dependencies` 中，正常安装即可获得）：

| 依赖 | 用途 |
| --- | --- |
| `@blueking/bkui-library` | **Vue3 运行时**，包内所有 `vue` 导入都指向它 |
| `monitor-api` / `monitor-common` / `monitor-ui` / `monitor-pc` / `monitor-static` | 蓝鲸监控工程内的请求层、公共能力与图标资源 |
| `echarts` / `monaco-editor` / `dayjs` / `@prometheus-io/lezer-promql` | 体积较大且宿主通常已有 |

> **Vue3 运行时不叫 `vue`**：包内不存在对裸 `vue` 的引用，运行时统一从 `@blueking/bkui-library`
> （内容即 `export * from '@vue/runtime-dom'`）获取，因此 Vue2 宿主安装本包不会与自己的 `vue`（v2）冲突。

> **`monitor-*` 是工程内包**：全部由宿主提供（蓝鲸监控仓库内经 pnpm workspace 软链自动满足）。
> `monitor-api` 尤其不能各带一份，否则会出现两套请求拦截器与登录态。**因此本包只面向蓝鲸监控工程内部使用。**

> **类名前缀是 `bkmv3-`**：包内蓝鲸组件类名统一改写为该前缀（如 `.bkmv3-button`），
> 与宿主自带的 Vue2 版 `.bk-*` 样式隔离。覆盖样式请以 `.bkmv3-*` 书写。

## 4. 宿主接入注意

- **挂载期间的 `window.i18n`**：子应用加载时会临时使用宿主的 `window.i18n`，宿主可在 `await import`
  前后保存并恢复，避免全局被污染（参考 monitor-ui 内 `apm-alarm-center` 容器的实现）。
- **异步挂载竞态**：`mount` 是在 `await import` 之后调用的，宿主组件若在此期间被销毁，需用标志位跳过挂载。
- **嵌入态差异**：包内通过 `src/trace/common/embed-context.ts` 的运行时上下文识别「已被宿主嵌入」，
  据此收敛查询的业务范围、隐藏宿主已提供的筛选控件、调整弹层样式，无需宿主额外配置。
