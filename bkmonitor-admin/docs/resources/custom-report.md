# Custom Report 资源设计

## 资源范围

`Custom Report` 覆盖 metadata 自定义上报相关资源：

- 自定义指标：`TimeSeriesGroup`，指标明细为 `TimeSeriesMetric`。
- 自定义事件：`EventGroup`，事件字段需要通过轻量摘要展示。
- 日志：面向自定义上报链路中的 log 类型 ResultTable 与 DataSource。

同时需要展示和业务侧页面的关系：

- `monitor_web` 自定义指标页面创建的自定义指标。
- `monitor_web` 自定义事件页面创建的自定义事件。
- APM 创建或关联使用的自定义指标、自定义事件、日志。

## 列表字段

- `report_type`：原始类型，建议值 `custom_metric`、`custom_event`、`custom_log`。
- `group_id`：资源主键，指标为 `time_series_group_id`，事件为 `event_group_id`，日志为后端归一后的 group id。
- `group_name`
- `bk_biz_id`
- `bk_tenant_id`
- `bk_data_id`
- `table_id`
- `data_label`
- `created_from`
- `is_enable`
- `metric_count` / `field_count`
- `monitor_web_source`
- `apm_application_count`
- `last_modify_time`

## 详情结构

```json
{
  "report": {},
  "datasource": {},
  "result_table": {},
  "monitor_web_relation": {},
  "apm_relations": [],
  "event_fields": [],
  "warnings": []
}
```

## 大列表策略

`TimeSeriesMetric` 数量可能非常大，详情接口只返回统计，不返回明细。明细通过 `admin.custom_report.metric_list` 分页查询。

默认分页：

- `page`: 1
- `page_size`: 20
- 最大 `page_size`: 100

## 后端 RPC

### admin.custom_report.list

入参：

```json
{
  "bk_tenant_id": "system",
  "report_type": "custom_metric",
  "bk_biz_id": 2,
  "bk_data_id": 50010,
  "table_id": "2_bkmonitor_time_series.__default__",
  "group_name": "custom_metric_demo",
  "created_from": "monitor_web",
  "apm_application_id": 1,
  "page": 1,
  "page_size": 20
}
```

出参：分页返回列表字段。

### admin.custom_report.detail

入参：

```json
{
  "bk_tenant_id": "system",
  "report_type": "custom_metric",
  "group_id": 1001,
  "include": ["datasource", "result_table", "monitor_web", "apm"]
}
```

出参：返回详情结构。

### admin.custom_report.metric_list

入参：

```json
{
  "bk_tenant_id": "system",
  "group_id": 1001,
  "field_name": "http_request_total",
  "is_active": true,
  "page": 1,
  "page_size": 20
}
```

出参：

```json
{
  "items": [
    {
      "field_name": "http_request_total",
      "table_id": "2_bkmonitor_time_series.__default__",
      "description": "request counter",
      "unit": "none",
      "type": "float",
      "is_active": true,
      "last_modify_time": "2026-04-26 12:00:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```
