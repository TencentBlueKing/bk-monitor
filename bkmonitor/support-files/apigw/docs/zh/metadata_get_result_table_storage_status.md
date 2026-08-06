### 功能描述

批量查询结果表关联的 Elasticsearch（ES）和 Doris 存储配置、历史存储分段、集群连通性及运行时元信息，单次最多查询 50 个结果表。

- 历史分段包含已停用、已删除的 `StorageClusterRecord` 记录；单个结果表内同一集群只探测一次。不同结果表引用同一集群时，表相关运行时信息仍分别查询。
- 虚拟结果表使用实体表的历史分段执行查询，同时保留请求结果表的信息。
- ES 返回索引基础信息、文档数和存储大小；受管索引额外返回日期别名关系。不透传原始响应，不查询 mapping 或样例数据。
- Doris 返回经过固定字段投影的 DorisBinding、物理库表、字段及分区信息。
- 单个结果表、集群连通性检查或运行时查询失败时，接口仍返回其他结果表和集群的成功结果。
- 集群探测使用进程内共享的两级调度器：总并发最多 20，同一租户下相同 `cluster_id` 的并发最多 5；待执行队列有固定上限。
- 响应中的存储配置和集群信息已脱敏，不返回用户名、密码或证书。

### 请求方法与路径

```text
GET /app/metadata/get_result_table_storage_status/
```

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| table_ids | array[string] | 是 | 结果表 ID 列表，长度 1–50，不允许重复 |
| timeout | int | 否 | 单次集群连通性检查、ES API 或 Doris 连接/读取的超时时间，单位为秒；默认 15，取值范围 1–30 |
| total_timeout | int | 否 | 整个批量请求的总等待时间，单位为秒；默认 60，取值范围 1–300。到期后取消未启动任务并停止等待运行中任务 |

`bk_tenant_id` 由 APIGW 根据调用应用所属租户注入，调用方无需显式传递。

### 请求参数示例

```json
{
  "table_ids": [
    "2_bkmonitor_time_series_50010.base",
    "2_bklog.demo"
  ],
  "timeout": 10,
  "total_timeout": 60
}
```

### 响应参数

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求参数是否合法；单个结果表查询失败不会使整个批次为 `false` |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | 存储状态数据 |
| request_id | string | 请求 ID |

#### data 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| items | array | 按 `table_ids` 输入顺序返回的结果表查询项 |

#### items 元素说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| table_id | string | 当前查询项对应的结果表 ID |
| data | object/null | 查询成功时为原单表存储状态；失败时为 `null` |
| error | object/null | 单表失败信息；成功时为 `null` |

#### items[].data 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result_table | object | 请求结果表的基础信息，包括 `table_id`、`bk_tenant_id`、`bk_biz_id`、`default_storage`、启用/删除状态等 |
| history_table_id | string/null | 历史分段实际所属结果表；虚拟结果表为实体表 `origin_table_id`，其他情况等于请求的 `table_id`。ES/Doris 指向不同实体表时为 `null`，并停止运行时探测 |
| storage_configs | object | 当前 ES/Doris 安全配置，键为 `elasticsearch`、`doris`；未配置的类型值为 `null` |
| segments | array | 完整历史存储分段，按启用时间、创建时间、记录 ID 排序 |
| cluster_results | object | 按集群去重后的连通性和运行时信息；key 为字符串形式的 `cluster_id`，顺序与历史集群首次出现顺序一致 |
| warnings | array | 顶层告警，例如配置存在但历史分段缺失、虚拟表使用实体表配置 |
| errors | array | 顶层错误，例如没有 ES/Doris 配置或配置不一致 |

#### segments 元素说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| id | int | `StorageClusterRecord` 记录 ID |
| table_id | string | 历史分段所属结果表 ID |
| cluster_id | int | 存储集群 ID |
| storage_type | string | 集群类型：`elasticsearch`、`doris`；集群记录缺失时为 `unknown` |
| is_current | bool | 是否为当前生效分段 |
| is_deleted | bool | 分段是否已删除 |
| creator | string | 创建者 |
| create_time | string/null | 创建时间，ISO 8601 格式 |
| enable_time | string/null | 启用时间，ISO 8601 格式 |
| disable_time | string/null | 停用时间，ISO 8601 格式 |
| delete_time | string/null | 删除时间，ISO 8601 格式 |

#### cluster_results value 说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| storage_type | string | `elasticsearch`、`doris` 或 `unknown` |
| is_current | bool | `is_current_segment` 或 `is_configured_current` 任一为 true；用于兼容判断当前集群 |
| is_current_segment | bool | 是否存在 `is_current=true` 的关联历史分段 |
| is_configured_current | bool | 当前 ESStorage/DorisStorage 是否指向该集群；配置缺少历史分段时仍可为 true |
| cluster | object/null | 脱敏集群信息，包括 ID、名称、类型、域名、端口、版本及协议 |
| connectivity | object/null | 轻量连通性检查结果，仅包含 `is_connected` 和 `error`；未执行或集群配置缺失时为 `null` |
| runtime | object/null | ES 或 Doris 运行时信息 |
| runtime_skipped | bool | 是否因连通性检查失败、配置缺失或不支持的存储类型而跳过运行时查询 |
| config_source | string | 运行时配置来源，当前固定为 `current_storage_config` |
| warnings | array | 当前集群的告警列表 |
| errors | array | 当前集群的错误列表 |

`warnings`、`errors` 元素均包含 `code`、`message`，必要时包含 `details`。历史记录没有保存当时的索引规则或 Doris 物理表快照，因此历史集群运行时查询使用当前保留的 Storage 配置，并返回 `HISTORICAL_CONFIG_NOT_SNAPSHOTTED` 告警。

#### ES runtime 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| table_id | string | Storage 配置所属结果表 ID |
| origin_table_id | string/null | 虚拟结果表关联的实体表 ID |
| table_kind | string | `physical` 或 `virtual` |
| index_set | string | ES index set |
| need_create_index | bool | 是否由 Metadata 管理索引生命周期 |
| index_query | object/null | 本次索引查询规则，包含 `mode`、`source`、`expression` 等字段 |
| indices | object/null | 索引关键字段汇总及 `items`；查询失败时为 `null` |
| aliases | object/null | 别名数量、索引关联数及可枚举的 `items`；查询失败时为 `null` |

索引查询规则：

- `need_create_index=true`：`index_query.mode=managed`，使用 Metadata 管理的日期分片规则，优先查询 v2 索引，没有 v2 索引时回退 v1；`candidates` 给出候选表达式，`index_version` 给出实际命中的版本。
- `need_create_index=false`：`index_query.mode=external`，将 `index_set` 原样作为 ES 索引查询字符串；不使用 v1/v2 日期规则，不执行当前索引或轮转检查，也不查询别名。此时 `aliases.queried=false`。

##### indices 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| count | int | 命中索引数量 |
| total_docs | int | 所有命中索引的文档数合计 |
| total_store_size_bytes | int | 所有命中索引的存储大小合计，单位 byte |
| items | array | 索引列表 |

`items` 仅返回稳定的关键字段：`index`、`uuid`、`health`、`status`、`docs_count`、`docs_deleted`、`store_size_bytes`、`primary_store_size_bytes`、`primary_shards`、`replica_shards`、`replica_factor`、`shards`、`creation_date_ms`。字段在当前 ES 版本不可用时省略，不透传原始 stats/settings/cat 响应。

##### aliases 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| queried | bool | 是否实际执行了 alias API 查询；仅 `need_create_index=true` 时为 `true` |
| count | int | 唯一日期别名数量 |
| relation_count | int | 别名与索引的关联数量 |
| items | array | 日期别名列表，每项包含 `alias`、`alias_type`、`datetime`、关联的 `indices` 及可选写索引 `write_index` |

受管索引仅枚举符合 Metadata 读/写日期别名规则的实际别名；其他别名会被忽略，不返回 alias filter、routing 等任意配置内容。

#### Doris runtime 字段说明

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| request_table_id | string | 本次请求的 Storage 表 ID |
| metadata_context | object | 元信息来源上下文，说明实际连接集群、是否历史集群以及 Binding 快照情况 |
| binding | object | DorisBinding 摘要：`name`、`namespace`、`phase`、`message`、物理表名及其来源 |
| table | object/null | 物理表摘要 |
| columns | array | 按字段顺序返回的字段摘要 |
| partitions | array | 按分区顺序返回的分区摘要 |

`table` 仅包含：`schema`、`name`、`type`、`engine`、`rows`、`data_length_bytes`、`index_length_bytes`、`create_time`、`update_time`、`collation`、`comment`。

`columns` 每项仅包含：`name`、`position`、`is_nullable`、`data_type`、`column_type`、`key`、`default`、`extra`、`character_set`、`collation`、`comment`。

`partitions` 每项仅包含：`name`、`position`、`method`、`expression`、`description`、`rows`、`data_length_bytes`、`index_length_bytes`、`create_time`、`update_time`。对应 Doris 版本不提供的字段会省略，不透传 `information_schema` 原始整行数据。

历史 Doris 集群采用 best-effort 语义：`metadata_context.connection_cluster_id` 是实际连接的历史集群，但 `binding_source` 固定为 `current_doris_binding`。历史记录没有保存当时的 DorisBinding 或物理库表名；因此历史查询可能为空或指向与当时不同的物理表，并返回 `HISTORICAL_DORIS_BINDING_NOT_SNAPSHOTTED` 告警。

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "request_id": "408233306947415bb1772a86b9536867",
  "data": {
    "items": [
      {
        "table_id": "2_bkmonitor_time_series_50010.base",
        "data": {
    "result_table": {
      "table_id": "2_bkmonitor_time_series_50010.base",
      "bk_tenant_id": "system",
      "table_name_zh": "自定义指标",
      "bk_biz_id": 2,
      "data_label": "custom_metric",
      "default_storage": "elasticsearch",
      "is_enable": true,
      "is_deleted": false
    },
    "history_table_id": "2_bkmonitor_time_series_50010.base",
    "storage_configs": {
      "elasticsearch": {
        "table_id": "2_bkmonitor_time_series_50010.base",
        "origin_table_id": null,
        "bk_tenant_id": "system",
        "storage_cluster_id": 1,
        "retention": 30,
        "index_set": "2_bkmonitor_time_series_50010",
        "effective_table_id": "2_bkmonitor_time_series_50010.base"
      },
      "doris": null
    },
    "segments": [
      {
        "id": 101,
        "table_id": "2_bkmonitor_time_series_50010.base",
        "cluster_id": 1,
        "storage_type": "elasticsearch",
        "is_current": true,
        "is_deleted": false,
        "creator": "admin",
        "create_time": "2026-08-03T10:00:00+08:00",
        "enable_time": "2026-08-03T10:00:00+08:00",
        "disable_time": null,
        "delete_time": null
      }
    ],
    "cluster_results": {
      "1": {
        "storage_type": "elasticsearch",
        "is_current": true,
        "is_current_segment": true,
        "is_configured_current": true,
        "cluster": {
          "cluster_id": 1,
          "cluster_name": "default_es_storage",
          "display_name": "默认 ES",
          "cluster_type": "elasticsearch",
          "domain_name": "es.service.consul",
          "port": 9200,
          "version": "7.10.2",
          "schema": "http"
        },
        "connectivity": {
          "is_connected": true,
          "error": null
        },
        "runtime": {
          "table_id": "2_bkmonitor_time_series_50010.base",
          "origin_table_id": null,
          "table_kind": "physical",
          "index_set": "2_bkmonitor_time_series_50010",
          "need_create_index": true,
          "index_query": {
            "mode": "managed",
            "need_create_index": true,
            "source": "generated_table_pattern",
            "expression": "v2_2_bkmonitor_time_series_50010_base_*",
            "index_version": "v2",
            "candidates": [
              "v2_2_bkmonitor_time_series_50010_base_*",
              "2_bkmonitor_time_series_50010_base_*"
            ]
          },
          "indices": {
            "count": 1,
            "total_docs": 1280,
            "total_store_size_bytes": 1048576,
            "items": [
              {
                "index": "v2_2_bkmonitor_time_series_50010_base_20260803_0",
                "health": "green",
                "status": "open",
                "docs_count": 1280,
                "store_size_bytes": 1048576,
                "primary_shards": 1,
                "replica_shards": 1,
                "replica_factor": 1,
                "shards": 2
              }
            ]
          },
          "aliases": {
            "queried": true,
            "count": 1,
            "relation_count": 1,
            "items": [
              {
                "alias": "2_bkmonitor_time_series_50010_base_20260803_read",
                "alias_type": "read",
                "datetime": "20260803",
                "indices": ["v2_2_bkmonitor_time_series_50010_base_20260803_0"],
                "write_index": null
              }
            ]
          }
        },
        "runtime_skipped": false,
        "config_source": "current_storage_config",
        "warnings": [],
        "errors": []
      }
    },
    "warnings": [],
    "errors": []
        },
        "error": null
      }
    ]
  }
}
```

### 注意事项

- `table_ids` 上限为 50，不兼容旧参数 `table_id`；批量结果严格保持输入顺序并隔离单表失败。
- 同一进程内所有请求共享最多 20 个集群探测 worker；相同 `(bk_tenant_id, cluster_id)` 最多并发 5 个探测任务。集群探测待执行队列最多保留 100 个任务。
- 结果表查询也使用进程内共享线程池，不再为每个请求单独创建线程池；最多运行 20 个结果表任务，最多排队 40 个。
- `timeout` 作用于每次下游 I/O；`total_timeout` 是整个批量请求的总等待 deadline。deadline 到期后取消尚未启动的结果表及集群任务，已经进入下游 I/O 的任务不能被线程安全地强制中断，但接口不再继续等待。
- 单个受管 ES 集群正常路径会依次执行 ping、索引 stats、cat、settings、aliases；v2 没有命中时 stats 还会回退查询 v1，理论上最多约为 `6 × timeout`。外部 ES 不查询 aliases，正常路径约为 `4 × timeout`。
- 单个 Doris 集群会先用 `SELECT 1` 检查连通性，再建立运行时查询连接并执行 3 条 `information_schema` 元信息 SQL；连接和每次读取分别受 `timeout` 约束。因此调用方/APIGW 超时时间应高于单次 I/O timeout。
- `result=true` 不代表每个结果表或集群探测均成功，请同时检查 `items[].error` 及 `items[].data.cluster_results` 中的 `warnings`、`errors`。
- 连通性检查失败时不会继续查询该集群的运行时信息，此时 `runtime_skipped=true`。
- 当前框架没有可安全中断阻塞中下游 I/O 的请求取消信号；客户端提前断开本身不会触发取消，批次 deadline 会负责取消未启动任务。已经进入下游 I/O 的任务仍会完成或等待自身 I/O timeout。
