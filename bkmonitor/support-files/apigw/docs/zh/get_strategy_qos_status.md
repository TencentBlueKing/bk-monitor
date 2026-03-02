### 功能描述

获取告警策略流控状态（QoS检查）

### 请求参数

| 字段        | 类型  | 必选 | 描述   |
|-----------|-----|----|------|
| bk_biz_id | int | 是  | 业务ID |

### 请求参数示例

```json
{
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型          | 描述        |
|---------|-------------|-----------|
| result  | bool        | 请求是否成功    |
| code    | int         | 返回的状态码    |
| message | string      | 描述信息      |
| data    | list[tuple] | 返回数据，元组列表 |

#### data 元素字段说明

data 是一个元组列表（list[tuple]），每个元组包含3个元素：

| 索引位置 | 类型  | 描述                  |
|------|-----|---------------------|
| 0    | int | 策略ID（strategy_id）   |
| 1    | str | 策略名称（strategy_name） |
| 2    | str | 结果表ID（table_id）     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        [
            123,
            "CPU使用率告警策略",
            "2_bkmonitor_time_series_123456.__default__"
        ],
        [
            456,
            "内存使用率告警策略",
            "2_bkmonitor_time_series_789012.__default__"
        ],
        [
            789,
            "磁盘IO告警策略",
            "2_bkmonitor_time_series_345678.__default__"
        ]
    ]
}
```
