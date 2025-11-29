### 功能描述

获取告警事件维度值

### 请求参数

| 字段名        | 类型  | 是否必选 | 描述                                                        |
|------------|-----|------|-----------------------------------------------------------|
| bk_biz_id  | int | 是    | 业务ID                                                      |
| field      | str | 是    | 要查询的维度字段名（如 `"status"`、`"tags.device_name"`、`"event.ip"`） |
| start_time | int | 是    | 查询开始时间                                                    |
| end_time   | int | 是    | 查询结束时间                                                    |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "field": "status",
  "start_time": 1728316800,
  "end_time": 1728921600
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | list | 数据     |

#### data

| 字段    | 类型  | 描述                    |
|-------|-----|-----------------------|
| id    | str | 维度值的原始标识              |
| name  | str | 维度值的显示名称              |
| count | int | 该维度值在指定时间范围内出现的告警事件数量 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
    "id": "ABNORMAL",
    "name": "ABNORMAL",
    "count": 125
    },
    {
    "id": "CLOSED",
    "name": "CLOSED",
    "count": 89
    },
    {
    "id": "RECOVERED",
    "name": "RECOVERED",
    "count": 42
    }
  ]
}
```
