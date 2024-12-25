### 功能描述

将 Grafana 仪表盘中的图表查询配置转换为监控策略的查询配置格式。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | int | 是 | 业务ID |
| dashboard_uid | string | 是 | 仪表盘UID |
| panel_id | int | 是 | 图表ID |
| ref_id | string | 是 | 图表RefID |
| variables | object | 否 | 变量映射,格式为{"变量名": ["变量值"]} |

### 请求参数示例
```json
{
    "bk_biz_id": 1,
    "dashboard_uid": "dashboard-uid",
    "panel_id": 1,
    "ref_id": "A",
    "variables": {"var1": ["value1", "value2"]}
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| expression | string | 表达式 |
| functions | array[object] | 函数列表 |
| query_configs | array | 查询配置列表 |
| target | array[array[object]] | 监控目标配置（同策略的target） |

#### query_configs 字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| alias | string | 查询别名 |
| data_source_label | string | 数据源标签 |
| data_type_label | string | 数据类型标签 |
| agg_interval | int | 聚合周期(秒) |
| agg_dimension | array | 聚合维度 |
| agg_method | string | 聚合方法 |
| agg_condition | array | 过滤条件 |
| metric_field | string | 指标名 |
| result_table_id | string | 结果表ID |
| promql | string | PromQL语句(仅Prometheus数据源) |

### 响应参数示例
```json
{
    "expression": "expression",
    "functions": [{"id": "func1", "params": [{"id": "param1", "value": "value1"}]}],
    "query_configs": [
        {
            "alias": "a",
            "data_source_label": "bk_monitor",
            "data_type_label": "metric",
            "agg_interval": 60,
            "agg_dimension": ["bk_target_ip"],
            "agg_method": "avg",
            "agg_condition": [],
            "metric_field": "usage",
            "result_table_id": "system:cpu_summary",
        }
    ],
    "target": [[{"bk_target_ip": "127.0.0.1"}]]
}
```
