# @blueking/monitor-vue3-components

> 蓝鲸监控（bkmonitor）从 `src/trace`（Vue3 + TSX 工程）中抽取、对外发布的一套通用组件与组合式函数集合。
> 包含 **检索筛选**、**PromQL 编辑器**、**图表探索** 等能力，供其它 Vue3 项目直接复用。

本文档基于 `src/trace/components.ts` 的对外导出编写，覆盖其导出的**全部一级组件、组合式函数、工具函数与类型**。

---

## 目录

- [1. 安装与引入](#1-安装与引入)
- [2. 运行环境与依赖要求](#2-运行环境与依赖要求)
- [3. 导出总览](#3-导出总览)
- [4. 组件（Components）](#4-组件components)
  - [4.1 PromqlEditor · PromQL 编辑器](#41-promqleditor--promql-编辑器)
  - [4.2 RetrievalFilter · 检索筛选](#42-retrievalfilter--检索筛选)
  - [4.3 ExploreChart · 图表探索](#43-explorechart--图表探索)
  - [4.4 ChartTitle · 图表标题栏](#44-charttitle--图表标题栏)
  - [4.5 CommonLegend · 通用图例](#45-commonlegend--通用图例)
  - [4.6 ChartSkeleton · 图表骨架屏](#46-chartskeleton--图表骨架屏)
- [5. 组合式函数（Composables）](#5-组合式函数composables)
  - [5.1 useEcharts](#51-useecharts)
  - [5.2 useEchartsOptions](#52-useechartsoptions)
  - [5.3 useChartLegend](#53-usechartlegend)
  - [5.4 useChartTitleEvent](#54-usecharttitleevent)
- [6. 工厂函数与工具函数](#6-工厂函数与工具函数)
- [7. 类型参考（Types）](#7-类型参考types)
- [8. 常见问题（FAQ）](#8-常见问题faq)

---

## 1. 安装与引入

```bash
npm install @blueking/monitor-vue3-components
# 或
yarn add @blueking/monitor-vue3-components
```

包内产物只有三个文件：`index.mjs`（ESM 组件代码）、`index.css`（样式）、`readme.md`。

**按需引入组件 + 全量样式：**

```ts
// 组件、组合式函数、工具函数、类型均从包根导出
import { PromqlEditor, RetrievalFilter, ExploreChart } from '@blueking/monitor-vue3-components';

// 样式需要单独引入一次（建议放在应用入口）
import '@blueking/monitor-vue3-components/index.css';
```

> 所有导出统一从包根 `@blueking/monitor-vue3-components` 获取，**不要**深入 `dist`、`src` 等内部路径。

---

## 2. 运行环境与依赖要求

组件基于 **Vue 3 + TSX** 构建。打包时以下依赖被声明为 `external`（即由宿主工程提供），因此你的项目需要自行安装并可用：

| 依赖 | 用途 | 相关组件/能力 |
| --- | --- | --- |
| `vue` (^3.5) | 运行时 | 全部 |
| `vue-i18n` | 国际化（`useI18n` / `window.i18n`） | `ExploreChart`、`ChartTitle`、`RetrievalFilter` |
| `bkui-vue` | 蓝鲸 Vue3 组件库 | `ChartTitle`（Popover 等） |
| `@blueking/tdesign-ui` | 蓝鲸 tdesign 封装 | 部分交互 |
| `monaco-editor` (0.44.0) | 代码编辑器内核 | `PromqlEditor` |
| `@prometheus-io/lezer-promql` | PromQL 语法解析 | `PromqlEditor` |
| `echarts` + `vue-echarts` | 图表渲染 | `ExploreChart` |
| `dayjs` | 时间处理 | `ExploreChart` 的 x 轴格式化 |
| `vue-tippy` | 提示气泡 | 部分交互 |

> **重要（`ExploreChart` 的隐式约定）**：该组件依赖两项运行时环境，接入前请确认：
>
> 1. 通过 `app.config.globalProperties.$api` 提供请求模块（组件内使用 `instance.appContext.config.globalProperties.$api[apiModule][apiFunc]` 发起请求）。
> 2. 通过 `provide('timeRange', ...)`、`provide('refreshImmediate', ...)` 注入时间范围与刷新信号（未注入时 `timeRange` 退化为内置默认值）。
>
> 若你只想复用 ECharts 配置生成逻辑而不想耦合这些约定，请改用 [`useEchartsOptions`](#52-useechartsoptions)。

---

## 3. 导出总览

`@blueking/monitor-vue3-components` 的一级导出可分为四类：

<details>
<summary><b>① 组件（6 个）</b></summary>

| 导出名 | 说明 | 章节 |
| --- | --- | --- |
| `PromqlEditor` | 基于 Monaco 的 PromQL 编辑器 | [4.1](#41-promqleditor--promql-编辑器) |
| `RetrievalFilter` | 检索筛选（UI / QueryString 双模式） | [4.2](#42-retrievalfilter--检索筛选) |
| `ExploreChart` | 图表探索（含标题、图例、下钻等） | [4.3](#43-explorechart--图表探索) |
| `ChartTitle` | 图表标题栏（指标、告警、菜单） | [4.4](#44-charttitle--图表标题栏) |
| `CommonLegend` | 通用图例 | [4.5](#45-commonlegend--通用图例) |
| `ChartSkeleton` | 图表加载骨架屏 | [4.6](#46-chartskeleton--图表骨架屏) |

</details>

<details>
<summary><b>② 组合式函数（4 个）</b></summary>

| 导出名 | 说明 | 章节 |
| --- | --- | --- |
| `useEcharts` | 依据 `panel` + `$api` 拉取数据并生成 ECharts 配置 | [5.1](#51-useecharts) |
| `useEchartsOptions` | 依据现成 `seriesList` 生成 ECharts 配置（无需 panel） | [5.2](#52-useechartsoptions) |
| `useChartLegend` | 图例数据计算与联动筛选 | [5.3](#53-usechartlegend) |
| `useChartTitleEvent` | 图表标题菜单（检索、关联告警、截图、导出等）事件 | [5.4](#54-usecharttitleevent) |

</details>

<details>
<summary><b>③ 工厂函数与工具函数（8 个）</b></summary>

| 导出名 | 说明 |
| --- | --- |
| `createSeries` | 由原始 series 生成对齐后的 ECharts series + xAxis |
| `createXAxis` | 生成 x 轴配置（含时间格式化） |
| `createYAxis` | 生成 y 轴配置（按单位分轴） |
| `createOptions` | 组装完整 ECharts options |
| `handleExplore` | 跳转到指标/日志检索 |
| `handleRelateAlert` | 跳转到关联告警 |
| `handleAddStrategy` | 跳转到添加监控策略 |
| `handleStoreImage` | 将目标 DOM 截图保存为 PNG |

详见 [第 6 章](#6-工厂函数与工具函数)。

</details>

<details>
<summary><b>④ 类型（Types）</b></summary>

组件相关类型（`SeriesItem`、`ILegendItem`、`DataZoomEvent`、`CustomOptions`、`PanelModel` 等）均可直接从包根按需 `import type`，详见 [第 7 章](#7-类型参考types)。

</details>

---

## 4. 组件（Components）

### 4.1 PromqlEditor · PromQL 编辑器

基于 `monaco-editor` 封装的 PromQL 编辑器，内置 PromQL 语法校验（`@prometheus-io/lezer-promql`）、占位提示、自适应高度与手动拉伸能力。

#### 基础用法

```tsx
import { defineComponent, ref } from 'vue';
import { PromqlEditor } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

export default defineComponent({
  name: 'DemoPromqlEditor',
  setup() {
    const promql = ref('sum(rate(http_requests_total[5m]))');

    return () => (
      <PromqlEditor
        value={promql.value}
        minHeight={68}
        onChange={(v: string) => (promql.value = v)}
        onBlur={(v: string, hasError: boolean) => {
          if (!hasError) {
            // 语法正确，可发起查询
          }
        }}
        executeQuery={(hasError: boolean) => {
          // 在编辑器内按下 Enter（且无补全弹层）时触发
        }}
      />
    );
  },
});
```

<details>
<summary><b>Props</b></summary>

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `value` | `string` | `null` | 受控值；变化时会同步进编辑器 |
| `defaultValue` | `string` | `''` | 非受控初始值（`value` 为 `null` 时生效） |
| `minHeight` | `number` | `68` | 最小高度（px） |
| `isError` | `boolean` | `false` | 是否显示错误态样式 |
| `language` | `string` | `'promql'` | 语言 |
| `theme` | `string` | `'vs'` | Monaco 主题 |
| `options` | `object` | 内置 `defaultOptions` | 透传给 Monaco 的 editor options |
| `overrideServices` | `object` | `{}` | Monaco `overrideServices` |
| `className` | `string` | `null` | 追加到编辑器的 `extraEditorClassName` |
| `readonly` | `boolean` | `false` | 是否只读 |
| `resizable` | `boolean` | `true` | 是否显示底部拖拽条以手动调整高度 |
| `executeQuery` | `(hasError: boolean) => void` | `() => null` | 光标处于编辑器、无补全弹层时按下 Enter 触发；参数为“当前是否存在语法错误” |
| `uri` | `(monaco) => monaco.Uri` | — | 自定义 model uri（用于复用/隔离 model） |

</details>

<details>
<summary><b>Emits</b></summary>

| 事件 | 回调签名 | 触发时机 |
| --- | --- | --- |
| `change` | `(value: string)` | 编辑器内容变化 |
| `blur` | `(value: string, hasError: boolean)` | 编辑器失焦，第二参数为是否存在语法错误 |
| `focus` | `()` | 编辑器聚焦 |

</details>

---

### 4.2 RetrievalFilter · 检索筛选

检索筛选组件，支持 **UI 模式** 与 **QueryString 模式** 切换，提供“收藏”“常驻筛选”“复制/清空/搜索”等能力，并可通过默认插槽在最左侧追加自定义控件（如空间选择、业务模块选择）。

#### 快速上手

```tsx
import { defineComponent, ref } from 'vue';
import { RetrievalFilter } from '@blueking/monitor-vue3-components';
import type { IFilterField, IGetValueFnParams, IWhereValueOptionsItem } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

export default defineComponent({
  name: 'DemoRetrievalFilter',
  setup() {
    const fields = ref<IFilterField[]>([
      {
        alias: '服务名',
        name: 'service_name',
        type: 'keyword' as any,
        isEnableOptions: true,
        methods: [
          { alias: '=', value: 'equal' },
          { alias: '!=', value: 'not_equal' },
          { alias: '包含', value: 'include' },
          { alias: '不包含', value: 'exclude' },
        ],
      },
    ]);
    const where = ref<any[]>([]);
    const queryString = ref('');

    const getValueFn = async (_params: IGetValueFnParams): Promise<IWhereValueOptionsItem> => {
      // 这里对接后端检索候选值接口
      return {
        count: 2,
        list: [
          { id: 'svc-a', name: 'svc-a' },
          { id: 'svc-b', name: 'svc-b' },
        ],
      };
    };

    return () => (
      <RetrievalFilter
        fields={fields.value}
        where={where.value}
        queryString={queryString.value}
        getValueFn={getValueFn}
        isShowResident={true}
        isShowCopy={true}
        isShowClear={true}
        onWhereChange={v => (where.value = v)}
        onQueryStringChange={v => (queryString.value = v)}
        onSearch={() => {
          /* 发起查询 */
        }}
      />
    );
  },
});
```

#### 高级示例（插槽 + 常驻筛选 + 收藏）

```tsx
<RetrievalFilter
  fields={fields}
  where={conditions}
  queryString={queryString}
  filterMode={filterMode}
  getValueFn={getValueFn}
  // 内部 → 外部 格式转换
  changeWhereFormatter={where =>
    where.map(w => ({ key: w.key, method: w.method, value: w.value, condition: w.condition }))
  }
  // 常驻筛选
  commonWhere={residentCondition}
  isShowResident={true}
  residentSettingOnlyId={residentSettingOnlyId}
  // 收藏
  favoriteList={favoriteList}
  isShowClear={true}
  isShowCopy={true}
  // 常驻设置读写用户配置
  handleGetUserConfig={handleGetUserConfig}
  handleSetUserConfig={handleSetUserConfig}
  loadDelay={0}
  onCommonWhereChange={handleResidentConditionChange}
  onModeChange={handleFilterModeChange}
  onQueryStringChange={handleQueryStringChange}
  onSearch={handleQuery}
  onWhereChange={handleConditionChange}
>
  {{
    // 左侧模式切换与输入区之间，放置空间选择器、模块选择等自定义控件
    default: () => <YourCustomControls />,
  }}
</RetrievalFilter>
```

#### QueryString 模式示例

```tsx
<RetrievalFilter
  fields={fields}
  filterMode={'queryString'}
  queryString={queryString}
  onQueryStringChange={v => (queryString = v)}
  onSearch={() => {
    /* 提交查询 */
  }}
/>
```

> 若解析错误，组件会在右侧高亮并通过提示气泡显示错误信息。

<details>
<summary><b>Props（完整）</b></summary>

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `fields` | `IFilterField[]` | — | 字段列表（**必传**） |
| `getValueFn` | `(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>` | 返回空列表 | 候选值获取函数，支持滚动加载与延迟加载 |
| `where` | `IWhereItem[]` | `[]` | UI 模式条件值（外部格式，可配合 `whereFormatter`/`changeWhereFormatter` 转换） |
| `commonWhere` | `IWhereItem[]` | `[]` | 常驻筛选条件值 |
| `queryString` | `string` | `''` | QueryString 模式语句 |
| `selectFavorite` | `{ commonWhere?: IWhereItem[]; where?: IWhereItem[] } \| null` | `null` | 当前选中的收藏项 |
| `favoriteList` | `IFavoriteListItem[]` | `[]` | 收藏列表 |
| `residentSettingOnlyId` | `string` | — | 常驻设置唯一 ID，用于读写用户配置 |
| `isDefaultResidentSetting` | `boolean` | `false` | 是否使用“默认常驻设置”（true 时 `residentSettingValue` 来源为 `commonWhere`） |
| `filterMode` | `EMode` | `ui` | 当前模式，`ui \| queryString` |
| `isShowFavorite` | `boolean` | `false` | 是否显示收藏按钮 |
| `isShowResident` | `boolean` | `false` | 是否显示常驻筛选按钮 |
| `isShowCopy` | `boolean` | `false` | 是否显示复制按钮 |
| `isShowClear` | `boolean` | `false` | 是否显示清空按钮 |
| `isShowSearchBtn` | `boolean` | `true` | 是否显示最右侧搜索按钮 |
| `defaultShowResidentBtn` | `boolean` | `false` | 进入时是否默认展开常驻设置 |
| `defaultResidentSetting` | `string[]` | `[]` | 默认常驻设置显示字段集合 |
| `placeholder` | `string` | `快捷键 / ，可直接输入` | 输入占位文案 |
| `isSingleMode` | `boolean` | `false` | 是否单模式（隐藏模式切换） |
| `whereFormatter` | `(where: any[]) => INormalWhere[]` | 原样返回 | 外部 → 内部 格式化 |
| `changeWhereFormatter` | `(where: INormalWhere[]) => any[]` | 原样返回 | 内部 → 外部 格式化 |
| `handleGetUserConfig` | `(key: string, config?: Record<string, any>) => Promise<string[] \| undefined>` | — | 常驻设置读取用户配置 |
| `handleSetUserConfig` | `(value: string, configId?: string) => Promise<boolean>` | — | 常驻设置写入用户配置 |
| `loadDelay` | `number` | `300` | 候选值加载延时（ms） |
| `limit` | `number` | `200` | 候选值滚动加载每次条数 |

</details>

<details>
<summary><b>Emits（完整）</b></summary>

| 事件 | 回调签名 | 说明 |
| --- | --- | --- |
| `favorite` | `(isEdit: boolean)` | 点击收藏；`true` 覆盖当前收藏，`false` 另存为新收藏 |
| `whereChange` | `(v: IWhereItem[])` | UI 模式条件变更（已通过 `changeWhereFormatter` 转换为外部格式） |
| `queryStringChange` | `(v: string)` | QueryString 提交（点击搜索或触发查询时） |
| `modeChange` | `(v: EMode)` | 模式切换 |
| `queryStringInputChange` | `(v: string)` | QueryString 输入中变更（未提交） |
| `commonWhereChange` | `(where: IWhereItem[])` | 常驻筛选条件变更 |
| `showResidentBtnChange` | `(v: boolean)` | 常驻设置面板展开/收起变化 |
| `search` | `()` | 点击“搜索”按钮触发 |
| `copyWhere` | `(v: IWhereItem[])` | UI 模式点击“复制”时触发 |
| `setFavoriteCache` | `(commonWhere: IWhereItem[])` | “收起常驻设置”且非默认常驻设置时，用于写入收藏缓存 |

</details>

<details>
<summary><b>Slots</b></summary>

| 插槽 | 说明 |
| --- | --- |
| `default` | 渲染在左侧模式切换与输入区域之间，常用于追加空间、模块等条件入口 |

```tsx
<RetrievalFilter>
  {{
    default: () => <SpaceSelector /* 自定义控件 */ />,
  }}
</RetrievalFilter>
```

</details>

<details>
<summary><b>字段模型规范（IFilterField / EFieldType）</b></summary>

`fields: IFilterField[]` 决定了 UI 与 QueryString 的能力边界，建议按以下规范配置：

```ts
enum EFieldType {
  all = 'all', // 全文检索
  boolean = 'boolean',
  date = 'date',
  duration = 'duration', // 耗时组件（提供范围/单位处理）
  input = 'input',
  integer = 'integer',
  keyword = 'keyword',
  long = 'long',
  text = 'text',
}

interface IFilterField {
  alias: string; // 展示名，如 “服务名”
  name: string; // 字段名，如 service_name
  type: EFieldType;
  isEnableOptions?: boolean; // 存在大量候选值时建议开启，并通过 getValueFn 拉取
  methods: Array<{
    alias: string; // 操作符展示名（支持 i18n）
    value: string; // 操作符标识，如 equal / not_equal / include / exclude
    placeholder?: string;
    wildcardValue?: string; // 异步搜索时默认操作符
    options?: Array<{
      name: string; // 'is_wildcard' | 'group_relation' 等
      label: string; // 选项展示名
      default?: boolean | string;
      children?: Array<{ label: string; value: string }>; // 供下拉选择
    }>;
  }>;
}
```

- **通配符开关（is_wildcard）**：适用于 `keyword/text` 等文本类字段，允许用户在 UI 模式选择“通配符匹配”。
- **组关系（group_relation）**：适用于“值分组”场景，由后端/检索引擎决定含义，组件只负责透传。
- **耗时字段（duration）**：自动启用耗时输入子组件，前端内置 ms/s/min 等单位换算逻辑。

</details>

<details>
<summary><b>外部 where 与内部格式（类型参考）</b></summary>

```ts
// 外部 where（whereChange / commonWhereChange / copyWhere 等输出）
interface IWhereItem {
  key: string;
  value: Array<string | number>;
  method?: string; // equal / not_equal / include / exclude ...
  condition?: 'and' | string;
  options?: { is_wildcard?: boolean; group_relation?: boolean };
}

// 组件内部格式（仅用于 whereFormatter / changeWhereFormatter）
interface INormalWhere {
  key: string;
  value: Array<string | number>;
  method: string;
  condition: 'and';
  options: Record<string, any>;
}
```

</details>

<details>
<summary><b>QueryString 能力与提示</b></summary>

- **解析与提示**：解析失败时右侧出现红色高亮，并通过提示气泡展示错误详情。
- **支持的 token（内部）**：`key`、`method`、`value`、`condition(AND/OR)`、`bracket`、`split`、`value-condition`；UI 会在需要时给出建议。
- **候选联想**：输入过程中，组件基于 `fields` 与 `getValueFn` 给出键/值联想与收藏项选择。

> 对于包含海量离散值的字段（如主机、服务、实例），优先走 `getValueFn` + 分页，避免前端硬编码全集。

</details>

<details>
<summary><b>常驻筛选与收藏交互细节</b></summary>

- **展开/收起**：点击右侧“齿轮”按钮可展开/收起常驻面板；`defaultShowResidentBtn` 控制默认展开。
- **回填规则**：收起时若常驻面板存在值，组件会将其“回填”到上方 UI 模式条件区并清空面板，伴随提示。
- **收藏**：
  - `isShowFavorite` 开启后显示收藏按钮；
  - `favoriteList` 提供收藏数据；
  - `favorite(isEdit)`：`true` 覆盖当前收藏，`false` 另存为；
  - `setFavoriteCache(commonWhere)`：在“非默认常驻设置”收起时触发，帮助外部缓存与当前收藏关联的临时值；
  - `selectFavorite`：传入当前选中的收藏项（含 `where/commonWhere`），组件按该收藏渲染。

</details>

<details>
<summary><b>事件时序与行为说明</b></summary>

- **UI 模式**：
  - `onWhereChange`：UI 条件变化即触发，外部可立即同步状态；
  - `onSearch`：点击最右侧“搜索”按钮触发，通常用于真正发起请求；
  - `onCopyWhere`：点击“复制”时触发，返回格式与 `onWhereChange` 一致。
- **QueryString 模式**：
  - `onQueryStringInputChange`：输入中变化（未提交）；
  - `onQueryStringChange`：点击“搜索”或主动提交时触发；
  - `onSearch`：与 UI 模式一致，作为统一“执行查询”的时机；
  - 解析错误：不阻断输入与提交，但会给出错误提示，建议外部收到 `onQueryStringChange` 后兜底校验。
- **模式切换**：`onModeChange` —— UI 与 QueryString 间切换，外部可据此决定是否转换条件或清理状态。
- **常驻面板**：`onCommonWhereChange`（常驻条件变化）、`onShowResidentBtnChange`（面板显隐）。

</details>

---

### 4.3 ExploreChart · 图表探索

一个“开箱即用”的时序图表组件：内部通过 [`useEcharts`](#51-useecharts) 依据 `panel` 拉取数据、生成 ECharts 配置，并组合了 [`ChartTitle`](#44-charttitle--图表标题栏)（标题/告警/菜单）、[`CommonLegend`](#45-commonlegend--通用图例)（图例联动）与 [`ChartSkeleton`](#46-chartskeleton--图表骨架屏)（加载态）。

> 使用前请先阅读 [第 2 章的隐式约定](#2-运行环境与依赖要求)：需要全局 `$api` 与 `provide('timeRange')`。

#### 基础用法

```tsx
import { defineComponent, provide, ref } from 'vue';
import { ExploreChart } from '@blueking/monitor-vue3-components';
import type { PanelModel } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

export default defineComponent({
  name: 'DemoExploreChart',
  setup() {
    // 时间范围通过 provide 注入，供组件内部 inject 消费
    provide('timeRange', ref(['now-1h', 'now']));

    const panel = ref<PanelModel>({
      title: '请求量',
      subTitle: 'http_requests_total',
      // targets: [{ apiModule, apiFunc, data: { query_configs: [...] } }],
    } as PanelModel);

    return () => (
      <ExploreChart
        panel={panel.value}
        showTitle={true}
        showRestore={false}
        onDataZoomChange={([start, end]) => {
          // 框选缩放后返回 [startTime, endTime]
        }}
        onDurationChange={(ms: number) => {
          // 接口请求耗时（ms）
        }}
      />
    );
  },
});
```

<details>
<summary><b>Props</b></summary>

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `panel` | `PanelModel` | — | 面板配置（**必传**），包含 `title`、`subTitle`、`targets`、`options` 等 |
| `params` | `Record<string, any>` | `{}` | 附加查询参数，会与 `target.data` 合并后请求 |
| `showTitle` | `boolean` | `true` | 是否显示 `ChartTitle` |
| `showRestore` | `boolean` | `false` | 是否显示“复位”按钮 |
| `hoverAllTooltips` | `boolean` | `false` | 联动图表中任一 hover 是否展示全部 tooltip |
| `customOptions` | `CustomOptions` | `{}` | 自定义数据/series/options/tooltips 处理，见 [类型](#7-类型参考types) |
| `customLegendOptions` | `LegendCustomOptions` | `{}` | 自定义图例数据与点击行为 |

</details>

<details>
<summary><b>Emits</b></summary>

| 事件 | 回调签名 | 说明 |
| --- | --- | --- |
| `dataZoomChange` | `([startTime, endTime]: number[])` | 框选缩放后的时间范围 |
| `durationChange` | `(ms: number)` | 接口请求耗时变化 |
| `restore` | `()` | 点击复位按钮 |
| `mouseover` | `(params)` | 图表鼠标移入 |
| `mouseout` | `(params)` | 图表鼠标移出 |

</details>

---

### 4.4 ChartTitle · 图表标题栏

图表标题栏组件：展示标题/副标题、单指标告警状态（响铃图标）、数据步长、指标提示，以及右上角“更多”菜单（`menuList`）与下钻等操作。通常由 `ExploreChart` 内部使用，也可单独使用。

#### 基础用法

```tsx
import { defineComponent } from 'vue';
import { ChartTitle } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

export default defineComponent({
  setup() {
    return () => (
      <ChartTitle
        title='请求量'
        subtitle='http_requests_total'
        showMore={true}
        menuList={['more', 'explore', 'area', 'drill-down', 'relate-alert']}
        metrics={[]}
        onMenuClick={item => {
          /* 菜单点击 */
        }}
        onMetricClick={metric => {
          /* 指标点击（添加策略） */
        }}
        onAlarmClick={alarm => {
          /* 告警图标点击 */
        }}
      />
    );
  },
});
```

<details>
<summary><b>Props</b></summary>

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `title` | `string` | — | 主标题 |
| `subtitle` | `string` | — | 副标题 |
| `metrics` | `IExtendMetricData[]` | `[]` | 指标列表；长度为 1 时展示单指标告警状态 |
| `collectInterval` | `string` | `'0'` | 采集周期 |
| `showMore` | `boolean` | `false` | 是否显示“更多”菜单入口 |
| `dragging` | `boolean` | `false` | 是否处于拖拽态（拖拽时不弹菜单） |
| `isInstant` | `boolean` | `false` | 是否即时数据 |
| `showAddMetric` | `boolean` | `true` | 是否显示“添加策略”入口 |
| `menuList` | `ChartTitleMenuType[]` | `[]` | 菜单项列表 |
| `drillDownOption` | `IMenuChildItem[]` | `[]` | 下钻子菜单 |
| `isShowAlarm` | `boolean` | `false` | 是否展示告警操作列表 |
| `details` | `object` | `{}` | 附加详情 |

</details>

<details>
<summary><b>Emits & Slots</b></summary>

**Emits：** `menuClick(item)`、`selectChild(data)`、`metricClick(metric)`、`allMetricClick()`、`alarmClick(alarmStatus)`、`updateDragging(v)`、`successLoad()`

**Slots：** `title`、`subtitle`、`tagTitle`、`customTools`

</details>

---

### 4.5 CommonLegend · 通用图例

通用图例组件：渲染图例列表，支持点击（单选/仅显示当前）与 `Shift + 点击`（多选切换）。通常与 [`useChartLegend`](#53-usechartlegend) 配合使用。

#### 基础用法

```tsx
import { defineComponent, ref } from 'vue';
import { CommonLegend } from '@blueking/monitor-vue3-components';
import type { ILegendItem } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

export default defineComponent({
  setup() {
    const legendData = ref<ILegendItem[]>([
      { name: 'svc-a', color: '#7EB26D', show: true },
      { name: 'svc-b', color: '#EAB839', show: true },
    ]);

    return () => (
      <CommonLegend
        legendData={legendData.value}
        onSelectLegend={({ actionType, item }) => {
          // actionType: 'click' | 'shift-click' | 'highlight' | 'downplay'
        }}
      />
    );
  },
});
```

<details>
<summary><b>Props & Emits</b></summary>

| Props | 类型 | 说明 |
| --- | --- | --- |
| `legendData` | `ILegendItem[]` | 图例数据（**必传**） |

| Emits | 回调签名 | 说明 |
| --- | --- | --- |
| `selectLegend` | `({ actionType: LegendActionType, item: ILegendItem })` | 点击图例；组件内部会自动区分 `click` 与 `shift-click` |

</details>

---

### 4.6 ChartSkeleton · 图表骨架屏

无 Props 的纯展示组件，用于图表数据加载中的占位骨架。

```tsx
import { ChartSkeleton } from '@blueking/monitor-vue3-components';
import '@blueking/monitor-vue3-components/index.css';

// 加载态占位
<ChartSkeleton />;
```

---

## 5. 组合式函数（Composables）

### 5.1 useEcharts

图表数据获取 + ECharts 配置生成的核心 Hook（`ExploreChart` 内部即基于它实现）。它会监听 `timeRange`（inject）/`panel`/`params` 变化，自动通过全局 `$api` 拉取数据，支持 `lazyRender` 分阶段渲染与请求取消。

```ts
import { useEcharts } from '@blueking/monitor-vue3-components';

const { options, loading, series, metricList, targets, duration, chartId, getEchartOptions } = useEcharts({
  panel, // MaybeRef<PanelModel>
  params, // MaybeRef<Record<string, any>>
  chartRef, // Ref<HTMLElement>，用于 tooltip 定位
  $api, // Record<string, () => Promise<any>>，请求模块
  customOptions: {}, // CustomOptions
  interactionState: { isMouseOver, hoverAllTooltips }, // 可选
  // downSampleRangeComputed: (timeRange) => string | undefined, // 可选降采样
});
```

<details>
<summary><b>入参（ChartOptions）与返回值</b></summary>

**入参字段：** `panel`、`chartRef`、`$api`、`params`、`customOptions`、`interactionState?`、`downSampleRangeComputed?`

**返回：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `loading` | `ShallowRef<boolean>` | 加载态 |
| `options` | `ShallowRef<any>` | ECharts 完整 options |
| `series` | `ShallowRef<any[]>` | 合并后的原始 series |
| `metricList` | `ShallowRef<any[]>` | 去重后的指标列表 |
| `targets` | `ShallowRef<IDataQuery[]>` | 请求后的 targets |
| `duration` | `ShallowRef<number>` | 接口请求耗时（ms） |
| `chartId` | `ShallowRef<string>` | 图表 id，每次刷新会变化 |
| `getEchartOptions` | `() => Promise<any>` | 手动触发一次拉取 |

</details>

---

### 5.2 useEchartsOptions

与 `useEcharts` 类似，但**不依赖 panel / $api / timeRange**，直接由外部传入现成的 `seriesList` 生成 ECharts 配置。适合你已经拿到了序列数据、只想复用蓝鲸的图表样式与 tooltip 逻辑的场景。

```ts
import { useEchartsOptions } from '@blueking/monitor-vue3-components';
import type { SeriesItem } from '@blueking/monitor-vue3-components';

const { options, series, chartId, getEchartOptions } = useEchartsOptions({
  chartRef, // Ref<HTMLElement>
  seriesList, // MaybeRef<SeriesItem[]>
  customOptions: {}, // CustomOptions
  interactionState: { isMouseOver, hoverAllTooltips }, // 可选
});
```

---

### 5.3 useChartLegend

根据 ECharts `options` 计算图例数据（max/min/avg/total 等统计值），并提供图例点击后的联动筛选逻辑。返回 `{ legendData, handleSelectLegend }`，可直接对接 [`CommonLegend`](#45-commonlegend--通用图例)。

```ts
import { useChartLegend } from '@blueking/monitor-vue3-components';
import type { LegendCustomOptions } from '@blueking/monitor-vue3-components';

const customOptions: LegendCustomOptions = {
  // 自定义图例数据加工
  legendData: list => list,
  // 自定义点击行为，返回新的 legendData
  legendClick: (actionType, item, legendData) => legendData,
};

const { legendData, handleSelectLegend } = useChartLegend(options, chartId, customOptions);
```

---

### 5.4 useChartTitleEvent

封装图表标题菜单的常用交互：跳转检索、关联告警、截图、导出 CSV、添加策略等。返回 `{ handleAlarmClick, handleMenuClick, handleMetricClick }`，可直接绑定到 [`ChartTitle`](#44-charttitle--图表标题栏) 的事件上。

> 内部通过 `inject('timeRange')` 获取时间范围，请确保上层已 `provide('timeRange', ...)`。

```ts
import { useChartTitleEvent } from '@blueking/monitor-vue3-components';

const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
  metrics, // MaybeRef<Array<Record<string, any>>>
  targets, // MaybeRef<IDataQuery[]>
  title, // MaybeRef<string>（截图/导出文件名）
  seriesData, // MaybeRef<IUnifyQuerySeriesItem[]>（导出 CSV 用）
  chartRef, // MaybeRef<HTMLElement>（截图目标）
);
```

`handleMenuClick(item)` 依据 `item.id` 分发：`explore`（跳检索）、`relate-alert`（关联告警）、`screenshot`（截图）、`export-csv`（导出 CSV）。

---

## 6. 工厂函数与工具函数

### ECharts 配置工厂

这些函数是 `useEcharts` / `useEchartsOptions` 的底层构建块，可单独调用以完全自定义图表配置。

```ts
import { createSeries, createXAxis, createYAxis, createOptions } from '@blueking/monitor-vue3-components';
import type { SeriesItem, EchartSeriesItem, CustomOptions } from '@blueking/monitor-vue3-components';

// 1. 由原始 series 生成对齐后的 series + xAxis（自动补齐首尾 null、复用同构 x 轴）
const { xData, seriesData, xAxis } = createSeries(rawSeries /* SeriesItem[] */, customSeries);

// 2. 生成 x 轴（含按时间跨度自动选择的时间格式化）
const xAxisOption = createXAxis(xData /* number[] */, { show: true });

// 3. 生成 y 轴（按 unit 自动分轴、格式化刻度）
const yAxisOption = createYAxis(seriesData /* EchartSeriesItem[] */, 'line');

// 4. 组装完整 options（含 tooltip/grid/toolbox 等默认配置）
const options = createOptions(xAxis, yAxisOption, seriesData, customOptions);
```

<details>
<summary><b>签名一览</b></summary>

| 函数 | 签名 |
| --- | --- |
| `createSeries` | `(series: SeriesItem[], customSeries?: CustomOptions['series']) => { xData: number[]; seriesData: EchartSeriesItem[]; xAxis: any[] }` |
| `createXAxis` | `(xData: number[], options?: { show: boolean }) => any[]` |
| `createYAxis` | `(yData: EchartSeriesItem[], type?: string) => any[]` |
| `createOptions` | `(xAxis, yAxis, series, customOptions?: CustomOptions['options']) => any` |

</details>

### 跳转与截图工具

```ts
import { handleExplore, handleRelateAlert, handleAddStrategy, handleStoreImage } from '@blueking/monitor-vue3-components';
```

| 函数 | 签名 | 说明 |
| --- | --- | --- |
| `handleExplore` | `(targets: IDataQuery[], timeRange: string[], autoNavTo = true) => void \| targets` | 跳转到指标/日志检索；`autoNavTo=false` 时仅返回 `targets` |
| `handleRelateAlert` | `(targets: IDataQuery[], timeRange: string[]) => void` | 依据指标 ID 跳转关联告警中心 |
| `handleAddStrategy` | `(targets: IDataQuery[], metric: IExtendMetricData \| null) => void` | 跳转到添加监控策略页 |
| `handleStoreImage` | `(title: string, targetEl: HTMLElement, customSave = false) => Promise<void \| string>` | 将 DOM 截图为 PNG 下载；`customSave=true` 时返回 dataURL 而不下载 |

> 这些工具函数依赖 `window`（如 `window.cc_biz_id`、`window.bk_log_search_url`）等蓝鲸运行时全局变量，请在蓝鲸体系内使用。

---

## 7. 类型参考（Types）

所有类型均可从包根按需 `import type`：

```ts
import type {
  PanelModel,
  SeriesItem,
  Series,
  EchartSeriesItem,
  ILegendItem,
  LegendActionType,
  DataZoomEvent,
  CustomOptions,
  LegendCustomOptions,
  ChartInteractionState,
  ValueFormatter,
} from '@blueking/monitor-vue3-components';
```

<details>
<summary><b>数据序列相关</b></summary>

```ts
// 原始序列（对外输入）
interface SeriesItem extends MonitorEchartOptions {
  datapoints: [number, number][]; // [value, timestamp][]
  alias?: string;
  target?: string;
  unit?: string;
  type?: string;
  stack?: boolean | string;
  markPoints?: [number, number][]; // 告警点 [value, timestamp][]
  markTimeRange?: IMarkTimeRange[]; // 时间范围标记
  thresholds?: IThreshold[]; // 阈值配置
  dimensions?: Record<string, any>;
  dimensions_translation?: Record<string, any>;
  metric_field?: string;
  z?: number;
}

type Series = SeriesItem[];

// 处理后的 ECharts series（对齐首尾、含 mark* 配置）
interface EchartSeriesItem {
  name: string;
  data: number[] | { value: null | number }[];
  raw_data: SeriesItem;
  alignedDatapoints?: [null | number, number][];
  unit?: string;
  type?: string;
  stack?: string;
  xAxisIndex?: number;
  yAxisIndex?: number;
  markArea?: IMarkAreaConfig;
  markLine?: IMarkLineConfig;
  markPoint?: IMarkPointConfig;
}
```

</details>

<details>
<summary><b>图例相关</b></summary>

```ts
interface ILegendItem {
  name: string;
  color: string;
  show: boolean;
  alias?: string;
  hidden?: boolean;
  max?: number | string;
  min?: number | string;
  avg?: number | string;
  total?: number | string;
  metricField?: string;
  // ...及 *Source 原始值字段
}

type LegendActionType = 'click' | 'downplay' | 'highlight' | 'shift-click';
type TableLegendHeadType = 'Avg' | 'Max' | 'Min';
```

</details>

<details>
<summary><b>自定义配置相关</b></summary>

```ts
// ExploreChart / useEcharts 的自定义处理钩子
interface CustomOptions {
  formatterData?: (formatter: any, target: IDataQuery) => any; // 请求结果预处理
  series?: (series: EchartSeriesItem[]) => EchartSeriesItem[]; // series 二次加工
  options?: (options: any) => any; // 最终 options 二次加工
  tooltips?: { showTotal?: boolean };
}

// 图例自定义
interface LegendCustomOptions {
  legendData?: (legendData: ILegendItem[]) => ILegendItem[];
  legendClick?: (actionType: LegendActionType, item: ILegendItem, legendData: ILegendItem[]) => ILegendItem[];
}

// 图表交互状态
interface ChartInteractionState {
  isMouseOver: MaybeRef<boolean>;
  hoverAllTooltips?: MaybeRef<boolean>;
}
```

</details>

<details>
<summary><b>标记（mark*）与缩放相关</b></summary>

```ts
// 数据框选缩放事件
interface DataZoomEvent {
  batch: DataZoomBatchItem[];
  type: string; // "datazoom"
}

// 时间范围标记
interface IMarkTimeRange {
  from: number;
  to: number;
  color?: string;
  borderColor?: string;
  borderType?: 'dashed' | 'dotted' | 'solid';
  shadowColor?: string;
}

// 阈值配置
interface IThreshold {
  yAxis: number;
  name?: string;
  method?: string;
  condition?: string;
}

// 另有 IMarkAreaConfig / IMarkLineConfig / IMarkPointConfig 及各自的 *DataItem
// 用于 markArea / markLine / markPoint 的精细配置
```

</details>

<details>
<summary><b>格式化相关</b></summary>

```ts
type DecimalCount = null | number | undefined;

interface FormattedValue {
  text: string;
  prefix?: string;
  suffix?: string;
}

type ValueFormatter = (
  value: number,
  decimals?: DecimalCount,
  scaledDecimals?: DecimalCount,
  timeZone?: string
) => FormattedValue;

type FormatterFunc = ((v: string) => string) | string;
```

</details>

---

## 8. 常见问题（FAQ）

- **样式错乱 / 没有样式**：确认已在应用入口引入 `import '@blueking/monitor-vue3-components/index.css';`。

- **`ExploreChart` 不出数据**：检查是否已提供全局 `$api`（`app.config.globalProperties.$api`）以及 `provide('timeRange', ...)`；`panel.targets` 中的 `apiModule` / `apiFunc` 需与 `$api` 对应。若不想耦合这些约定，请改用 [`useEchartsOptions`](#52-useechartsoptions) + 自行渲染 `vue-echarts`。

- **依赖缺失报错**：`vue-i18n`、`bkui-vue`、`monaco-editor`、`echarts` + `vue-echarts`、`dayjs` 等被声明为 external，需由宿主工程安装，详见 [第 2 章](#2-运行环境与依赖要求)。

- **`RetrievalFilter` 候选值加载慢**：适当调小 `limit`、增大 `loadDelay`，并确认 `getValueFn` 后端接口分页性能；完整用法见其随包 `readme.md`。

- **组件无对外实例方法**：本包组件均通过 Props / Emits / Slots 交互，未通过 `expose` 暴露命令式方法；需要更细粒度控制时请使用对应的组合式函数（`useEcharts` / `useChartLegend` 等）。
