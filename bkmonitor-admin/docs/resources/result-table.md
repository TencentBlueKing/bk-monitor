# ResultTable 资源设计

## 资源定位

ResultTable 是查询侧和存储侧的核心逻辑表，以 `table_id + bk_tenant_id` 唯一标识。管理后台需要展示结果表基础信息、字段、字段选项、结果表选项、存储配置、数据源关系和自定义分组关系。

ResultTableField 可能数量非常大，必须作为独立分页资源处理。

## 涉及模型

主模型：

- ResultTable

关联模型：

- ResultTableOption
- ResultTableField
- ResultTableFieldOption
- DataSourceResultTable
- DataSource
- TimeSeriesGroup
- EventGroup
- LogGroup
- ESStorage
- AccessVMRecord

## 关键字段

列表建议展示：

| 字段 | 说明 |
| --- | --- |
| table_id | 结果表 ID |
| table_name_zh | 结果表中文名 |
| bk_tenant_id | 租户 ID |
| bk_biz_id | 所属业务 |
| label | 结果表标签 |
| data_label | 数据标签 |
| schema_type | schema 类型 |
| default_storage | 默认存储 |
| is_custom_table | 是否自定义结果表 |
| is_builtin | 是否内置 |
| is_enable | 是否启用 |
| is_deleted | 是否已删除 |
| create_time | 创建时间 |
| last_modify_time | 更新时间 |

列表摘要建议额外返回：

- field_count
- datasource_count
- has_es_storage
- has_vm_record
- custom_group_type

## 检索与过滤

一期支持：

| 过滤项 | 类型 | 匹配方式 | 备注 |
| --- | --- | --- | --- |
| table_id | string | 精确 / 前缀 / 包含 | 最常用 |
| table_name_zh | string | 包含 | 控制查询范围 |
| bk_biz_id | number | 精确 | 业务维度 |
| bk_data_id | number | 关联过滤 | 通过 DataSourceResultTable |
| data_label | string | 包含 / 精确 | 用于路由排查 |
| label | enum | 精确 | 结果表标签 |
| schema_type | enum | 精确 | free / dynamic / fixed |
| default_storage | enum | 精确 | es / influxdb / kafka 等 |
| is_enable | boolean | 精确 | 默认不过滤 |
| is_deleted | boolean | 精确 | 默认不过滤 |
| is_builtin | boolean | 精确 | 默认不过滤 |
| bk_tenant_id | string | 精确 | 必选或由环境上下文注入 |

## 列表行为

- 默认不展示字段明细。
- 默认按 `last_modify_time desc` 或 `table_id asc` 排序。
- `data_label` 可能包含多个标签，列表中需要支持折叠和复制。
- `labels` JSON 不直接铺开，只在详情中展示。
- `is_deleted` 和 `is_enable` 必须同时展示，避免只看一个状态误判。

## 详情页面

建议详情分 tab：

### 概览

展示 ResultTable 基础字段：

- table_id
- table_name_zh
- bk_tenant_id
- bk_biz_id
- bk_biz_id_alias
- schema_type
- default_storage
- label
- data_label
- labels
- is_custom_table
- is_builtin
- is_enable
- is_deleted
- creator / last_modify_user
- create_time / last_modify_time

### Options

展示 ResultTableOption：

- name
- value
- value_type
- creator
- create_time

重点关注：

- cmdb_level_config
- es_unique_field_list
- group_info_alias
- dimension_values
- segmented_query_enable
- is_split_measurement
- enable_field_black_list
- binding_bcs_cluster_id

### 字段

ResultTableField 独立分页：

列表字段：

- field_name
- field_type
- tag
- description
- unit
- is_config_by_user
- alias_name
- is_disabled
- last_modify_time

过滤：

- field_name
- field_type
- tag
- is_config_by_user
- is_disabled
- has_option

字段详情展示 ResultTableFieldOption：

- es_type
- es_include_in_all
- es_format
- es_doc_values
- es_index
- influxdb_disabled

### 数据源

通过 DataSourceResultTable 展示关联 DataSource：

- bk_data_id
- data_name
- created_from
- source_label
- type_label
- is_enable
- is_custom_source

`bk_data_id` 可跳转到 DataSource 详情。

### 自定义分组

按 `table_id` 或 `bk_data_id` 关联：

- TimeSeriesGroup
- EventGroup
- LogGroup

展示公共字段：

- group id
- group name
- bk_data_id
- bk_biz_id
- table_id
- label
- is_enable
- is_delete
- is_split_measurement

不同类型补充字段：

- TimeSeriesGroup：metric_group_dimensions
- EventGroup：status、last_check_report_time
- LogGroup：log_group_name、bk_data_token 是否存在

### 存储

一期重点展示 ESStorage：

- table_id
- origin_table_id
- storage_cluster_id
- retention
- slice_size
- slice_gap
- date_format
- time_zone
- source_type
- index_set
- need_create_index
- archive_index_days
- warm_phase_days
- warm_phase_settings
- long_term_storage_settings

后续可扩展 InfluxDBStorage、KafkaStorage、BkDataStorage 等。

### VM 接入

展示 AccessVMRecord：

- data_type
- result_table_id
- bcs_cluster_id
- storage_cluster_id
- vm_cluster_id
- bk_base_data_id
- bk_base_data_name
- vm_result_table_id
- remark
- bk_tenant_id

## ResultTableField 大数据量处理

字段不能跟随 ResultTable 列表返回，也不建议在详情首屏一次性返回。

建议策略：

- 字段 tab 首次打开时再请求。
- 默认 page size 50。
- 支持服务端分页和服务端过滤。
- field_name 过滤优先走前缀或精确匹配；包含匹配需要评估索引与数据量。
- FieldOption 默认不随字段列表展开，只返回 `option_count` 或 `has_option`。
- 点击字段行后再请求字段 options。

如果后端需要为字段列表做接口，建议返回：

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 0,
  "summary": {
    "metric_count": 0,
    "dimension_count": 0,
    "timestamp_count": 0,
    "disabled_count": 0
  }
}
```

## 与 DataSource 的关系

ResultTable 到 DataSource 的主路径是：

```text
ResultTable.table_id
  -> DataSourceResultTable.table_id
  -> DataSourceResultTable.bk_data_id
  -> DataSource.bk_data_id
```

在多租户环境下必须同时带上 `bk_tenant_id`。

## 后端接口需求

这些接口后续都应沉淀为 Agent-facing operation，并提供 input/output schema、examples 和 `safety_level=read`。

所有请求都必须携带 `environment_id`，或由已绑定环境的会话上下文注入。

### admin.result_table.list

Agent operation：`result_table.list`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "data_label": "bk_monitor",
  "default_storage": "influxdb",
  "page": 1,
  "page_size": 20
}
```

响应 item 建议带：

- ResultTable 轻量字段
- field_count
- datasource_count
- has_es_storage
- has_vm_record
- custom_group_type

### admin.result_table.detail

Agent operation：`result_table.detail`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "table_id": "system.cpu"
}
```

响应建议：

```json
{
  "result_table": {},
  "options": [],
  "datasource_relations": [],
  "datasources": [],
  "custom_groups": {
    "time_series_groups": [],
    "event_groups": [],
    "log_groups": []
  },
  "storages": {
    "es": []
  },
  "access_vm_records": []
}
```

### admin.result_table.field_list

Agent operation：`result_table.field_list`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "field_name": "usage",
  "tag": "metric",
  "page": 1,
  "page_size": 50
}
```

响应建议：

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 0,
  "summary": {}
}
```

### admin.result_table.field_options

Agent operation：`result_table.field_options`

Safety level：`read`

请求示例：

```json
{
  "environment_id": "prod-main",
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "field_name": "usage"
}
```

响应建议：

```json
{
  "field": {},
  "options": []
}
```

## 一期验收标准

- 能按 `table_id` 快速定位唯一 ResultTable。
- 能按 `bk_data_id` 反查关联 ResultTable。
- 能按 `data_label`、`default_storage`、`label`、`schema_type` 过滤。
- 详情能展示 options、数据源关系、自定义分组、ESStorage、AccessVMRecord。
- 字段列表分页加载，不拖慢 ResultTable 列表和详情首屏。
- 字段详情能查看 FieldOption。
