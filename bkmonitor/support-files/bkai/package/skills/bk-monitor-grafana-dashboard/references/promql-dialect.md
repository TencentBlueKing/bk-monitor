# 蓝鲸 PromQL / query_configs 方言

## 两种写法

| mode | 用在 | 必填 | 必须空 |
| --- | --- | --- | --- |
| `ui` | 主机/标准结果表、今日昨日上周 | `query_configs` | `source` |
| `code` | 手写 PromQL、容器、复杂计算 | `source` | `query_configs`（`[]`） |

## UI：`query_configs` 字段

最少：

```json
{
  "alias": "今日",
  "data_source_label": "bk_monitor",
  "data_type_label": "time_series",
  "display": true,
  "filter_dict": {},
  "functions": [],
  "group_by": [],
  "interval": 60,
  "interval_unit": "s",
  "method": "AVG",
  "metric_field": "usage",
  "refId": "a",
  "result_table_id": "system.cpu_summary",
  "result_table_label": "os",
  "time_field": "time",
  "where": []
}
```

- `metric_field` 只写指标名：`usage`、`pct_used`、`in_use`。不要 `cpu_summary.usage`。
- `data_source_label`：`bk_monitor` | `custom` | `bk_data`
- 时间对比：昨日 `functions: [{ "id": "time_shift", "params": [{ "id": "n", "value": "1d" }] }]`；上周 `1w`
- 按维度拆线：`group_by: ["device_name"]`，`alias: "$tag_device_name"`

颜色 override（今日红、昨日绿、上周灰）：

```json
{ "matcher": { "id": "byName", "options": "今日" }, "properties": [{ "id": "color", "value": { "fixedColor": "red", "mode": "fixed" } }] }
```

## Code：PromQL 前缀

`{前缀}:{结果表}:{指标}[窗口]`

| 数据 | 前缀 | 例子 |
| --- | --- | --- |
| 主机内置 | `bkmonitor:system` | `bkmonitor:system:cpu_summary:usage` |
| 自定义上报 | `custom` | `custom:blueking_report:metric` |
| 计算平台 | `bkdata` | `bkdata:demo_metric_table:delay_5min_cnt` |
| 容器 | `bkmonitor` **无结果表** | `bkmonitor:container_cpu_usage_seconds_total` |

常用包装：`avg(avg_over_time(<metric>[1m]))`。百分比类 AVG。

### 错例

```text
custom:system:cpu_summary:usage
bkmonitor:system:container:container_cpu_usage_seconds_total
bkmonitor:blueking_report:xxx
bkmonitor:system:cpu_summary:cpu_summary__bk_46__usage
```

## 验数

`extract-promql` 会：

- code：直接取出 `source`
- ui：拼成 `avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))` 这类探针语句

有 `$namespace` 等变量时标 `has_variables: true`。没有用户给的替换值就不要调 `execute_range_query`，并在结果里写未实查。
