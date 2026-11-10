# LLM Token 统计

## 0x01 响应样例

```json
{
  "token_matrix": {
    "nodes": [
      {
        "key": "input",
        "label": "输入",
        "tokens": 1000,
        "children": [
          {
            "key": "system",
            "label": "系统提示词",
            "tokens": 158,
            "children": []
          },
          {
            "key": "definitions",
            "label": "可用工具",
            "tokens": 395,
            "children": []
          },
          {
            "key": "context",
            "label": "会话上下文",
            "tokens": 447,
            "children": [
              {
                "key": "tool_calls",
                "label": "工具调用",
                "tokens": 237,
                "children": []
              },
              {
                "key": "conversation",
                "label": "会话内容",
                "tokens": 210,
                "children": [
                  {
                    "key": "model",
                    "label": "模型消息",
                    "tokens": 92,
                    "children": []
                  },
                  {
                    "key": "user",
                    "label": "用户消息",
                    "tokens": 118,
                    "children": []
                  },
                  {
                    "key": "other",
                    "label": "其他",
                    "tokens": 0,
                    "children": []
                  }
                ]
              }
            ]
          }
        ],
        "estimate_ratio": 0.076
      },
      {
        "key": "output",
        "label": "输出",
        "tokens": 200,
        "children": [
          {
            "key": "content",
            "label": "内容",
            "tokens": 150,
            "children": []
          },
          {
            "key": "reasoning",
            "label": "推理",
            "tokens": 50,
            "children": []
          }
        ],
        "estimate_ratio": 0.32
      }
    ],
    "tools": [
      {
        "trace_id": "trace-1",
        "name": "search",
        "label": "search",
        "span_ids": [
          "model-1"
        ],
        "call_count": 1,
        "tokens": 237
      }
    ]
  },
  "token_categories": [
    {
      "key": "gen_ai.system_instructions",
      "label": "系统提示词",
      "tokens": 158
    },
    {
      "key": "gen_ai.tool.definitions",
      "label": "可用工具",
      "tokens": 395
    },
    {
      "key": "gen_ai.input.messages",
      "label": "输入",
      "tokens": 447
    },
    {
      "key": "gen_ai.output.messages",
      "label": "输出",
      "tokens": 200
    }
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
| `token_matrix.nodes` | `array<object>` | 是 | 输入、输出根节点 |
| `<node>.key` | `string` | 是 | 同级唯一的分类标识 |
| `<node>.label` | `string` | 是 | 展示名称 |
| `<node>.tokens` | `int` | 是 | 校准后的估算量 *[1]* |
| `<node>.children` | `array<object>` | 是 | 同结构子节点，叶子为 `[]` |
| `<node>.estimate_ratio` | `number / null` | 否 | 仅根节点返回：校准前估算总量 ÷ 上报总量 *[2]* |

- *[1] 父节点等于子节点之和，输入、输出总量分别对齐模型用量。*
- *[2] `1` 表示两者相等，该侧存在未上报用量的模型或上报总量为 `0` 时返回 `null`。*
- *[3] 已上报推理量计入输出比例的分子，输出校准时优先保留推理量，其余分配给内容。*

### b. 工具占用

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

### c. 分类与来源

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `token_categories[].key` | `string` | 是 | 对应的标准属性名 |
| `token_categories[].label` | `string` | 是 | 分类展示名称 |
| `token_categories[].tokens` | `int` | 是 | 从矩阵共用的计数结果汇总 *[1]* |
| `estimated_token_fields` | `array<string>` | 否 | 用估算补齐的字段，如 `["input_tokens"]` *[2]* |

- *[1] 系统提示词、可用工具、输入三个分类之和等于矩阵输入总量，输出分类等于矩阵输出总量。*
- *[2] 模型节点、包含估算回填的 Agent 节点、Trace 和执行线响应顶层携带此标记。*
- *[3] 字段取值为 `input_tokens`、`output_tokens`，已上报的 `0` 不算缺失。*
