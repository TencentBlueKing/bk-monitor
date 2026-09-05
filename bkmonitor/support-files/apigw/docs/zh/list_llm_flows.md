### 功能描述

按一个 `group_field`、`group_id` 精确查询 Agent 执行事件线。接口先定位分组内的 Trace，再将每个 Trace 的标准化 Span 按 `span_id`、`parent_span_id` 组织为树。

每个树节点的字段与 `list_llm_spans` 返回的 Span 一致，并增加 `childs` 保存直接子 Span。一个 Trace 可以有多个根节点；当父 Span 未出现在标准化结果中时，该 Span 作为根节点返回。

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

### 响应参数示例

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
                        "parent_span_id": "",
                        "span_name": "invoke_agent demo-agent",
                        "start_time": 1787912684072035,
                        "end_time": 1787912699650734,
                        "elapsed_time": 15578699,
                        "status": {
                            "code": 1,
                            "message": ""
                        },
                        "resource": {
                            "service.name": "agent-demo-service"
                        },
                        "attributes": {
                            "gen_ai.operation.name": "invoke_agent",
                            "gen_ai.conversation.id": "conversation-demo-01",
                            "gen_ai.agent.name": "demo-agent"
                        },
                        "childs": [
                            {
                                "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                                "span_id": "89c0d0e71b37fa50",
                                "parent_span_id": "30e66c2d28e1bfd8",
                                "span_name": "chat demo-model",
                                "start_time": 1787912684078297,
                                "end_time": 1787912689487839,
                                "elapsed_time": 5409542,
                                "status": {
                                    "code": 1,
                                    "message": ""
                                },
                                "resource": {
                                    "service.name": "agent-demo-service"
                                },
                                "attributes": {
                                    "gen_ai.operation.name": "chat",
                                    "gen_ai.response.model": "demo-model",
                                    "gen_ai.usage.input_tokens": 120,
                                    "gen_ai.usage.output_tokens": 32
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
