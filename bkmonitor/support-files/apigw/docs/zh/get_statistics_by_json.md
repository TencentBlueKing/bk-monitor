### 功能描述

获取json格式的运营数据

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型     | 描述         |
|---------|--------|------------|
| result  | bool   | 请求是否成功     |
| code    | int    | 返回的状态码     |
| message | string | 描述信息       |
| data    | list   | 运营数据指标列表   |

#### data[n]

| 字段        | 类型     | 描述                        |
|-----------|--------|---------------------------|
| name      | string | 指标名称                      |
| labels    | dict   | 指标标签，包含该指标的维度信息           |
| value     | float  | 指标值                       |
| timestamp | int    | 时间戳（可选，通常为null）           |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "name": "bkmonitor_alert_count",
      "labels": {"bk_biz_id": "2", "status": "active"},
      "value": 10.0,
      "timestamp": null
    },
    {
      "name": "bkmonitor_strategy_count",
      "labels": {"bk_biz_id": "2"},
      "value": 25.0,
      "timestamp": null
    },
    {
      "name": "bkmonitor_dashboard_count",
      "labels": {"bk_biz_id": "2"},
      "value": 50.0,
      "timestamp": null
    }
  ]
}
```
