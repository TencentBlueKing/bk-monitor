### 功能描述

后端应用根据日志平台选择的 metadata Kafka 集群 ID，读取连接及已同步的 BKBase KafkaChannel 引用。凭证只用于后端 Kafka 客户端，不传给浏览器或 Databus apply 请求。

### 请求参数

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| bk_tenant_id | string | 沿用网关和 metadata 的租户上下文 |
| cluster_id | int | metadata 已登记并同步 BKBase 的 Kafka 集群 ID |

GET `/app/metadata/resolve_clustering_kafka/`；沿用应用认证和资源调用权限。

### 返回 data 示例

```json
{
  "cluster_id": 12345,
  "kafka_resource": {"kind": "KafkaChannel", "namespace": "bklog", "name": "log-kafka"},
  "connection": {"bootstrap.servers": "kafka.example:9092", "security.protocol": "PLAINTEXT"}
}
```

多租户时 `kafka_resource` 还包含 `tenant`；单租户沿用 BKBase 默认 tenant。SASL 连接还返回 `sasl.mechanism`、`sasl.username`、`sasl.password`，使用 metadata 已成功同步的 KafkaChannel 连接快照，不使用全局认证默认值。当前 KafkaChannel 不支持 TLS，接口明确报错，不降级协议。

调用不会自动注册连接、创建 Topic 或变更集群。不存在、租户不符、尚未同步的集群均返回参数错误。日志平台给 Runtime 传数字 ID；给 BKBase 传返回的 KafkaChannel 引用。
