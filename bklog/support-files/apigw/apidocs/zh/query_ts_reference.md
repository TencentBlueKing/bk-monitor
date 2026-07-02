## 功能描述

查询日志转指标数据（非时序类型）。基于 UnifyQuery 协议，对原始数据进行筛选与聚合计算，返回引用结果。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段              | 类型         | 必选 | 描述                                                     |
| ----------------- | ------------ | ---- | -------------------------------------------------------- |
| bk_biz_id         | int          | 是   | 业务 ID，用于业务隔离与权限控制                          |
| query_list        | []query_list | 是   | 查询条件列表，包含 1 个或多个查询配置对象               |
| metric_merge      | string       | 是   | 指标合并标识，需与 query_list 中某一对象的 reference_name 一致 |
| order_by          | array        | 否   | 排序字段列表，`-` 前缀表示降序；`_value` 表示聚合结果值，`_time` 表示时间字段 |
| step              | string       | 否   | 数据聚合的时间步长（单位 s/m/h/d），与时间聚合窗口配合使用 |
| start_time        | string       | 是   | 查询开始时间戳（秒级）                                   |
| end_time          | string       | 否   | 查询结束时间戳（秒级）                                   |
| timezone          | string       | 否   | 时区设置，影响时间相关计算与展示                         |

#### query_list

| 字段             | 类型             | 必选 | 描述                                                   |
| ---------------- | ---------------- | ---- | ------------------------------------------------------ |
| data_source      | string           | 是   | 数据源名称，日志平台传 `bklog`                         |
| table_id         | string           | 是   | 查询的数据表，格式固定为 `bklog_index_set_{索引集ID}`  |
| time_aggregation | time_aggregation | 否   | 时间聚合配置，空对象 `{}` 表示不启用时间聚合           |
| field_name       | string           | 是   | 核心查询字段名称                                       |
| reference_name   | string           | 是   | 查询引用名称，需唯一且与 metric_merge 对应             |
| dimensions       | array            | 否   | 维度字段列表，用于分组聚合                             |
| time_field       | string           | 否   | 时间字段名称                                           |
| conditions       | conditions       | 否   | 筛选条件配置                                           |
| function         | function         | 否   | 聚合函数列表（非时间维度的统计逻辑）                   |
| limit            | number           | 否   | 结果返回条数限制                                       |

#### time_aggregation

用于配置时间窗口内的聚合逻辑，为空对象 `{}` 表示不启用时间聚合。

| 子字段   | 类型   | 必选（启用时） | 描述                              |
| -------- | ------ | -------------- | --------------------------------- |
| function | string | 是             | 时间聚合函数，如 `max_over_time`  |
| window   | string | 是             | 时间窗口大小（单位 s/m/h/d）      |

#### conditions

| 子字段         | 类型  | 必选 | 描述               |
| -------------- | ----- | ---- | ------------------ |
| field_list     | array | 否   | 参与筛选的字段列表 |
| condition_list | array | 否   | 筛选条件           |

#### function

| 子字段     | 类型   | 必选 | 描述                          |
| ---------- | ------ | ---- | ----------------------------- |
| method     | string | 是   | 聚合方法（非时间维度），如 max、min、avg |
| dimensions | array  | 是   | 聚合维度字段列表              |

## 参数示例

### Case 1：单指标聚合（不启用时间聚合）

对整个时间范围求 `gseIndex` 最大值，`time_aggregation` 传空对象表示不启用时间聚合。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "time_aggregation": {},
      "field_name": "gseIndex",
      "reference_name": "a",
      "time_field": "time",
      "function": [
        {"method": "max", "dimensions": []}
      ]
    }
  ],
  "metric_merge": "a",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 2：按维度分组统计 TopK

按 `serverIp` 分组求和，取聚合结果值最大的前 10 个。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "time_aggregation": {},
      "field_name": "gseIndex",
      "reference_name": "a",
      "dimensions": ["serverIp"],
      "time_field": "time",
      "function": [
        {"method": "sum", "dimensions": ["serverIp"]}
      ],
      "limit": 10
    }
  ],
  "metric_merge": "a",
  "order_by": ["-_value"],
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 3：使用 query_string 过滤

先用 `query_string` 过滤 `ERROR` 日志，再对 `gseIndex` 求和。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "query_string": "level: ERROR",
      "time_aggregation": {},
      "field_name": "gseIndex",
      "reference_name": "a",
      "time_field": "time",
      "function": [
        {"method": "sum", "dimensions": []}
      ]
    }
  ],
  "metric_merge": "a",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 4：使用结构化过滤条件

统计 `level` 为 `WARN` 或 `ERROR` 的日志，按 `level` 分组求和。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "conditions": {
        "field_list": [
          {"field_name": "level", "op": "eq", "value": ["WARN", "ERROR"]}
        ],
        "condition_list": []
      },
      "time_aggregation": {},
      "field_name": "gseIndex",
      "reference_name": "a",
      "dimensions": ["level"],
      "time_field": "time",
      "function": [
        {"method": "sum", "dimensions": ["level"]}
      ]
    }
  ],
  "metric_merge": "a",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

## 返回结果示例

```json
{
  "result": {
    "data": {
      "series": [
        {
          "name": "_result0",
          "metric_name": "",
          "columns": ["_time", "_value"],
          "types": ["float", "float"],
          "group_keys": ["__ipv6__"],
          "group_values": [],
          "values": [1754029191000, 39648, 1]
        }
      ]
    },
    "trace_id": "3ffeed0d076c1bb5b1e1f9c2995992b1",
    "code": 0,
    "message": ""
  }
}
```
