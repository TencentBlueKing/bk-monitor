# 第三期规划：ESStorage 资源接入与 ES 实时观测能力

本文档跟踪 `bkmonitor-admin` 第三期改造任务。核心目标：

1. 新增 ESStorage 独立资源，支持围绕实体表、虚拟表、集群和 ResultTable 的检索与跳转。
2. 在 ResultTable 与 ClusterInfo 详情中补齐 ESStorage 关联导航，形成 DataSource / ResultTable / ESStorage / ClusterInfo 闭环。
3. 在 ESStorage 详情页提供来自 Elasticsearch 的实时查询能力，包括索引基础信息、mapping、别名和最新一条数据。

## 状态约定

| 状态        | 说明                       |
| ----------- | -------------------------- |
| Todo        | 尚未开始                   |
| In Progress | 正在实现                   |
| Blocked     | 被依赖、环境或方案问题阻塞 |
| Review      | 已完成实现，等待 review    |
| Done        | 已完成并验证               |

## 总体里程碑

| 阶段 | 目标                                            | 状态 |
| ---- | ----------------------------------------------- | ---- |
| M1   | 后端新增 ESStorage 列表、详情与实时 ES 查询 RPC | Todo |
| M2   | 前端新增 ESStorage 列表页、详情页和导航入口     | Todo |
| M3   | ResultTable / ClusterInfo 关联跳转增强          | Todo |
| M4   | ESStorage 详情页实时信息与最新数据取样          | Todo |
| M5   | 联调、测试、文档收口                            | Todo |

---

## 一、需求背景与资源关系

### 1.1 ESStorage 的资源定位

`ESStorage` 是 ResultTable 的 Elasticsearch 存储配置，也是日志、事件等场景排查索引问题的关键入口。第三期将它提升为独立资源，而不是只作为 ResultTable 详情中的一个附属 JSON 块。

列表页用于回答：

- 某个 `table_id` 是否存在 ES 存储。
- 某个 ES 集群下有哪些存储配置。
- 哪些记录是实体表，哪些记录是虚拟表。
- 某个实体表关联了哪些虚拟表。

详情页用于回答：

- 这条 ESStorage 的静态配置是什么。
- 它关联哪个 ResultTable 和 ClusterInfo。
- 它经历过哪些 ES 集群迁移，当前写入集群和历史集群分别是什么。
- 运行时 ES 中实际有哪些索引、别名、mapping。
- 能否从指定索引中读取最新一条数据。

### 1.2 实体表与虚拟表

`ESStorage.origin_table_id` 是实体表/虚拟表判定字段：

| 类型   | 判定规则                                       | 说明                                                 |
| ------ | ---------------------------------------------- | ---------------------------------------------------- |
| 实体表 | `origin_table_id` 为空字符串、`null` 或 `None` | 对应真实物理索引创建与生命周期管理                   |
| 虚拟表 | `origin_table_id` 非空                         | 关联到一个实体表，用于日志平台索引集等跨索引查询场景 |

第三期必须在过滤条件中明确提供“表类型”过滤：

| 前端过滤项 | 后端参数     | 取值                                                             |
| ---------- | ------------ | ---------------------------------------------------------------- |
| 表类型     | `table_kind` | `physical` / `virtual` / 空                                      |
| 表 ID      | `table_id`   | 同时匹配 `ESStorage.table_id` 与 `ESStorage.origin_table_id`     |
| 数据标签   | `data_label` | 先精确匹配 ResultTable.data_label，再用 table_ids 查询 ESStorage |

> 注意：虚拟表也具备 `ResultTable`、`ESStorage`、`ESFieldQueryAliasOption` 和 ResultTableOption 相关配置，运行时 ES 信息应按虚拟表自身配置正常查询。虚拟表不具备集群迁移记录，但它的索引匹配信息是完备的，通常由 `index_set`、`date_format`、`slice_gap` 等时间分片规则共同决定。

### 1.3 关键关联关系

```text
DataSource
  -> DataSourceResultTable.bk_data_id
  -> ResultTable.table_id
  -> ESStorage.table_id
  -> ClusterInfo.cluster_id = ESStorage.storage_cluster_id

ESStorage(虚拟表).origin_table_id
  -> ESStorage(实体表).table_id
  -> ResultTable(实体表).table_id
```

导航要求：

- ESStorage 列表和详情中的 `table_id` 可跳转 ResultTable 详情。
- ESStorage 详情中的 `storage_cluster_id` 可跳转 ClusterInfo 详情，并自动定位为 `cluster_type=elasticsearch`。
- ResultTable 详情中的 ESStorage 区域可跳转 ESStorage 详情。
- ClusterInfo 详情中 `cluster_type=elasticsearch` 时，关联存储数可跳转 ESStorage 列表并预填 `storage_cluster_id`。
- 虚拟表详情展示实体表链接，实体表详情展示关联虚拟表列表。

---

## 二、后端新增 RPC

> 实现性能要求：列表接口不做逐行关联查询。ResultTable、ClusterInfo、虚拟表数量等关联数据必须通过 `values_list`、`in`、`COUNT/GROUP BY` 或批量查询组装。实时 ES 查询只在详情页或显式按钮触发时执行。

### P3-001 `admin.es_storage.list` — ESStorage 列表

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供 `ESStorage` 只读列表查询。
- 显式支持实体表/虚拟表过滤。
- 返回 ResultTable 和 ClusterInfo 的轻量摘要，支持前端直接渲染跳转信息。

入参：

```json
{
  "bk_tenant_id": "system",
  "table_id": "2_bklog",
  "data_label": "bk_log",
  "table_kind": "virtual",
  "storage_cluster_id": 1,
  "source_type": "log",
  "need_create_index": true,
  "page": 1,
  "page_size": 20,
  "ordering": "table_id"
}
```

| 字段                 | 类型    | 必填 | 说明                                                                                       |
| -------------------- | ------- | ---- | ------------------------------------------------------------------------------------------ |
| `bk_tenant_id`       | string  | 否   | 租户 ID                                                                                    |
| `table_id`           | string  | 否   | 表 ID，同时在 `ESStorage.table_id` 与 `ESStorage.origin_table_id` 上做精确、前缀、子串匹配 |
| `data_label`         | string  | 否   | 精确匹配 ResultTable.data_label，再用匹配到的 table_ids 查询 ESStorage                     |
| `table_kind`         | string  | 否   | `physical` / `virtual`，为空表示不过滤                                                     |
| `storage_cluster_id` | integer | 否   | ES 集群 ID                                                                                 |
| `source_type`        | string  | 否   | 数据源类型，如 `log`                                                                       |
| `need_create_index`  | boolean | 否   | 是否需要创建物理索引                                                                       |
| `page` / `page_size` | int     | 否   | 分页                                                                                       |
| `ordering`           | string  | 否   | 排序字段                                                                                   |

出参（列表项）：

```json
{
  "id": 1,
  "table_id": "2_bklog_rt",
  "origin_table_id": "2_bklog_origin",
  "table_kind": "virtual",
  "bk_tenant_id": "system",
  "storage_cluster_id": 12,
  "storage_cluster": {
    "cluster_id": 12,
    "cluster_name": "es-default",
    "display_name": "默认 ES 集群",
    "cluster_type": "elasticsearch"
  },
  "result_table": {
    "table_id": "2_bklog_rt",
    "table_name_zh": "日志结果表",
    "bk_biz_id": 2,
    "default_storage": "elasticsearch",
    "is_enable": true,
    "is_deleted": false
  },
  "physical_table": {
    "table_id": "2_bklog_origin",
    "exists": true
  },
  "virtual_table_count": 0,
  "retention": 7,
  "slice_size": 500,
  "slice_gap": 120,
  "date_format": "%Y%m%d",
  "time_zone": "UTC",
  "source_type": "log",
  "index_set": "demo_index_set",
  "need_create_index": false,
  "archive_index_days": 0,
  "warm_phase_days": 0,
  "create_time": "2026-04-25 10:00:00",
  "last_modify_time": "2026-04-25 10:00:00"
}
```

实现要点：

- `table_kind=physical`：过滤 `origin_table_id` 为空字符串或 `NULL`。
- `table_kind=virtual`：过滤 `origin_table_id` 非空且非 `NULL`。
- `table_id` 过滤条件默认覆盖 `ESStorage.table_id` 和 `ESStorage.origin_table_id`，不再单独提供 `origin_table_id` 过滤项。
- `data_label` 过滤先精确查询 `ResultTable.objects.filter(data_label=data_label)` 得到 table_ids，再查询 `ESStorage.table_id__in=table_ids`。
- `storage_cluster_id` 精确过滤，且只用于 ESStorage；ClusterInfo 类型由详情和前端跳转限制为 `elasticsearch`。
- `virtual_table_count` 对实体表有效，通过一次聚合查询 `origin_table_id -> count` 生成；虚拟表返回 0。
- ResultTable 摘要通过 `table_id__in` 批量查询。
- ClusterInfo 摘要通过 `storage_cluster_id__in` 批量查询。
- 列表仅展示 `index_set`，不作为过滤条件。
- 排序白名单建议：`id`、`table_id`、`origin_table_id`、`storage_cluster_id`、`retention`、`source_type`、`create_time`、`last_modify_time`。

### P3-002 `admin.es_storage.detail` — ESStorage 详情

状态：Todo  
建议负责人：Backend Agent

目标：

- 提供单条 ESStorage 详情。
- 返回实体/虚拟关系、ResultTable 摘要、ClusterInfo 摘要、StorageClusterRecord 集群迁移历史和关联虚拟表列表。
- 默认不访问 Elasticsearch，仅返回数据库静态配置。

入参：

```json
{
  "bk_tenant_id": "system",
  "table_id": "2_bklog_rt",
  "include": ["relations"]
}
```

| 字段           | 类型          | 必填 | 说明                           |
| -------------- | ------------- | ---- | ------------------------------ |
| `bk_tenant_id` | string        | 否   | 租户 ID                        |
| `table_id`     | string        | 是   | ESStorage.table_id             |
| `include`      | string / list | 否   | 展开范围，初期支持 `relations` |

出参：

```json
{
  "es_storage": {
    "id": 1,
    "table_id": "2_bklog_rt",
    "origin_table_id": "2_bklog_origin",
    "table_kind": "virtual",
    "bk_tenant_id": "system",
    "storage_cluster_id": 12,
    "date_format": "%Y%m%d",
    "slice_size": 500,
    "slice_gap": 120,
    "retention": 7,
    "warm_phase_days": 0,
    "warm_phase_settings": {},
    "index_settings": {},
    "mapping_settings": {},
    "time_zone": "UTC",
    "source_type": "log",
    "index_set": "demo_index_set",
    "need_create_index": false,
    "archive_index_days": 0,
    "long_term_storage_settings": {}
  },
  "result_table": { "table_id": "2_bklog_rt", "table_name_zh": "日志结果表" },
  "storage_cluster": {
    "cluster_id": 12,
    "cluster_name": "es-default",
    "cluster_type": "elasticsearch"
  },
  "storage_cluster_records": [
    {
      "table_id": "2_bklog_origin",
      "cluster_id": 10,
      "cluster": {
        "cluster_id": 10,
        "cluster_name": "es-old",
        "display_name": "旧 ES 集群",
        "cluster_type": "elasticsearch"
      },
      "is_current": false,
      "is_deleted": false,
      "enable_time": "1970-01-01 00:00:00",
      "disable_time": "2026-04-20 10:00:00",
      "delete_time": null,
      "creator": "system",
      "create_time": "2026-04-01 10:00:00"
    },
    {
      "table_id": "2_bklog_origin",
      "cluster_id": 12,
      "cluster": {
        "cluster_id": 12,
        "cluster_name": "es-default",
        "display_name": "默认 ES 集群",
        "cluster_type": "elasticsearch"
      },
      "is_current": true,
      "is_deleted": false,
      "enable_time": "2026-04-20 10:00:00",
      "disable_time": null,
      "delete_time": null,
      "creator": "system",
      "create_time": "2026-04-20 10:00:00"
    }
  ],
  "result_table_options": [
    { "name": "es_unique_field_list", "value": ["event", "target", "time"] }
  ],
  "field_aliases": [
    {
      "query_alias": "trace_id",
      "field_path": "json.trace_id",
      "path_type": "keyword",
      "mapping_alias": {
        "type": "alias",
        "path": "json.trace_id"
      }
    }
  ],
  "physical_table": {
    "table_id": "2_bklog_origin",
    "es_storage": {},
    "result_table": {}
  },
  "virtual_tables": [
    {
      "table_id": "2_bklog_virtual",
      "result_table": { "table_id": "2_bklog_virtual", "table_name_zh": "虚拟日志表" }
    }
  ]
}
```

实现要点：

- `index_settings`、`mapping_settings`、`warm_phase_settings`、`long_term_storage_settings` 尝试 JSON 解析；解析失败时返回原始字符串并增加 warning。
- 虚拟表详情中的 `physical_table` 来自 `origin_table_id`。
- 实体表详情中的 `virtual_tables` 来自 `ESStorage.objects.filter(origin_table_id=table_id)`。
- `storage_cluster_records` 来自 `StorageClusterRecord`，用于展示 ESStorage 的集群迁移历史；字段包括 `table_id`、`cluster_id`、`is_current`、`is_deleted`、`enable_time`、`disable_time`、`delete_time`、`creator`、`create_time`。
- 虚拟表查询 `StorageClusterRecord` 时需要沿用现有 `StorageClusterRecord.compose_table_id_storage_cluster_records(...)` 语义：如果当前 ESStorage 存在 `origin_table_id`，使用实体表 `origin_table_id` 查询历史集群记录。
- `storage_cluster_records` 中的 `cluster_id` 需要批量补充 ClusterInfo 摘要，支持前端跳转历史集群详情。
- 返回与 ES 查询密切相关的 `ResultTableOption` 摘要，优先包含 `es_unique_field_list`、`dimension_values`、`segmented_query_enable` 等排查常用项。
- `ESFieldQueryAliasOption` 是详情页核心关联信息，需要查询未删除记录并展示 `query_alias`、`field_path`、`path_type`，同时返回 `ESFieldQueryAliasOption.generate_query_alias_settings(...)` 的结果，帮助解释运行时查询别名和 mapping alias 的关系。
- 不在详情接口里默认查询 ES，避免页面首屏被外部集群网络拖慢。

### P3-003 `admin.es_storage.runtime_overview` — ES 索引、mapping 与别名概览

状态：Todo  
建议负责人：Backend Agent

目标：

- 从 ESStorage 关联的 Elasticsearch 集群实时读取索引基础信息、mapping 和别名。
- 安全级别标记为 `inspect`，区别于纯元数据读取。

入参：

```json
{
  "bk_tenant_id": "system",
  "table_id": "2_bklog_rt",
  "include": ["indices", "aliases", "mapping"],
  "index": "v2_2_bklog_index_set_20260425_0"
}
```

| 字段           | 类型   | 必填 | 说明                                                                 |
| -------------- | ------ | ---- | -------------------------------------------------------------------- |
| `bk_tenant_id` | string | 否   | 租户 ID                                                              |
| `table_id`     | string | 是   | ESStorage.table_id                                                   |
| `include`      | list   | 否   | 默认 `["indices", "aliases", "mapping"]`                             |
| `index`        | string | 否   | 指定索引；不传时使用 ESStorage 的 `index_set`/时间规则生成索引通配符 |

出参：

```json
{
  "table_id": "2_bklog_rt",
  "index_set": "2_bklog_index_set",
  "index_pattern": "v2_2_bklog_index_set_*",
  "indices": [
    {
      "index": "v2_2_bklog_index_set_20260425_0",
      "health": "green",
      "status": "open",
      "docs_count": 1024,
      "store_size": "12mb",
      "creation_date": "2026-04-25 10:00:00"
    }
  ],
  "aliases": [
    {
      "alias": "2_bklog_index_set_20260425_read",
      "indices": ["v2_2_bklog_index_set_20260425_0"],
      "is_write_index": false
    }
  ],
  "mapping": {
    "properties": {}
  }
}
```

实现要点：

- 客户端使用 `ESStorage.get_client()`，禁止前端传 ES 地址或凭据。
- 索引相关信息必须优先复用 `ESStorage` 已有方法，避免重复实现索引匹配和版本兼容逻辑。优先调用 `get_index_names()`、`get_index_stats()`、`current_index_info()`、`index_exist()`、`search_format_v2()`、`search_format_v1()` 等方法，并在返回中保留这些方法得到的结果。
- 虚拟表优先按当前 `ESStorage` 自身配置查询 ES；如果现有 `ESStorage` 方法对虚拟表场景无法准确处理，再使用关联实体表 `origin_table_id` 对应的 ESStorage 实例调用同一批现有方法，并在响应中返回 warning 说明 fallback；仍无法处理时，前端提示跳转实体表查看。
- 不在 admin RPC 中自行拼接复杂索引规则。`index_set`、`date_format`、`slice_gap`、v1/v2 前缀、`index_re_v1/index_re_v2` 等规则以现有 `ESStorage` 方法为准；如未来模型逻辑调整，admin 能力应跟随模型方法自动对齐。
- `indices` 可通过 `get_index_names()` 与 `get_index_stats()` 组合生成；只有现有方法没有覆盖的展示字段，才允许做轻量补充查询。
- `aliases` 使用 `indices.get_alias(index=pattern)`。
- `mapping` 使用 `indices.get_mapping(index=index_or_pattern)`；三期先按 JSON 展示，不做字段级搜索或高亮。
- mapping 展示区需要并列展示 `ESFieldQueryAliasOption`，因为查询别名最终会影响 ES mapping alias 和用户查询字段路径的解释。
- 当 mapping 过大时，后端仍返回完整 JSON，前端通过折叠/展开控制渲染；如后续发现响应过大，再增加字段摘要接口。
- 每类实时查询单独捕获异常，返回部分结果和 warnings，不因 mapping 失败影响索引列表展示。
- 超时时间建议控制在 10 秒内。

### P3-004 `admin.es_storage.sample` — ES 最新一条数据查询

状态：Todo  
建议负责人：Backend Agent

目标：

- 类似 DataSource 详情页的 Kafka 最新数据拉取，在 ESStorage 详情页支持点击后从特定索引中查询最新一条数据。
- 安全级别标记为 `inspect`。

入参：

```json
{
  "bk_tenant_id": "system",
  "table_id": "2_bklog_rt",
  "index": "v2_2_bklog_index_set_20260425_0",
  "time_field": "dtEventTimeStamp"
}
```

| 字段           | 类型   | 必填 | 默认               | 说明                                                                           |
| -------------- | ------ | ---- | ------------------ | ------------------------------------------------------------------------------ |
| `bk_tenant_id` | string | 否   | `system`           | 租户 ID                                                                        |
| `table_id`     | string | 是   |                    | ESStorage.table_id                                                             |
| `index`        | string | 是   |                    | 指定查询索引，必须来自当前 ESStorage 的索引列表或匹配当前 `index_set`/时间规则 |
| `time_field`   | string | 否   | `dtEventTimeStamp` | 排序时间字段                                                                   |

出参：

```json
{
  "table_id": "2_bklog_rt",
  "index": "v2_2_bklog_index_set_20260425_0",
  "time_field": "dtEventTimeStamp",
  "took": 12,
  "hit": {
    "_id": "abc",
    "_index": "v2_2_bklog_index_set_20260425_0",
    "_source": {}
  }
}
```

实现要点：

- 最新数据查询优先复用 `ESStorage.get_raw_data(index_name, time_field)`，不要在 admin RPC 中重复拼查询体。
- `index` 不允许任意通配符，且必须匹配当前 ESStorage 的 `index_set`/时间分片规则，避免通过该接口扫全集群。
- 如果虚拟表现有方法无法准确校验 index，则使用关联实体表实例执行同一套校验或要求用户跳转实体表。
- 若指定 `time_field` 不存在，可返回 ES 错误摘要和 warning，并建议用户从 mapping 中选择字段。
- 按钮触发式调用，不自动轮询。

### P3-005 后端测试

状态：Todo  
建议负责人：Backend Agent / QA Agent

目标：

- 覆盖 P3-001 ~ P3-004 的入参校验、实体/虚拟表过滤、关联组装和 ES client mock。

重点用例：

- `origin_table_id` 为 `None`、空字符串时均识别为实体表。
- `origin_table_id` 非空时识别为虚拟表。
- 实体表可返回关联虚拟表数量和列表。
- 虚拟表可返回实体表摘要。
- 详情接口返回 StorageClusterRecord 集群迁移历史；虚拟表使用实体表 `origin_table_id` 查询迁移记录。
- 详情接口返回 ESFieldQueryAliasOption 关联记录和 `generate_query_alias_settings(...)` 生成结果。
- `data_label` 精确过滤会先查 ResultTable，再用 table_ids 查询 ESStorage。
- 索引信息查询优先调用 ESStorage 现有方法；虚拟表无法处理时 fallback 到实体表实例或提示跳转实体表。
- `runtime_overview` 在 indices 成功、mapping 失败时返回部分数据和 warning。
- 虚拟表 `runtime_overview` 按自身 `index_set` 和时间规则查询 ES。
- `sample` 拒绝不属于当前 ESStorage `index_set`/时间规则的索引名。

---

## 三、前端新增 ESStorage 资源

### P3-101 ESStorage schema、API 与 Query

状态：Todo  
建议负责人：Frontend Agent

主要产出：

- `src/features/es-storage/schemas.ts`
- `src/features/es-storage/api.ts`
- `src/features/es-storage/queries.ts`
- `src/features/es-storage/constants.ts`

新增 operation 映射：

```typescript
{
  'es_storage.list': 'admin.es_storage.list',
  'es_storage.detail': 'admin.es_storage.detail',
  'es_storage.runtime_overview': 'admin.es_storage.runtime_overview',
  'es_storage.sample': 'admin.es_storage.sample'
}
```

前端类型重点：

- `tableKind: 'physical' | 'virtual'`
- `EsStorageSummary`
- `EsStorageDetailResponse`
- `EsRuntimeOverviewResponse`
- `EsSampleResponse`

### P3-102 ESStorage 列表页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 新增 `/es-storages` 页面，展示 ESStorage 列表和过滤器。
- 将虚拟表作为重点过滤条件放在主筛选区域，而不是高级筛选中隐藏。

过滤配置：

```typescript
const esStorageFilterFields: FilterField[] = [
  { key: 'tableId', label: '表 ID', type: 'text', placeholder: '匹配 table_id / origin_table_id' },
  {
    key: 'dataLabel',
    label: 'data_label',
    type: 'text',
    placeholder: '精确匹配 ResultTable.data_label'
  },
  {
    key: 'tableKind',
    label: '表类型',
    type: 'select',
    options: [
      { label: '实体表', value: 'physical' },
      { label: '虚拟表', value: 'virtual' }
    ]
  },
  { key: 'storageClusterId', label: 'ES 集群 ID', type: 'number' },
  { key: 'sourceType', label: 'source_type', type: 'text', advanced: true },
  { key: 'needCreateIndex', label: '需要创建索引', type: 'boolean', advanced: true }
];
```

表格列：

| 列                         | 内容                                               |
| -------------------------- | -------------------------------------------------- |
| `table_id`                 | 可点击跳转 ESStorage 详情，也提供 ResultTable 跳转 |
| `表类型`                   | Badge：实体表 / 虚拟表                             |
| `origin_table_id`          | 虚拟表显示实体表链接；实体表显示 `-`               |
| `storage_cluster`          | 集群名 + ID，可跳转 ClusterInfo 详情               |
| `result_table`             | 中文名、业务 ID、启用/删除状态                     |
| `virtual_table_count`      | 实体表显示关联虚拟表数量                           |
| `retention`                | 保留天数                                           |
| `slice_size` / `slice_gap` | 切片配置                                           |
| `need_create_index`        | Badge                                              |
| `last_modify_time`         | 更新时间                                           |

### P3-103 ESStorage 详情页

状态：Todo  
建议负责人：Frontend Agent

目标：

- 新增 `/es-storages/$tableId` 详情页。
- 首屏展示静态配置和关系，实时 ES 信息通过按钮或 tab 懒加载。

页面结构：

```text
ESStorage Detail
├── 基本信息
│   ├── table_id / table_kind / origin_table_id
│   ├── ResultTable 跳转
│   └── ClusterInfo 跳转
├── 存储配置
│   ├── retention / slice_size / slice_gap / date_format / time_zone
│   └── source_type / index_set / need_create_index
├── 实体/虚拟关系
│   ├── 虚拟表：展示实体表链接
│   └── 实体表：展示关联虚拟表列表
├── 集群迁移历史
│   ├── 当前写入集群
│   └── 历史集群记录（enable_time / disable_time / delete_time）
├── 字段查询别名
│   ├── ESFieldQueryAliasOption 列表
│   └── mapping alias 预览
├── 配置 JSON
│   ├── index_settings
│   ├── mapping_settings
│   ├── warm_phase_settings
│   └── long_term_storage_settings
└── ES 实时信息
    ├── 索引列表
    ├── Mapping
    ├── 别名
    └── 最新一条数据
```

交互要求：

- 虚拟表顶部显示提示：“该 ESStorage 是虚拟表，运行时 ES 信息按自身 `index_set` 与时间分片规则查询；`origin_table_id` 仅表示实体表关联关系。”
- 集群迁移历史以时间线或表格展示，`is_current=true` 的记录高亮；每个 `cluster_id` 可跳转 ClusterInfo 详情。
- 字段查询别名区域展示 `query_alias -> field_path`，并说明这些配置与 mapping alias、查询字段路径解释相关。
- 实时信息区域默认未加载，点击“加载 ES 实时信息”后调用 `es_storage.runtime_overview`。
- 索引列表每行提供“查询最新一条”按钮，点击后调用 `es_storage.sample`。
- mapping、alias、sample 结果统一用 `JsonBlock` 展示；mapping 默认折叠，内容较长时必须支持展开/收起。
- 实时读取属于 `inspect` 行为，按钮旁显示“会访问目标 ES 集群”的提示。

### P3-104 左侧导航入口与路由

状态：Todo  
建议负责人：Frontend Agent

目标：

- 在左侧“资源管理”下新增 “ESStorage”。
- 新增路由：
  - `/es-storages`
  - `/es-storages/$tableId`

---

## 四、关联跳转增强

### P3-201 ResultTable 详情增强

状态：Todo  
建议负责人：Frontend Agent

目标：

- ResultTable 详情中的 ESStorage 区域不再只展示第一条记录或原始 JSON。
- 展示 ESStorage 类型、实体/虚拟关系、集群摘要和详情跳转。

改动点：

- 后端 `admin.result_table.detail` 的 `storages.es` 保持数组结构；前端 schema 不应再压缩成单个 `es_storage`。
- ResultTable 详情页 ESStorage tab 中展示：
  - `table_id`
  - `table_kind`
  - `origin_table_id`
  - `storage_cluster_id`
  - `index_set`
  - `need_create_index`
  - “查看 ESStorage”链接
- 如果当前 ResultTable 对应虚拟 ESStorage，需要展示“关联实体表”链接。

### P3-202 ClusterInfo 详情增强

状态：Todo  
建议负责人：Frontend Agent

目标：

- 当 `cluster_type=elasticsearch` 时，ClusterInfo 详情页增加 ESStorage 关联入口。

改动点：

- 关联统计卡片中的 `associated_storages` 可点击跳转 `/es-storages?storageClusterId=<cluster_id>`。
- 详情页新增“关联 ESStorage”区域，可按需调用 `es_storage.list` 展示该集群下前 10 条。
- 非 ES 集群仍维持二期行为。

### P3-203 全局跳转参数约定

状态：Todo  
建议负责人：Frontend Agent

约定：

| 来源             | 目标                | 参数                                                |
| ---------------- | ------------------- | --------------------------------------------------- |
| ResultTable 详情 | ESStorage 详情      | `/es-storages/$tableId`                             |
| ESStorage 详情   | ResultTable 详情    | `/result-tables/$tableId`                           |
| ESStorage 详情   | ClusterInfo 详情    | `/clusters/$storageClusterId`                       |
| ClusterInfo 详情 | ESStorage 列表      | `/es-storages?storageClusterId=<cluster_id>`        |
| ESStorage 虚拟表 | 实体 ESStorage 详情 | `/es-storages/$originTableId`                       |
| ESStorage 实体表 | 虚拟表列表          | `/es-storages?tableId=<table_id>&tableKind=virtual` |

所有跳转必须保留当前 `env` 和 `tenant` 查询参数，并复用现有 return target 机制。

---

## 五、验收标准

### ESStorage 列表

- [ ] 可按 `table_id`（同时匹配 `table_id/origin_table_id`）、`data_label`、`storage_cluster_id`、`table_kind` 检索。
- [ ] 表类型过滤明确展示实体表/虚拟表，且判定规则符合 `origin_table_id` 是否为空。
- [ ] `index_set` 仅作为详情/列表展示字段，不作为列表过滤项。
- [ ] 列表展示 ResultTable 和 ClusterInfo 摘要，且可点击跳转。
- [ ] 实体表显示关联虚拟表数量。

### ESStorage 详情

- [ ] 展示完整 ESStorage 静态配置。
- [ ] 虚拟表详情明确提示 `origin_table_id` 关联关系，并说明运行时 ES 信息按自身 `index_set` 与时间分片规则查询。
- [ ] 虚拟表可跳转实体表，实体表可查看关联虚拟表。
- [ ] 展示 StorageClusterRecord 集群迁移历史，包含当前集群、历史集群和启停/删除时间。
- [ ] 虚拟表详情中的集群迁移历史使用实体表 `origin_table_id` 对应的记录。
- [ ] 展示 ESFieldQueryAliasOption 关联记录，并能对照 mapping alias / 字段路径。
- [ ] 可跳转 ResultTable 详情和 ClusterInfo 详情。

### ES 实时信息

- [ ] 点击后可加载索引基础信息、mapping 和别名。
- [ ] 索引基础信息查询优先复用 ESStorage 现有方法，不在 Admin RPC 中重复实现索引匹配逻辑。
- [ ] 虚拟表可按自身 `index_set` 和时间分片规则正常加载 ES 信息。
- [ ] 虚拟表索引信息无法准确处理时，能够 fallback 到实体表实例或提示跳转实体表。
- [ ] 单类实时查询失败时不影响其他结果展示，并展示 warning。
- [ ] 索引列表可选择某个索引查询最新一条数据。
- [ ] 最新数据以格式化 JSON 展示。
- [ ] mapping 以 JSON 展示，默认折叠，长内容可展开。
- [ ] `inspect` 行为有明确提示。

### 关联跳转

- [ ] ResultTable 详情可跳转 ESStorage。
- [ ] ClusterInfo ES 集群详情可跳转预过滤的 ESStorage 列表。
- [ ] ESStorage 页面所有跳转保留当前环境和租户。

### 技术质量

- [ ] 前端 `pnpm format:check` 通过。
- [ ] 前端 `pnpm lint` 通过。
- [ ] 前端 `pnpm typecheck` 通过。
- [ ] 前端 `pnpm test` 通过。
- [ ] 后端新增 RPC 语法检查、ruff 和单元测试通过；如本地 Django 环境阻塞，需要记录原因。
- [ ] Playwright 冒烟覆盖 ESStorage 列表、详情、实时信息按钮基础状态。

---

## 六、风险与待确认

| 风险 / 问题                              | 影响                                      | 建议处理                                                                                    |
| ---------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------- |
| ES mapping 可能很大                      | 详情页渲染卡顿                            | mapping 先以 JSON 展示，默认折叠；必要时再增加字段摘要接口                                  |
| ES 最新数据排序字段不统一                | `dtEventTimeStamp` 不一定存在             | 默认用 `dtEventTimeStamp`，允许用户从 mapping 字段中选择                                    |
| ES client 版本差异                       | `cat.indices`、`get_mapping` 返回结构不同 | 后端封装兼容层，单元测试 mock ES5/ES6 常见结构                                              |
| 指定 index 查询安全边界                  | 可能被用来读取同集群其他索引              | 后端校验 index 必须匹配当前 ESStorage 的 `index_set`/时间分片规则                           |
| ClusterInfo 与 ESStorage 的租户关系      | 跨租户跳转可能误查                        | 所有接口强制带 `bk_tenant_id`，前端保留租户参数                                             |
| ResultTable 详情当前只取第一条 ESStorage | 会丢失多存储/虚拟表信息                   | 三期调整 schema，恢复数组展示                                                               |
| ResultTableOption / 字段别名影响查询解释 | 只看 ESStorage 不足以解释查询行为         | 详情页展示相关 ResultTableOption 和 ESFieldQueryAliasOption 摘要，并在 mapping 区域对照展示 |
| 虚拟表集群迁移历史不在自身 table_id 下   | 直接查虚拟表 table_id 会漏掉迁移记录      | 按现有 `compose_table_id_storage_cluster_records` 语义回到 `origin_table_id` 查询           |
| Admin RPC 重复实现索引规则               | 未来 ESStorage 索引逻辑调整时容易不一致   | 索引、统计、最新数据优先调用 ESStorage 现有方法；缺口只做薄封装                             |

待确认问题：

1. 最新一条数据的默认排序字段是否固定为 `dtEventTimeStamp`，是否需要前端提供字段选择器？

---

## 七、文档维护

第三期实施过程中需同步更新：

- `docs/backend-admin-rpc.md`：新增 `admin.es_storage.*` RPC 契约。
- `docs/resources/result-table.md`：更新 ESStorage 从附属信息升级为可跳转资源。
- `docs/resources/es-storage.md`：新增 ESStorage 资源设计文档。
- `docs/kernel-rpc.md`：新增 operation 映射和 `inspect` 安全级别说明。
- `docs/agent-friendly.md`：新增 ESStorage 排查调用示例。
- 本 `docs/phase-3-plan.md`：持续更新任务状态、阻塞项和验收结果。
