### 功能描述

按 Trace ID 查询工具调用的开始时间、耗时、执行状态和事件。支持 `gen_ai.operation.name = execute_tool` 的标准工具 Span。

单次最多返回 `10000` 条记录，按 `start_time`、`span_id` 正序排列，不提供分页参数。

### 调用方式

`POST /api/v4/apm_llm_web/list_tool_calls/`

调用需要监控站点的有效登录态及应用查看权限。将示例域名替换为实际站点，`cookies.txt` 使用该站点的有效登录 Cookie 文件。

```bash
curl --request POST \
  'https://monitor.example.com/api/v4/apm_llm_web/list_tool_calls/' \
  --cookie cookies.txt \
  --header 'Content-Type: application/json' \
  --data '{
    "bk_biz_id": 11,
    "app_name": "demo_app",
    "trace_id": "0123456789abcdef0123456789abcdef"
  }'
```

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| trace_id | string | 是 | Trace ID，非空，精确匹配 |

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
| trace_id | string | 请求的 Trace ID |
| total | int | 本次返回的记录数，与 `tool_calls` 长度一致 |
| tool_calls | list | 工具执行记录；无匹配记录时为空列表 |

#### tool_calls 元素

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| span_id | string | 工具 Span ID |
| tool_call_id | string/null | 工具调用 ID，可与消息中工具请求或响应 Part 的 `id` 关联；缺失时为 `null` |
| tool_name | string/null | 工具名称，缺失时为 `null` |
| start_time | int/null | 开始时间，Unix 时间戳，单位为微秒；缺失时为 `null` |
| elapsed_time | int/null | 耗时，单位为微秒；`0` 表示零耗时，缺失时为 `null` |
| status | object | 工具执行状态，缺失时为空对象 |
| events | list | 工具执行期间记录的事件，缺失时为空列表 |

相同 `tool_call_id` 可能对应多个 Span。调用方应保留这些记录，避免覆盖；缺少调用 ID 的记录无法按 ID 关联。

#### status 字段

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| code | int | 状态码，取值见下表 |
| message | string | 状态说明，可为空；发生错误时可包含错误原因 |

| code | 名称 | 含义 |
| --- | --- | --- |
| 0 | UNSET | 未显式设置状态，不能据此确定执行成功或失败 |
| 1 | OK | 执行成功 |
| 2 | ERROR | 执行错误 |

#### events 元素

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| name | string | 事件名称，例如 `exception` |
| timestamp | int | 事件时间，Unix 时间戳，单位为微秒 |
| attributes | object | 事件属性，字段随事件类型和采集数据变化 |

`exception` 事件的常见属性包括 `exception.type`（异常类型）、`exception.message`（异常信息）和 `exception.stacktrace`（异常堆栈），这些属性可能缺失。事件用于补充执行详情；存在异常事件不等于 `status.code` 一定为 `2`。

### 响应示例

查询成功并返回两条工具执行记录，其中一条工具执行失败：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "trace_id": "0123456789abcdef0123456789abcdef",
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
    "total": 0,
    "tool_calls": []
  }
}
```

请求失败时，`result` 为 `false`，按 `code`、`message` 处理错误；请求失败与查询成功但无匹配记录是不同情况。
