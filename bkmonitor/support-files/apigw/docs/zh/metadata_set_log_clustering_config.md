### 功能描述

保存日志 V4 链路的聚类绑定，并下发 LogClusteringSink。

Databus 尚未引用聚类 Sink 时按日志链路完整下发（Databus.spec.sinks 改为引用聚类 Sink，原存储绑定作为 raw_sink）；
已引用时下发 Pattern、可选独立结果表的 ResultTable／ES Binding 和聚类 Sink，默认回写时同步源 ResultTable 字段声明，不重复下发 Databus，raw_sink 取本链路当前唯一的 ES 存储绑定，无法唯一确定时仍按日志链路完整下发。
运行集群与远端 Databus.spec.preferCluster 不一致时也完整下发，使其与 clustering.runtime_cluster 一致。
接口不等待 BKBase 排空，也不代表 Runtime 已采用新配置。

同一链路的本地绑定在行锁内落库；同一索引集的变更由调用方串行发起。
下发失败时，调用方重试同一请求即可；下发范围按远端 Databus 的实际引用重新判断。

### 请求参数

| 字段                | 类型     | 必选 | 描述                                                                       |
|-------------------|--------|----|--------------------------------------------------------------------------|
| bk_tenant_id      | string | 否  | 租户ID，缺省时取请求租户                                                            |
| table_id          | string | 是  | 日志采集项对应的监控结果表ID                                                          |
| binding           | dict   | 是  | 聚类绑定配置                                                                   |
| kafka_resource    | dict   | 是  | 已登记的 Kafka 资源引用，kind 为 Kafka                                             |
| runtime_cluster | dict | 是 | 已登记的 DatabusCluster 引用，同时用于 Databus.spec.preferCluster |
| recovery_resource | dict | 是 | 已登记的 ElasticSearch 引用，用于结果关联上下文存储 |
| result_mode | string | 否 | update_original（默认）或 append；省略时沿用已登记模式，是否允许切换由调用方决定 |
| pattern_store | dict | 是 | Pattern 表：`table_id`（metadata 结果表 ID）、`cluster_id`（ES 集群 ID） |
| result_store | dict | 否 | 独立聚类结果表，字段同 `pattern_store`；`append` 时必填，省略时沿用已登记值 |

环境资源引用包含 kind、namespace、name，可选 tenant；所有引用必须属于请求租户。默认下发 `clustering.result.mode=update_original` 回写原表。

Pattern 表与独立结果表的表名和 ES 集群由调用方决定，metadata 负责登记和生命周期，与原日志表的分工一致。`table_id`、`cluster_id` 只在 metadata 内使用，不下发给 BKBase。

metadata 按 `pattern_store`（及 `append` 时的 `result_store`）登记实体 ResultTable，复用已有 ResultTableConfig、ESStorageBindingConfig、ESStorage 与 StorageClusterRecord。物理索引名由 `table_id` 推导（`.` 替换为 `_`），通过 Binding 注解 `physical_table_name` 指定给 BKBase；不同集群使用同一物理名。BKBase 资源名为 `bklog_<binding.index_id>_pattern` 或 `bklog_<binding.index_id>_clustered`，租户通过资源 tenant 隔离。两张表均不新增 DataID 或 Databus，写入仅来自聚类算子。

Pattern 字段为 index_set_id、distance_threshold、signature、pattern、pattern_hash、task_id（string），generation、publish_revision、dtEventTimeStamp（V4 long）；前三个字段支持精确检索。`dtEventTimeStamp` 单位为毫秒，ES mapping 为 `date`、`format=epoch_millis`。Pattern 固定按日轮转；保留天数、索引设置沿用源日志 ESStorage，由 metadata 负责建索引、日期写别名和过期清理。跨日重复映射由应用查询侧去重。

独立结果表保留原日志字段，并追加 `__log_signature`（string）和 `__log_cluster_publish_revision`（long）；字段分词配置、轮转和保留设置沿用源日志。默认回写时，metadata 为源日志表登记这两个字段，在首次接入及重新下发时准备索引和写别名。关闭、重开不删除字段。

调用方声明的 `cluster_id` 与已登记存储不同时，metadata 复用同一实体表和物理名，在目标集群登记或复用 Binding，记录新的 StorageClusterRecord，并更新 Sink 引用；旧分段保留，不复制历史数据。metadata 不跟随源日志表自动切换，也不修改或发布查询路由。查询路由和 `signature` 别名由调用方通过现有日志路由接口注册，`origin_table_id` 指向实体表即可复用其历史分段。

#### binding

`binding` 为 BKBase `LogClusteringSink.spec.clustering.binding`，由调用方按 BKBase 协议组装。metadata 只校验必须提供 `index_id`（用于 BKBase 资源命名），其余字段原样保存和下发；过滤规则、距离档位、版本号和消息大小由调用方与 BKBase 校验。

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "binding": {
        "task_id": "0f1d2c3b-4a59-4e6f-8a7b-9c0d1e2f3a4b",
        "index_id": "42",
        "generation": 1,
        "config_revision": 1,
        "kafka": {
            "cluster_ref": "quix-e2e",
            "input_topic": "lc-0f1d2c3b-in",
            "output_topic": "lc-0f1d2c3b-out",
            "consumer_group": "lc-0f1d2c3b-worker",
            "result_group": "lc-0f1d2c3b-result",
            "partitions": 2,
            "retention_ms": 604800000,
            "recovery_window_ms": 86400000,
            "source_namespace": "bklog",
            "mapping_revision": "log-v1"
        },
        "log_filter": [{"key": "level", "method": "eq", "value": ["ERROR"], "condition": ""}],
        "input_mapping": {"log": "log", "timestamp": "dtEventTimeStamp"},
        "distance_threshold": "0.5",
        "state_index": "log-clustering-context"
    },
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "registered_clustering_kafka"},
    "runtime_cluster": {"kind": "DatabusCluster", "namespace": "bklog", "name": "quix_runtime"},
    "recovery_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "context_es"},
    "pattern_store": {"table_id": "2_bklog.42_pattern", "cluster_id": 3}
}
```

### 响应参数

| 字段             | 类型     | 描述                                         |
|----------------|--------|--------------------------------------------|
| attached       | bool   | Databus 是否引用聚类 Sink                         |
| applied_scope  | string | 本次下发范围：datalink（完整链路）或 sink_only（结果表资源与聚类 Sink，不含 Databus） |
| sink           | dict   | 聚类 Sink 身份：tenant、namespace、name            |
| databus        | dict   | Databus 身份：tenant、namespace、name            |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "attached": true,
        "applied_scope": "datalink",
        "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_50010_a1b2c3d4e5f6"},
        "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"}
    }
}
```
