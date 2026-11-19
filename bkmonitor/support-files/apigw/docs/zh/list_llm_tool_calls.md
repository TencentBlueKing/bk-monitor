### 功能描述

按 Trace ID 或会话 ID 查询工具调用的开始时间、耗时、执行状态和事件。

按 `start_time`、`span_id` 正序排列，使用 `offset`、`limit` 分页，`limit` 默认 `10000`。

### 请求地址

`POST /api/v4/apm_llm_web/list_tool_calls/`

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| group_field | string | 否 | 分组字段，默认 `attributes.gen_ai.conversation.id`；按 Trace 查询时传 `trace_id` |
| group_id | string | 否 | 分组值，精确匹配 |
| trace_id | string | 否 | 兼容旧请求；非空时在序列化器中覆盖 `group_field=trace_id`、`group_id=trace_id` 的值 |
| offset | int | 否 | 分页偏移，默认 `0`，最小 `0` |
| limit | int | 否 | 分页大小，默认 `10000`，范围 `1～10000` |

- *[1] `group_id` 和兼容参数 `trace_id` 至少填写一个非空值。*
- *[2] 默认会话过滤匹配工具 Span 自身的 `gen_ai.conversation.id`。*

### 请求参数示例

```json
{
  "bk_biz_id": 11,
  "app_name": "demo_app",
  "trace_id": "0123456789abcdef0123456789abcdef"
}
```

按会话查询：

```json
{"bk_biz_id": 11, "app_name": "demo_app", "group_id": "session-001", "offset": 0, "limit": 100}
```

### 响应参数

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 接口请求是否成功，与工具执行状态无关 |
| code | int | 接口返回码，`0` 表示请求成功 |
| message | string | 接口请求的提示或错误信息 |
| data | object | 工具调用查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| trace_id | string | 请求的 Trace ID，未传时为空字符串 |
| group_field | string | 序列化器归一后的分组字段 |
| group_id | string | 序列化器归一后的分组值 |
| total | int | 本次返回的记录数，与 `tool_calls` 长度一致 |
| tool_calls | list | 工具执行记录；无匹配记录时为空列表 |

#### tool_calls 元素

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| span_id | string | 工具 Span ID |
| tool_call_id | string/null | 工具调用 ID，可与消息中工具请求或响应 Part 的 `id` 关联；缺失时为 `null` |
| tool_name | string/null | 工具名称，缺失时为 `null` |
| start_time | int/null | 开始时间，Unix 时间戳，单位为微秒；缺失时为 `null` |
| elapsed_time | int/null | 耗时，单位为微秒；缺失时为 `null` |
| status | object | 工具执行状态，缺失时为空对象 |
| events | list | 工具执行期间记录的事件，缺失时为空列表 |

#### status 字段

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| code | int | 状态码，取值见下表 |
| message | string | 状态说明，可为空；发生错误时可包含错误原因 |

| code | 名称 | 含义 |
| --- | --- | --- |
| 0 | UNSET | 未设置状态 |
| 1 | OK | 执行成功 |
| 2 | ERROR | 执行错误 |

#### events 元素

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| name | string | 事件名称，例如 `exception` |
| timestamp | int | 事件时间，Unix 时间戳，单位为微秒 |
| attributes | object | 事件属性，字段随事件类型和采集数据变化 |

`exception` 事件的常见属性：`exception.type`（异常类型）、`exception.message`（异常信息）、`exception.stacktrace`（异常堆栈）。

### 响应示例

查询成功并返回两条工具执行记录，其中一条工具执行失败：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "trace_id": "0123456789abcdef0123456789abcdef",
    "group_field": "trace_id",
    "group_id": "0123456789abcdef0123456789abcdef",
    "total": 2,
    "tool_calls": [
      {
        "span_id": "0000000000000001",
        "tool_call_id": "call_search_001",
        "tool_name": "search",
        "start_time": 1700000000000000,
        "elapsed_time": 12000,
        "status": {
          "code": 1,
          "message": ""
        },
        "events": []
      },
      {
        "span_id": "0000000000000002",
        "tool_call_id": "call_fetch_001",
        "tool_name": "fetch_page",
        "start_time": 1700000000020000,
        "elapsed_time": 3000000,
        "status": {
          "code": 2,
          "message": "Tool execution timed out"
        },
        "events": [
          {
            "name": "exception",
            "timestamp": 1700000003020000,
            "attributes": {
              "exception.type": "TimeoutError",
              "exception.message": "Tool execution timed out"
            }
          }
        ]
      }
    ]
  }
}
```

查询成功但无匹配记录：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "trace_id": "0123456789abcdef0123456789abcdef",
    "group_field": "trace_id",
    "group_id": "0123456789abcdef0123456789abcdef",
    "total": 0,
    "tool_calls": []
  }
}
```
