### 功能描述

按 `group_field`、`group_id` 精确查询 Agent 执行事件线。接口先定位分组内的 Trace，再将每个 Trace 的标准化 Span 按 `span_id`、`parent_span_id` 组织为树。

树节点与 `list_llm_spans` 返回的 Span 字段一致，`childs` 表示直接子 Span。一个 Trace 可以有多个根节点；父 Span 未出现在标准化结果中时，该 Span 作为根节点返回。

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| group_field | string | 是 | 分组字段，例如 `trace_id`、`attributes.gen_ai.conversation.id` |
| group_id | string | 是 | 分组值，精确匹配 |

### 请求参数示例

按会话查看其中所有 Trace 的事件线：

```json
{
    "bk_biz_id": 11,
    "app_name": "demo_app",
    "group_field": "attributes.gen_ai.conversation.id",
    "group_id": "conversation-demo-01"
}
```

按 Trace 查看单条事件线：

```json
{
    "bk_biz_id": 11,
    "app_name": "demo_app",
    "group_field": "trace_id",
    "group_id": "9519ce8934ad4c2f04753eef6ce44b08"
}
```

### 响应参数

| 字段名 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | 层级 Span 查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
|---|---|---|
| group_field | string | 本次查询的分组字段 |
| group_id | string | 本次查询的分组值 |
| traces | list | 分组内的 Trace 列表；没有匹配结果时为空列表 |

#### traces 元素

| 字段名 | 类型 | 描述 |
|---|---|---|
| trace_id | string | Trace ID |
| flow | list | 该 Trace 的根 Span 列表 |

`flow` 及其递归 `childs` 节点包含 `list_llm_spans` 的完整 Span 字段，包括 `trace_id`、`span_id`、`parent_span_id`、`span_name`、`start_time`、`end_time`、`elapsed_time`、`status`、`resource` 和 `attributes`。

### 前端展示归类规则

`flow` 节点与 `list_llm_spans` 的 `spans` 元素使用相同规则。节点类型和内容由 Span 字段决定，
与树中位置无关。

#### Span 类型

| 页面节点类型 | `attributes.gen_ai.operation.name` 取值 |
|---|---|
| Agent | `invoke_agent`、`invoke_workflow` |
| 模型 | `chat`、`text_completion` |
| Tool | `execute_tool` |

其他操作值按通用 GenAI Span 展示，不归入上述三类。

#### 输入区块

| 页面区块 | 字段 | 取值或条件 |
|---|---|---|
| 模型消息 | `gen_ai.input.messages[]` | 消息 `role = assistant`，展示其中 `type = text` 的 Part |
| 用户消息 | `gen_ai.input.messages[]` | 消息 `role = user`，展示其中 `type = text` 的 Part |
| 系统 Prompt | `gen_ai.system_instructions[]` | `type = text`，展示 `content` |
| 推理过程 | `gen_ai.input.messages[].parts[]` | `type = reasoning`，展示 `content` |
| 工具调用记录 | `gen_ai.input.messages[].parts[]` | `type = tool_call` 或 `tool_call_response` |
| 可用工具 | `gen_ai.tool.definitions[]` | 展示 `name`、`description` 和 `parameters` |

#### 输出区块

| 页面区块 | 字段 | 取值或条件 |
|---|---|---|
| 推理过程 | `gen_ai.output.messages[].parts[]` | `type = reasoning`，展示 `content` |
| 规划的工具调用 | `gen_ai.output.messages[].parts[]` | `type = tool_call`，展示 `id`、`name` 和 `arguments` |
| 模型输出 | `gen_ai.output.messages[]` | 消息 `role = assistant`，展示其中 `type = text` 的 Part |

`reasoning`、`tool_call`、`tool_call_response` 按 Part 类型归类；`text` Part 再按消息 `role`
归入用户消息或模型消息。

#### 工具调用关联

以下字段使用同一个调用 ID：模型输出中的 `tool_call.id`、Tool Span 中的
`gen_ai.tool.call.id`、后续模型输入中的 `tool_call_response.id`。`tool_call.name`、
`gen_ai.tool.name` 对应同一个 `gen_ai.tool.definitions[].name`。发起工具调用的 Chat 使用
`gen_ai.response.finish_reasons = ["tool_call"]`，输出最终回答的 Chat 使用 `["stop"]`。

### 响应参数示例

以下示例与 `list_llm_spans` 使用同一组脱敏 Span，仅增加 `childs` 层级。

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "group_field": "attributes.gen_ai.conversation.id",
        "group_id": "conversation-demo-01",
        "traces": [
            {
                "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                "flow": [
                    {
                        "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                        "span_id": "30e66c2d28e1bfd8",
                        "parent_span_id": "a75a608f6c6bf9ee",
                        "span_name": "invoke_agent 标准排障",
                        "start_time": 1787912684072035,
                        "end_time": 1787912699650734,
                        "elapsed_time": 15578699,
                        "status": {
                            "code": 1,
                            "message": ""
                        },
                        "resource": {
                            "service.name": "agent-demo-service",
                            "telemetry.sdk.language": "python",
                            "telemetry.sdk.name": "opentelemetry"
                        },
                        "attributes": {
                            "gen_ai.operation.name": "invoke_agent",
                            "gen_ai.conversation.id": "conversation-demo-01",
                            "gen_ai.agent.id": "agent-demo",
                            "gen_ai.agent.name": "标准排障",
                            "gen_ai.provider.name": "bkaidev",
                            "gen_ai.request.model": "k3",
                            "gen_ai.usage.input_tokens": 340,
                            "gen_ai.usage.output_tokens": 96,
                            "gen_ai.usage.cache_read.input_tokens": 164,
                            "gen_ai.usage.reasoning.output_tokens": 27,
                            "gen_ai.input.messages": [
                                {
                                    "role": "user",
                                    "parts": [
                                        {
                                            "type": "text",
                                            "content": "查询当前故障"
                                        }
                                    ]
                                }
                            ],
                            "gen_ai.output.messages": [
                                {
                                    "role": "assistant",
                                    "parts": [
                                        {
                                            "type": "text",
                                            "content": "检测到 CPU 使用率持续升高，请优先检查高负载进程。"
                                        }
                                    ]
                                }
                            ]
                        },
                        "childs": [
                            {
                                "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                                "span_id": "89c0d0e71b37fa50",
                                "parent_span_id": "30e66c2d28e1bfd8",
                                "span_name": "chat k3",
                                "start_time": 1787912684078297,
                                "end_time": 1787912689487839,
                                "elapsed_time": 5409542,
                                "status": {
                                    "code": 1,
                                    "message": ""
                                },
                                "resource": {
                                    "service.name": "agent-demo-service",
                                    "telemetry.sdk.language": "python",
                                    "telemetry.sdk.name": "opentelemetry"
                                },
                                "attributes": {
                                    "gen_ai.operation.name": "chat",
                                    "gen_ai.conversation.id": "conversation-demo-01",
                                    "gen_ai.provider.name": "bkaidev",
                                    "gen_ai.request.model": "k3",
                                    "gen_ai.request.reasoning.level": "medium",
                                    "gen_ai.request.temperature": 1,
                                    "gen_ai.response.model": "k3",
                                    "gen_ai.response.finish_reasons": [
                                        "tool_call"
                                    ],
                                    "gen_ai.response.time_to_first_chunk": 3.836437940597534,
                                    "gen_ai.usage.input_tokens": 120,
                                    "gen_ai.usage.output_tokens": 32,
                                    "gen_ai.usage.cache_read.input_tokens": 64,
                                    "gen_ai.usage.reasoning.output_tokens": 12,
                                    "gen_ai.system_instructions": [
                                        {
                                            "type": "text",
                                            "content": "你是故障排查助手。先查询事实，再给出结论和建议。"
                                        }
                                    ],
                                    "gen_ai.input.messages": [
                                        {
                                            "role": "user",
                                            "parts": [
                                                {
                                                    "type": "text",
                                                    "content": "查询当前故障"
                                                }
                                            ]
                                        }
                                    ],
                                    "gen_ai.tool.definitions": [
                                        {
                                            "type": "function",
                                            "name": "list_incident_events",
                                            "description": "查询指定故障关联的事件列表",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "incident_id": {
                                                        "type": "string",
                                                        "description": "故障 ID"
                                                    }
                                                },
                                                "required": [
                                                    "incident_id"
                                                ],
                                                "additionalProperties": false
                                            }
                                        }
                                    ],
                                    "gen_ai.output.messages": [
                                        {
                                            "role": "assistant",
                                            "parts": [
                                                {
                                                    "type": "reasoning",
                                                    "content": "需要先查询故障关联的事件列表。"
                                                },
                                                {
                                                    "type": "text",
                                                    "content": "我先查询该故障的事件记录。"
                                                },
                                                {
                                                    "type": "tool_call",
                                                    "id": "tool-call-demo-01",
                                                    "name": "list_incident_events",
                                                    "arguments": {
                                                        "incident_id": "incident-demo"
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                },
                                "childs": [
                                    {
                                        "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                                        "span_id": "55e489f22aa46592",
                                        "parent_span_id": "89c0d0e71b37fa50",
                                        "span_name": "execute_tool list_incident_events",
                                        "start_time": 1787912689507924,
                                        "end_time": 1787912689798924,
                                        "elapsed_time": 291000,
                                        "status": {
                                            "code": 1,
                                            "message": ""
                                        },
                                        "resource": {
                                            "service.name": "agent-demo-service",
                                            "telemetry.sdk.language": "python",
                                            "telemetry.sdk.name": "opentelemetry"
                                        },
                                        "attributes": {
                                            "gen_ai.operation.name": "execute_tool",
                                            "gen_ai.conversation.id": "conversation-demo-01",
                                            "gen_ai.agent.name": "标准排障",
                                            "gen_ai.tool.name": "list_incident_events",
                                            "gen_ai.tool.type": "function",
                                            "gen_ai.tool.call.id": "tool-call-demo-01",
                                            "gen_ai.tool.call.arguments": {
                                                "incident_id": "incident-demo"
                                            },
                                            "gen_ai.tool.call.result": {
                                                "events": [
                                                    {
                                                        "level": "critical",
                                                        "name": "CPU 使用率持续升高",
                                                        "started_at": "2026-08-28T10:15:00+08:00"
                                                    }
                                                ]
                                            }
                                        },
                                        "childs": []
                                    }
                                ]
                            },
                            {
                                "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                                "span_id": "6218ec01f35516ef",
                                "parent_span_id": "30e66c2d28e1bfd8",
                                "span_name": "chat k3",
                                "start_time": 1787912689802118,
                                "end_time": 1787912699639749,
                                "elapsed_time": 9837631,
                                "status": {
                                    "code": 1,
                                    "message": ""
                                },
                                "resource": {
                                    "service.name": "agent-demo-service",
                                    "telemetry.sdk.language": "python",
                                    "telemetry.sdk.name": "opentelemetry"
                                },
                                "attributes": {
                                    "gen_ai.operation.name": "chat",
                                    "gen_ai.conversation.id": "conversation-demo-01",
                                    "gen_ai.provider.name": "bkaidev",
                                    "gen_ai.request.model": "k3",
                                    "gen_ai.request.reasoning.level": "medium",
                                    "gen_ai.request.temperature": 1,
                                    "gen_ai.response.model": "k3",
                                    "gen_ai.response.finish_reasons": [
                                        "stop"
                                    ],
                                    "gen_ai.response.time_to_first_chunk": 2.104,
                                    "gen_ai.usage.input_tokens": 220,
                                    "gen_ai.usage.output_tokens": 64,
                                    "gen_ai.usage.cache_read.input_tokens": 100,
                                    "gen_ai.usage.reasoning.output_tokens": 15,
                                    "gen_ai.system_instructions": [
                                        {
                                            "type": "text",
                                            "content": "你是故障排查助手。先查询事实，再给出结论和建议。"
                                        }
                                    ],
                                    "gen_ai.input.messages": [
                                        {
                                            "role": "user",
                                            "parts": [
                                                {
                                                    "type": "text",
                                                    "content": "查询当前故障"
                                                }
                                            ]
                                        },
                                        {
                                            "role": "assistant",
                                            "parts": [
                                                {
                                                    "type": "reasoning",
                                                    "content": "需要先查询故障关联的事件列表。"
                                                },
                                                {
                                                    "type": "text",
                                                    "content": "我先查询该故障的事件记录。"
                                                },
                                                {
                                                    "type": "tool_call",
                                                    "id": "tool-call-demo-01",
                                                    "name": "list_incident_events",
                                                    "arguments": {
                                                        "incident_id": "incident-demo"
                                                    }
                                                }
                                            ]
                                        },
                                        {
                                            "role": "tool",
                                            "parts": [
                                                {
                                                    "type": "tool_call_response",
                                                    "id": "tool-call-demo-01",
                                                    "response": {
                                                        "events": [
                                                            {
                                                                "level": "critical",
                                                                "name": "CPU 使用率持续升高",
                                                                "started_at": "2026-08-28T10:15:00+08:00"
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        }
                                    ],
                                    "gen_ai.tool.definitions": [
                                        {
                                            "type": "function",
                                            "name": "list_incident_events",
                                            "description": "查询指定故障关联的事件列表",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "incident_id": {
                                                        "type": "string",
                                                        "description": "故障 ID"
                                                    }
                                                },
                                                "required": [
                                                    "incident_id"
                                                ],
                                                "additionalProperties": false
                                            }
                                        }
                                    ],
                                    "gen_ai.output.messages": [
                                        {
                                            "role": "assistant",
                                            "parts": [
                                                {
                                                    "type": "reasoning",
                                                    "content": "事件表明 CPU 使用率持续升高，需要检查高负载进程。"
                                                },
                                                {
                                                    "type": "text",
                                                    "content": "检测到 CPU 使用率持续升高，请优先检查高负载进程。"
                                                }
                                            ]
                                        }
                                    ]
                                },
                                "childs": []
                            }
                        ]
                    }
                ]
            }
        ]
    }
}
```
