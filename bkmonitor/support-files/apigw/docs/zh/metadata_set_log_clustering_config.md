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

环境资源引用包含 kind、namespace、name，可选 tenant；所有引用必须属于请求租户。默认下发 `clustering.result.mode=update_original` 回写原表。

Pattern 资源由 metadata 自动注册，调用方不再提供 `pattern_store`。每个租户、索引集一张实体 ResultTable，复用已有 ResultTableConfig、ESStorageBindingConfig、ESStorage 与 StorageClusterRecord。不同距离档位共用该表；关闭、重开和模型更新不重新建表。Pattern 不新增 DataID 或 Databus，写入仅来自聚类算子。

Pattern 资源名使用 `bklog_<索引集ID>_pattern`，不使用哈希；租户通过资源 tenant 隔离。metadata 结果表 ID 为 `<存储业务ID>_bklog.<索引集ID>_pattern`，其默认 ES 索引名即 BKBase 完整结果表 ID `<ResultTable.spec.bizId>_bklog_<索引集ID>_pattern`，建表、写入与查询名称一致。

默认回写时，metadata 为源日志表登记 `__log_signature`（ES keyword）和 `__log_cluster_publish_revision`（ES long），在首次接入及重新下发时准备索引和写别名，后续轮转继续包含这两个字段。关闭、重开不删除字段。`signature` 查询别名和查询路由由调用方通过现有日志路由接口注册，metadata 不登记业务别名。链路未接入聚类时，普通日志下发不处理聚类资源。

Pattern 默认使用源日志的 ES 集群，由 metadata 管理按日索引和日期写别名。字段为 index_set_id、distance_threshold、signature、pattern、pattern_hash、task_id（string），generation、publish_revision、dtEventTimeStamp（V4 long）；前三个字段支持精确检索。`dtEventTimeStamp` 单位为毫秒，ES mapping 为 `date`、`format=epoch_millis`。首次注册和旧表重新下发均补齐字段与持久化选项，供后续建索引和轮转使用。时间值由 BKBase 写入，metadata 不伪造时间或回填历史文档；同模板再次命中的时间刷新语义仍需与 BKBase 联调确认。

已接入聚类的源日志切存储时，Pattern 复用原实体表与固定物理名称，在目标集群登记或复用对应的 Binding，并更新 Sink 引用。旧存储分段保留，不复制历史数据。origin_table_id 指向该实体表的已注册路由同步切到当前集群并重新发布，UnifyQuery 按 StorageClusterRecord 覆盖历史集群；路由写入沿用日志路由的容错，失败会记录日志，重新下发即可补发。Pattern 按日轮转并沿用源日志的保留设置，由 metadata 负责过期清理；跨日重复映射由应用查询侧去重。

#### 独立聚类结果表

`append` 时 metadata 自动注册 `bklog_<索引集ID>_clustered`，完整 BKBase 表 ID 为 `<存储业务ID>_bklog_<索引集ID>_clustered`。保留原日志字段，并追加 `__log_signature`（string）和 `__log_cluster_publish_revision`（long）。不带前缀的同名业务字段仍按原日志字段保存。结果表声明采用 BKBase 的 field_name、field_type、field_alias、is_dimension、field_index 字段格式。

独立结果表复用源日志 ES 集群、字段分词配置、轮转和保留设置，由 metadata 现有 ESStorage 能力准备索引与日期写别名。写别名前缀为 `write_%Y%m%d_<完整BKBase表ID>`，查询使用对应的日期读别名；Pattern 表则独立按日轮转。原表继续保存原文，聚类完成后 BKBase 向独立表写入原文及聚类字段。`_clustered` 指向独立结果表，`_pattern` 仍单独指向 Pattern 表。

源日志切存储时，两张表分别更新目标 Binding，并保留各自历史路由；索引准备失败不下发新引用，同一操作可以重试。该模式不新增数据源或 Databus。

#### binding

`binding` 为 BKBase `LogClusteringSink.spec.clustering.binding`，由调用方按 BKBase 协议组装。metadata 只校验必须提供 `index_id`（用于 Pattern 与独立结果表命名），其余字段原样保存和下发；过滤规则、距离档位、版本号和消息大小由调用方与 BKBase 校验。

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
    "recovery_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "context_es"}
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
