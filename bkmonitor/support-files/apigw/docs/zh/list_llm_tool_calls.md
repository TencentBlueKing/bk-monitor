### 功能描述

按 Trace ID 查询标准工具调用的执行摘要，为消息中的工具调用补充执行时间、状态和事件。接口仅匹配 `gen_ai.operation.name = execute_tool`，不执行产品字段转换或工具名、入参兜底关联。

接口不提供分页参数，单次最多返回 `10000` 条工具 Span，按 `start_time`、`span_id` 正序排列。查询只读取摘要字段和 `events`，不读取调用参数、工具返回结果或模型消息。

### 调用方式

使用监控站点接口 `POST /api/v4/apm_llm_web/list_tool_calls/`，需要有效登录态及应用查看权限。接口不注册到 API 网关。

将示例域名替换为实际监控站点；`cookies.txt` 为该站点已有有效登录态的 Cookie 文件：

```bash
curl --request POST \
  'https://monitor.example.com/api/v4/apm_llm_web/list_tool_calls/' \
  --cookie cookies.txt \
  --header 'Content-Type: application/json' \
  --data '{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "trace_id": "75af275f001a16ef24300359b8c66f3f"
  }'
```

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称，需要应用查看权限 |
| trace_id | string | 是 | Trace ID，非空，精确匹配 |

### 响应参数

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | 工具调用查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| trace_id | string | 请求的 Trace ID |
| total | int | 本次返回的工具 Span 数量，不是存储中的总命中数 |
| tool_calls | list | 工具执行摘要；无匹配记录时为空列表 |

#### tool_calls 元素

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| span_id | string | 工具 Span ID |
| tool_call_id | string/null | 标准 `gen_ai.tool.call.id`，缺失时为 `null`，不能用于精确关联 |
| tool_name | string/null | 标准 `gen_ai.tool.name`，缺失时为 `null` |
| start_time | int/null | 开始时间，Unix 时间戳，单位为微秒；缺失时为 `null` |
| elapsed_time | int/null | 耗时，单位为微秒；保留显式 `0`，缺失时为 `null` |
| status | object | 原始 OTel Span 状态，包含 `code`、`message`；缺失时为空对象 |
| events | list | 原始 Span 事件，用于补充异常等信息；缺失时为空列表 |

`tool_call_id` 可与消息中工具请求、工具响应 Part 的 `id` 精确匹配。相同调用 ID 的不同 Span 分别保留，调用方需判断关联歧义；接口不推断重试关系。未上报标准操作名的 Langfuse 等产品记录不在查询范围内。

查询异常按接口错误返回，不转换为空列表。`status.code = 0` 表示 `UNSET`，接口不将其改写为成功或失败，也不根据 `events` 改写原始状态。

### 响应示例

以下字段取自已归档的标准 Span 样例，经本接口字段映射整理，并非在线接口实测响应。该 Trace 包含 `8` 条工具记录，示例仅展示第一条；`events` 在该条原始记录中为空列表。

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "trace_id": "75af275f001a16ef24300359b8c66f3f",
    "total": 8,
    "tool_calls": [
      {
        "span_id": "d5d39ab5e709b82f",
        "tool_call_id": "call_EPm1DZ9oJz3kaouuvbxRg4EQ",
        "tool_name": "exec",
        "start_time": 1788143634561000,
        "elapsed_time": 163000,
        "status": {
          "code": 1,
          "message": ""
        },
        "events": []
      }
    ]
  }
}
```

未匹配到标准工具 Span 时，响应结构如下：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "trace_id": "75af275f001a16ef24300359b8c66f3f",
    "total": 0,
    "tool_calls": []
  }
}
```
