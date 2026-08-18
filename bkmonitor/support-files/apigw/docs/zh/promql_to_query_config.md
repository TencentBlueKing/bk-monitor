### 功能描述

将 PromQL 语句转换为监控查询配置（query_config）。对应 SaaS 接口 `POST /rest/v2/strategies/promql_to_query_config/`。

转换结果可用于策略保存或图表查询。不支持未注册函数、多次维度聚合，以及 `ignoring` / `on` / `group_left` / `group_right` 等匹配算符（会被剔除后按默认逻辑处理）。


### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | int | 是 | 业务ID |
| promql | str | 是 | PromQL 语句 |
| query_config_format | str | 否 | 输出格式，可选 `strategy`（默认）或 `graph` |

`strategy` 返回策略查询配置字段（`result_table_id`、`metric_field`、`agg_method` 等）；`graph` 返回图表查询字段（`table`、`metric`、`method` 等）。

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "promql": "avg by (bk_target_ip, bk_target_cloud_id) (avg_over_time(bkmonitor:system:disk:in_use{bk_target_ip=\"12.0.0.1\"}[5m]))",
  "query_config_format": "strategy"
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
| expression | str | 多指标表达式。单指标单表达式时可能为空字符串 |
| query_configs | list[dict] | 查询配置列表 |

#### query_configs 元素字段说明（query_config_format=strategy）

| 字段 | 类型 | 描述 |
|------|------|------|
| data_source_label | str | 数据源，如 `bk_monitor`、`custom`、`bk_data` |
| data_type_label | str | 数据类型，时序为 `time_series` |
| alias | str | 指标别名 |
| metric_id | str | 指标 ID |
| metric_field | str | 指标字段 |
| result_table_id | str | 结果表 |
| agg_method | str | 聚合方法 |
| agg_interval | int | 聚合周期（秒） |
| agg_dimension | list[str] | 聚合维度 |
| agg_condition | list[dict] | 过滤条件 |
| functions | list[dict] | 计算函数 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "expression": "",
    "query_configs": [
      {
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "alias": "a",
        "metric_id": "bk_monitor.system.disk.in_use",
        "functions": [],
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
        "metric_field": "in_use"
      }
    ]
  }
}
```
