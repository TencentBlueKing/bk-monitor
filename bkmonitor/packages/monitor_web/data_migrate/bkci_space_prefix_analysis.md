# BKCI space_id tenant prefix repair analysis

## Background

BCS migration may change `project_code` by adding a tenant prefix, for example
`blueking` becomes `tencent-blueking`. In monitor metadata, BKCI space `space_id`
is sourced from BCS `project_code`, while `space_code` is sourced from BCS
`project_id`. This report analyzes which persisted tables may need adjustment
when existing BKCI `space_id` values are repaired from the legacy unprefixed
form to the tenant-prefixed form.

## Step 1: model inventory

The scan covered Django ORM models under `metadata`, `bkmonitor`, and `packages`.
After excluding abstract models and non-Django pydantic objects, the automated
AST pass identified 157 ORM model classes. The package-specific scans also
covered models that use local aliases or custom base classes; the inventory
below is the merged coverage list used for the analysis.

### metadata models

- `metadata.models.data_source`: `DataSource`, `DataSourceResultTable`.
- `metadata.models.es_snapshot`: `EsSnapshot`, `EsSnapshotRepository`, `EsSnapshotIndice`, `EsSnapshotRestore`.
- `metadata.models.common`: `Label`.
- `metadata.models.result_table`: `ResultTable`, `ResultTableField`, `ResultTableRecordFormat`, `CMDBLevelRecord`, `ESFieldQueryAliasOption`.
- `metadata.models.influxdb_cluster`: `InfluxDBTagInfo`, `InfluxDBClusterInfo`, `InfluxDBHostInfo`, `InfluxDBProxyStorage`.
- `metadata.models.storage`: `ClusterInfo`, `KafkaTopicInfo`, `InfluxDBStorage`, `RedisStorage`, `KafkaStorage`, `ESStorage`, `BkDataStorage`, `ArgusStorage`, `StorageClusterRecord`, `SpaceRelatedStorageInfo`, `DorisStorage`.
- `metadata.models.ping_server`: `PingServerSubscriptionConfig`.
- `metadata.models.custom_report`: `Event`, `CustomReportSubscriptionConfig`, `CustomReportSubscription`, `LogSubscriptionConfig`, `TimeSeriesScope`, `TimeSeriesMetric`, `TimeSeriesTag`.
- `metadata.models.bcs`: `BCSClusterInfo`, `BcsFederalClusterInfo`, `ReplaceConfig`, `PodMonitorInfo`, `ServiceMonitorInfo`, `LogCollectorInfo`.
- `metadata.models.record_rule`: `RecordRule`, `ResultTableFlow`, `RecordRuleV4`, `RecordRuleV4Spec`, `RecordRuleV4SpecRecord`, `RecordRuleV4Resolved`, `RecordRuleV4ResolvedRecord`, `RecordRuleV4Flow`, `RecordRuleV4Event`.
- `metadata.models.bkdata`: `BkBaseResultTable`.
- `metadata.models.vm`: `AccessVMRecord`, `SpaceVMInfo`, `VMShortLinkRecord`.
- `metadata.models.space`: `SpaceType`, `Space`, `SpaceDataSource`, `SpaceResource`, `SpaceStickyInfo`, `BkAppSpaceRecord`.
- `metadata.models.data_link`: `DataLink`, `DataLinkResourceConfigBase`, `ClusterConfig`.

### bkmonitor models

- Core and report models: `GlobalConfig`, `MonitorMigration`, `ExternalPermission`, `ExternalPermissionApplyRecord`, `HomeAlarmGraphConfig`, `AIFeatureSettings`, `AsCodeImportTask`, `SnapshotHostIndex`, `BaseAlarm`, `ResultTableSQLConfig`, `ResultTableDSLConfig`, `CustomEventQueryConfig`, `BaseAlarmQueryConfig`, `Item`, `Strategy`, `DetectAlgorithm`, `Action`, `NoticeTemplate`, `NoticeGroup`, `ActionNoticeMapping`, `AnomalyRecord`, `Event`, `EventAction`, `EventStats`, `Alert`, `AlertCollect`, `Shield`, `CacheNode`, `CacheRouter`, `ReportItems`, `ReportContents`, `ReportStatus`, `Report`, `ReportChannel`, `ReportSendRecord`, `ReportApplyRecord`, `RenderImageTask`, `StatisticsMetric`, `MetricListCache`, `QueryTemplate`, `ApiAuthToken`, `TokenAccessRecord`, `IssueMergeRelation`, `StrategyIssueConfig`.
- BCS models: `BCSCluster`, `BCSClusterLabels`, `BCSLabel`, `BCSNode`, `BCSNodeLabels`, `BCSPod`, `BCSPodLabels`, `BCSContainer`, `BCSContainerLabels`, `BCSWorkload`, `BCSWorkloadLabels`, `BCSService`, `BCSServiceLabels`, `BCSIngress`, `BCSIngressLabels`, `BCSPodMonitorLabels`, `BCSServiceMonitorLabels`.
- Strategy models: `ItemModel`, `DetectModel`, `AlgorithmModel`, `QueryConfigModel`, `StrategyLabel`, `StrategyModel`, `StrategyHistoryModel`, `UserGroup`, `DutyRule`, `DutyRuleSnap`, `DutyRuleRelation`, `DutyPlanSendRecord`, `DutyArrange`, `MetricMappingConfigModel`, `DutyArrangeSnap`, `DutyPlan`, `DefaultStrategyBizAccessModel`, `AlgorithmChoiceConfig`, `NoticeSubscribe`.
- FTA models: `ActionPlugin`, `ActionConfig`, `ActionInstance`, `ActionInstanceLog`, `ConvergeInstance`, `ConvergeRelation`, `StrategyActionConfigRelation`, `AlertAssignGroup`, `AlertAssignRule`, `EventPlugin`, `EventPluginV2`, `EventPluginInstance`, `AlertConfig`.

### packages models

- `packages.monitor_api`: `AlarmCollectDef`.
- `packages.weixin`: `BkWeixinUser`.
- `packages.monitor_web`: `AlertSolution`, `CollectConfigMeta`, `DeploymentConfigVersion`, `CustomEventGroup`, `CustomEventItem`, `CustomTSField`, `CustomTSTable`, `CustomTSItem`, `CustomTSGroupingRule`, `QueryHistory`, `FavoriteGroup`, `DataTargetMapping`, `ImportHistory`, `ImportDetail`, `ImportParse`, `UploadedFileInfo`, `BCSProjectModel`, `BCSClusterModel`, `BCSAreaModel`, `CollectorPlugin`, `CollectorPluginMeta`, `PluginVersionHistory`, `OperatorSystem`, `SceneModel`, `SceneViewModel`, `SceneViewOrderModel`, `UserAccessRecord`.
- `packages.apm_web`: `Application`, `ApplicationRelationInfo`, `ApmMetaConfig`, `ApplicationCustomService`, `ProfileUploadRecord`, `CMDBServiceRelation`, `EventServiceRelation`, `LogServiceRelation`, `AppServiceRelation`, `UriServiceRelation`, `ApdexServiceRelation`, `CodeRedefinedConfigRelation`, `StrategyTemplate`, `StrategyInstance`, `TraceComparison`, `UserVisitRecord`.
- `packages.fta_web`: `SearchHistory`, `SearchFavorite`, `AlertExperience`, `AlertSuggestion`, `AlertFeedback`, `MetricRecommendationFeedback`, `AlarmApplication`, `AlarmType`, `Solution`, `AlarmDef`.
- `packages.monitor`: `RolePermission`, `UserConfig`, `ApplicationConfig`, `GlobalConfig`, `UptimeCheckTaskCollectorLog`, `UploadedFile`, `DataGenerateConfig`, `DataCollector`, `LogCollector`, `Exporter`, `ExporterConfig`, `OperateRecord`, `MonitorHostSticky`, `ServiceAuthorization`, `HostProperty`, `MetricConf`, `Application`, `ApplicationGroupMembership`, `ComponentCategory`, `ComponentCategoryRelationship`, `IndexColorConf`, `MonitorSource`, `MonitorItemGroup`, `MonitorItem`, `AlarmSource`, `DetectAlgorithmConfig`, `SolutionConfig`, `ConvergeConfig`, `NoticeConfig`, `NoticeGroup`.

## Step 2: per-table data-source analysis

### Must be handled by the repair function

| Table / model | Fields | Data source / writer | Reason |
| --- | --- | --- | --- |
| `metadata_space` / `Space` | `space_id` | `sync_bcs_space()`, `create_bcs_spaces()`; BCS `project_code` | BKCI `space_id` is the root value that changes from old project code to prefixed project code. |
| `metadata_spacedatasource` / `SpaceDataSource` | `space_id` | `create_bcs_spaces()`, `refresh_cluster_resource()`, space authorization utilities | Space to data_id relation is queried by `(space_type_id, space_id)`. |
| `metadata_spaceresource` / `SpaceResource` | `space_id`, `resource_id` | `create_bcs_spaces()`, `refresh_bcs_project_biz()`, `refresh_cluster_resource()` | BKCI rows use `space_id=project_code`; `resource_type in ('bcs', 'bkci')` may also use project code as `resource_id`. `resource_type='bkcc'` is business ID and must not change. |
| `metadata_spaceresource` / `SpaceResource` | `dimension_values` | `add_bkci_metrics_and_dimensions` and some system BKCI setup | Usually stores `cluster_id/namespace/bk_biz_id`, but system BKCI records may contain `{"project_id": old_space_id}`. Repair should use exact-value JSON replacement only. |
| `metadata_datasource` / `DataSource` | `space_uid` | `CreateDataIDResource`, `DataSource.create_data_source()`, `DataSource.update_config()` | Stores `bkci__{space_id}` explicitly. |
| `bkmonitor_bcscluster` / `BCSCluster` | `space_uid` | `BCSCluster.load_list_from_api()`, `sync_bcs_cluster_to_db()` | Cluster rows map BCS cluster `project_id` to `Space.space_code -> Space.space_uid`. Historical rows can keep old `bkci__old`. |
| `metadata_spacestickyinfo` / `SpaceStickyInfo` | `space_uid_list` | `StickSpaceResource` | User sticky spaces store `bkci__old` directly. |
| `metadata_bkappspacerecord` / `BkAppSpaceRecord` | `space_uid` | Application-space authorization | App authorization stores `bkci__old` directly. |
| `metadata_spacerelatedstorageinfo` / `SpaceRelatedStorageInfo` | `space_id` | Admin/configuration path, future storage selection path | If `space_type_id='bkci'` rows exist, they must follow the new `space_id`. |
| `metadata_spacevminfo` / `SpaceVMInfo` | `space_id` | `SpaceVMInfoManager.create_record()`, VM access utilities | VM access can be keyed by non-BKCC space. |
| `metadata_vmshortlinkrecord` / `VMShortLinkRecord` | `space_id` | `apply_vm_short_links()`, `update_vm_short_links()` | Current common path is BKCC, but model supports arbitrary spaces; BKCI rows must follow `space_id`. |
| `metadata_recordrule` / `RecordRule` | `space_id` | `RecordRuleService.create_record_rule()` | Pre-calculation rules are queried by `(space_type, space_id)`. |
| `metadata_recordrulev4` / `RecordRuleV4` | `space_id` | `RecordRuleV4Operator.create()`, `RecordRuleV4.create()` | V4 pre-calculation main table stores the space identity. |
| `metadata_recordrulev4flow` / `RecordRuleV4Flow` | `flow_config` | `RecordRuleV4Flow.compose_flow_config()` | `flow_config.metadata.annotations` can contain `space-uid = bkci__old`; exact JSON replacement or re-resolve/re-apply is needed. |

### Needs additional data sampling before adding to the function

| Table / model | Fields | Why it is only suspicious |
| --- | --- | --- |
| `metadata_recordrule` / `RecordRule` | `table_id`, `dst_vm_table_id` | These may be derived from `space_id` by pre-calculation table-name generation. Changing them is much riskier than changing `space_id`; sample real rows before deciding. If old table IDs exist in BKBase/VM storage, renaming them may require external changes. |
| `metadata_recordrulev4spec` / `RecordRuleV4Spec` | `raw_config` | User input JSON may contain `bkci__old` or old `space_id`, but normal generated config is mostly rule spec. Exact-value scan is recommended. |
| `metadata_recordrulev4specrecord` / `RecordRuleV4SpecRecord` | `input_config` | May contain query/source metadata; exact-value scan is recommended. |
| `metadata_recordrulev4resolved` / `RecordRuleV4Resolved` | `resolved_config` | Derived snapshot; can be regenerated, but stale snapshots may still be read. |
| `metadata_recordrulev4resolvedrecord` / `RecordRuleV4ResolvedRecord` | `src_result_table_configs` | Usually result table metadata, but can indirectly encode source labels. Sample before mutating. |
| `packages_monitor_web_bcsprojectmodel`, `packages_monitor_web_bcsclustermodel` | `project_id` | Looks like old/legacy Kubernetes model; no current non-test writer was found. If tables are non-empty and `project_id` is actually project code, sample before repair. |
| `packages_fta_web_searchfavorite`, `packages_fta_web_searchhistory` | `params` JSON | Favorites/history are open JSON. Common search serializers convert `space_uids` to `bk_biz_ids`, but old front-end params may remain. Scan exact `bkci__old` values before deciding. |
| `api_auth_token` / `ApiAuthToken` | `namespaces`, `params` | Standard path stores `biz#...`; admin-created custom `project#old` namespaces are possible but not confirmed. |

### Cache / derived state after DB repair

These should not be treated as DB rows to migrate, but the repair workflow should refresh or clear them:

- `SPACE_TO_RESULT_TABLE_KEY`: hash fields include `bkci__{space_id}`. Need push new router and remove stale old field.
- Space detail Redis entries produced by `push_space_to_redis()`: new `bkci__new` needs publishing, old `bkci__old` should be removed.
- Strategy cache: strategy DB mostly uses negative `bk_biz_id`, but cache snapshots may contain stale query config. Refresh after DB repair.
- `MetricListCache`: no direct `bkci__space_uid` field found, but it is derived from space/biz mappings; refresh after DB repair.

### No DB value repair needed

- `metadata.ResultTable*`, `DataSourceResultTable`, `DataSourceOption`, storage tables, datalink tables, custom report tables: these primarily store `bk_tenant_id`, `bk_biz_id`, `bk_data_id`, `table_id`, or storage identifiers, not BKCI project code.
- `metadata.BCSClusterInfo.project_id`: this is BCS cluster-manager `project_id`, not BCS `project_code`; do not tenant-prefix it for this issue.
- BCS resource tables such as pods, containers, workloads, services, ingress, service monitor, pod monitor, labels: they store `bcs_cluster_id`, `bk_biz_id`, `namespace`, and resource names. They rely on `BCSCluster.space_uid` for project linkage.
- APM service relation JSON stores `bcs_cluster_id/namespace/kind/name`, not BKCI `space_uid`.
- Grafana / `bk_dataview` dashboards and permissions convert request `space_uid` to `bk_biz_id`/org context; stored dashboard UID and permission scope are not project code.
- `QueryTemplate.space_scope` stores business IDs, not `bkci__space_id`.
- Old monitor / monitor_api / FTA alarm configuration tables use `biz_id`, `cc_biz_id`, `bk_biz_id`, strategy JSON, or alert snapshots. They are not the source of the BKCI space mapping.

## Current repair function gap list

The current helper `repair_bkci_space_id_prefix()` already covers the main high-confidence tables:

- `Space`
- `SpaceDataSource`
- `SpaceResource.space_id`
- `SpaceResource.resource_id` for `resource_type in ('bkci', 'bcs')`
- `SpaceResource.dimension_values` exact-value JSON replacement
- `DataSource.space_uid`
- `BCSCluster.space_uid`
- `SpaceStickyInfo.space_uid_list`
- `BkAppSpaceRecord.space_uid`
- `SpaceRelatedStorageInfo.space_id`
- `SpaceVMInfo.space_id`
- `VMShortLinkRecord.space_id`
- `RecordRule.space_id`
- `RecordRuleV4.space_id`
- `RecordRuleV4Flow.flow_config`

Recommended follow-up changes before production use:

1. Add optional exact JSON scan/report for RecordRuleV4 spec/resolved snapshot tables, even if mutation remains disabled by default.
2. Add Redis cleanup/refresh guidance or helper output for old/new `space_uid` keys.
3. Keep `RecordRule.table_id` and `dst_vm_table_id` out of automatic mutation until real data confirms they contain the legacy space ID and external BKBase/VM consequences are understood.
