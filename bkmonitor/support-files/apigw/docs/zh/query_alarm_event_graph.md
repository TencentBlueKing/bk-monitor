### 功能描述

查询告警事件图表

### 请求参数

| 字段名           | 类型         | 是否必选 | 描述                                                                             |
|---------------|------------|------|--------------------------------------------------------------------------------|
| bk_biz_id     | int        | 是    | 业务ID                                                                           |
| where         | list[dict] | 否    | 查询条件列表                                                                         |
| group_by      | list[str]  | 否    | 分组维度字段列表（如 `["strategy_id", "status"]`），默认为空列表                                 |
| start_time    | int        | 是    | 查询开始时间（Unix 时间戳，单位：秒）                                                          |
| end_time      | int        | 是    | 查询结束时间（Unix 时间戳，单位：秒）                                                          |
| interval      | str        | 否    | 时间间隔，可为 `"auto"` 或整数。若为整数，需配合 `interval_unit` 使用，默认为 `"auto"`                  |
| interval_unit | str        | 否    | 时间间隔单位，仅在 `interval` 为整数时生效。可选值：`"s"`（秒）、`"m"`（分）、`"h"`（小时）、`"d"`（天），默认为 `"s"` |

#### where

| 字段名    | 类型  | 是否必选 | 描述                                          |
|--------|-----|------|---------------------------------------------|
| key    | str | 否    | 字段名称                                        |
| method | str | 否    | 查询条件: "include/exclude/terms/gte/gt/lte/lt" |
| value  | any | 否    | 匹配值(字符串、列表或范围对象)                            |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "where": [
    {"key": "alert_name", "method": "eq", "value": "CPU使用率过高"},
    {"key": "severity", "method": "gte", "value": 2}
  ],
  "group_by": ["status", "strategy_id"],
  "start_time": 1728921600,
  "end_time": 1728925200,
  "interval": "auto"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段     | 类型         | 描述       |
|--------|------------|----------|
| series | list[dict] | 图表数据序列列表 |

#### data.series

| 字段         | 类型              | 描述                                                            |
|------------|-----------------|---------------------------------------------------------------|
| datapoints | list[list[int]] | 时间序列数据点，每个子列表为[count: int, timestamp: int]，分别表示告警数量和 Unix 时间戳 |
| dimensions | dict[str, Any]  | 当前序列的维度键值对（如{"status": "ABNORMAL", "strategy_id": "1001"}）    |
| target     | str             | 维度的字符串标识，格式为 `key1:value1`                                    |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "series": [
    {
      "datapoints": [
        [5, 1728921600],
        [3, 1728921900],
        [7, 1728922200]
      ],
      "dimensions": {
        "status": "ABNORMAL",
        "strategy_id": "1001"
      },
      "target": "status:ABNORMAL|strategy_id:1001"
    },
    {
      "datapoints": [
        [2, 1728921600],
        [4, 1728921900],
        [1, 1728922200]
      ],
      "dimensions": {
        "status": "CLOSED",
        "strategy_id": "1001"
      },
      "target": "status:CLOSED|strategy_id:1001"
    }
  ]
  }
}
```
