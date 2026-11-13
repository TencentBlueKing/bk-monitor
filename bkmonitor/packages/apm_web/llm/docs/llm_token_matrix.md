# LLM Token 统计

## 0x01 响应样例

```json
{
  "token_matrix": {
    "estimated_to_reported_ratio": 0.17666666666666667,
    "nodes": [
      {
        "id": "input", "name": "输入", "value": 1000,
        "children": [
          {"id": "system", "name": "系统提示词", "value": 81, "children": []},
          {"id": "definitions", "name": "可用工具", "value": 203, "children": []},
          {
            "id": "context", "name": "会话上下文", "value": 716,
            "children": [
              {
                "id": "tool_calls", "name": "工具调用", "value": 608,
                "children": [
                  {"id": "tool_calls/tool/search", "name": "search", "value": 311, "call_count": 3, "children": []},
                  {"id": "tool_calls/tool/write", "name": "write", "value": 95, "call_count": 1, "children": []},
                  {"id": "tool_calls/tool/read", "name": "read", "value": 81, "call_count": 1, "children": []},
                  {"id": "tool_calls/other", "name": "其他工具", "value": 121, "call_count": 2, "children": []}
                ]
              },
              {
                "id": "conversation", "name": "会话内容", "value": 108,
                "children": [
                  {"id": "model", "name": "模型消息", "value": 47, "children": []},
                  {"id": "user", "name": "用户消息", "value": 61, "children": []}
                ]
              }
            ]
          }
        ],
        "estimated_to_reported_ratio": 0.148
      },
      {
        "id": "output", "name": "输出", "value": 200,
        "children": [
          {"id": "content", "name": "内容", "value": 150, "children": []},
          {"id": "reasoning", "name": "推理", "value": 50, "children": []}
        ],
        "estimated_to_reported_ratio": 0.32
      }
    ]
  },
  "token_categories": [
    {"key": "gen_ai.system_instructions", "label": "系统提示词", "tokens": 81},
    {"key": "gen_ai.tool.definitions", "label": "可用工具", "tokens": 203},
    {"key": "gen_ai.input.messages", "label": "输入", "tokens": 716},
    {"key": "gen_ai.output.messages", "label": "输出", "tokens": 200}
  ]
}
```

- *[1] 样例中的模型上报输入 `1,000` Token、输出 `200` Token，其中推理 `50` Token。*
- *[2] `token_categories` 只统计分类总数，不返回消息或 Part 的 Token 数。*

## 0x02 返回位置

| 请求 | 字段位置 | 条件 |
| --- | --- | --- |
| `list_flows` | `traces[].token_matrix` | 按 Trace 加载正文，`include_input_output=true` |
| `list_flows` | `traces[].flow[].token_categories` | 模型节点，包含正文预览模式 *[1]* |
| `list_flows` | `traces[].flow[].tokens` | 工具节点，`include_input_output=true` *[4]* |
| `span_detail` | `trace_tree.spans[].llm_detail` | 模型 Span，包含样例中的两个字段 *[2]* |

- *[1] `flow` 中的 `childs` 模型节点也返回分类统计。*
- *[2] 完整正文执行线与 Span 详情返回修复后的 JSON，正文预览使用修复后的数据。*
- *[3] `span_detail.origin_data` 保留原始上报内容。*
- *[4] 工具节点的 `tokens` 估算名称、参数和结果的合计，不计入 Trace 的模型 Token 总量。*

## 0x03 字段

### a. 矩阵节点

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_matrix.estimated_to_reported_ratio` | `number` | 是 | 输入、输出校准前估算量合计 ÷ 上报量合计 *[2]* |
| `token_matrix.nodes` | `array<object>` | 是 | 输入、输出根节点，可直接传入 ECharts Treemap 的 `series.data` *[4]* |
| `<node>.id` | `string` | 是 | 树内唯一、跨请求稳定的节点标识 |
| `<node>.name` | `string` | 是 | 展示名称 |
| `<node>.value` | `int` | 是 | 校准后的估算量 *[1]* |
| `<node>.children` | `array<object>` | 是 | 同结构子节点，叶子为 `[]` |
| `<node>.estimated_to_reported_ratio` | `number` | 否 | 仅根节点返回：校准前估算总量 ÷ 上报总量 *[2]* |

- *[1] 父节点等于子节点之和；已上报的用量用于校准，缺失用量时仅矩阵使用正文估算值。*
- *[2] `1` 表示两者相等；顶层按输入与输出合计计算，根节点按各侧计算。统计范围存在未上报用量的模型或上报总量为 `0` 时返回 `0`。*
- *[3] 已上报推理量计入输出比例的分子，输出校准时优先保留推理量，其余分配给内容。*
- *[4] 节点采用 [ECharts Treemap 数据结构](https://echarts.apache.org/en/option.html#series-treemap.data)，`estimated_to_reported_ratio` 为业务扩展字段。*
- *[5] 会话内容的 `other` 仅在非零时返回，承接角色无法归类的正文或无可计数正文的上报输入量。*

### b. 工具调用节点

| 节点 ID | `name` | `value` | `call_count` | `children` |
| --- | --- | --- | --- | --- |
| `tool_calls` | 工具调用 | 全部工具的输入占用 | 不返回 | Top3 工具及其他工具 *[1]* |
| `tool_calls/tool/<编码后的工具名>` | 工具名或“未知工具” | 该工具的输入占用 | 该工具的调用次数 *[2]* | `[]` |
| `tool_calls/other` | 其他工具 | Top3 之外的 Token 合计 | Top3 之外的调用次数合计 | `[]` *[5]* |

- *[1] 按工具原名汇总 Token 和调用次数，再按 Token 数降序取前三，Token 数相同时按原名排序。*
- *[2] 仅工具叶子（含“其他工具”）必填 `int` 类型的 `call_count`，统计输入中已出现的调用，输出中新生成的调用计入 `output.content`。*
- *[3] 按 `(trace_id, call_id)` 去重，同一调用的参数、结果和重复上下文只计 `1` 次，Token 累计消耗，无调用 ID 时按出现位置计数。*
- *[4] 工具 ID 使用原名的 URL 百分号编码，名称缺失时编码部分为空。*
- *[5] 存在 Top3 之外的工具时追加“其他工具”，即使 Token 为 `0` 也保留调用次数。*

### c. 分类统计

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_categories[].key` | `string` | 是 | 对应的标准属性名 |
| `token_categories[].label` | `string` | 是 | 分类展示名称 |
| `token_categories[].tokens` | `int` | 是 | 从矩阵共用的计数结果汇总 *[1][2]* |

- *[1] 系统提示词、可用工具、输入三个分类之和等于矩阵输入总量，输出分类等于矩阵输出总量。*
- *[2] 分类估算不写入 Span 的 `gen_ai.usage.input_tokens` 或 `gen_ai.usage.output_tokens`。*
