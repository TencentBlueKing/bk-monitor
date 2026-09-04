### 功能描述

根据 Trace ID 或 Span ID 查询 Span，并将 AgentLens、Galileo、BKAIDev 等来源转换为统一的 OTel GenAI Span 结构。该接口用于 Trace 详情展示；只返回转换后与 Agent/LLM 观测有关的字段。

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
    "bk_biz_id": 100147,
    "app_name": "bkfara",
    "trace_id": "9519ce8934ad4c2f04753eef6ce44b08"
}
```

按 Span ID 精确查询：

```json
{
    "bk_biz_id": 100147,
    "app_name": "bkfara",
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
| parent_span_id | string | 父 Span ID；根 Span 为空字符串 |
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
| gen_ai.response.model | string | 响应模型 |
| gen_ai.input.messages | list | 标准化输入消息 |
| gen_ai.output.messages | list | 标准化输出消息 |
| gen_ai.usage.input_tokens | int | 输入 Token 数 |
| gen_ai.usage.output_tokens | int | 输出 Token 数 |
| gen_ai.usage.cache_read.input_tokens | int | 缓存读取 Token 数 |
| gen_ai.usage.cache_creation.input_tokens | int | 缓存写入 Token 数 |
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

### 响应参数示例

以下响应对应未传 `span_id` 的完整 Trace 查询示例。示例基于 Agent Trace 的实际返回结构整理，会话标识、资源信息、工具参数和对话正文已替换为示例值；Span 关系、时间和字段集合保持真实结构。

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
                    "gen_ai.usage.cache_read.input_tokens": 19456,
                    "gen_ai.usage.reasoning.output_tokens": 51,
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
                                    "content": "已完成故障分析"
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
                    "gen_ai.usage.cache_read.input_tokens": 9728,
                    "gen_ai.usage.reasoning.output_tokens": 28,
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
                        "events": []
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
                "elapsed_time": 9837630,
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
                    "gen_ai.usage.cache_read.input_tokens": 9728,
                    "gen_ai.usage.reasoning.output_tokens": 23,
                    "gen_ai.input.messages": [
                        {
                            "role": "tool",
                            "parts": [
                                {
                                    "type": "tool_call_response",
                                    "id": "tool-call-demo-01",
                                    "response": {
                                        "events": []
                                    }
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
                                    "content": "已完成故障分析"
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
