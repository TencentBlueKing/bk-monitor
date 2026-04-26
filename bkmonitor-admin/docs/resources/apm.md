# APM 资源设计

## 资源范围

APM 管理视图以应用为中心，展示应用和监控数据链路的关系：

- `ApmApplication`
- Trace / Metric / Log / Profiling DataSource
- 关联 ResultTable
- Service / Topo Node / Topo Relation
- 自定义指标、自定义事件、日志关联

本期只做只读展示，不执行启停、删除、链路操作。

## 列表字段

- `application_id`
- `app_name`
- `app_alias`
- `bk_biz_id`
- `bk_tenant_id`
- `status`
- `metric_data_id`
- `trace_data_id`
- `log_data_id`
- `profile_data_id`
- `service_count`
- `topo_node_count`
- `last_modify_time`

## 详情结构

```json
{
  "application": {},
  "datasources": [],
  "result_tables": [],
  "custom_reports": [],
  "service_summary": {},
  "topo_summary": {}
}
```

Service 和 Topo 可能变大，详情只返回摘要与默认前几条。完整数据通过独立 RPC 分页查询。

## 后端 RPC

### admin.apm.application_list

入参：

```json
{
  "bk_tenant_id": "system",
  "bk_biz_id": 2,
  "app_name": "checkout",
  "status": "normal",
  "bk_data_id": 50010,
  "table_id": "2_bkapm.metric",
  "page": 1,
  "page_size": 20
}
```

出参：分页返回 APM 应用列表。

### admin.apm.application_detail

入参：

```json
{
  "bk_tenant_id": "system",
  "application_id": 1,
  "include": ["datasources", "result_tables", "custom_reports", "summary"]
}
```

出参：返回详情结构。

### admin.apm.service_list

入参：

```json
{
  "bk_tenant_id": "system",
  "application_id": 1,
  "service_name": "checkout-api",
  "kind": "service",
  "page": 1,
  "page_size": 20
}
```

出参：分页返回 Service / TopoInstance 摘要。

### admin.apm.topo

入参：

```json
{
  "bk_tenant_id": "system",
  "application_id": 1,
  "topo_key": "checkout-api",
  "include_relations": true,
  "page": 1,
  "page_size": 50
}
```

出参：返回分页 topo nodes 与 relations。
