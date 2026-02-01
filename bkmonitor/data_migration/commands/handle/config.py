"""handle 配置（可变全局注册表）。

说明：
    - 这里存放"可变的全局注册表"，避免与 pipeline 核心逻辑混在一起
    - 之所以单独拆出来，是为了让 export/handle 等调用方可以明确依赖"配置层"
"""

from __future__ import annotations

from data_migration.config import (
    BIZ_TENANT_ID_MAPPING,
    DEFAULT_TARGET_TENANT_ID,
    EXCLUDED_BIZ_IDS,
)

from .builtins import disable_enable_fields, filter_is_deleted, replace_bk_tenant_id
from .handle import GlobalPipelineContext, GlobalPipelineSpec, RowTransformer
from .metadata_relations import filter_metadata_by_biz

# 表级别处理映射
#
# key 支持两类：
# - "app_label.ModelName"：指定单张表的处理链
# - "*"：通配处理，会被追加到每张表处理链的最后执行
TABLE_PIPELINE_MAPPING: dict[str, list[RowTransformer]] = {
    "*": [replace_bk_tenant_id],
    "bkmonitor.StrategyModel": [disable_enable_fields],
    "monitor_web.CollectConfigMeta": [disable_enable_fields],
    "monitor_web.UptimeCheckTask": [disable_enable_fields],
    "bkmonitor.ReportItems": [disable_enable_fields],
    "bkmonitor.Report": [disable_enable_fields],
    "metadata.DataSource": [disable_enable_fields],
    "metadata.ResultTable": [disable_enable_fields],
    "bkmonitor.Shield": [filter_is_deleted],
}

# =============================================================================
# Metadata 表集合（用于全局处理依赖声明）
# =============================================================================

# 所有需要业务过滤的 metadata 表
METADATA_MODELS: set[str] = {
    # Label & CustomRelationStatus
    "metadata.Label",
    "metadata.CustomRelationStatus",
    # Space
    "metadata.Space",
    "metadata.SpaceType",
    "metadata.SpaceDataSource",
    "metadata.SpaceResource",
    "metadata.SpaceStickyInfo",
    "metadata.SpaceVMInfo",
    "metadata.SpaceRelatedStorageInfo",
    "metadata.BkAppSpaceRecord",
    # Cluster
    "metadata.ClusterInfo",
    "metadata.ClusterConfig",
    # BCS
    "metadata.BCSClusterInfo",
    "metadata.BcsFederalClusterInfo",
    "metadata.ServiceMonitorInfo",
    "metadata.PodMonitorInfo",
    "metadata.LogCollectorInfo",
    # DataSource
    "metadata.DataSource",
    "metadata.DataSourceOption",
    "metadata.DataSourceResultTable",
    # ResultTable
    "metadata.ResultTable",
    "metadata.ResultTableOption",
    "metadata.ResultTableField",
    "metadata.ResultTableFieldOption",
    # Storage
    "metadata.ESStorage",
    "metadata.AccessVMRecord",
    "metadata.KafkaStorage",
    "metadata.DorisStorage",
    "metadata.StorageClusterRecord",
    "metadata.KafkaTopicInfo",
    "metadata.ESFieldQueryAliasOption",
    # ES Snapshot
    "metadata.EsSnapshot",
    "metadata.EsSnapshotIndice",
    "metadata.EsSnapshotRepository",
    "metadata.EsSnapshotRestore",
    # Custom Report
    "metadata.TimeSeriesGroup",
    "metadata.TimeSeriesMetric",
    "metadata.EventGroup",
    "metadata.Event",
    "metadata.LogGroup",
    # Collector Installer
    "metadata.CustomReportSubscription",
    "metadata.CustomReportSubscriptionConfig",
    "metadata.LogSubscriptionConfig",
    "metadata.PingServerSubscriptionConfig",
    # DataLink
    "metadata.BkBaseResultTable",
    "metadata.DataLink",
    "metadata.DataIdConfig",
    "metadata.DataBusConfig",
    "metadata.ResultTableConfig",
    "metadata.ESStorageBindingConfig",
    "metadata.VMStorageBindingConfig",
    "metadata.DorisStorageBindingConfig",
    "metadata.ConditionalSinkConfig",
}


# =============================================================================
# 全局处理函数
# =============================================================================


def _run_metadata_biz_filter(ctx: GlobalPipelineContext) -> None:
    """执行 metadata 业务过滤。

    按 EXCLUDED_BIZ_IDS 排除指定业务的数据，并按 BIZ_TENANT_ID_MAPPING 替换租户ID。
    """
    # 收集所有 metadata 表数据
    rows_by_model: dict[str, list] = {}
    for model_label in ctx.models():
        if model_label.startswith("metadata."):
            rows_by_model[model_label] = ctx.get(model_label)

    # 执行过滤和租户ID替换
    filtered_rows_by_model = filter_metadata_by_biz(
        rows_by_model,
        excluded_biz_ids=EXCLUDED_BIZ_IDS,
        biz_tenant_mapping=BIZ_TENANT_ID_MAPPING,
        default_tenant_id=DEFAULT_TARGET_TENANT_ID,
    )

    # 更新上下文中的数据
    for model_label, rows in filtered_rows_by_model.items():
        if model_label.startswith("metadata."):
            ctx.set(model_label, rows)


# =============================================================================
# 全局处理列表（按顺序执行）
# =============================================================================

GLOBAL_PIPELINES: list[GlobalPipelineSpec] = [
    GlobalPipelineSpec(
        name="metadata_biz_filter",
        required_models=METADATA_MODELS,
        fn=_run_metadata_biz_filter,
    ),
]
