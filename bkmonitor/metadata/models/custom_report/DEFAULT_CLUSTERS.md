# 场景默认集群

动态配置 `SCENE_DEFAULT_STORAGE_CLUSTERS` 按“场景 → 存储类型 → ClusterInfo.cluster_id”配置，默认值为 `{}`。

```json
{
  "custom_event": {"kafka": 101, "elasticsearch": 201},
  "bcs_event": {"kafka": 102, "elasticsearch": 202}
}
```

上述 ID 为示例。存储类型 key 直接使用标准 ClusterType（即 `ClusterInfo.TYPE_*` 的值），不兼容 `es` / `vm` 等别名，也不额外校验 key；写错 key 不会匹配，沿用默认逻辑。

场景集群按当前租户、集群类型和 ID 查询。未配置、值为 `null`、集群不存在或属于其他租户时，均沿用后续默认逻辑，最终使用当前租户的默认集群。

## 已接入的创建流程

- 标准自定义事件（`bk_standard_v2_event`）的 Kafka：显式 `mq_cluster` → `custom_event.kafka` → 当前租户默认 Kafka。
- EventGroup 的 ES：显式 `default_storage_config.cluster_id` → `custom_event.elasticsearch` → 原有 ES 默认选择逻辑。
- BCS 容器事件的 Kafka：`bcs_event.kafka` → 原有 `BCS_KAFKA_STORAGE_CLUSTER_ID` → `custom_event.kafka` → 当前租户默认 Kafka。
- BCS 容器事件的 ES：`bcs_event.elasticsearch` → 原有 `BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID` → `custom_event.elasticsearch` → 原有 ES 默认选择逻辑。

BCS 容器指标与自定义指标继续使用原有 BCS 配置，不受事件场景配置影响。

通过现有全局配置管理入口修改配置；读取遵循现有 DynamicSettings 缓存刷新机制，无需重启进程。默认配置仅参与新建数据源和事件组时的集群选择，不会迁移已有 DataID、Kafka Topic 或 ES 存储。复用已有 DataID 时仍使用该 DataID 已记录的 Kafka。V4 事件链路注册到 BKBase 时继续使用数据源选定的 KafkaChannel 和 Topic。

## 扩展其他场景或存储

配置结构不限制场景及存储类型，可保存 `kafka`、`victoria_metrics`、`elasticsearch`、`doris` 等键。使用 `metadata.utils.default_cluster.get_scene_default_cluster(scene, storage_type, bk_tenant_id, default=None)` 读取默认值；每次调用读取动态配置，不额外缓存。

本次只接入上述事件 Kafka/ES 创建流程。其他场景以及 VM/Doris 的创建流程需后续接入该函数，单独填写配置不会改变它们的行为。
