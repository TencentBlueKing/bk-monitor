# 后端 Admin RPC 函数规划

## 实现位置

Admin 后端只读 RPC 建议放在 bkmonitor：

```text
kernel_api/rpc/functions/admin/
├── __init__.py
├── common.py
├── tenant.py
├── datasource.py
├── result_table.py
└── es_storage.py
```

注意：当前 `kernel_api/rpc/functions/__init__.py` 只会 import `functions` 目录下一层模块。如果使用 `functions/admin/` 子包，需要保证 `kernel_api.rpc.functions.admin` 被 import 后会继续 import `tenant.py`、`datasource.py`、`result_table.py` 等模块，从而触发 `KernelRPCRegistry.register(...)`。

推荐在 `admin/__init__.py` 中显式 import：

```python
from . import tenant
from . import datasource
from . import result_table
from . import es_storage

__all__ = ["tenant", "datasource", "result_table", "es_storage"]
```

## 命名约定

后端 `func_name` 使用 `admin.<resource>.<action>`：

- `admin.tenant.list`
- `admin.datasource.list`
- `admin.datasource.detail`
- `admin.result_table.list`
- `admin.result_table.detail`
- `admin.result_table.field_list`
- `admin.result_table.field_options`
- `admin.es_storage.list`
- `admin.es_storage.detail`
- `admin.es_storage.runtime_overview`
- `admin.es_storage.sample`

前端和 Agent-facing operation 可以保持去掉 `admin.` 前缀的稳定名称：

- `tenant.list`
- `datasource.list`
- `datasource.detail`
- `result_table.list`
- `result_table.detail`
- `result_table.field_list`
- `result_table.field_options`
- `es_storage.list`
- `es_storage.detail`
- `es_storage.runtime_overview`
- `es_storage.sample`

映射关系由 `bkmonitor-admin` 前端 RPC client 维护。

## 环境上下文说明

`environment_id` 是 `bkmonitor-admin` 管理多套 bkmonitor 环境的前端/Agent 上下文。它用于选择目标 bkmonitor API endpoint，不应该作为 bkmonitor 后端模型查询条件。

实际调用链：

```text
Agent/UI
  -> environment_id 选择目标环境
  -> POST <target>/api/v4/kernel_rpc/call/
  -> func_name = admin.datasource.detail
  -> params = {bk_tenant_id, bk_data_id}
```

后端 RPC 返回 `operation`、`safety_level`、`effective_bk_tenant_id` 等信息；`environment_id` 由前端 client 在最终 Agent-facing envelope 中补回。

## admin.tenant.list

用途：查询当前环境可见租户，用于管理后台顶部租户上下文切换。

Agent operation：`tenant.list`

Safety level：`read`

实现策略：

- 优先调用 `api.bk_login.list_tenant()` 获取租户列表。
- 补充 metadata 核心表中已经存在数据的 `bk_tenant_id`，避免外部租户接口异常或不完整时无法切换到已有租户。
- 至少返回 `system`。

入参：

```json
{
  "keyword": "system",
  "page": 1,
  "page_size": 100
}
```

出参：

```json
{
  "data": {
    "items": [
      {
        "id": "system",
        "name": "system",
        "display_name": "system",
        "source": "bk_login",
        "datasource_count": 12,
        "result_table_count": 48
      }
    ],
    "page": 1,
    "page_size": 100,
    "total": 1
  },
  "warnings": [],
  "meta": {
    "operation": "tenant.list",
    "func_name": "admin.tenant.list",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

## 通用入参

### 分页参数

```json
{
  "page": 1,
  "page_size": 20
}
```

约束：

- `page` 默认 `1`，最小 `1`。
- `page_size` 默认 `20`，最大 `100`。
- ResultTableField 默认 `50`，最大 `200`。

### 排序参数

```json
{
  "ordering": "-last_modify_time"
}
```

约束：

- 只允许白名单字段排序。
- 不支持任意 ORM 字段名透传。

### include 参数

详情接口可支持按需展开：

```json
{
  "include": ["options", "datasources"]
}
```

约束：

- 默认只返回适合首屏展示的信息。
- 大列表必须通过独立接口获取，例如 `ResultTableField`。

## 通用出参

后端 admin RPC 的 `result` 建议返回：

```json
{
  "data": {},
  "warnings": [],
  "meta": {
    "operation": "datasource.detail",
    "func_name": "admin.datasource.detail",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

列表结构：

```json
{
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  },
  "warnings": [],
  "meta": {
    "operation": "datasource.list",
    "func_name": "admin.datasource.list",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

错误仍沿用 `core.drf_resource.exceptions.CustomException`，message 要面向用户可读。后续如果需要 Agent 更稳定解析错误，可以在 admin RPC 内部统一抛出带 `code/details` 的异常结构。

## 函数清单

### admin.datasource.list

用途：DataSource 列表检索。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "bk_data_id": 50010,
  "data_name": "demo",
  "created_from": "bkdata",
  "source_label": "bk_monitor",
  "type_label": "time_series",
  "is_enable": true,
  "is_custom_source": true,
  "is_platform_data_id": false,
  "space_uid": "bkcc__2",
  "table_id": "system.cpu",
  "page": 1,
  "page_size": 20,
  "ordering": "-last_modify_time"
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID；未传时按 kernel RPC 租户注入逻辑处理 |
| bk_data_id | 否 | 数据源 ID，精确匹配 |
| data_name | 否 | 数据源名称，包含匹配或前缀匹配 |
| created_from | 否 | 数据源来源 |
| source_label | 否 | 数据源标签 |
| type_label | 否 | 数据类型标签 |
| is_enable | 否 | 是否启用 |
| is_custom_source | 否 | 是否自定义数据源 |
| is_platform_data_id | 否 | 是否平台级 ID |
| space_uid | 否 | 所属空间 UID |
| table_id | 否 | 通过 DataSourceResultTable 关联过滤 |
| page | 否 | 页码 |
| page_size | 否 | 每页数量 |
| ordering | 否 | 排序字段 |

#### 出参

```json
{
  "data": {
    "items": [
      {
        "bk_data_id": 50010,
        "bk_tenant_id": "system",
        "data_name": "demo",
        "data_description": "demo datasource",
        "type_label": "time_series",
        "source_label": "bk_monitor",
        "custom_label": null,
        "source_system": "bk_monitor",
        "is_enable": true,
        "is_custom_source": true,
        "is_platform_data_id": false,
        "space_type_id": "bkcc",
        "space_uid": "bkcc__2",
        "created_from": "bkdata",
        "mq_cluster_id": 1,
        "mq_config_id": 2,
        "kafka_cluster": {
          "cluster_id": 1,
          "cluster_name": "default-kafka",
          "display_name": "默认 Kafka 集群",
          "cluster_type": "kafka",
          "is_default_cluster": true,
          "registered_system": "_default",
          "label": "default"
        },
        "transfer_cluster_id": "default",
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00",
        "last_modify_user": "admin",
        "last_modify_time": "2026-04-24 10:00:00",
        "result_table_count": 1,
        "space_count": 1,
        "option_count": 3,
        "has_data_id_config": true
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "warnings": [],
  "meta": {
    "operation": "datasource.list",
    "func_name": "admin.datasource.list",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.datasource.detail

用途：查询 DataSource 详情和关联信息。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "bk_data_id": 50010,
  "include": ["options", "spaces", "result_tables", "data_id_config"]
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID |
| bk_data_id | 是 | 数据源 ID |
| include | 否 | 展开范围，默认展开基础关联，不展开高成本信息 |

#### 出参

```json
{
  "data": {
    "datasource": {
      "bk_data_id": 50010,
      "bk_tenant_id": "system",
      "data_name": "demo",
      "data_description": "demo datasource",
      "mq_cluster_id": 1,
      "mq_config_id": 2,
      "etl_config": "bk_standard_v2_time_series",
      "is_custom_source": true,
      "type_label": "time_series",
      "source_label": "bk_monitor",
      "custom_label": null,
      "source_system": "bk_monitor",
      "is_enable": true,
      "transfer_cluster_id": "default",
      "is_platform_data_id": false,
      "space_type_id": "bkcc",
      "space_uid": "bkcc__2",
      "created_from": "bkdata",
      "creator": "admin",
      "create_time": "2026-04-24 10:00:00",
      "last_modify_user": "admin",
      "last_modify_time": "2026-04-24 10:00:00",
      "has_token": true
    },
    "kafka_cluster": {
      "cluster_id": 1,
      "cluster_name": "default-kafka",
      "display_name": "默认 Kafka 集群",
      "cluster_type": "kafka",
      "is_default_cluster": true,
      "registered_system": "_default",
      "label": "default"
    },
    "kafka_topic_config": {
      "id": 2,
      "bk_data_id": 50010,
      "topic": "bkmonitor_50010",
      "partition": 1,
      "batch_size": 500,
      "flush_interval": "1s",
      "consume_rate": 1000
    },
    "options": [
      {
        "name": "flat_batch_key",
        "value": "data",
        "value_type": "string",
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00"
      }
    ],
    "space_datasources": [
      {
        "space_type_id": "bkcc",
        "space_id": "2",
        "space_uid": "bkcc__2",
        "bk_tenant_id": "system",
        "bk_data_id": 50010,
        "from_authorization": false
      }
    ],
    "data_source_result_tables": [
      {
        "bk_data_id": 50010,
        "table_id": "system.cpu",
        "bk_tenant_id": "system",
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00"
      }
    ],
    "result_tables": [
      {
        "table_id": "system.cpu",
        "bk_tenant_id": "system",
        "table_name_zh": "CPU",
        "bk_biz_id": 2,
        "data_label": "bk_monitor",
        "default_storage": "influxdb",
        "is_enable": true,
        "is_deleted": false
      }
    ],
    "data_id_config": {
      "bk_tenant_id": "system",
      "namespace": "bkmonitor",
      "name": "demo",
      "kind": "DataId",
      "bk_data_id": 50010
    }
  },
  "warnings": [],
  "meta": {
    "operation": "datasource.detail",
    "func_name": "admin.datasource.detail",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.result_table.list

用途：ResultTable 列表检索。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "table_name_zh": "CPU",
  "bk_biz_id": 2,
  "bk_data_id": 50010,
  "data_label": "bk_monitor",
  "label": "os",
  "schema_type": "fixed",
  "default_storage": "influxdb",
  "is_enable": true,
  "is_deleted": false,
  "is_builtin": true,
  "page": 1,
  "page_size": 20,
  "ordering": "table_id"
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID |
| table_id | 否 | 结果表 ID，支持精确、前缀或受控包含匹配 |
| table_name_zh | 否 | 中文名，受控包含匹配 |
| bk_biz_id | 否 | 所属业务 |
| bk_data_id | 否 | 通过 DataSourceResultTable 关联过滤 |
| data_label | 否 | 数据标签 |
| label | 否 | 结果表标签 |
| schema_type | 否 | free / dynamic / fixed |
| default_storage | 否 | 默认存储 |
| is_enable | 否 | 是否启用 |
| is_deleted | 否 | 是否删除 |
| is_builtin | 否 | 是否内置 |
| page | 否 | 页码 |
| page_size | 否 | 每页数量 |
| ordering | 否 | 排序字段 |

#### 出参

```json
{
  "data": {
    "items": [
      {
        "table_id": "system.cpu",
        "bk_tenant_id": "system",
        "table_name_zh": "CPU",
        "bk_biz_id": 2,
        "bk_biz_id_alias": "",
        "label": "os",
        "data_label": "bk_monitor",
        "schema_type": "fixed",
        "default_storage": "influxdb",
        "is_custom_table": false,
        "is_builtin": true,
        "is_enable": true,
        "is_deleted": false,
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00",
        "last_modify_user": "admin",
        "last_modify_time": "2026-04-24 10:00:00",
        "field_count": 20,
        "datasource_count": 1,
        "has_es_storage": false,
        "has_vm_record": false,
        "custom_group_type": null
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "warnings": [],
  "meta": {
    "operation": "result_table.list",
    "func_name": "admin.result_table.list",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.result_table.detail

用途：查询 ResultTable 详情和关联信息，不返回字段全量。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "include": ["options", "datasources", "custom_groups", "storages", "vm_records"]
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID |
| table_id | 是 | 结果表 ID |
| include | 否 | 展开范围，不支持 `fields` 全量展开 |

#### 出参

```json
{
  "data": {
    "result_table": {
      "table_id": "system.cpu",
      "bk_tenant_id": "system",
      "table_name_zh": "CPU",
      "bk_biz_id": 2,
      "bk_biz_id_alias": "",
      "schema_type": "fixed",
      "default_storage": "influxdb",
      "label": "os",
      "data_label": "bk_monitor",
      "labels": {},
      "is_custom_table": false,
      "is_builtin": true,
      "is_enable": true,
      "is_deleted": false,
      "creator": "admin",
      "create_time": "2026-04-24 10:00:00",
      "last_modify_user": "admin",
      "last_modify_time": "2026-04-24 10:00:00"
    },
    "summary": {
      "field_count": 20,
      "metric_field_count": 8,
      "dimension_field_count": 10,
      "disabled_field_count": 0,
      "datasource_count": 1
    },
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
  },
  "warnings": [
    {
      "code": "FIELDS_NOT_INCLUDED",
      "message": "字段数量可能较大，请通过 admin.result_table.field_list 分页查询"
    }
  ],
  "meta": {
    "operation": "result_table.detail",
    "func_name": "admin.result_table.detail",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.result_table.field_list

用途：ResultTableField 独立分页查询。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "field_name": "usage",
  "field_type": "float",
  "tag": "metric",
  "is_config_by_user": true,
  "is_disabled": false,
  "has_option": true,
  "page": 1,
  "page_size": 50,
  "ordering": "field_name"
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID |
| table_id | 是 | 结果表 ID |
| field_name | 否 | 字段名过滤 |
| field_type | 否 | 字段类型 |
| tag | 否 | metric / dimension / timestamp / group 等 |
| is_config_by_user | 否 | 是否用户确认字段 |
| is_disabled | 否 | 是否禁用 |
| has_option | 否 | 是否存在 FieldOption |
| page | 否 | 页码 |
| page_size | 否 | 每页数量，默认 50 |
| ordering | 否 | 排序字段 |

#### 出参

```json
{
  "data": {
    "items": [
      {
        "table_id": "system.cpu",
        "bk_tenant_id": "system",
        "field_name": "usage",
        "field_type": "float",
        "description": "CPU usage",
        "unit": "percent",
        "tag": "metric",
        "is_config_by_user": true,
        "default_value": null,
        "alias_name": "",
        "is_disabled": false,
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00",
        "last_modify_user": "admin",
        "last_modify_time": "2026-04-24 10:00:00",
        "option_count": 1,
        "has_option": true
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 1,
    "summary": {
      "metric_count": 8,
      "dimension_count": 10,
      "timestamp_count": 1,
      "disabled_count": 0
    }
  },
  "warnings": [],
  "meta": {
    "operation": "result_table.field_list",
    "func_name": "admin.result_table.field_list",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.result_table.field_options

用途：查询单个 ResultTableField 及其 FieldOption。

Safety level：`read`

#### 入参

```json
{
  "bk_tenant_id": "system",
  "table_id": "system.cpu",
  "field_name": "usage"
}
```

#### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| bk_tenant_id | 否 | 租户 ID |
| table_id | 是 | 结果表 ID |
| field_name | 是 | 字段名 |

#### 出参

```json
{
  "data": {
    "field": {
      "table_id": "system.cpu",
      "bk_tenant_id": "system",
      "field_name": "usage",
      "field_type": "float",
      "description": "CPU usage",
      "unit": "percent",
      "tag": "metric",
      "is_config_by_user": true,
      "alias_name": "",
      "is_disabled": false
    },
    "options": [
      {
        "name": "es_type",
        "value": "float",
        "value_type": "string",
        "creator": "admin",
        "create_time": "2026-04-24 10:00:00"
      }
    ]
  },
  "warnings": [],
  "meta": {
    "operation": "result_table.field_options",
    "func_name": "admin.result_table.field_options",
    "safety_level": "read",
    "effective_bk_tenant_id": "system"
  }
}
```

### admin.es_storage.list

用途：分页查询 ESStorage 独立资源。

Safety level：`read`

支持过滤：`table_id` 同时匹配 `ESStorage.table_id/origin_table_id`，`data_label` 先精确匹配 `ResultTable.data_label`，`table_kind` 支持 `physical/virtual`，并支持 `storage_cluster_id`、`source_type`、`need_create_index`。`index_set` 仅展示，不作为过滤条件。

### admin.es_storage.detail

用途：查询 ESStorage 静态配置和关系信息。

Safety level：`read`

返回 ESStorage 配置、ResultTable 摘要、ClusterInfo 摘要、实体/虚拟表关系、`StorageClusterRecord` 迁移历史、ES 相关 ResultTableOption，以及 `ESFieldQueryAliasOption.generate_query_alias_settings(...)` 生成的字段查询别名说明。虚拟表的迁移历史按实体表 `origin_table_id` 查询。

### admin.es_storage.runtime_overview

用途：实时读取 ES 索引、别名和 mapping 概览。

Safety level：`inspect`

实现优先复用 `ESStorage.get_index_names()`、`get_index_stats()`、`current_index_info()`、`index_exist()`、`search_format_v1()`、`search_format_v2()`；mapping 和 aliases 只做 ES client 薄封装。单类查询失败会返回 warning，不影响其他结果。

### admin.es_storage.sample

用途：从指定索引读取最新一条样例数据。

Safety level：`inspect`

`index` 必填且不允许通配符，必须属于当前 ESStorage 的索引集合或匹配当前索引规则；默认 `time_field=dtEventTimeStamp`，查询复用 `ESStorage.get_raw_data(index_name, time_field)`。

### admin.query_route.query

用途：Redis 查询路由诊断工具，查询 `SPACE_TO_RESULT_TABLE_KEY`、`DATA_LABEL_TO_RESULT_TABLE_KEY`、`RESULT_TABLE_DETAIL_KEY`。后端按 `settings.ENABLE_MULTI_TENANT_MODE` 自行拼接 Redis field，前端不需要感知单租/多租。

Safety level：`read`

入参支持 `bk_tenant_id`、`space_uid` 或 `space_type_id + space_id`、`table_ids`、`data_labels`/`data_label`、`field_names`。`table_ids`、`data_labels`、`field_names` 支持字符串、逗号分隔字符串或列表。

返回包含 `query` 回显、`space_route`、`data_label_routes`、`result_table_details`、`diagnostics`。其中 `space_route.items[].filter_groups` 会把每个 filter object 解析为 AND 条件组，多个组表示 OR；同时保留原始 `filters` 和 `raw`。接口只使用明确 field 的 `hget/hmget`，不做 `hgetall` 全量扫描。

### admin.query_route.refresh

用途：主动刷新 Redis 查询路由，刷新时 `is_publish=True`。

Safety level：`read`

入参同 `admin.query_route.query`，但至少需要指定 `space_uid`、`table_ids` 或 `data_labels` 中的一项。`space_uid` 刷新 `space_to_result_table`；`table_ids` 刷新 `result_table_detail` 并包含 ES 表；`data_labels` 或 `table_ids` 刷新 `data_label_to_result_table`。多租户下会用 `bk_tenant_id` 校验目标空间，避免跨租户刷新。

## 后续可扩展函数

一期先不实现，但可以预留命名：

- `admin.meta.tool_list`：返回 admin RPC tool 元信息。
- `admin.meta.tool_detail`：返回单个 tool 的 schema、示例和安全级别。
- `admin.vm.access_record_list`：按 table_id、bcs_cluster_id、bk_base_data_id 查询 VM 接入记录。
- `admin.datasource.kafka_sample`：读取 Kafka 样例数据，安全级别应为 `inspect`，不放入第一期默认能力。
