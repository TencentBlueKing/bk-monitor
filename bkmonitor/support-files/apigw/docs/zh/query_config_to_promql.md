### 功能描述

将监控查询配置（query_config）转换为 PromQL 语句。对应 SaaS 接口 `POST /rest/v2/strategies/query_config_to_promql/`。

仅支持时序数据源：`bk_monitor` / `custom` / `bk_data` + `time_series`。查询条件包含 `or` 时无法转换。


### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | int | 是 | 业务ID |
| expression | str | 是 | 多指标表达式，单指标通常为别名 `a` |
| query_configs | list[dict] | 是 | 查询配置列表 |
| query_config_format | str | 否 | 查询配置格式，可选 `strategy`（默认）或 `graph` |

#### query_configs 元素字段说明（query_config_format=strategy）

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| data_source_label | str | 是 | 数据源，可选 `bk_monitor`、`custom`、`bk_data` |
| data_type_label | str | 是 | 数据类型，必须为 `time_series` |
| alias | str | 是 | 指标别名，如 `a`、`b` |
| metric_field | str | 是 | 指标字段 |
| agg_method | str | 是 | 聚合方法，如 `AVG`、`SUM`、`MAX`、`MIN`、`COUNT` |
| agg_interval | int / str | 是 | 聚合周期（秒）。传 `auto` 时按 60 秒处理 |
| agg_dimension | list[str] | 否 | 聚合维度 |
| agg_condition | list[dict] | 否 | 过滤条件 |
| result_table_id | str | 否 | 结果表，如 `system.disk` |
| data_label | str | 否 | 数据标签 |
| functions | list[dict] | 否 | 计算函数，默认为空列表 |

`query_config_format=graph` 时，用图表字段名：`table`、`metric`、`method`、`group_by`、`where`、`interval`，含义分别对应 `result_table_id`、`metric_field`、`agg_method`、`agg_dimension`、`agg_condition`、`agg_interval`。

#### agg_condition 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| key | str | 是 | 维度名 |
| method | str | 是 | 操作符，如 `eq`、`neq`、`reg`、`nreg` |
| value | list | 是 | 匹配值列表 |
| condition | str | 否 | 与前一条件的连接方式，仅支持 `and` |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "expression": "a",
  "query_config_format": "strategy",
  "query_configs": [
    {
      "data_source_label": "bk_monitor",
      "data_type_label": "time_series",
      "alias": "a",
      "metric_field": "in_use",
      "result_table_id": "system.disk",
      "agg_method": "AVG",
      "agg_interval": 300,
      "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
      "agg_condition": [
        {
          "key": "bk_target_ip",
          "method": "eq",
          "value": ["12.0.0.1"]
        }
      ],
      "functions": []
    }
  ]
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 返回的状态码 |
| message | str | 描述信息 |
| data | dict | 转换结果 |

#### data 字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| promql | str | 转换得到的 PromQL 语句 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "promql": "avg by (bk_target_ip, bk_target_cloud_id) (avg_over_time(bkmonitor:system:disk:in_use{bk_target_ip=\"12.0.0.1\"}[5m]))"
  }
}
```
