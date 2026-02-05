### Metadata表关系整理

基于 `DataSource` 构建数据链路表关系图（含字段级关联 + 逻辑归属/上游）。说明：
- **逻辑归属**：表示业务语义上的上下游关系，不等同于外键约束。
- **图谱拆分**：主图聚焦 datasource/resulttable/custom_group 主链路；其余表按“存储/快照/BCS/空间/DataLink”等子图拆分，避免过度拥挤。

#### 元数据主链路

```mermaid
erDiagram
    DataSource ||--|| KafkaTopicInfo : "bk_data_id"
    DataSource ||--o{ DataSourceOption : "bk_data_id"

    DataSource ||--o{ DataSourceResultTable : "bk_data_id"
    DataSourceResultTable }o--|| ResultTable : "table_id"

    ResultTable ||--o{ ResultTableOption : "table_id"
    ResultTable ||--o{ ResultTableField : "table_id"
    ResultTableField ||--o{ ResultTableFieldOption : "table_id+field_name"

    %% 逻辑上游：ResultTable 上游自定义组
    ResultTable ||--o| TimeSeriesGroup : "table_id"
    ResultTable ||--o| EventGroup : "table_id"
    ResultTable ||--o| LogGroup : "table_id"

    %% 同时这些自定义组也与 DataSource 逻辑关联
    DataSource ||--o| TimeSeriesGroup : "bk_data_id"
    DataSource ||--o| EventGroup : "bk_data_id"
    DataSource ||--o| LogGroup : "bk_data_id"

    TimeSeriesGroup ||--o{ TimeSeriesMetric : "group_id"
    EventGroup ||--o{ Event : "event_group_id"

    %% 可选扩展：空间归属（如需可打开）
    DataSource ||--o{ SpaceDataSource : "bk_data_id"
    Space ||--o{ SpaceDataSource : "space_type_id+space_id"

    DataSource {
        int bk_data_id PK
        int mq_config_id
        int mq_cluster_id
        string bk_tenant_id
    }
    KafkaTopicInfo {
        int bk_data_id UK
        string topic
    }
    DataSourceResultTable {
        int bk_data_id FK
        string table_id FK
        string bk_tenant_id
    }
    ResultTable {
        bigint id PK
        string table_id UK
        string bk_tenant_id
    }
    ResultTableField {
        string table_id FK
        string field_name
        string bk_tenant_id
    }
    ResultTableOption {
        string table_id FK
        string name
        string bk_tenant_id
    }
    ResultTableFieldOption {
        string table_id FK
        string field_name FK
        string bk_tenant_id
    }
    TimeSeriesGroup {
        int time_series_group_id PK
        int bk_data_id FK
        string table_id FK
        string bk_tenant_id
    }
    TimeSeriesMetric {
        int group_id FK
        string table_id
    }
    EventGroup {
        int event_group_id PK
        int bk_data_id FK
        string table_id FK
        string bk_tenant_id
    }
    Event {
        int event_group_id FK
        string event_name
    }
    LogGroup {
        bigint log_group_id PK
        int bk_data_id FK
        string table_id FK
        string bk_tenant_id
    }
    DataSourceOption {
        int bk_data_id FK
        string name
        string bk_tenant_id
    }
    SpaceDataSource {
        int bk_data_id FK
        string space_type_id
        string space_id
        string bk_tenant_id
    }
    Space {
        string space_type_id
        string space_id
        string bk_tenant_id
    }
```

#### 计算平台/DataLink 配置链路
```mermaid
erDiagram
    DataLink ||--o{ DataIdConfig : "data_link_name"
    DataLink ||--o{ ResultTableConfig : "data_link_name"
    DataLink ||--o{ DataBusConfig : "data_link_name"
    DataLink ||--o{ VMStorageBindingConfig : "data_link_name"
    DataLink ||--o{ ESStorageBindingConfig : "data_link_name"
    DataLink ||--o{ DorisStorageBindingConfig : "data_link_name"
    DataLink ||--o{ ConditionalSinkConfig : "data_link_name"

    DataIdConfig }o--|| DataSource : "bk_data_id"
    DataBusConfig }o--|| DataSource : "bk_data_id"
    ResultTableConfig }o--|| ResultTable : "table_id"
    VMStorageBindingConfig }o--|| ResultTable : "table_id"
    ESStorageBindingConfig }o--|| ResultTable : "table_id"
    DorisStorageBindingConfig }o--|| ResultTable : "table_id"

    BkBaseResultTable }o--|| DataLink : "data_link_name"
    BkBaseResultTable }o--|| ResultTable : "monitor_table_id"
    BkBaseResultTable }o--|| ClusterInfo : "storage_cluster_id"

    ClusterConfig }o--|| ClusterInfo : "kind+name"

    DataLink {
        string data_link_name PK
        int bk_data_id
        string[] table_ids
        string bk_tenant_id
    }
    DataIdConfig {
        string data_link_name FK
        int bk_data_id
        string name
    }
    ResultTableConfig {
        string data_link_name FK
        string table_id
        string name
    }
    DataBusConfig {
        string data_link_name FK
        int bk_data_id
        string name
    }
    VMStorageBindingConfig {
        string data_link_name FK
        string table_id
        string vm_cluster_name
    }
    ESStorageBindingConfig {
        string data_link_name FK
        string table_id
        string es_cluster_name
    }
    DorisStorageBindingConfig {
        string data_link_name FK
        string table_id
    }
    ConditionalSinkConfig {
        string data_link_name FK
        string name
    }
    BkBaseResultTable {
        string data_link_name PK
        string monitor_table_id
        int storage_cluster_id
    }
    ClusterConfig {
        string kind
        string name
        string namespace
    }
    ClusterInfo {
        int cluster_id PK
        string cluster_type
        string cluster_name
    }
```

#### 存储/快照链路
```mermaid
erDiagram
    ResultTable ||--o{ ESStorage : "table_id"
    ResultTable ||--o{ KafkaStorage : "table_id"
    ResultTable ||--o{ DorisStorage : "table_id"
    ResultTable ||--o{ StorageClusterRecord : "table_id"

    ESStorage }o--|| ClusterInfo : "storage_cluster_id"
    KafkaStorage }o--|| ClusterInfo : "storage_cluster_id"
    DorisStorage }o--|| ClusterInfo : "storage_cluster_id"
    StorageClusterRecord }o--|| ClusterInfo : "cluster_id"

    EsSnapshot }o--|| ESStorage : "table_id"
    EsSnapshotRepository ||--o{ EsSnapshot : "repository_name"
    EsSnapshot ||--o{ EsSnapshotIndice : "table_id+snapshot_name"
    EsSnapshotRepository ||--o{ EsSnapshotIndice : "repository_name"
    EsSnapshotRepository }o--|| ClusterInfo : "cluster_id"
    EsSnapshotIndice }o--|| ESStorage : "table_id"
    EsSnapshotRestore }o--|| ESStorage : "table_id"
    ESStorage ||--o{ ESFieldQueryAliasOption : "table_id"

    ResultTable {
        string table_id PK
    }
    ESStorage {
        string table_id FK
        int storage_cluster_id
    }
    ESFieldQueryAliasOption {
        string table_id FK
        string field_path
        string query_alias
    }
    KafkaStorage {
        string table_id FK
        int storage_cluster_id
    }
    DorisStorage {
        string table_id FK
        int storage_cluster_id
    }
    StorageClusterRecord {
        string table_id FK
        int cluster_id
    }
    EsSnapshot {
        string table_id PK
        string target_snapshot_repository_name
    }
    EsSnapshotRepository {
        string repository_name PK
        int cluster_id
    }
    EsSnapshotIndice {
        string table_id
        string snapshot_name
        string repository_name
        int cluster_id
    }
    EsSnapshotRestore {
        int restore_id PK
        string table_id
    }
```

#### BCS 资源链路
```mermaid
erDiagram
    BCSClusterInfo ||--o{ PodMonitorInfo : "cluster_id"
    BCSClusterInfo ||--o{ ServiceMonitorInfo : "cluster_id"
    BCSClusterInfo ||--o{ LogCollectorInfo : "cluster_id"

    PodMonitorInfo }o--|| DataSource : "bk_data_id"
    ServiceMonitorInfo }o--|| DataSource : "bk_data_id"
    LogCollectorInfo }o--|| DataSource : "bk_data_id"

    BCSClusterInfo }o--|| DataSource : "K8sMetricDataID/CustomMetricDataID/K8sEventDataID/CustomEventDataID"

    BcsFederalClusterInfo }o--|| BCSClusterInfo : "host_cluster_id/sub_cluster_id/fed_cluster_id"

    BCSClusterInfo {
        string cluster_id PK
        int bk_biz_id
        int K8sMetricDataID
    }
    PodMonitorInfo {
        string cluster_id FK
        int bk_data_id
        string namespace
        string name
    }
    ServiceMonitorInfo {
        string cluster_id FK
        int bk_data_id
        string namespace
        string name
    }
    LogCollectorInfo {
        string cluster_id FK
        int bk_data_id
        string namespace
        string name
    }
    BcsFederalClusterInfo {
        string fed_cluster_id
        string host_cluster_id
        string sub_cluster_id
    }
```

#### 空间与资源链路
```mermaid
erDiagram
    SpaceType ||--o{ Space : "space_type_id"
    Space ||--o{ SpaceResource : "space_type_id+space_id"
    Space ||--o{ SpaceDataSource : "space_type_id+space_id"
    Space ||--o{ SpaceVMInfo : "space_type_id+space_id"
    Space ||--o{ SpaceRelatedStorageInfo : "space_type_id+space_id"

    SpaceRelatedStorageInfo }o--|| ClusterInfo : "cluster_id"
    SpaceVMInfo }o--|| ClusterInfo : "vm_cluster_id"

    BkAppSpaceRecord }o--|| Space : "space_uid"

    SpaceType {
        string type_id PK
    }
    Space {
        string space_type_id
        string space_id
        string bk_tenant_id
    }
    SpaceResource {
        string space_type_id
        string space_id
        string resource_type
    }
    SpaceVMInfo {
        string space_type
        string space_id
        int vm_cluster_id
    }
    SpaceRelatedStorageInfo {
        string space_type_id
        string space_id
        int cluster_id
    }
    BkAppSpaceRecord {
        string space_uid
        string bk_app_code
    }
    ClusterInfo {
        int cluster_id PK
    }
```

#### 未纳入关系图的表（待确认）
| 表(模型) | 原因/备注 |
|---|---|
| PingServerSubscriptionConfig | 仅订阅配置与主机信息，无直接 datasource/resulttable 关联 |
| CustomReportSubscriptionConfig | 已废弃订阅配置，无直接链路关联 |
| LogSubscriptionConfig | 订阅配置无显式 FK（仅 `bk_biz_id/log_name`） |
| SpaceStickyInfo | 用户置顶信息，与链路无关 |
| Label | 标签配置，非外键关系 |
| CustomRelationStatus | 自定义关联状态（通用元信息） |
| CustomReportSubscription | 自定义上报订阅 |

#### 无法归类到业务下的表（补充，待确认）
| 表(模型) | 原因/备注 |
|---|---|
| ClusterInfo | 集群信息，全局配置表 |
| SpaceType | 空间类型，全局配置表 |
| EsSnapshotRepository | ES 快照仓库配置，全局配置表 |
| ClusterConfig | 集群配置（DataLink），全局配置表 |
| Label | 标签配置，全局配置表 |
| CustomRelationStatus | 自定义关联状态，全局元信息 |
| PingServerSubscriptionConfig | 订阅配置，无直接关联 |
| CustomReportSubscription | 自定义上报订阅，无直接链路关联 |
| CustomReportSubscriptionConfig | 已废弃订阅配置，无直接链路关联 |
| SpaceStickyInfo | 用户置顶信息，与链路无关 |
| InfluxDBClusterInfo | InfluxDB 集群信息，全局配置表 |
| InfluxDBHostInfo | InfluxDB 主机信息，全局配置表 |
| InfluxDBProxyStorage | InfluxDB 代理存储，全局配置表 |
| InfluxDBTagInfo | InfluxDB 标签信息，全局配置表 |
| EntityMeta | 实体元信息，需特殊处理 |
