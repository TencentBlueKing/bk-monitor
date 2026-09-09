### 功能描述

按 Trace ID 或 Span ID 查询 Span。AgentLens、Galileo、BKAIDev 等来源统一转换为 OTel GenAI Span，响应仅包含 Agent/LLM 观测字段。

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| trace_id | string | 否 | Trace ID，精确匹配；与 `span_id` 至少传一个 |
| span_id | string | 否 | Span ID，精确匹配；与 `trace_id` 至少传一个 |

### 请求参数示例

查询 Trace 下的全部标准化 Span：

```json
{
    "bk_biz_id": 11,
    "app_name": "demo_app",
    "trace_id": "9519ce8934ad4c2f04753eef6ce44b08"
}
```

按 Span ID 精确查询：

```json
{
    "bk_biz_id": 11,
    "app_name": "demo_app",
    "span_id": "30e66c2d28e1bfd8"
}
```

只传 `trace_id` 时返回该 Trace 下的全部标准化 Span；只传 `span_id` 时按 Span ID 查询；两者同时传入时两个精确条件同时生效。

### 响应参数

| 字段名 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | Span 查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
|---|---|---|
| trace_id | string | Trace ID；只传 `span_id` 时取匹配结果中的 Trace ID，未匹配时为空字符串 |
| total | int | 转换后返回的 Span 数量 |
| spans | list | 按 `start_time` 正序排列的标准化 Span |

#### spans 元素

| 字段名 | 类型 | 描述 |
|---|---|---|
| trace_id | string | Trace ID |
| span_id | string | Span ID |
| parent_span_id | string | 父 Span ID；可能为空，也可能指向未包含在标准化结果中的外部父 Span |
| span_name | string | Span 名称 |
| start_time | int | 开始时间，单位为微秒 |
| end_time | int | 结束时间，单位为微秒 |
| elapsed_time | int | 耗时，单位为微秒 |
| status | object | OTel Span 状态，包含 `code` 和 `message` |
| resource | object | OTel Resource 属性，不同 SDK 上报的键可能不同 |
| attributes | object | 标准化后的 GenAI 属性，只返回实际存在的字段 |

常见的标准化 `attributes` 字段如下：

| 字段名 | 类型 | 描述 |
|---|---|---|
| gen_ai.operation.name | string | 操作类型，例如 `invoke_agent`、`chat`、`execute_tool` |
| gen_ai.conversation.id | string | 会话 ID |
| gen_ai.agent.id | string | Agent ID |
| gen_ai.agent.name | string | Agent 名称 |
| gen_ai.provider.name | string | 模型服务提供方 |
| gen_ai.request.model | string | 请求模型 |
| gen_ai.request.reasoning.level | string | 请求的推理强度 |
| gen_ai.response.model | string | 响应模型 |
| gen_ai.response.finish_reasons | list | 模型结束原因，例如 `tool_call`、`stop` |
| gen_ai.response.time_to_first_chunk | float | 首个响应分片耗时，单位为秒 |
| gen_ai.input.messages | list | 标准化输入消息 |
| gen_ai.output.messages | list | 标准化输出消息 |
| gen_ai.system_instructions | list | 标准化系统 Prompt，各元素使用消息 Part 结构 |
| gen_ai.tool.definitions | list | 当前模型请求可用的工具定义 |
| gen_ai.usage.input_tokens | int | 输入 Token 数 |
| gen_ai.usage.output_tokens | int | 输出 Token 数 |
| gen_ai.usage.cache_read.input_tokens | int | 缓存读取 Token 数 |
| gen_ai.usage.cache_creation.input_tokens | int | 缓存写入 Token 数 |
| gen_ai.usage.reasoning.output_tokens | int | 推理过程使用的输出 Token 数 |
| gen_ai.tool.name | string | 工具名称 |
| gen_ai.tool.call.id | string | 工具调用 ID |
| gen_ai.tool.call.arguments | object | 工具调用参数 |
| gen_ai.tool.call.result | object | 工具调用结果 |
| user.id | string | 用户 ID |

消息结构：

| 字段名 | 类型 | 描述 |
|---|---|---|
| role | string | 消息角色，例如 `user`、`assistant`、`tool` |
| parts | list | 消息内容列表 |
| parts[].type | string | 内容类型，例如 `text`、`reasoning`、`tool_call`、`tool_call_response` |
| parts[].content | string | `text` 或 `reasoning` 的文本内容 |
| parts[].id | string | `tool_call` 或 `tool_call_response` 的工具调用 ID |
| parts[].name | string | `tool_call` 计划调用的工具名称 |
| parts[].arguments | object | `tool_call` 计划使用的工具参数 |
| parts[].response | object | `tool_call_response` 返回的工具结果 |

工具定义结构：

| 字段名 | 类型 | 描述 |
|---|---|---|
| type | string | 工具类型，函数工具为 `function` |
| name | string | 工具名称，与 `tool_call.name`、`gen_ai.tool.name` 一致 |
| description | string | 工具用途说明 |
| parameters | object | 工具参数的 JSON Schema |

### 前端展示归类规则

#### Span 类型

`attributes.gen_ai.operation.name` 是节点类型的判断字段，`span_name` 仅用于展示：

| 页面节点类型 | `gen_ai.operation.name` 取值 |
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

以下响应为未传 `span_id` 时的完整 Trace 查询示例。会话标识、资源信息、工具参数和对话正文已脱敏。
`list_llm_flows` 使用同一组 Span，仅增加 `childs` 层级。

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
        "total": 4,
        "spans": [
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
                }
            },
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
                }
            },
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
                }
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
                }
            }
        ]
    }
}
```

### 使用说明

1. `total` 是当前 Trace 转换后 Span 的数量，不是分页总数。
2. Adapter 会过滤与 Agent/LLM 展示无关的厂商私有属性，因此 `attributes` 是稀疏对象，不保证每个字段都存在。
3. `resource` 保留 Span 上报的 OTel Resource 信息，具体键由 SDK 决定。
