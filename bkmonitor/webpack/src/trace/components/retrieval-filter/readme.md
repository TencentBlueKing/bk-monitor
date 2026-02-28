### RetrievalFilter 组件说明

检索筛选组件，支持 UI 模式与 QueryString 模式切换，提供“收藏”“常驻筛选”“复制/清空/搜索”等能力，并可通过插槽在最左侧追加自定义控件（如空间选择、业务模块选择）。

---

## 安装与引入

```tsx
import RetrievalFilter from '@/trace/components/retrieval-filter/retrieval-filter';
```

> 组件基于 `vue3 + tsx` 开发，仅适用于 `src/trace` 目录下的 Vue3 工程。

---

## 基础示例（UI 模式）

```tsx
import { defineComponent, ref } from 'vue';
import RetrievalFilter from '@/trace/components/retrieval-filter/retrieval-filter';
import type {
  IFilterField,
  EMode,
  IGetValueFnParams,
  IWhereValueOptionsItem,
} from '@/trace/components/retrieval-filter/typing';

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

    const conditions = ref<any[]>([]);
    const queryString = ref('');

    const getValueFn = async (_params: IGetValueFnParams): Promise<IWhereValueOptionsItem> => {
      // 这里对接后端检索值接口
      return {
        count: 2,
        list: [
          { id: 'svc-a', name: 'svc-a' },
          { id: 'svc-b', name: 'svc-b' },
        ],
      };
    };

    function handleWhereChange(v: any[]) {
      conditions.value = v; // 与 changeWhereFormatter 配合后的外部 where 格式
    }
    function handleQueryStringChange(v: string) {
      queryString.value = v;
    }
    function handleSearch() {
      // 触发查询
    }

    return () => (
      <RetrievalFilter
        fields={fields.value}
        where={conditions.value}
        queryString={queryString.value}
        filterMode={EMode.ui}
        getValueFn={getValueFn}
        isShowResident={true}
        isShowCopy={true}
        isShowClear={true}
        onWhereChange={handleWhereChange}
        onQueryStringChange={handleQueryStringChange}
        onSearch={handleSearch}
      />
    );
  },
});
```

---

## 高级示例（带插槽 + 常驻筛选 + 收藏）

参考 `alarm-retrieval-filter` 用法：

```tsx
<RetrievalFilter
  changeWhereFormatter={where =>
    where.map(w => ({ key: w.key, method: w.method, value: w.value, condition: w.condition }))
  }
  commonWhere={residentCondition}
  favoriteList={favoriteList}
  fields={fields}
  filterMode={filterMode}
  getValueFn={getValueFn}
  handleGetUserConfig={handleGetUserConfig}
  handleSetUserConfig={handleSetUserConfig}
  isShowClear={true}
  isShowCopy={true}
  isShowResident={true}
  loadDelay={0}
  queryString={queryString}
  residentSettingOnlyId={residentSettingOnlyId}
  where={conditions}
  onCommonWhereChange={handleResidentConditionChange}
  onModeChange={handleFilterModeChange}
  onQueryStringChange={handleQueryStringChange}
  onSearch={handleQuery}
  onWhereChange={handleConditionChange}
>
  {{
    default: () => (
      // 这里可以放置空间选择器、模块选择等自定义控件
      <YourCustomControls />
    ),
  }}
</RetrievalFilter>
```

---

## 属性（Props）

- `fields: IFilterField[]` 字段列表（必传）。
- `getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>` 候选值获取函数，支持滚动加载与延迟加载；默认返回空列表。
- `where: IWhereItem[]` UI 模式条件值（外部格式，可配合 `whereFormatter`/`changeWhereFormatter` 自定义转换）。
- `commonWhere: IWhereItem[]` 常驻筛选条件值。
- `queryString: string` QueryString 模式语句。
- `selectFavorite: { commonWhere?: IWhereItem[]; where?: IWhereItem[] } | null` 当前选中的收藏项。
- `favoriteList: IFavoriteListItem[]` 收藏列表。
- `residentSettingOnlyId: string` 常驻设置唯一 ID，用于读写用户配置。
- `isDefaultResidentSetting: boolean` 是否使用“默认常驻设置”（true 时 `residentSettingValue` 来源为 `commonWhere`）。
- `filterMode: EMode` 当前模式，`ui | queryString`，默认 `ui`。
- `isShowFavorite: boolean` 是否显示收藏按钮，默认 `false`。
- `isShowResident: boolean` 是否显示常驻筛选按钮，默认 `false`。
- `isShowCopy: boolean` 是否显示复制按钮，默认 `false`。
- `isShowClear: boolean` 是否显示清空按钮，默认 `false`。
- `isShowSearchBtn: boolean` 是否显示最右侧搜索按钮，默认 `true`。
- `defaultShowResidentBtn: boolean` 进入时是否默认展开常驻设置，默认 `false`。
- `defaultResidentSetting: string[]` 默认常驻设置显示字段集合。
- `placeholder: string` 输入占位文案，默认 `window.i18n.t('快捷键 / ，可直接输入')`。
- `isSingleMode: boolean` 是否是单模式（隐藏模式切换），默认 `false`。
- `whereFormatter: (where: any[]) => INormalWhere[]` 外部 → 内部格式化函数，默认原样返回。
- `changeWhereFormatter: (where: INormalWhere[]) => any[]` 内部 → 外部格式化函数，默认原样返回。
- `handleGetUserConfig: (key: string, config?: Record<string, any>) => Promise<string[] | undefined>` 常驻设置读取用户配置。
- `handleSetUserConfig: (value: string, configId?: string) => Promise<boolean>` 常驻设置写入用户配置。
- `loadDelay: number` 候选值加载延时（ms），默认 `300`。
- `limit: number` 候选值滚动加载每次条数，默认 `200`。

类型速览：

```ts
interface IFilterField {
  alias: string; // 字段别名
  name: string; // 字段名
  type: EFieldType; // 字段类型，如 keyword / integer / duration 等
  isEnableOptions?: boolean; // 是否需要异步加载候选项
  methods: Array<{
    alias: string; // 操作符展示别名（如 = / != / 包含）
    value: string; // 操作符值（如 equal / not_equal / include）
    options?: Array<{
      // 其他可选项（通配符、组关系等）
      name: string; // is_wildcard / group_relation 等
      label: string; // 展示名
      default?: boolean | string;
      children?: Array<{ label: string; value: string }>;
    }>;
    placeholder?: string;
    wildcardValue?: string; // 异步搜索时默认操作符
  }>;
}
```

---

## 事件（Emits）

- `favorite(isEdit: boolean)` 点击收藏按钮；`true` 表示“覆盖当前收藏”，`false` 表示“另存为新收藏”。
- `whereChange(v: IWhereItem[])` UI 模式条件变更（已通过 `changeWhereFormatter` 转换为外部所需格式）。
- `queryStringChange(v: string)` QueryString 提交（点击搜索或触发查询时）。
- `modeChange(v: EMode)` 模式切换。
- `queryStringInputChange(v: string)` QueryString 输入中变更（未提交）。
- `commonWhereChange(where: IWhereItem[])` 常驻筛选条件变更（格式同外部 where）。
- `showResidentBtnChange(v: boolean)` 常驻设置面板展开/收起变化。
- `search()` 点击“搜索”按钮触发。
- `copyWhere(v: IWhereItem[])` 在 UI 模式点击“复制”时触发，返回当前外部 where 格式。
- `setFavoriteCache(commonWhere: IWhereItem[])` 当“收起常驻设置”并且不是默认常驻设置时，用于写入收藏缓存。

---

## 插槽（Slots）

- `default` 渲染在左侧模式切换与输入区域之间，常用于追加空间、模块等条件入口。

```tsx
<RetrievalFilter>
  {{
    default: () => <SpaceSelector /* 自定义控件 */ />,
  }}
</RetrievalFilter>
```

---

## QueryString 模式示例

```tsx
<RetrievalFilter
  fields={fields}
  filterMode={EMode.queryString}
  queryString={queryString}
  onQueryStringChange={v => (queryString = v)}
  onSearch={() => {
    /* 提交查询 */
  }}
/>
```

> 若解析错误，组件会在右侧高亮并通过提示气泡显示错误信息。

---

## 常见问题

- 无“对外方法”：组件未通过 `expose` 导出方法，交互均通过 Props/Emits/插槽完成。
- 候选值加载卡顿：可适当调小 `limit`、增大 `loadDelay`，并确认 `getValueFn` 的后端接口分页性能。
- 外部条件格式不一致：使用 `whereFormatter` 与 `changeWhereFormatter` 双向转换内部/外部格式。

---

## 类型参考（外部 where 与内部格式）

```ts
// 外部 where（常用于 whereChange / commonWhereChange / copyWhere 等输出）
interface IWhereItem {
  key: string;
  value: Array<string | number>;
  method?: string; // equal / not_equal / include / exclude ...
  condition?: 'and' | string;
  options?: { is_wildcard?: boolean; group_relation?: boolean };
}

// 组件内部格式（仅用于 props whereFormatter / changeWhereFormatter）
interface INormalWhere {
  key: string;
  value: Array<string | number>;
  method: string;
  condition: 'and';
  options: Record<string, any>;
}
```

---

## 字段模型规范（重要）

`fields: IFilterField[]` 决定了 UI 与 QueryString 能力边界，建议按以下规范配置：

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
    wildcardValue?: string; // 异步搜索时默认操作符（有些场景需要）
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

---

## QueryString 能力与提示

- 解析与提示：当解析失败时，右侧会出现红色高亮，并通过提示气泡展示错误详情（来自解析器 `useQueryStringParseErrorState`）。
- 支持的 token 类型（内部）：`key`、`method`、`value`、`condition(AND/OR)`、`bracket`、`split`、`value-condition`。UI 会在需要时给出建议。
- 候选联想：在 QueryString 输入过程中，组件会基于 `fields` 与 `getValueFn` 给出键/值联想与收藏项选择。

> 建议：对于包含海量离散值的字段（如主机、服务、实例），优先走 `getValueFn` + 分页；避免在前端硬编码全集。

---

## 常驻筛选与收藏交互细节

- 展开/收起：点击右侧“齿轮”按钮可展开/收起常驻面板；`defaultShowResidentBtn` 可控制默认展开。
- 回填规则：收起时，如果常驻条件面板中存在值，组件会将其“回填”到上方 UI 模式的条件区域，并清空面板，伴随提示。
- 收藏：
  - `isShowFavorite` 开启后显示收藏按钮；
  - `favoriteList` 提供收藏数据；
  - `favorite(isEdit)` 事件：`true` 覆盖当前收藏，`false` 另存为；
  - `setFavoriteCache(commonWhere)`：在“非默认常驻设置”收起时触发，用于帮助外部缓存与当前收藏关联的临时值；
  - `selectFavorite`：传入当前选中的收藏项（含 `where/commonWhere`），组件会按该收藏渲染。

---

## 事件时序与行为说明

- UI 模式：
  - `onWhereChange`：UI 条件变化即触发，外部可立即同步状态；
  - `onSearch`：点击最右侧“搜索”按钮触发，通常用于真正发起请求；
  - `onCopyWhere`：点击“复制”时触发，返回格式与 `onWhereChange` 一致。
- QueryString 模式：
  - `onQueryStringInputChange`：输入中变化（未提交）；
  - `onQueryStringChange`：点击“搜索”或主动提交时触发；
  - `onSearch`：与 UI 模式一致，作为统一“执行查询”的时机；
  - 解析错误：不阻断输入与提交，但会给出错误提示，建议外部在收到 `onQueryStringChange` 后进行兜底校验。
- 模式切换：
  - `onModeChange`：UI 与 QueryString 间切换，外部可据此决定是否转换条件或清理状态。
- 常驻面板：
  - `onCommonWhereChange`：常驻条件变化；
  - `onShowResidentBtnChange`：面板显隐。

---
