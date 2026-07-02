## 功能描述

查询日志转指标数据（时序类型）。基于 UnifyQuery 协议，将日志按时间窗口聚合为时序数据点返回。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段              | 类型         | 必选 | 描述                                          |
| ----------------- | ------------ | ---- | --------------------------------------------- |
| bk_biz_id         | int          | 是   | 业务 ID                                       |
| query_list        | []query_list | 是   | 查询条件列表，可包含多个查询对象              |
| metric_merge      | string       | 是   | 指标合并标识，对应 query_list 中 reference_name |
| order_by          | array        | 否   | 排序字段，`-` 表示降序，如 `["-time"]`        |
| step              | string       | 否   | 时间步长，用于数据聚合的间隔，如 `5m`         |
| start_time        | string       | 是   | 开始时间戳（秒）                              |
| end_time          | string       | 是   | 结束时间戳（秒）                              |
| timezone          | string       | 否   | 时区，如 `Asia/Shanghai`                      |

#### query_list

| 字段             | 类型             | 必选 | 描述                                                     |
| ---------------- | ---------------- | ---- | -------------------------------------------------------- |
| data_source      | string           | 是   | 数据源名称，日志平台传 `bklog`                           |
| table_id         | string           | 是   | 查询的数据表，格式固定为 `bklog_index_set_{索引集ID}`    |
| time_aggregation | time_aggregation | 否   | 时间聚合配置                                             |
| keep_columns     | array            | 否   | 需要保留的字段列表                                       |
| field_name       | string           | 是   | 字段名称                                                 |
| reference_name   | string           | 是   | 引用名称，用于标识当前查询                               |
| dimensions       | array            | 否   | 维度字段列表                                             |
| time_field       | string           | 否   | 时间字段名称                                             |
| conditions       | conditions       | 否   | 查询条件                                                 |
| function         | function         | 否   | 聚合函数列表                                             |
| limit            | number           | 否   | 返回结果条数限制                                         |

#### time_aggregation

| 字段     | 类型   | 必选 | 描述           |
| -------- | ------ | ---- | -------------- |
| function | string | 是   | 时间聚合函数   |
| window   | string | 是   | 时间窗口       |

#### conditions

| 字段           | 类型  | 必选 | 描述         |
| -------------- | ----- | ---- | ------------ |
| field_list     | array | 否   | 条件字段列表 |
| condition_list | array | 否   | 条件列表     |

#### function

| 字段       | 类型   | 必选 | 描述                          |
| ---------- | ------ | ---- | ----------------------------- |
| method     | string | 是   | 聚合方法，如 max、min、avg 等 |
| dimensions | array  | 是   | 聚合维度字段列表              |

### 补充说明

1. 时间窗口和步长支持的单位：s（秒）、m（分钟）、h（小时）。
2. 时间聚合函数包括：`max_over_time`（时间窗口内最大值）、`min_over_time`（时间窗口内最小值）、`avg_over_time`（时间窗口内平均值）、`sum_over_time`（时间窗口内总和）。

## 参数示例

### Case 1：按时间窗口聚合并按维度分组

每 5 分钟统计各 `ip` 的 `gseIndex` 最大值。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "time_aggregation": {
        "function": "max_over_time",
        "window": "5m"
      },
      "field_name": "gseIndex",
      "reference_name": "a",
      "dimensions": ["ip"],
      "time_field": "time",
      "function": [
        {"method": "max", "dimensions": ["ip"]}
      ]
    }
  ],
  "metric_merge": "a",
  "order_by": ["-time"],
  "step": "5m",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 2：按时间窗口求平均值

每 1 分钟统计字段 `duration` 的平均值。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "time_aggregation": {
        "function": "avg_over_time",
        "window": "1m"
      },
      "field_name": "duration",
      "reference_name": "a",
      "dimensions": [],
      "time_field": "time",
      "function": [
        {"method": "avg", "dimensions": []}
      ]
    }
  ],
  "metric_merge": "a",
  "step": "1m",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 3：使用 query_string 过滤后聚合

先用 `query_string` 过滤 `ERROR` 日志，再每 1 分钟对 `gseIndex` 求和。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "query_string": "level: ERROR",
      "time_aggregation": {
        "function": "sum_over_time",
        "window": "1m"
      },
      "field_name": "gseIndex",
      "reference_name": "a",
      "dimensions": [],
      "time_field": "time",
      "function": [
        {"method": "sum", "dimensions": []}
      ]
    }
  ],
  "metric_merge": "a",
  "step": "1m",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 4：使用结构化过滤条件

统计 `level` 为 `WARN` 或 `ERROR` 的日志中 `gseIndex` 的最大值。

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
      "time_aggregation": {
        "function": "max_over_time",
        "window": "5m"
      },
      "field_name": "gseIndex",
      "reference_name": "a",
      "dimensions": ["level"],
      "time_field": "time",
      "function": [
        {"method": "max", "dimensions": ["level"]}
      ]
    }
  ],
  "metric_merge": "a",
  "step": "5m",
  "start_time": "1754893191",
  "end_time": "1755157695"
}
```

### Case 5：多查询与表达式合并

同时查询两个索引集并用 `metric_merge` 做表达式合并（此处为两条曲线求和）。

```json
{
  "bk_biz_id": 2,
  "query_list": [
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_1234",
      "time_aggregation": {"function": "sum_over_time", "window": "1m"},
      "field_name": "gseIndex",
      "reference_name": "a",
      "time_field": "time",
      "function": [{"method": "sum", "dimensions": []}]
    },
    {
      "data_source": "bklog",
      "table_id": "bklog_index_set_5678",
      "time_aggregation": {"function": "sum_over_time", "window": "1m"},
      "field_name": "gseIndex",
      "reference_name": "b",
      "time_field": "time",
      "function": [{"method": "sum", "dimensions": []}]
    }
  ],
  "metric_merge": "a + b",
  "step": "1m",
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
          "name": "result0",
          "metric_name": "",
          "columns": ["time", "value"],
          "types": ["float", "float"],
          "group_keys": ["gseIndex"],
          "group_values": ["35429"],
          "values": [1754874900000, 35429, 1]
        }
      ]
    },
    "trace_id": "d797ffa07addf81a4401428d910c58",
    "code": 0,
    "message": ""
  }
}
```
