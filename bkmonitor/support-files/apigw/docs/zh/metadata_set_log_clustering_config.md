### 功能描述

保存日志 V4 链路的聚类绑定，并下发 LogClusteringSink。

Databus 尚未引用聚类 Sink 时按日志链路完整下发（Databus.spec.sinks 改为引用聚类 Sink，原存储绑定作为 raw_sink）；
已引用时下发 Pattern ResultTable／ES Binding 和聚类 Sink，不重复下发 Databus，raw_sink 取本链路当前唯一的 ES 存储绑定，无法唯一确定时仍按日志链路完整下发。
运行集群与远端 Databus.spec.preferCluster 不一致时也完整下发，使其与 clustering.runtime_cluster 一致。
接口不等待 BKBase 排空，也不代表 Runtime 已采用新配置。

同一链路的聚类配置变更从落库到远端下发全程互斥；有其他变更进行中时直接返回错误。
变更进行中或下发失败时，调用方稍后重试同一请求即可；下发范围按远端 Databus 的实际引用重新判断。

### 请求参数

| 字段                | 类型     | 必选 | 描述                                                                       |
|-------------------|--------|----|--------------------------------------------------------------------------|
| bk_tenant_id      | string | 否  | 租户ID，缺省时取请求租户                                                            |
| table_id          | string | 是  | 日志采集项对应的监控结果表ID                                                          |
| binding           | dict   | 是  | 聚类绑定配置                                                                   |
| kafka_resource    | dict   | 是  | 已登记的 Kafka 资源引用，kind 为 Kafka                                             |
| runtime_cluster | dict | 是 | 已登记的 DatabusCluster 引用，同时用于 Databus.spec.preferCluster |
| recovery_resource | dict | 是 | 已登记的 ElasticSearch 引用，用于结果关联上下文存储 |

环境资源引用包含 kind、namespace、name，可选 tenant；所有引用必须属于请求租户。首版下发 `clustering.result.mode=update_original`，默认回写原表，不新增独立结果表开关。资源字段使用 `raw_sink`、`kafka_resource`、`runtime_cluster`、`recovery_resource`、`pattern_store`。

Pattern 资源由 metadata 自动注册，调用方不再提供 `pattern_store`。每个租户、索引集一张实体 ResultTable，复用已有 ResultTableConfig、ESStorageBindingConfig、ESStorage 与 StorageClusterRecord。不同距离档位共用该表；关闭、重开和模型更新不重新建表。Pattern 不新增 DataID 或 Databus，写入仅来自聚类算子。

Pattern 资源名使用 `bklog_pattern_<索引集ID>`，不使用哈希；租户通过资源 tenant 隔离。建表、写入与查询统一使用 BKBase 完整结果表 ID，即 `<ResultTable.spec.bizId>_bklog_pattern_<索引集ID>`，业务前缀沿用现有租户与存储业务映射。

Pattern 默认使用源日志的 ES 集群。采用固定物理索引，字段为 index_set_id、distance_threshold、signature、pattern、pattern_hash、task_id（string），generation、publish_revision（long）；前三个字段支持精确检索。时间字段的实际写入与最近命中刷新仍需 BKBase 联调确认，不由 metadata 伪造。

源日志切存储时，Pattern 复用原实体表与固定物理名称，在目标集群登记或复用对应 Binding，并更新 Sink 引用。旧存储分段保留，不复制历史数据。`_pattern` 通过 origin_table_id 关联 Pattern 实体表，UnifyQuery 按 StorageClusterRecord 覆盖历史集群。路由发布失败由同一操作重试补发。Pattern 的保留清理策略不沿用普通日志按天删索引，本接口不删除旧 Pattern 索引。

日志平台复用 `MINI_CLUSTERING_CONFIG.feature_config.bkbase_quix`，仅需配置 BKFara profile、kafka_resource、runtime_cluster、recovery_resource、state_index 及可选消息上限。state_index 首次开启保存，重试及重开沿用；恢复上下文存储与 Pattern 存储独立。

#### binding

| 字段                 | 类型     | 必选 | 描述                                               |
|--------------------|--------|----|--------------------------------------------------|
| task_id            | string | 是  | BKFara 任务ID                                      |
| index_id           | string | 是  | 日志平台索引集ID                                        |
| generation         | int    | 是  | BKFara 任务 current_generation                     |
| config_revision    | int    | 是  | BKFara 聚类配置 input_revision                       |
| kafka              | dict   | 是  | BKFara 聚类配置返回的 Kafka 绑定                          |
| log_filter         | list   | 否  | 聚类过滤规则，method 取值见下表，首条 condition 为空 |
| input_mapping      | dict   | 是  | 模型入参映射，log 为正文字段，timestamp 为毫秒时间字段               |
| distance_threshold | string | 否  | 距离档位，默认字符串 "0.5"，取 0.1/0.3/0.5/0.7/0.9 |
| state_index        | string | 是  | 部署方提供的结果关联上下文索引名                                          |
| max_message_bytes  | int    | 否  | 单条 Kafka 候选消息的序列化大小上限（字节），默认 1048576（1 MiB），范围 1～16777216（16 MiB） |

#### 聚类过滤方法

| method | 含义 |
|---|---|
| eq | 等于 |
| neq | 不等于 |
| include | 包含 |
| exclude | 不包含 |
| starts_with | 以给定值开头 |
| not_starts_with | 不以给定值开头 |
| ends_with | 以给定值结尾 |
| not_ends_with | 不以给定值结尾 |

metadata 校验方法枚举并原样保存和下发规则，不执行日志匹配。匹配值中的空字符串、首尾空白和特殊字符不被裁剪或改写；未知方法拒绝下发。

#### 版本来源与消息大小

generation 取 BKFara 任务查询返回的 current_generation；config_revision 取 BKFara 聚类配置返回的 input_revision。
调用方原样提供，metadata 不生成或递增这两个版本。它们不是 metadata 本地配置修订号，修改过滤规则时也不自行加一。

max_message_bytes 用于候选 Kafka 消息的体积预算，不是原文日志长度配置。metadata 只校验并透传该值，
不根据它裁剪或丢弃日志。实际超限处理及对原文入库的影响由 BKBase Runtime 负责，需要在联调中验证。

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
| applied_scope  | string | 本次下发范围：datalink（完整链路）或 sink_only（Pattern 资源与聚类 Sink，不含 Databus） |
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
