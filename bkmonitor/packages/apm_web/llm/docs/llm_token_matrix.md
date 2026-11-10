# LLM Token 统计

## 0x01 响应样例

```json
{
  "token_matrix": {
    "nodes": [
      {
        "id": "input", "name": "输入", "value": 1000,
        "children": [
          {"id": "system", "name": "系统提示词", "value": 100, "children": []},
          {"id": "definitions", "name": "可用工具", "value": 250, "children": []},
          {
            "id": "context", "name": "会话上下文", "value": 650,
            "children": [
              {
                "id": "tool_calls", "name": "工具调用", "value": 517,
                "children": [
                  {"id": "tool_calls/tool/search", "name": "search", "value": 150, "children": []},
                  {"id": "tool_calls/tool/write", "name": "write", "value": 117, "children": []},
                  {"id": "tool_calls/tool/read", "name": "read", "value": 100, "children": []},
                  {"id": "tool_calls/other", "name": "其他工具", "value": 150, "children": []}
                ]
              },
              {
                "id": "conversation", "name": "会话内容", "value": 133,
                "children": [
                  {"id": "model", "name": "模型消息", "value": 58, "children": []},
                  {"id": "user", "name": "用户消息", "value": 75, "children": []}
                ]
              }
            ]
          }
        ],
        "estimated_to_reported_ratio": 0.12
      },
      {
        "id": "output", "name": "输出", "value": 200,
        "children": [
          {"id": "content", "name": "内容", "value": 150, "children": []},
          {"id": "reasoning", "name": "推理", "value": 50, "children": []}
        ],
        "estimated_to_reported_ratio": 0.32
      }
    ],
    "tools": [
      {
        "trace_id": "trace-1", "name": "search", "label": "search",
        "span_ids": ["model-1"], "call_count": 1, "tokens": 150
      },
      {
        "trace_id": "trace-1", "name": "write", "label": "write",
        "span_ids": ["model-1"], "call_count": 1, "tokens": 117
      },
      {
        "trace_id": "trace-1", "name": "read", "label": "read",
        "span_ids": ["model-1"], "call_count": 1, "tokens": 100
      },
      {
        "trace_id": "trace-1", "name": "query", "label": "query",
        "span_ids": ["model-1"], "call_count": 1, "tokens": 83
      },
      {
        "trace_id": "trace-1", "name": "exec", "label": "exec",
        "span_ids": ["model-1"], "call_count": 1, "tokens": 67
      }
    ]
  },
  "token_categories": [
    {"key": "gen_ai.system_instructions", "label": "系统提示词", "tokens": 100},
    {"key": "gen_ai.tool.definitions", "label": "可用工具", "tokens": 250},
    {"key": "gen_ai.input.messages", "label": "输入", "tokens": 650},
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
| `span_detail` | `trace_tree.spans[].llm_detail` | 模型 Span，包含样例中的两个字段 *[2]* |

- *[1] `flow` 中的 `childs` 模型节点也返回分类统计。*
- *[2] 完整正文执行线与 Span 详情返回修复后的 JSON 和补齐用量，正文预览使用修复后的数据。*
- *[3] `span_detail.origin_data` 保留原始上报内容。*

## 0x03 字段

### a. 矩阵节点

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_matrix.nodes` | `array<object>` | 是 | 输入、输出根节点，可直接传入 ECharts Treemap 的 `series.data` *[4]* |
| `<node>.id` | `string` | 是 | 树内唯一、跨请求稳定的节点标识 |
| `<node>.name` | `string` | 是 | 展示名称 |
| `<node>.value` | `int` | 是 | 校准后的估算量 *[1]* |
| `<node>.children` | `array<object>` | 是 | 同结构子节点，叶子为 `[]` |
| `<node>.estimated_to_reported_ratio` | `number / null` | 否 | 仅根节点返回：校准前估算总量 ÷ 上报总量 *[2]* |

- *[1] 父节点等于子节点之和，输入、输出总量分别对齐模型用量。*
- *[2] `1` 表示两者相等，该侧存在未上报用量的模型或上报总量为 `0` 时返回 `null`。*
- *[3] 已上报推理量计入输出比例的分子，输出校准时优先保留推理量，其余分配给内容。*
- *[4] 节点采用 [ECharts Treemap 数据结构](https://echarts.apache.org/en/option.html#series-treemap.data)，`estimated_to_reported_ratio` 为业务扩展字段。*
- *[5] 会话内容的 `other` 仅在非零时返回，承接角色无法归类的正文或无可计数正文的上报输入量。*

### b. 工具调用节点

| 节点 ID | `name` | `value` | `children` |
| --- | --- | --- | --- |
| `tool_calls` | 工具调用 | 全部工具的输入占用 | Top3 工具及其他工具 *[1]* |
| `tool_calls/tool/<编码后的工具名>` | 工具名或“未知工具” | 该工具的输入占用 | `[]` *[2]* |
| `tool_calls/other` | 其他工具 | Top3 之外的合计 | `[]` *[3]* |

- *[1] 同名工具汇总后按 Token 数降序取前三，数量相同时按原名排序，工具参数与结果合并统计。*
- *[2] ID 使用工具原名的 URL 百分号编码，名称缺失时编码部分为空，调用次数与 Span 关联见 `token_matrix.tools`。*
- *[3] 其余工具合计非零时追加“其他工具”，与会话内容的 `other` 含义不同。*

### c. 工具占用

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_matrix.tools[].trace_id` | `string` | 是 | 所属 Trace |
| `token_matrix.tools[].name` | `string` | 是 | 工具名，无法关联时为空字符串 |
| `token_matrix.tools[].label` | `string` | 是 | 工具名或“未知工具” |
| `token_matrix.tools[].span_ids` | `array<string>` | 是 | 输入上下文包含该调用的模型 Span |
| `token_matrix.tools[].call_count` | `int` | 是 | 按调用 ID 去重的次数 *[1]* |
| `token_matrix.tools[].tokens` | `int` | 是 | 输入中工具参数与结果的合计 *[2]* |

- *[1] 无调用 ID 时按出现位置计数。*
- *[2] 同一调用被多次携带时累计重复消耗，输出中新生成的工具调用计入 `output.content`。*
- *[3] 返回全部工具，按 Token 数降序排列。*

### d. 分类与来源

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_categories[].key` | `string` | 是 | 对应的标准属性名 |
| `token_categories[].label` | `string` | 是 | 分类展示名称 |
| `token_categories[].tokens` | `int` | 是 | 从矩阵共用的计数结果汇总 *[1]* |
| `estimated_token_fields` | `array<string>` | 否 | 用估算补齐的字段，如 `["input_tokens"]` *[2]* |

- *[1] 系统提示词、可用工具、输入三个分类之和等于矩阵输入总量，输出分类等于矩阵输出总量。*
- *[2] 模型节点、包含估算回填的 Agent 节点、Trace 和执行线响应顶层携带此标记。*
- *[3] 字段取值为 `input_tokens`、`output_tokens`，已上报的 `0` 不算缺失。*
