### 功能描述

保存日志 V4 链路的聚类绑定，并下发 LogClusteringSink。

Databus 尚未引用聚类 Sink 时按日志链路完整下发（Databus.spec.sinks 改为引用聚类 Sink，原存储绑定作为 rawSink）；
已引用时只下发聚类 Sink。接口不等待 BKBase 排空，也不代表 Runtime 已采用新配置。

### 请求参数

| 字段                | 类型     | 必选 | 描述                                                                       |
|-------------------|--------|----|--------------------------------------------------------------------------|
| bk_tenant_id      | string | 否  | 租户ID，缺省时取请求租户                                                            |
| table_id          | string | 是  | 日志采集项对应的监控结果表ID                                                          |
| operation_id      | string | 是  | 操作ID；同一操作重试时保持不变，同一 operation_id 携带不同内容会被拒绝                               |
| expected_revision | int    | 是  | 期望的当前配置版本，首次接入为 0；与当前版本不一致时拒绝                                            |
| binding           | dict   | 是  | 聚类绑定配置                                                                   |
| kafka_resource    | dict   | 是  | 已登记的 Kafka 资源引用，kind 为 Kafka                                             |
| pattern_resource  | dict   | 是  | 已登记的 Pattern ES 资源引用，kind 为 ElasticSearch                                 |

#### binding

| 字段                 | 类型     | 必选 | 描述                                               |
|--------------------|--------|----|--------------------------------------------------|
| task_id            | string | 是  | BKFara 任务ID                                      |
| index_id           | string | 是  | 日志平台索引集ID                                        |
| generation         | int    | 是  | BKFara 任务 current_generation                     |
| config_revision    | int    | 是  | BKFara 聚类配置 input_revision                       |
| kafka              | dict   | 是  | BKFara 聚类配置返回的 Kafka 绑定                          |
| log_filter         | list   | 否  | 聚类过滤规则，method 取 eq/neq/include/exclude，首条 condition 为空 |
| input_mapping      | dict   | 是  | 模型入参映射，log 为正文字段，timestamp 为毫秒时间字段               |
| distance_threshold | string | 是  | 距离档位，取 0.1/0.3/0.5/0.7/0.9                      |
| pattern_index      | string | 是  | Pattern 索引名                                      |
| state_index        | string | 是  | 恢复状态索引名                                          |
| max_message_bytes  | int    | 否  | 候选消息上限，默认 1048576，最大 16 MiB                     |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "operation_id": "enable-24466-0001",
    "expected_revision": 0,
    "binding": {
        "task_id": "0f1d2c3b-4a59-4e6f-8a7b-9c0d1e2f3a4b",
        "index_id": "24466",
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
        "pattern_index": "log-clustering-24466-pattern",
        "state_index": "log-clustering-24466-state"
    },
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "registered_clustering_kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "registered_pattern_es"}
}
```

### 响应参数

| 字段             | 类型     | 描述                                         |
|----------------|--------|--------------------------------------------|
| revision       | int    | 当前配置版本                                     |
| attached       | bool   | Databus 是否引用聚类 Sink                         |
| applied_scope  | string | 本次下发范围：datalink（完整链路）或 sink_only（仅聚类 Sink） |
| sink           | dict   | 聚类 Sink 身份：tenant、namespace、name            |
| databus        | dict   | Databus 身份：tenant、namespace、name            |
| raw_sink       | dict   | 原日志存储绑定引用                                  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "revision": 1,
        "attached": true,
        "applied_scope": "datalink",
        "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_50010_a1b2c3d4e5f6"},
        "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"},
        "raw_sink": {"kind": "ElasticSearchBinding", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"}
    }
}
```
