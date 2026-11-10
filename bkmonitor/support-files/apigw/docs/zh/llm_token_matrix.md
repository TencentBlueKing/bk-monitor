### 功能说明

Token 矩阵描述模型调用的输入、输出组成。矩阵节点、工具占用和分类统计中的 `tokens` 使用同一套校准后的估算值，不能视为供应商逐项计费数据。

| 场景 | 获取位置 |
| --- | --- |
| 单 Trace 的正文或预览请求 | `list_flows` 返回的 `traces[].token_matrix` |
| 单模型 Span 详情 | `span_detail` 返回的 `trace_tree.spans[].llm_detail.token_matrix` |
| 模型 Span 分类统计 | `llm_detail.token_estimates`；完整正文模式的 `flow` 中也提供此字段 |
| 结构请求、会话概览 | 不返回矩阵或分类统计；按 Trace 加载正文后获取 |

`list_flows` 的第二次请求使用 `include_input_output=true`。即使同时设置 `input_output_preview=true`，也返回根据完整已采集正文计算的矩阵，执行线正文仍保持预览长度。

### Token 口径

| 上报情况 | 总量与分项 |
| --- | --- |
| 输入或输出总量已上报 | 保留总量，分项按 `上报总量 × 分项原始估算 / 原始估算总和` 校准，向上或向下缩放均适用；整数舍入后分项之和等于总量 |
| 输入或输出总量未上报 | 用原始估算补齐对应的 `gen_ai.usage.input_tokens` 或 `gen_ai.usage.output_tokens` |
| 显式上报 `0` | 保留 `0`，不按缺失处理 |
| 推理 Token 已上报 | 输出中的推理量优先使用上报值，其余输出分配给内容；推理量超过输出总量时，矩阵推理量以输出总量为限，原上报属性不变 |
| 没有可计数正文 | 输入总量归入“其他”；输出使用已知推理量，其余归入“内容”，不将这部分分配给具体消息或工具 |

未上报而补齐的字段通过 `estimated_token_fields` 表示，例如 `["input_tokens"]`。该字段仅在使用估算补齐时出现，位于对应模型 Span、Trace 概览及 `list_flows` 顶层。Agent 从子节点回填的用量包含估算时，也携带此字段；Agent 自己已上报的值保持不变。该标记不表示矩阵是否经过比例校准。

正文采用模型对应的分词编码估算，无法匹配的模型使用通用编码。估算不包含供应商私有封装开销，也不根据图片 URL、音频数据或推理摘要推测不可见内容的实际用量。缓存读写属于输入总量的子集，不再次累计。

截断 JSON 尽量保留可恢复的正文；无法恢复的内容保持原值。修复只影响标准化的 LLM 数据，`origin_data` 保留原始上报内容。

### 矩阵结构

`token_matrix` 包含 `nodes` 和 `tools`。`nodes` 是输入、输出两棵树，所有层级使用相同的节点结构。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| key | string | 稳定标识，用于合并；不使用中文名称作为关联键 |
| label | string | 后台返回的展示名称，中文环境下为下表中的名称 |
| tokens | int | 校准后的估算 Token 数；父节点等于直接子节点之和 |
| children | array | 子节点，叶子为 `[]` |
| estimate_ratio | number / null | 仅输入、输出根节点提供：校准前估算总量 / 上报总量。`1` 表示两者相等，`0.8` 表示原始估算是上报值的 `80%`。任一模型未上报该侧总量，或所有模型该侧总量之和为 `0` 时为 `null` |

存在已上报推理量时，输出比例的分子使用“内容原始估算 + 上报推理量”，不使用推理摘要长度。该比例衡量原始估算和上报量的接近程度，不代表每个分项的准确率。

| 节点路径 | 中文名称 | 范围 |
| --- | --- | --- |
| input | 输入 | 系统提示词、工具定义和会话上下文 |
| input.system | 系统提示词 | 系统指令及输入中的 system / developer 消息 |
| input.definitions | 可用工具 | 工具名称、描述、参数定义 |
| input.context | 会话上下文 | 工具调用及会话内容 |
| input.context.tool_calls | 工具调用 | 输入历史中的工具参数与工具结果，合并统计 |
| input.context.conversation | 会话内容 | 模型消息、用户消息及其他内容 |
| input.context.conversation.model | 模型消息 | assistant / model 的非工具内容 |
| input.context.conversation.user | 用户消息 | 用户的非工具内容 |
| input.context.conversation.other | 其他 | 未归入上述类别的输入及无正文可归因的输入总量 |
| output | 输出 | 内容与推理 |
| output.content | 内容 | 除 Reasoning 外的模型输出，包含工具调用 |
| output.reasoning | 推理 | 已上报推理用量，缺失时使用可见 reasoning 正文估算 |

前端按 `children` 遍历节点，允许后台扩展分类；`key` 只需在同级内唯一。各分类为 `0` 时仍返回。

### 工具占用

`tools` 返回全部工具聚合项，按 `tokens` 降序排列，不在单 Trace 内截取 TopK。

```json
{
  "trace_id": "trace-demo",
  "name": "search",
  "label": "search",
  "span_ids": ["model-span-1", "model-span-2"],
  "call_count": 3,
  "tokens": 420
}
```

| 字段 | 说明 |
| --- | --- |
| trace_id | 所属 Trace |
| name | 工具名，无法关联时为空字符串 |
| label | 展示名称；无法关联时为“未知工具” |
| span_ids | 输入上下文包含该工具调用的模型 Span ID 列表，用于定位 Token 消耗来源 |
| call_count | 当前 Trace 已加载模型上下文中不同工具调用 ID 的数量；同一调用的参数与结果只计一次。无 ID 时按出现位置计数 |
| tokens | 该工具在输入上下文中的校准后估算量；同一历史调用被多个模型请求再次携带时，重复消耗累计 |

工具实际执行 Span 的用量不重复加入矩阵。输出中新生成的工具调用计入 `output.content`，只有后续模型请求将其作为输入时，才计入工具占用。

### 分类统计

`token_estimates` 是分类列表，分别对应系统提示词、可用工具、输入消息和输出消息。示例为某条模型 Span 的输入分类：

```json
{
  "key": "gen_ai.input.messages",
  "label": "输入",
  "tokens": 12,
  "items": [
    {"tokens": 5, "parts": [5]},
    {"tokens": 7, "parts": [3, 4]}
  ]
}
```

`items` 与该属性的数组顺序一致；消息的 `parts` 与消息正文 Part 顺序一致。系统提示词、工具定义的每个条目只使用 `tokens`，`parts` 为 `[]`。系统提示词、可用工具、输入三个分类的总和等于矩阵输入总量，输出分类等于矩阵输出总量。

已知总量但缺少正文时，分类总量包含无法分配到条目的部分。已上报而没有可见正文的推理用量也包含在输出分类总量中，不凭空补造消息条目。

### 跨 Trace 合并

1. 按 `trace_id` 保存每次加载结果；刷新同一 Trace 时替换旧结果，避免重复累计。
2. 节点按完整 `key` 路径合并，`tokens` 求和。
3. 输入、输出比例分别按对应根节点的 `tokens` 加权：`Σ(tokens × estimate_ratio) / Σtokens`。任一参与结果的比例为 `null` 时，合并比例也为 `null`。
4. 工具按 `name` 汇总 Token 数和调用次数，同时保留各 Trace 的 `span_ids`。全部合并后再取 TopK。

合并结果只描述已经加载的 Trace。会话概览不包含正文，不能据此推算尚未加载 Trace 的矩阵。
