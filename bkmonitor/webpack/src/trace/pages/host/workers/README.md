# 主机列表 Web Worker 技术文档

## 1. 背景与目标

主机列表接口返回**全量数据**（规模可达数十万甚至百万级）。若在主线程完成以下操作，会导致页面长时间卡死、无法交互：

| 操作 | 原主线程行为 | 数据量级影响 |
| --- | --- | --- |
| 行派生字段计算 | `createHostListRow` 对全量数据 `map` | CPU 密集，阻塞渲染 |
| 拓扑 / 快捷 / where / 关键字过滤 | 多次 `filter` 全量遍历 | 每次交互都重算 |
| 排序 | `sort` 全量数组 | 大数组排序耗时显著 |
| 过滤候选项构建 | `buildFilterOptionsMap` 遍历全量 | 阻塞 retrieval-filter |
| 内存占用 | 主线程持有 `rawRows: IHostListRow[]` | 百万行对象占用大量堆内存 |

**目标**：将重计算迁移到 Web Worker，主线程仅持有**当前页数据**（默认 50 条）与轻量 UI 状态。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 主线程（use-host-list.ts）                                       │
│  - UI 状态：keyword / where / page / selectedRowKeys ...        │
│  - 轻量结果：pagedRows / total / categoryStats / rawRowCount    │
│  - API 请求：getHostInfoList / getHostMetricInfoList            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ postMessage（结构化克隆的纯对象）
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Worker 线程（host-list.worker.raw.js）                           │
│  - 全量行数据 rawRows（仅 Worker 内存中维护）                    │
│  - 过滤候选项 filterOptionsMap                                   │
│  - 行转换 / 过滤 / 排序 / 分页切片 / 统计 / IP 查询              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ postMessage（仅回传一页 + 统计）
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 视图层（host-list.tsx / host-list-table.tsx）                    │
│  - 表格只渲染 pagedRows                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 分层职责

| 层级 | 文件 | 职责 |
| --- | --- | --- |
| 视图 | `components/host-list/*` | 渲染、事件绑定，不直接接触全量数据 |
| 编排 | `composables/use-host-list.ts` | 状态管理、API 调用、触发 Worker 计算 |
| Worker 客户端 | `composables/use-host-list-worker.ts` | Worker 生命周期、消息协议、序列化 |
| Worker 运行时 | `workers/host-list.worker.raw.js` | 全量数据存储与重计算 |
| 纯函数（主线程） | `utils/host-list-core.ts` | 与 Worker 逻辑对齐的 TS 纯函数（类型安全、可单测） |
| 对外 re-export | `utils/host-list.ts` | 从 `host-list-core` 导出，兼容旧引用 |

---

## 3. 文件说明

```
workers/
├── README.md                    # 本文档
├── host-list.worker.raw.js      # Worker 运行时代码（纯 JS，无 import）
└── raw.d.ts                     # ?raw 导入的类型声明

composables/
├── use-host-list.ts             # 业务编排，消费 Worker 结果
└── use-host-list-worker.ts      # Worker 客户端封装

utils/
├── host-list-core.ts            # 主线程侧纯计算逻辑（TypeScript）
└── host-list.ts                 # re-export
```

### 3.1 为何使用 `host-list.worker.raw.js` 而非 `*.worker.ts`？

曾尝试 webpack 5 原生 Worker 写法：

```ts
new Worker(new URL('./host-list.worker.ts', import.meta.url));
```

在 trace 微前端（bk-weweb）场景下连续踩坑，**最终放弃该方案**，改用 **Blob Worker**：

| 方案 | 问题 |
| --- | --- |
| webpack Worker + `importScripts` | babel `useBuiltIns: 'usage'` 注入 core-js，拆出 vendor chunk；Worker 的 `publicPath` 与主应用不一致，请求路径变成 `/js/js/vendors-xxx.js` |
| 跨域 Worker URL | trace 子应用资源在 `:7002`，主壳在 `:9002`，`new Worker(url)` 受同源策略限制 |
| 与主 bundle 共享 chunk | Worker import 业务模块会触发 splitChunks，仍走 `importScripts` |

**最终方案**：

1. Worker 源码维护为**纯 JS 单文件**（`host-list.worker.raw.js`），无任何 `import`
2. 主 bundle 通过 `?raw` 以**字符串**形式打入（不生成独立 Worker chunk）
3. 运行时 `Blob` + `URL.createObjectURL` 创建 Worker，与页面**同源**，无 `importScripts`

```ts
import workerSource from '../workers/host-list.worker.raw.js?raw';

const blob = new Blob([workerSource], { type: 'application/javascript' });
const worker = new Worker(URL.createObjectURL(blob));
```

### 3.2 逻辑双份维护说明

| 文件 | 用途 |
| --- | --- |
| `utils/host-list-core.ts` | 主线程侧 TypeScript 纯函数，有完整类型 |
| `workers/host-list.worker.raw.js` | Worker 运行时，纯 JS，**逻辑须与 core 保持同步** |

修改过滤 / 排序 / 行派生逻辑时，**两处都要改**。Worker 侧只内联了运行所需常量（阈值、状态映射等），避免引入外部依赖。

---

## 4. Webpack 配置

在根目录 `webpack.config.js` 中为 trace 应用增加：

```js
/** trace Worker 源码以字符串打入主 bundle，运行时通过 Blob URL 创建 Worker */
const setupTraceWorkerWebpack = config => {
  const workerRawRule = {
    resourceQuery: /raw/,
    type: 'asset/source',
  };
  const oneOfRule = config.module.rules.find(rule => rule.oneOf);
  if (oneOfRule) {
    oneOfRule.oneOf.unshift(workerRawRule);
    return;
  }
  config.module.rules.unshift(workerRawRule);
};

// app === 'trace' 时调用
setupTraceWorkerWebpack(config);
```

类型声明（`workers/raw.d.ts`）：

```ts
declare module '*?raw' {
  const content: string;
  export default content;
}
```

---

## 5. Worker 消息协议

所有消息均带 `requestId` 用于请求/响应匹配；`COMPUTE` 另用 `latestComputeId` 丢弃过期结果。

### 5.1 主线程 → Worker

#### `INIT_BASE` — 初始化基础数据

```ts
{
  type: 'INIT_BASE',
  requestId: number,
  baseList: IHostBaseInfo[],  // searchHostInfo 原始响应
}
```

Worker 内部：`createHostListRow` → 构建 `rawRows` → 构建 `filterOptionsMap`。

#### `MERGE_METRICS` — 合并指标

```ts
{
  type: 'MERGE_METRICS',
  requestId: number,
  metricListMap: Record<string, IHostMetricInfo>,  // key 为 bk_host_id
}
```

Worker 内部：按 `bk_host_id` 合并指标并重建行与候选项。

#### `COMPUTE` — 过滤 / 排序 / 分页（高频）

```ts
{
  type: 'COMPUTE',
  requestId: number,
  params: {
    selectedNode: { id, bk_obj_id?, bk_host_id? } | null,  // 精简拓扑节点
    activeCategory: '' | 'alarm' | 'cpu' | 'mem' | 'disk',
    where: IWhereItem[],
    keyword: string,
    sortInfo: string,   // tdesign 格式：'key' | '-key'
    page: number,
    pageSize: number,
  },
}
```

计算流水线：

```
rawRows
  → matchTopoNode（拓扑范围）
  → computeCategoryStats（快捷卡片统计）
  → matchQuickCategory + matchWhere + matchKeyword（过滤）
  → sortRows（排序）
  → slice（分页，仅保留当前页）
```

#### `GET_FILTER_OPTIONS` — retrieval-filter 候选项

```ts
{
  type: 'GET_FILTER_OPTIONS',
  requestId: number,
  field: string,
  search: string,
  limit: number,
}
```

从 Worker 内缓存的 `filterOptionsMap` 查询，支持搜索与截断。

#### `GET_SELECTED_IPS` — 复制选中 IP

```ts
{
  type: 'GET_SELECTED_IPS',
  requestId: number,
  rowKeys: string[],
}
```

### 5.2 Worker → 主线程

| type | 字段 | 说明 |
| --- | --- | --- |
| `INIT_BASE_DONE` | `rawRowCount`, `filterOptionsMap` | 基础数据就绪 |
| `MERGE_METRICS_DONE` | `filterOptionsMap` | 指标合并完成 |
| `COMPUTE_DONE` | `categoryStats`, `total`, `pagedRows` | 过滤排序分页结果 |
| `GET_FILTER_OPTIONS_DONE` | `result: { count, list }` | 候选项 |
| `GET_SELECTED_IPS_DONE` | `ips: string[]` | 内网 IP 列表 |

---

## 6. 主线程编排（use-host-list.ts）

### 6.1 状态变化

| 原方案 | Worker 方案 |
| --- | --- |
| `rawRows` 全量数组 | `rawRowCount` 仅记录条数 |
| `computed` 链式派生 | `categoryStats` / `total` / `pagedRows` 由 Worker 回写 |
| `selectedRows` computed | `selectedRowKeys` + Worker `GET_SELECTED_IPS` |
| `optionsMap` computed | Worker 内缓存 + `GET_FILTER_OPTIONS` |

### 6.2 数据加载（两段式，与原先一致）

```ts
// 1. 基础数据先到 → Worker INIT_BASE → 立即 COMPUTE（先展示无指标列）
baseList = await getHostInfoList();
await hostListWorker.initBaseData(baseList);

// 2. 指标后到 → Worker MERGE_METRICS → 再次 COMPUTE
metricListMap = await getHostMetricInfoList({ bk_host_ids });
await hostListWorker.mergeMetrics(metricListMap);
```

注意：`bk_host_ids` 从第一次请求的 `baseList` 提取，**不重复请求** `getHostInfoList`。

### 6.3 过滤条件变更

`watch([selectedNode, activeCategory, where, keyword, sortInfo, page, pageSize])` 触发 `refreshList()`：

- 默认走 `scheduleCompute`（**150ms 防抖**），避免连续输入时 Worker 堆积
- 数据加载完成后走 `computeNow`（**立即计算**）

### 6.4 视图层微调

`host-list.tsx` 中 `hasSelection` 改为读取 `selectedRowKeys.length`，不再依赖 `selectedRows`。

---

## 7. Worker 客户端细节（use-host-list-worker.ts）

### 7.1 请求竞态处理

- **Promise 类请求**（`INIT_BASE` / `MERGE_METRICS` / `GET_*`）：`pendingRequests` Map 按 `requestId` resolve
- **COMPUTE**：仅保留最新 `latestComputeId`，过期响应直接丢弃

### 7.2 postMessage 序列化（DataCloneError 修复）

`postMessage` 使用结构化克隆算法，**不能传递**：

- Vue `reactive` / `readonly` 代理对象
- 函数、DOM 节点、含循环引用的对象

处理方式：

```ts
/** 通用深拷贝：剥离 Vue 代理 */
const cloneWorkerPayload = <T>(value: T): T => JSON.parse(JSON.stringify(toRaw(value)));

/** 拓扑节点只传过滤所需三字段，避免克隆整棵 children 子树 */
const serializeTopoNodeForWorker = (node) => ({
  id: node.id,
  bk_obj_id: node.bk_obj_id,
  bk_host_id: node.bk_host_id,
});
```

所有 `postRequest` 走 `cloneWorkerPayload`；`COMPUTE` 的 `params` 走 `serializeComputeParams`。

### 7.3 生命周期

`onScopeDispose` 时 `worker.terminate()`，清空 pending 请求，避免组件卸载后仍回写状态。

---

## 8. Worker 内计算逻辑摘要

与 `host-list-core.ts` 对齐，核心函数：

| 函数 | 作用 |
| --- | --- |
| `createHostListRow` | 派生 `bkClusters` / `clusterNames` / `rowId` / `totalAlarmCount` 等 |
| `matchTopoNode` | 拓扑节点范围过滤 |
| `matchQuickCategory` | 快捷卡片（告警 / CPU / 内存 / 磁盘） |
| `matchWhere` | retrieval-filter where 条件 |
| `matchKeyword` | 关键字模糊搜索 |
| `sortRows` | tdesign 排序字符串 |
| `buildFilterOptionsMap` | 全量候选项 Map |
| `computeCategoryStats` | 快捷卡片命中数 |

内联常量（与 `constants/host-list.ts` 保持一致）：

- `HOST_METRIC_OVER_THRESHOLD = 80`
- `HOST_NUMBER_FILTER_FIELDS`（数值比较字段集合）
- `HOST_STATUS_MAP`（采集状态展示名）

---

## 9. 踩坑记录

### 9.1 importScripts /js/js/ 路径错误

```
Failed to execute 'importScripts' on 'WorkerGlobalScope':
The script at 'http://host:7002/js/js/vendors-...core-js....js' failed to load.
```

**原因**：webpack Worker chunk + babel core-js 按需注入 + 微前端 publicPath 拼接错误。

**解决**：放弃 webpack 原生 Worker，改用 Blob 方案。

### 9.2 Worker 跨域

trace 作为 bk-weweb 子应用，主壳与 trace dev server 端口不同，`new Worker(远程URL)` 失败。

**解决**：Blob Worker 与主页面同源创建。

### 9.3 DataCloneError

```
Failed to execute 'postMessage' on 'Worker': #<Object> could not be cloned.
```

**原因**：`selectedNode`（props ref）、`where`（reactive 数组）含 Proxy。

**解决**：`toRaw` + `JSON` 深拷贝；拓扑节点精简字段。

---

## 10. 性能特征与边界

### 10.1 收益

| 维度 | 效果 |
| --- | --- |
| 主线程 CPU | 过滤 / 排序 / 行转换不阻塞 UI |
| 主线程内存 | 仅 ~50 条 `pagedRows`，不持有百万行 |
| 交互响应 | 过滤防抖 150ms，减少 Worker 排队 |

### 10.2 仍在主线程的开销

| 环节 | 说明 |
| --- | --- |
| API JSON 解析 | fetch 层，与 Worker 无关 |
| `postMessage` 拷贝 | 传入 `baseList` / `metricListMap` 时有一次结构化克隆 |
| Worker 内存 | 全量数据在 Worker 线程独立堆中，不减轻总内存，只减轻主线程压力 |
| 百万级 `bk_host_ids` | 指标接口一次传全量 ID 仍可能超时，需后端分批（未在本方案 scope） |

### 10.3 后续可优化方向

1. **后端分页 / 服务端过滤**：从根本上减少全量传输
2. **指标接口分批**：`getHostMetricInfoList` 按 batch 请求
3. **Worker 内增量索引**：对常用过滤字段建 Map 索引，降低每次 filter 复杂度
4. **SharedArrayBuffer**：极端场景下的零拷贝（需 COOP/COEP，成本高）

---

## 11. 开发维护指南

### 11.1 修改计算逻辑

1. 先改 `utils/host-list-core.ts`（TypeScript，有类型检查）
2. 同步改 `workers/host-list.worker.raw.js`（去掉类型，保持 ES 语法 Worker 可执行）
3. 本地大数据场景验证：加载、过滤、排序、分页、复制 IP、retrieval-filter 候选项

### 11.2 新增 Worker 消息类型

1. 在 `host-list.worker.raw.js` 的 `self.onmessage` 增加 `case`
2. 在 `use-host-list-worker.ts` 补充 `WorkerResponse` 类型与客户端方法
3. 在 `use-host-list.ts` 编排层调用
4. **记得** `postMessage` 前序列化，不传 Vue 代理

### 11.3 本地调试

- 修改 `host-list.worker.raw.js` 后需**重新编译**（`?raw` 打入主 bundle）
- Chrome DevTools → Sources → 搜索 `host-list.worker` 可找到 Blob Worker 源码
- Application → Workers 面板可查看 Worker 线程

### 11.4 新增其他 Worker

复用本模式：

```
workers/xxx.worker.raw.js     # 纯 JS，无 import
composables/use-xxx-worker.ts # Blob 创建 + 消息协议
webpack.config.js             # 已有 ?raw rule，无需重复配置
```

---

## 12. 相关代码入口

| 场景 | 入口 |
| --- | --- |
| 页面挂载加载数据 | `host-list.tsx` → `onMounted` → `ctx.loadData()` |
| Worker 创建 | `use-host-list-worker.ts` → `createBlobWorker()` |
| 过滤触发计算 | `use-host-list.ts` → `watch` → `refreshList()` |
| 表格渲染 | `host-list-table.tsx` → `props.data` = `pagedRows` |
