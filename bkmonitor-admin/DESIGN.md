# Design System

`bkmonitor-admin` 是面向蓝鲸监控平台管理和排障的后台工具。界面设计优先服务于高密度信息浏览、检索、对比和问题定位，不做营销式页面和装饰性视觉。

## 设计目标

- 信息优先：核心资源字段、关联关系、状态和异常线索必须容易扫描。
- 操作可预期：列表、详情、筛选、分页、环境/租户切换保持统一交互。
- 管理后台气质：克制、清晰、稳定，不使用大面积插画、渐变背景或卡片堆叠。
- AI 友好：组件职责清晰、命名直接、组合方式固定，方便 Agent 后续扩展页面。
- 原始数据可见：用于排障的字段默认显示原始值，不随意翻译或语义归一。

## 页面结构

### App Shell

- 左侧固定导航，右侧内容区滚动。
- 左侧顺序固定为：Logo、环境选择、租户选择、资源导航、系统设置。
- 环境和租户上下文只放在左侧导航顶部，不在页面正文重复展示。
- 新增一级资源页面时，优先挂到现有导航分组，不新建独立布局。

### 列表页

列表页统一使用：

- 外层：`<section className="page-panel">`
- 标题区：`.page-heading`
- 筛选区：`FilterToolbar`
- 表格：`DataTable`
- 分页：`Pagination`

列表页正文不要再包一层大卡片。筛选工具栏本身可以有边框和背景，表格组件负责自己的边界。

### 详情页

详情页按“摘要信息 + 关联数据 + 原始配置/JSON”组织：

- 顶部展示资源 ID / 名称和返回列表入口。
- 基础字段用紧凑 Info Grid。
- 关联对象优先用表格。
- 大对象、配置、API 返回体使用 `JsonBlock`。
- 不要把详情页拆成过多视觉卡片；只有重复项、配置块、JSON 块需要明确边界。

## 颜色和视觉

- 主题色使用现有 CSS token：`--primary`、`--border`、`--muted`、`--card` 等。
- 页面主体保持浅色背景，左侧导航保持深色背景。
- 不新增大面积单一色系主题，不使用紫蓝渐变、装饰光斑、背景 SVG。
- 状态颜色仅表达风险或语义：
  - `success`：启用、运行正常、默认启用项
  - `danger`：删除、禁用、失败、高风险
  - `warning`：部分异常、跳过校验、需要注意
  - `muted`：无、否、默认弱信息
- 不为了“好看”给所有枚举都上颜色；没有明确语义时用默认样式或原始文本。

## 字体和密度

- 不使用随 viewport 缩放的字体。
- 表格、筛选、侧边栏使用紧凑字号，避免 hero 级标题。
- 页面标题通常为 24px 左右；卡片/块标题使用更小字号。
- 按钮、选择器、输入框高度保持 32-40px 区间。
- 文本必须在移动和桌面宽度下不溢出容器；长 ID 用截断、换行或等宽块展示。

## 组件规范

### 基础组件位置

- `src/shared/components/ui/`：shadcn/ui 风格的基础 copy-in 组件。
- `src/shared/components/`：跨业务复用的组合组件。
- `src/features/*/`：资源专属组件、页面、API 和 schema。

页面组件不要直接拼基础 DOM 样式来重新实现已有控件。优先组合现有共享组件。

### ChoiceInput

`ChoiceInput` 是项目统一选择组件，负责替代原生下拉框和临时 datalist。

使用场景：

- 单选：环境、租户、分页 page size、枚举过滤。
- 多选：状态、类型等多值过滤。
- 自定义输入：后端枚举不完整、需要输入原始值的排障字段。

使用规则：

- 单选使用 `mode="single"` 或默认模式。
- 多选使用 `mode="multiple"`。
- 允许用户输入后端未枚举值时设置 `allowCustom`。
- 管理排障字段的选项 label 和 value 默认都用原始值。
- 不要用原生 `<select>` 做新页面交互，除非是临时降级并在同轮补齐。

示例：

```tsx
<ChoiceInput
  value={status}
  mode="multiple"
  allowCustom
  options={[
    { label: 'RUNNING', value: 'RUNNING' },
    { label: 'deleted', value: 'deleted' }
  ]}
  placeholder="全部"
  onChange={setStatus}
/>
```

### FilterToolbar

列表过滤统一使用 `FilterToolbar`。

支持字段类型：

- `text`：普通文本。
- `number`：数字输入。
- `select`：单选。
- `multi-select`：多选，默认可配合自定义输入。
- `combobox`：建议值 + 自定义输入。
- `boolean`：三态，全部 / 是 / 否。

使用规则：

- 常用 3-4 个字段放主筛选区，其余加 `advanced: true`。
- 回车必须触发搜索。
- 重置必须清空所有过滤并回到第一页。
- 活动过滤条件必须以 Badge/Chip 展示，并支持单独清除。
- 多选值在页面状态中使用 `string[]`，不要为了传参把它提前压成 CSV 字符串。

### Badge

`Badge` 用于短状态、枚举、标签和布尔结果。

使用规则：

- Badge 文案优先显示后端原始值。
- 只有用户明确需要中文含义时，才额外加中文说明。
- 排障敏感字段，例如 `status`、`phase`、`kind`，默认不翻译。
- 不要用 Badge 承载长文本、描述段落或复杂 JSON。

### DataTable

列表和关联对象表格统一使用 `DataTable`。

使用规则：

- 列数量要克制，列表页只放扫描所需字段。
- 大字段、字段数组、JSON、长配置不要塞进列表列，放详情页。
- ID、名称、状态、关联计数、更新时间优先出现在列表。
- 详情页中关联对象也使用 `DataTable`，不要单独手写表格样式。

### Pagination

分页统一使用 `Pagination`。

使用规则：

- page size 选项保持 20 / 50 / 100。
- 列表搜索或 page size 变化必须回到第一页。
- 分页放在表格下方，不放页面顶部。

### JsonBlock

`JsonBlock` 用于展示配置、RPC 返回、component_config、存储配置等对象。

使用规则：

- 不要把 JSON 转成散乱的文本段落。
- 不要对大 JSON 默认全部展开成页面正文。
- 敏感字段展示前必须在后端或前端 schema 层确认已脱敏。

## 表单和筛选

- 输入、选择、按钮必须对齐，筛选栏采用横向换行布局。
- 筛选字段 label 使用后端字段名，如 `bk_data_id`、`cluster_type`、`status`。
- 业务排障字段不要翻译成含糊中文名，避免失去和后端模型的对应关系。
- 布尔字段展示可用“是/否”，但请求参数仍使用 boolean。
- 枚举字段如果存在大小写差异，不做自动合并；用户选择什么原始值就查什么。

## 原始值原则

管理后台首先服务排障。以下字段默认展示原始值：

- 资源 ID：`bk_data_id`、`table_id`、`cluster_id`
- 状态：`status`、`phase`
- 类型：`cluster_type`、`source_label`、`type_label`、`schema_type`
- 来源：`created_from`、`registered_system`
- 配置键：option name、storage config key、component config key

允许加颜色、分组和 tooltip，但不要替换原始值。

## 空态、加载和错误

- 加载态统一使用 `PageState`。
- 错误态要展示可诊断信息，例如 `KernelRpcError` message。
- 无数据时显示明确空态，不渲染空白区域。
- 没有环境配置时必须引导添加环境，不应让页面抛错。

## 响应式

- 左侧导航在桌面固定。
- 窄屏下侧边栏可转为顶部或流式布局，但环境/租户选择仍必须靠近导航入口。
- 表格可横向滚动，不能压缩到列内容互相覆盖。
- 按钮文本不允许溢出；必要时使用图标按钮或更短文案。

## 新增页面检查清单

新增或重构页面前，先确认：

- 是否使用了 App Shell 现有布局。
- 是否通过 `FilterToolbar` 实现列表筛选。
- 是否通过 `ChoiceInput` 实现单选、多选或自定义输入。
- 是否通过 `DataTable` 展示列表和关联对象。
- 是否通过 `Pagination` 处理分页。
- 是否保留排障字段原始值。
- 是否避免在列表中展示大字段或大数组。
- 是否处理 loading、error、empty 状态。
- 是否同步更新相关 docs / task list。

## 禁止事项

- 不新增 Ant Design、MUI、react-select 等大型组件库，除非重新做技术选型并更新文档。
- 不在页面内直接使用原生 `<select>` 作为正式交互控件。
- 不做营销落地页、hero 区、大插画背景。
- 不使用装饰性渐变、光斑、SVG 背景。
- 不把 UI 卡片层层嵌套。
- 不把后端原始状态值强行翻译或别名合并。
- 不在页面组件里直接拼 `kernel_rpc` 请求。
