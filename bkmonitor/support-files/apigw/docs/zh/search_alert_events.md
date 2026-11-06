### 功能描述

查询指定告警关联的异常事件，兼容原 `monitor_v3.search_alert_events` 接口。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 是 | 业务 ID，用于网关资源鉴权 |
| alert_id | string | 是 | 告警 ID |
| query_string | string | 否 | 事件查询字符串，默认空字符串 |
| ordering | list[string] | 否 | 排序字段，默认空列表 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 10，最大 1000 |
| show_dsl | bool | 否 | 是否返回查询 DSL，默认 false |
| record_history | bool | 否 | 是否记录查询历史，默认 false |
| show_raw | bool | 否 | 是否返回原始事件，默认 false |

### 请求示例

```json
{
  "bk_biz_id": 2,
  "alert_id": "1792066377188629310",
  "query_string": "",
  "ordering": ["-time"],
  "page": 1,
  "page_size": 10
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回消息 |
| data | dict | 查询结果 |
| data.total | int | 事件总数 |
| data.events | list[dict] | 关联异常事件列表 |
| data.dsl | dict | 查询 DSL，仅在 `show_dsl=true` 时返回 |

### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "total": 1,
    "events": [
      {
        "event_id": "5ca07cad5c46c30777b3bd032a8127be.1792066200.204947.207619.2",
        "time": 1792066200
      }
    ]
  }
}
```
