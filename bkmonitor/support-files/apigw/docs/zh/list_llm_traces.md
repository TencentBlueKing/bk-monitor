### 功能描述

分页查询指定 APM 应用中的 Agent Trace。接口默认按 `trace_id` 返回每轮对话摘要；指定会话字段后，按该字段聚合多个 Trace，并通过 `childs` 返回会话中的每轮对话。

接口只返回 Agent/LLM 相关 Trace，不返回普通 HTTP、RPC Trace。分页采用 `offset + limit` 增量查询，不计算 `total`；当 `items` 为空时表示没有下一页。

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| start_time | int | 是 | 查询开始时间，Unix 时间戳，单位为秒 |
| end_time | int | 是 | 查询结束时间，Unix 时间戳，单位为秒，不能小于 `start_time` |
| group_field | string | 否 | 标准分组字段，默认 `trace_id`。会话视图传 `attributes.gen_ai.conversation.id` |
| service_name | string | 否 | OTel 服务名称，精确匹配原始 Span 的 `resource.service.name`；会话查询时也用于缩小产品字段范围 |
| keyword | string | 否 | 高级搜索关键词，可匹配 Trace ID、Span ID、用户 ID 或会话 ID |
| offset | int | 否 | 分页偏移量，默认 `0`，最小为 `0` |
| limit | int | 否 | 每页分组数量，默认 `20`，取值范围为 `1`～`100` |

会话视图统一传标准字段 `attributes.gen_ai.conversation.id`。后端复用服务拓扑中的 LLM 产品识别结果，将标准字段映射为对应产品的原始字段：

| 产品 | 产品原始字段 |
|---|---|
| Default、Langfuse | `attributes.gen_ai.conversation.id` |
| AgentLens | `attributes.gen_ai.session.id` |
| Galileo | `attributes.gen_ai.session_id` |
| BKAIDev | `attributes.agent.session.session_code` |

接口按映射后的原始字段聚合，以每个会话中最新 Span 的 `end_time` 排序，再合并同名会话并分页。查询窗口内不同产品字段的分组结果会统一合并，某个日索引没有候选字段 mapping 时也不会导致整次查询失败。未传 `service_name` 时会合并应用内已识别产品的原始字段；产品尚未识别时查询全部候选字段。响应中的 `group_field` 始终保留调用方传入的标准字段。

### 请求参数示例

按 Trace 查询：

```json
{
    "bk_biz_id": 100147,
    "app_name": "bkfara",
    "start_time": 1787910000,
    "end_time": 1787917200,
    "group_field": "trace_id",
    "service_name": "agent-demo-service",
    "keyword": "",
    "offset": 0,
    "limit": 20
}
```

按会话查询：

```json
{
    "bk_biz_id": 100147,
    "app_name": "bkfara",
    "start_time": 1787910000,
    "end_time": 1787917200,
    "group_field": "attributes.gen_ai.conversation.id",
    "service_name": "agent-demo-service",
    "keyword": "conversation-demo-01",
    "offset": 0,
    "limit": 20
}
```

### 响应参数

| 字段名 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | 查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
|---|---|---|
| offset | int | 当前分页偏移量 |
| limit | int | 当前分页大小 |
| items | list | Trace 或会话列表 |

#### items 元素

| 字段名 | 类型 | 描述 |
|---|---|---|
| group_id | string | 当前分组值。按 Trace 查询时等于 `trace_id`；按会话查询时为会话 ID |
| group_field | string | 当前分组字段 |
| trace_id | string | Trace ID，仅 Trace 层对象返回 |
| input | string | 逻辑根 Agent/Workflow Span 中最后一条用户文本；会话层返回空字符串 |
| output | string | 逻辑根 Agent/Workflow Span 中最后一条助手文本；会话层返回空字符串 |
| input_tokens | int | 分组内输入 Token 总数 |
| output_tokens | int | 分组内输出 Token 总数 |
| cache_read_input_tokens | int | 分组内缓存读取 Token 总数 |
| cache_creation_input_tokens | int | 分组内缓存写入 Token 总数 |
| start_time | int | 根 Span 开始时间，单位为微秒 |
| elapsed_time | int | Trace 或会话持续时间，单位为微秒 |
| user_id | string | Span 中上报的用户 ID，未上报时为空字符串 |
| childs | list | 会话包含的 Trace 列表；仅 `group_field != trace_id` 时返回，元素结构与 Trace 层对象一致 |

### 响应参数示例

以下示例基于 Agent Trace 的实际返回结构整理，会话标识和对话正文已替换为示例值。

按 Trace 查询：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "offset": 0,
        "limit": 20,
        "items": [
            {
                "group_id": "9519ce8934ad4c2f04753eef6ce44b08",
                "group_field": "trace_id",
                "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                "input": "查询当前故障",
                "output": "已完成故障分析",
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 38912,
                "cache_creation_input_tokens": 0,
                "start_time": 1787912681484550,
                "elapsed_time": 294398,
                "user_id": ""
            }
        ]
    }
}
```

按会话查询：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "offset": 0,
        "limit": 20,
        "items": [
            {
                "group_id": "conversation-demo-01",
                "group_field": "attributes.gen_ai.conversation.id",
                "input": "",
                "output": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 38912,
                "cache_creation_input_tokens": 0,
                "start_time": 1787912681484550,
                "elapsed_time": 294398,
                "user_id": "",
                "childs": [
                    {
                        "group_id": "9519ce8934ad4c2f04753eef6ce44b08",
                        "group_field": "trace_id",
                        "trace_id": "9519ce8934ad4c2f04753eef6ce44b08",
                        "input": "查询当前故障",
                        "output": "已完成故障分析",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_input_tokens": 38912,
                        "cache_creation_input_tokens": 0,
                        "start_time": 1787912681484550,
                        "elapsed_time": 294398,
                        "user_id": ""
                    }
                ]
            }
        ]
    }
}
```

### 使用说明

1. 默认 `group_field=trace_id` 时，`items` 直接返回 Trace，不包含 `childs`。
2. 指定会话字段后，外层 `items` 表示会话，`childs` 表示该会话中的多轮 Trace。
3. `keyword` 会同时匹配标准字段及各产品实际上报的会话字段。
4. Token 数量为当前 Trace 或会话内所有已标准化 Span 的求和结果。
5. 接口不返回 `total`。调用方按 `offset + limit` 拉取下一页，直到 `items` 为空。
