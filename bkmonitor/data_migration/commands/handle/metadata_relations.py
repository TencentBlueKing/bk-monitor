"""Metadata 关联数据处理模块。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from data_migration.config import LOG_SOURCE_SYSTEMS
from data_migration.utils.types import RowDict

ValueNormalizer = Callable[[Any], Any | None]
FilterMode = Literal["include", "exclude"]

# =====================================================================
# Metadata 表分类常量
# =====================================================================

# 全局表（不需要业务过滤，直接保留）
METADATA_GLOBAL_TABLES: set[str] = {
    "metadata.Label",
    "metadata.SpaceType",
    "metadata.ClusterInfo",
    "metadata.ClusterConfig",
    "metadata.PingServerSubscriptionConfig",
    "metadata.EsSnapshotRepository",
    "metadata.SpaceStickyInfo",
    "metadata.CustomRelationStatus",
}

# 有直接 bk_biz_id 字段的表
METADATA_TABLES_WITH_BIZ_ID: set[str] = {
    # 其他
    "metadata.CustomReportSubscription",
    "metadata.CustomReportSubscriptionConfig",
    "metadata.LogSubscriptionConfig",
}

# 按 table_id 关联的表（字段名 -> 表集合）
METADATA_TABLES_BY_TABLE_ID: dict[str, set[str]] = {
    "table_id": {
        "metadata.ResultTable",
        "metadata.TimeSeriesGroup",
        "metadata.EventGroup",
        "metadata.LogGroup",
        "metadata.ResultTableOption",
        "metadata.ResultTableField",
        "metadata.ResultTableFieldOption",
        "metadata.ESStorage",
        "metadata.KafkaStorage",
        "metadata.DorisStorage",
        "metadata.StorageClusterRecord",
        "metadata.ESFieldQueryAliasOption",
        "metadata.EsSnapshot",
        "metadata.EsSnapshotIndice",
        "metadata.EsSnapshotRestore",
    },
    "result_table_id": {
        "metadata.AccessVMRecord",
    },
    "monitor_table_id": {
        "metadata.BkBaseResultTable",
    },
}

# 按 bk_data_id 关联的表
METADATA_TABLES_BY_DATA_ID: set[str] = {
    "metadata.DataSource",
    "metadata.DataSourceOption",
    "metadata.DataSourceResultTable",
    "metadata.KafkaTopicInfo",
}

# Space 相关表（字段组合 -> 表集合）
METADATA_SPACE_TABLES: dict[tuple[str, ...], set[str]] = {
    ("space_type_id", "space_id"): {
        "metadata.Space",
        "metadata.SpaceDataSource",
        "metadata.SpaceResource",
        "metadata.SpaceRelatedStorageInfo",
    },
    ("space_type", "space_id"): {
        "metadata.SpaceVMInfo",
    },
}

# BkAppSpaceRecord 通过 space_uid 关联
METADATA_SPACE_UID_TABLES: set[str] = {
    "metadata.BkAppSpaceRecord",
}

# BCS 相关表（字段名 -> 表集合）
METADATA_BCS_TABLES: dict[str, set[str]] = {
    "cluster_id": {
        "metadata.BCSClusterInfo",
        "metadata.ServiceMonitorInfo",
        "metadata.PodMonitorInfo",
        "metadata.LogCollectorInfo",
    },
}

# BcsFederalClusterInfo 通过多个 cluster_id 字段关联
METADATA_BCS_FEDERAL_TABLES: set[str] = {
    "metadata.BcsFederalClusterInfo",
}

# DataLink 相关表（通过 data_link_name 关联）
METADATA_DATALINK_TABLES: set[str] = {
    "metadata.DataLink",
    # 注意：DataLink 相关配置表的 bk_biz_id 可能不准确，统一通过 data_link_name 关联
    "metadata.ResultTableConfig",
    "metadata.DataBusConfig",
    "metadata.DataIdConfig",
    "metadata.VMStorageBindingConfig",
    "metadata.ESStorageBindingConfig",
    "metadata.DorisStorageBindingConfig",
    "metadata.ConditionalSinkConfig",
}

# 二级关联表
METADATA_SECONDARY_TABLES: dict[str, tuple[str, str]] = {
    # model_label: (关联字段, 来源表的ID字段)
    "metadata.TimeSeriesMetric": ("group_id", "time_series_group_id"),
    "metadata.Event": ("event_group_id", "event_group_id"),
}

# 所有 metadata 表集合（用于快速判断）
ALL_METADATA_TABLES: set[str] = (
    METADATA_GLOBAL_TABLES
    | METADATA_TABLES_WITH_BIZ_ID
    | set().union(*METADATA_TABLES_BY_TABLE_ID.values())
    | METADATA_TABLES_BY_DATA_ID
    | set().union(*METADATA_SPACE_TABLES.values())
    | METADATA_SPACE_UID_TABLES
    | set().union(*METADATA_BCS_TABLES.values())
    | METADATA_BCS_FEDERAL_TABLES
    | METADATA_DATALINK_TABLES
    | set(METADATA_SECONDARY_TABLES.keys())
)


def _normalize_int(value: Any) -> int | None:
    """将值标准化为 int。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _normalize_str(value: Any) -> str | None:
    """将值标准化为 str。"""
    if value is None:
        return None
    return str(value)


def _extract_field_values(
    rows: Iterable[RowDict],
    field_name: str,
    normalizer: ValueNormalizer | None = None,
) -> set[Any]:
    """从数据行中提取指定字段的值集合。"""
    values: set[Any] = set()
    for row in rows:
        value = row.get(field_name)
        if normalizer:
            value = normalizer(value)
        if value is not None:
            values.add(value)
    return values


def _build_composite_key(
    row: RowDict,
    field_names: tuple[str, ...],
    normalizer: ValueNormalizer | None = None,
) -> tuple[Any, ...] | None:
    """构建复合键。"""
    values: list[Any] = []
    for field_name in field_names:
        value = row.get(field_name)
        if normalizer:
            value = normalizer(value)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def _filter_by_field(
    rows: list[RowDict],
    field_name: str,
    allowed_values: set[Any],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按单字段过滤数据行。"""
    if not rows or not allowed_values:
        return []
    normalized_allowed = {normalizer(v) if normalizer else v for v in allowed_values}
    return [
        row
        for row in rows
        if (normalizer(row.get(field_name)) if normalizer else row.get(field_name)) in normalized_allowed
    ]


def _filter_by_fields(
    rows: list[RowDict],
    field_names: tuple[str, ...],
    allowed_keys: set[tuple[Any, ...]],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按复合字段过滤数据行。"""
    if not rows or not allowed_keys:
        return []
    return [row for row in rows if _build_composite_key(row, field_names, normalizer) in allowed_keys]


def _filter_by_any_field(
    rows: list[RowDict],
    field_names: tuple[str, ...],
    allowed_values: set[Any],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按任意字段匹配过滤数据行。"""
    if not rows or not allowed_values:
        return []
    normalized_allowed = {normalizer(v) if normalizer else v for v in allowed_values}
    filtered: list[RowDict] = []
    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)
            if normalizer:
                value = normalizer(value)
            if value in normalized_allowed:
                filtered.append(row)
                break
    return filtered


def _exclude_by_field(
    rows: list[RowDict],
    field_name: str,
    excluded_values: set[Any],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按单字段排除数据行。"""
    if not rows:
        return []
    if not excluded_values:
        return rows
    normalized_excluded = {normalizer(v) if normalizer else v for v in excluded_values}
    return [
        row
        for row in rows
        if (normalizer(row.get(field_name)) if normalizer else row.get(field_name)) not in normalized_excluded
    ]


def _exclude_by_fields(
    rows: list[RowDict],
    field_names: tuple[str, ...],
    excluded_keys: set[tuple[Any, ...]],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按复合字段排除数据行。"""
    if not rows:
        return []
    if not excluded_keys:
        return rows
    return [row for row in rows if _build_composite_key(row, field_names, normalizer) not in excluded_keys]


def _exclude_by_any_field(
    rows: list[RowDict],
    field_names: tuple[str, ...],
    excluded_values: set[Any],
    normalizer: ValueNormalizer | None = None,
) -> list[RowDict]:
    """按任意字段匹配排除数据行（任一字段命中则排除）。"""
    if not rows:
        return []
    if not excluded_values:
        return rows
    normalized_excluded = {normalizer(v) if normalizer else v for v in excluded_values}
    filtered: list[RowDict] = []
    for row in rows:
        should_exclude = False
        for field_name in field_names:
            value = row.get(field_name)
            if normalizer:
                value = normalizer(value)
            if value in normalized_excluded:
                should_exclude = True
                break
        if not should_exclude:
            filtered.append(row)
    return filtered


# =====================================================================
# Metadata 业务过滤辅助函数
# =====================================================================


def _replace_tenant_id_in_row(
    row: RowDict,
    biz_id: int | None,
    biz_tenant_mapping: dict[int, str],
    default_tenant_id: str,
) -> None:
    """替换行数据中的租户ID（原地修改）。

    Args:
        row: 数据行
        biz_id: 业务ID
        biz_tenant_mapping: 业务ID到租户ID的映射
        default_tenant_id: 默认租户ID
    """
    if "bk_tenant_id" not in row:
        return
    if biz_id is not None:
        row["bk_tenant_id"] = biz_tenant_mapping.get(biz_id, default_tenant_id)
    else:
        row["bk_tenant_id"] = default_tenant_id


@dataclass
class MetadataRelationResult:
    """Metadata 关联数据结果。"""

    # 核心关联
    data_source_result_tables: list[RowDict] = field(default_factory=list)

    # 按 bk_data_id 关联
    data_sources: list[RowDict] = field(default_factory=list)
    kafka_topic_infos: list[RowDict] = field(default_factory=list)
    data_source_options: list[RowDict] = field(default_factory=list)
    time_series_groups: list[RowDict] = field(default_factory=list)
    event_groups: list[RowDict] = field(default_factory=list)
    log_groups: list[RowDict] = field(default_factory=list)
    space_data_sources: list[RowDict] = field(default_factory=list)

    # 按 table_id 关联
    result_tables: list[RowDict] = field(default_factory=list)
    result_table_options: list[RowDict] = field(default_factory=list)
    result_table_fields: list[RowDict] = field(default_factory=list)
    result_table_field_options: list[RowDict] = field(default_factory=list)

    # 存储相关
    es_storages: list[RowDict] = field(default_factory=list)
    kafka_storages: list[RowDict] = field(default_factory=list)
    doris_storages: list[RowDict] = field(default_factory=list)
    storage_cluster_records: list[RowDict] = field(default_factory=list)
    es_field_query_alias_options: list[RowDict] = field(default_factory=list)

    # 二级关联
    time_series_metrics: list[RowDict] = field(default_factory=list)
    events: list[RowDict] = field(default_factory=list)

    # 快照相关
    es_snapshots: list[RowDict] = field(default_factory=list)
    es_snapshot_indices: list[RowDict] = field(default_factory=list)
    es_snapshot_restores: list[RowDict] = field(default_factory=list)

    # DataLink 配置（通过 data_link_name 关联）
    bk_base_result_tables: list[RowDict] = field(default_factory=list)
    data_links: list[RowDict] = field(default_factory=list)
    data_id_configs: list[RowDict] = field(default_factory=list)
    data_bus_configs: list[RowDict] = field(default_factory=list)
    result_table_configs: list[RowDict] = field(default_factory=list)
    vm_storage_binding_configs: list[RowDict] = field(default_factory=list)
    es_storage_binding_configs: list[RowDict] = field(default_factory=list)
    doris_storage_binding_configs: list[RowDict] = field(default_factory=list)
    conditional_sink_configs: list[RowDict] = field(default_factory=list)

    # Space 相关（通过 biz_ids 关联）
    spaces: list[RowDict] = field(default_factory=list)
    space_resources: list[RowDict] = field(default_factory=list)
    space_vm_infos: list[RowDict] = field(default_factory=list)
    space_related_storage_infos: list[RowDict] = field(default_factory=list)
    bk_app_space_records: list[RowDict] = field(default_factory=list)

    # BCS 相关（通过 biz_ids 关联）
    bcs_cluster_infos: list[RowDict] = field(default_factory=list)
    pod_monitor_infos: list[RowDict] = field(default_factory=list)
    service_monitor_infos: list[RowDict] = field(default_factory=list)
    log_collector_infos: list[RowDict] = field(default_factory=list)
    bcs_federal_cluster_infos: list[RowDict] = field(default_factory=list)


def _get_table_ids_for_biz0(rows_by_model: dict[str, list[RowDict]]) -> set[str]:
    """按业务 0 获取全局表的 table_ids（占位实现）。

    Args:
        rows_by_model: 预加载的模型数据

    Returns:
        业务 0 的结果表 ID 集合。
    """
    _ = rows_by_model
    return set()


def get_table_ids_by_biz(biz_ids: set[int], rows_by_model: dict[str, list[RowDict]]) -> set[str]:
    """按业务获取业务下所有的 table_ids。

    Args:
        biz_ids: 业务ID集合
        rows_by_model: 预加载的模型数据

    Returns:
        结果表 ID 集合。
    """
    normalized_biz_ids = {bid for bid in (_normalize_int(b) for b in biz_ids) if bid is not None}
    if not normalized_biz_ids:
        return set()

    table_ids: set[str] = set()
    if 0 in normalized_biz_ids:
        table_ids.update(_get_table_ids_for_biz0(rows_by_model))

    biz_ids_for_filter = {bid for bid in normalized_biz_ids if bid != 0}
    if not biz_ids_for_filter:
        return table_ids

    # 直接按业务字段关联
    result_tables = _filter_by_field(
        rows_by_model.get("metadata.ResultTable", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(result_tables, "table_id", _normalize_str))

    time_series_groups = _filter_by_field(
        rows_by_model.get("metadata.TimeSeriesGroup", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(time_series_groups, "table_id", _normalize_str))

    event_groups = _filter_by_field(
        rows_by_model.get("metadata.EventGroup", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(event_groups, "table_id", _normalize_str))

    log_groups = _filter_by_field(
        rows_by_model.get("metadata.LogGroup", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(log_groups, "table_id", _normalize_str))

    plugin_biz_map: dict[tuple[str, str], int] = {}
    for row in rows_by_model.get("monitor_web.CollectorPluginMeta", []):
        tenant_id = _normalize_str(row.get("bk_tenant_id"))
        plugin_id = _normalize_str(row.get("plugin_id"))
        biz_id = _normalize_int(row.get("bk_biz_id"))
        if not tenant_id or not plugin_id or biz_id is None:
            continue
        plugin_biz_map[(tenant_id, plugin_id.lower())] = biz_id

    # 插件采集
    for row in rows_by_model.get("metadata.ResultTable", []):
        table_id = _normalize_str(row.get("table_id"))
        row_biz_id: int | None = None
        if not table_id:
            continue
        if "k8s_qcloud_exporter_" in table_id:
            db_name, _ = table_id.split(".", 1)
            row_biz_id = _normalize_int(db_name.rsplit("_", 1)[1])
        elif (
            table_id.startswith("exporter_")
            or table_id.startswith("script_")
            or table_id.startswith("pushgateway_")
            or table_id.startswith("jmx_")
            or table_id.startswith("snmp_")
            or table_id.startswith("datadog_")
        ):
            db_name, _ = table_id.split(".", 1)
            _plugin_type, plugin_id = db_name.split("_", 1)
            tenant_id = _normalize_str(row.get("bk_tenant_id"))
            if tenant_id:
                row_biz_id = plugin_biz_map.get((tenant_id, plugin_id))

        if row_biz_id in biz_ids_for_filter:
            table_ids.add(table_id)

    # 日志采集：bklog_index_set_ 前缀结果表直接按 bk_biz_id 判定
    for row in rows_by_model.get("metadata.ResultTable", []):
        table_id = _normalize_str(row.get("table_id"))
        if not table_id or not table_id.startswith("bklog_index_set_"):
            continue
        row_biz_id = _normalize_int(row.get("bk_biz_id"))
        if row_biz_id in biz_ids_for_filter:
            table_ids.add(table_id)

    # 自定义指标：CustomTSTable -> TimeSeriesGroup
    custom_ts_rows = _filter_by_field(
        rows_by_model.get("monitor_web.CustomTSTable", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(custom_ts_rows, "table_id", _normalize_str))
    custom_ts_group_ids = _extract_field_values(custom_ts_rows, "time_series_group_id", _normalize_int)
    if custom_ts_group_ids:
        custom_ts_groups = _filter_by_field(
            rows_by_model.get("metadata.TimeSeriesGroup", []),
            "time_series_group_id",
            custom_ts_group_ids,
            _normalize_int,
        )
        table_ids.update(_extract_field_values(custom_ts_groups, "table_id", _normalize_str))

    # 自定义事件：CustomEventGroup -> EventGroup
    custom_event_rows = _filter_by_field(
        rows_by_model.get("monitor_web.CustomEventGroup", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    table_ids.update(_extract_field_values(custom_event_rows, "table_id", _normalize_str))
    custom_event_group_ids = _extract_field_values(custom_event_rows, "bk_event_group_id", _normalize_int)
    if custom_event_group_ids:
        custom_event_groups = _filter_by_field(
            rows_by_model.get("metadata.EventGroup", []),
            "event_group_id",
            custom_event_group_ids,
            _normalize_int,
        )
        table_ids.update(_extract_field_values(custom_event_groups, "table_id", _normalize_str))

    # 日志关键字/snmp_trap：CustomEventGroup.type == keyword
    keyword_event_rows = [row for row in custom_event_rows if _normalize_str(row.get("type")) == "keyword"]
    table_ids.update(_extract_field_values(keyword_event_rows, "table_id", _normalize_str))

    # BCS 集群：BCSClusterInfo DataID -> DataSourceResultTable
    bcs_cluster_infos = _filter_by_field(
        rows_by_model.get("metadata.BCSClusterInfo", []),
        "bk_biz_id",
        biz_ids_for_filter,
        _normalize_int,
    )
    bcs_data_id_fields = (
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
        "SystemLogDataID",
        "CustomLogDataID",
    )
    bcs_data_ids: set[int] = set()
    for field_name in bcs_data_id_fields:
        bcs_data_ids.update(_extract_field_values(bcs_cluster_infos, field_name, _normalize_int))
    if bcs_data_ids:
        bcs_dsrt_rows = _filter_by_field(
            rows_by_model.get("metadata.DataSourceResultTable", []),
            "bk_data_id",
            bcs_data_ids,
            _normalize_int,
        )
        table_ids.update(_extract_field_values(bcs_dsrt_rows, "table_id", _normalize_str))

    # APM 应用：ApmDataSourceConfigBase 派生表
    apm_model_labels = (
        "apm.MetricDataSource",
        "apm.LogDataSource",
        "apm.TraceDataSource",
        "apm.ProfileDataSource",
    )
    for model_label in apm_model_labels:
        apm_rows = _filter_by_field(
            rows_by_model.get(model_label, []),
            "bk_biz_id",
            biz_ids_for_filter,
            _normalize_int,
        )
        table_ids.update(_extract_field_values(apm_rows, "result_table_id", _normalize_str))

    # 日志采集：DataSource(type_label=log) -> DataSourceResultTable -> ResultTable
    log_sources = [
        row
        for row in rows_by_model.get("metadata.DataSource", [])
        if _normalize_str(row.get("type_label")) == "log"
        and _normalize_str(row.get("source_system")) in LOG_SOURCE_SYSTEMS
    ]
    log_data_ids = _extract_field_values(log_sources, "bk_data_id", _normalize_int)
    if log_data_ids:
        log_dsrt_rows = _filter_by_field(
            rows_by_model.get("metadata.DataSourceResultTable", []),
            "bk_data_id",
            log_data_ids,
            _normalize_int,
        )
        log_table_ids = _extract_field_values(log_dsrt_rows, "table_id", _normalize_str)
        log_result_tables = _filter_by_field(
            rows_by_model.get("metadata.ResultTable", []),
            "table_id",
            log_table_ids,
            _normalize_str,
        )
        for row in log_result_tables:
            if _normalize_int(row.get("bk_biz_id")) in biz_ids_for_filter:
                table_id = _normalize_str(row.get("table_id"))
                if table_id:
                    table_ids.add(table_id)

    return {table_id for table_id in table_ids if table_id}


def get_metadata_by_table_ids(
    table_ids: set[str],
    biz_ids: set[int],
    rows_by_model: dict[str, list[RowDict]],
) -> MetadataRelationResult:
    """基于 table_ids 和 biz_ids 获取完整的 metadata 关联数据。

    Args:
        table_ids: 结果表ID集合
        biz_ids: 业务ID集合（用于 Space/BCS 相关表过滤）
        rows_by_model: 预加载的模型数据

    Returns:
        Metadata 关联数据结果。
    """
    normalized_table_ids = {tid for tid in (_normalize_str(t) for t in table_ids) if tid}
    normalized_biz_ids = {bid for bid in (_normalize_int(b) for b in biz_ids) if bid is not None}

    dsrt_rows = _filter_by_field(
        rows_by_model.get("metadata.DataSourceResultTable", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    bk_data_ids = _extract_field_values(dsrt_rows, "bk_data_id", _normalize_int)

    # BCS 相关
    bcs_cluster_infos = _filter_by_field(
        rows_by_model.get("metadata.BCSClusterInfo", []),
        "bk_biz_id",
        normalized_biz_ids,
        _normalize_int,
    )
    bcs_cluster_ids = _extract_field_values(bcs_cluster_infos, "cluster_id", _normalize_str)
    bcs_data_id_fields = (
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
        "SystemLogDataID",
        "CustomLogDataID",
    )
    for field_name in bcs_data_id_fields:
        bk_data_ids.update(_extract_field_values(bcs_cluster_infos, field_name, _normalize_int))

    pod_monitor_infos = _filter_by_field(
        rows_by_model.get("metadata.PodMonitorInfo", []),
        "cluster_id",
        bcs_cluster_ids,
        _normalize_str,
    )
    service_monitor_infos = _filter_by_field(
        rows_by_model.get("metadata.ServiceMonitorInfo", []),
        "cluster_id",
        bcs_cluster_ids,
        _normalize_str,
    )
    log_collector_infos = _filter_by_field(
        rows_by_model.get("metadata.LogCollectorInfo", []),
        "cluster_id",
        bcs_cluster_ids,
        _normalize_str,
    )
    bcs_federal_cluster_infos = _filter_by_any_field(
        rows_by_model.get("metadata.BcsFederalClusterInfo", []),
        ("host_cluster_id", "sub_cluster_id", "fed_cluster_id"),
        bcs_cluster_ids,
        _normalize_str,
    )

    # 按 bk_data_id 关联
    data_sources = _filter_by_field(
        rows_by_model.get("metadata.DataSource", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    kafka_topic_infos = _filter_by_field(
        rows_by_model.get("metadata.KafkaTopicInfo", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    data_source_options = _filter_by_field(
        rows_by_model.get("metadata.DataSourceOption", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    time_series_groups = _filter_by_field(
        rows_by_model.get("metadata.TimeSeriesGroup", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    event_groups = _filter_by_field(
        rows_by_model.get("metadata.EventGroup", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    log_groups = _filter_by_field(
        rows_by_model.get("metadata.LogGroup", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )
    space_data_sources = _filter_by_field(
        rows_by_model.get("metadata.SpaceDataSource", []),
        "bk_data_id",
        bk_data_ids,
        _normalize_int,
    )

    # 按 table_id 关联
    result_tables = _filter_by_field(
        rows_by_model.get("metadata.ResultTable", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    result_table_options = _filter_by_field(
        rows_by_model.get("metadata.ResultTableOption", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    result_table_fields = _filter_by_field(
        rows_by_model.get("metadata.ResultTableField", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    result_table_field_options = _filter_by_field(
        rows_by_model.get("metadata.ResultTableFieldOption", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    es_storages = _filter_by_field(
        rows_by_model.get("metadata.ESStorage", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    kafka_storages = _filter_by_field(
        rows_by_model.get("metadata.KafkaStorage", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    doris_storages = _filter_by_field(
        rows_by_model.get("metadata.DorisStorage", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    storage_cluster_records = _filter_by_field(
        rows_by_model.get("metadata.StorageClusterRecord", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )
    es_field_query_alias_options = _filter_by_field(
        rows_by_model.get("metadata.ESFieldQueryAliasOption", []),
        "table_id",
        normalized_table_ids,
        _normalize_str,
    )

    # 二级关联
    time_series_group_ids = _extract_field_values(time_series_groups, "time_series_group_id", _normalize_int)
    time_series_metrics = _filter_by_field(
        rows_by_model.get("metadata.TimeSeriesMetric", []),
        "group_id",
        time_series_group_ids,
        _normalize_int,
    )
    event_group_ids = _extract_field_values(event_groups, "event_group_id", _normalize_int)
    events = _filter_by_field(
        rows_by_model.get("metadata.Event", []),
        "event_group_id",
        event_group_ids,
        _normalize_int,
    )

    # 快照相关（基于 ESStorage 结果表）
    es_storage_table_ids = _extract_field_values(es_storages, "table_id", _normalize_str)
    es_snapshots = _filter_by_field(
        rows_by_model.get("metadata.EsSnapshot", []),
        "table_id",
        es_storage_table_ids,
        _normalize_str,
    )
    es_snapshot_indices = _filter_by_field(
        rows_by_model.get("metadata.EsSnapshotIndice", []),
        "table_id",
        es_storage_table_ids,
        _normalize_str,
    )
    es_snapshot_restores = _filter_by_field(
        rows_by_model.get("metadata.EsSnapshotRestore", []),
        "table_id",
        es_storage_table_ids,
        _normalize_str,
    )

    # DataLink 关联：通过 data_link_name
    bk_base_result_tables = _filter_by_field(
        rows_by_model.get("metadata.BkBaseResultTable", []),
        "monitor_table_id",
        normalized_table_ids,
        _normalize_str,
    )
    data_link_names = _extract_field_values(bk_base_result_tables, "data_link_name", _normalize_str)
    data_links = _filter_by_field(
        rows_by_model.get("metadata.DataLink", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    data_id_configs = _filter_by_field(
        rows_by_model.get("metadata.DataIdConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    data_bus_configs = _filter_by_field(
        rows_by_model.get("metadata.DataBusConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    result_table_configs = _filter_by_field(
        rows_by_model.get("metadata.ResultTableConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    vm_storage_binding_configs = _filter_by_field(
        rows_by_model.get("metadata.VMStorageBindingConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    es_storage_binding_configs = _filter_by_field(
        rows_by_model.get("metadata.ESStorageBindingConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    doris_storage_binding_configs = _filter_by_field(
        rows_by_model.get("metadata.DorisStorageBindingConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )
    conditional_sink_configs = _filter_by_field(
        rows_by_model.get("metadata.ConditionalSinkConfig", []),
        "data_link_name",
        data_link_names,
        _normalize_str,
    )

    # Space 关联：space_type_id == "bkcc" && space_id in biz_ids
    space_keys = {("bkcc", str(biz_id)) for biz_id in normalized_biz_ids}
    spaces = _filter_by_fields(
        rows_by_model.get("metadata.Space", []),
        ("space_type_id", "space_id"),
        space_keys,
        _normalize_str,
    )
    space_key_from_spaces = {
        (str(row.get("space_type_id")), str(row.get("space_id")))
        for row in spaces
        if row.get("space_type_id") is not None and row.get("space_id") is not None
    }
    space_uids = {f"{space_type_id}__{space_id}" for space_type_id, space_id in space_key_from_spaces}
    space_resources = _filter_by_fields(
        rows_by_model.get("metadata.SpaceResource", []),
        ("space_type_id", "space_id"),
        space_key_from_spaces,
        _normalize_str,
    )
    space_vm_infos = _filter_by_fields(
        rows_by_model.get("metadata.SpaceVMInfo", []),
        ("space_type", "space_id"),
        space_key_from_spaces,
        _normalize_str,
    )
    space_related_storage_infos = _filter_by_fields(
        rows_by_model.get("metadata.SpaceRelatedStorageInfo", []),
        ("space_type_id", "space_id"),
        space_key_from_spaces,
        _normalize_str,
    )
    bk_app_space_records = _filter_by_field(
        rows_by_model.get("metadata.BkAppSpaceRecord", []),
        "space_uid",
        space_uids,
        _normalize_str,
    )

    return MetadataRelationResult(
        data_source_result_tables=dsrt_rows,
        data_sources=data_sources,
        kafka_topic_infos=kafka_topic_infos,
        data_source_options=data_source_options,
        time_series_groups=time_series_groups,
        event_groups=event_groups,
        log_groups=log_groups,
        space_data_sources=space_data_sources,
        result_tables=result_tables,
        result_table_options=result_table_options,
        result_table_fields=result_table_fields,
        result_table_field_options=result_table_field_options,
        es_storages=es_storages,
        kafka_storages=kafka_storages,
        doris_storages=doris_storages,
        storage_cluster_records=storage_cluster_records,
        es_field_query_alias_options=es_field_query_alias_options,
        time_series_metrics=time_series_metrics,
        events=events,
        es_snapshots=es_snapshots,
        es_snapshot_indices=es_snapshot_indices,
        es_snapshot_restores=es_snapshot_restores,
        bk_base_result_tables=bk_base_result_tables,
        data_links=data_links,
        data_id_configs=data_id_configs,
        data_bus_configs=data_bus_configs,
        result_table_configs=result_table_configs,
        vm_storage_binding_configs=vm_storage_binding_configs,
        es_storage_binding_configs=es_storage_binding_configs,
        doris_storage_binding_configs=doris_storage_binding_configs,
        conditional_sink_configs=conditional_sink_configs,
        spaces=spaces,
        space_resources=space_resources,
        space_vm_infos=space_vm_infos,
        space_related_storage_infos=space_related_storage_infos,
        bk_app_space_records=bk_app_space_records,
        bcs_cluster_infos=bcs_cluster_infos,
        pod_monitor_infos=pod_monitor_infos,
        service_monitor_infos=service_monitor_infos,
        log_collector_infos=log_collector_infos,
        bcs_federal_cluster_infos=bcs_federal_cluster_infos,
    )


# =====================================================================
# Metadata 业务过滤核心函数
# =====================================================================


def _build_metadata_relation_caches(
    rows_by_model: dict[str, list[RowDict]],
) -> tuple[
    dict[str, int],  # table_id_to_biz
    dict[int, int],  # data_id_to_biz
    dict[tuple[str, str], int],  # space_key_to_biz
    dict[str, int],  # cluster_id_to_biz
    dict[str, int],  # data_link_name_to_biz
]:
    """构建 metadata 关联缓存。

    从核心表中构建关联键到业务ID的映射，供过滤函数使用。

    Args:
        rows_by_model: 预加载的模型数据

    Returns:
        关联缓存的元组：
        - table_id_to_biz: table_id -> bk_biz_id
        - data_id_to_biz: bk_data_id -> bk_biz_id
        - space_key_to_biz: (space_type_id, space_id) -> bk_biz_id
        - cluster_id_to_biz: cluster_id -> bk_biz_id
        - data_link_name_to_biz: data_link_name -> bk_biz_id
    """
    table_id_to_biz: dict[str, int] = {}
    data_id_to_biz: dict[int, int] = {}
    space_key_to_biz: dict[tuple[str, str], int] = {}
    cluster_id_to_biz: dict[str, int] = {}
    data_link_name_to_biz: dict[str, int] = {}

    # 从 ResultTable 构建 table_id -> bk_biz_id 映射
    for row in rows_by_model.get("metadata.ResultTable", []):
        biz_id = _normalize_int(row.get("bk_biz_id"))
        table_id = _normalize_str(row.get("table_id"))
        if biz_id is not None and table_id:
            table_id_to_biz[table_id] = biz_id

    # 从 TimeSeriesGroup/EventGroup/LogGroup 补充 table_id 和 bk_data_id 映射
    for model_label in ("metadata.TimeSeriesGroup", "metadata.EventGroup", "metadata.LogGroup"):
        for row in rows_by_model.get(model_label, []):
            biz_id = _normalize_int(row.get("bk_biz_id"))
            table_id = _normalize_str(row.get("table_id"))
            data_id = _normalize_int(row.get("bk_data_id"))
            if biz_id is not None:
                if table_id:
                    table_id_to_biz.setdefault(table_id, biz_id)
                if data_id is not None:
                    data_id_to_biz.setdefault(data_id, biz_id)

    # 从 BCSClusterInfo 构建 cluster_id -> bk_biz_id 映射和 DataID 映射
    bcs_data_id_fields = (
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
        "SystemLogDataID",
        "CustomLogDataID",
    )
    for row in rows_by_model.get("metadata.BCSClusterInfo", []):
        biz_id = _normalize_int(row.get("bk_biz_id"))
        cluster_id = _normalize_str(row.get("cluster_id"))
        if biz_id is not None:
            if cluster_id:
                cluster_id_to_biz[cluster_id] = biz_id
            # 收集 BCS 的 DataID
            for field_name in bcs_data_id_fields:
                data_id = _normalize_int(row.get(field_name))
                if data_id is not None:
                    data_id_to_biz.setdefault(data_id, biz_id)

    # 构建 Space 关联缓存
    # 当 space_type_id == "bkcc" 时，space_id 就是业务ID
    for row in rows_by_model.get("metadata.Space", []):
        space_type_id = _normalize_str(row.get("space_type_id"))
        space_id = _normalize_str(row.get("space_id"))
        if space_type_id and space_id:
            space_key = (space_type_id, space_id)
            if space_type_id == "bkcc":
                biz_id = _normalize_int(space_id)
                if biz_id is not None:
                    space_key_to_biz[space_key] = biz_id

    # 从 BkBaseResultTable 构建 data_link_name 映射
    for row in rows_by_model.get("metadata.BkBaseResultTable", []):
        monitor_table_id = _normalize_str(row.get("monitor_table_id"))
        data_link_name = _normalize_str(row.get("data_link_name"))
        if monitor_table_id and data_link_name and monitor_table_id in table_id_to_biz:
            biz_id = table_id_to_biz[monitor_table_id]
            data_link_name_to_biz[data_link_name] = biz_id

    return (
        table_id_to_biz,
        data_id_to_biz,
        space_key_to_biz,
        cluster_id_to_biz,
        data_link_name_to_biz,
    )


def _should_keep_row(biz_id: int | None, target_biz_ids: set[int], mode: FilterMode) -> bool:
    """判断是否保留数据行。

    Args:
        biz_id: 数据行的业务ID（可能为 None）
        target_biz_ids: 目标业务ID集合
        mode: 过滤模式
            - "include": 只保留指定业务的数据
            - "exclude": 排除指定业务的数据

    Returns:
        是否保留该数据行
    """
    if mode == "include":
        return biz_id is not None and biz_id in target_biz_ids
    else:  # exclude
        return biz_id is None or biz_id not in target_biz_ids


def _collect_retained_group_ids(
    rows_by_model: dict[str, list[RowDict]],
    target_biz_ids: set[int],
) -> dict[str, set[int]]:
    """收集保留的父表 group_id（用于二级关联表过滤）。

    预先处理 TimeSeriesGroup 和 EventGroup，收集保留的 group_id，
    以便后续过滤 TimeSeriesMetric 和 Event 等二级关联表。

    Args:
        rows_by_model: 预加载的模型数据
        target_biz_ids: 目标业务ID集合
    Returns:
        父表ID字段名 -> 保留的ID集合的映射
        例如: {"time_series_group_id": {1, 2, 3}, "event_group_id": {4, 5, 6}}
    """
    normalized_biz_ids = {bid for bid in (_normalize_int(b) for b in target_biz_ids) if bid is not None}
    biz_to_table_ids = {biz_id: get_table_ids_by_biz({biz_id}, rows_by_model) for biz_id in normalized_biz_ids}
    target_table_ids: set[str] = set().union(*biz_to_table_ids.values()) if biz_to_table_ids else set()

    def _should_keep_by_table_id(table_id: str | None) -> bool:
        return bool(table_id) and table_id in target_table_ids

    result: dict[str, set[int]] = {}

    # TimeSeriesGroup -> time_series_group_id
    ts_group_rows = rows_by_model.get("metadata.TimeSeriesGroup", [])
    retained_ts_group_ids: set[int] = set()
    for row in ts_group_rows:
        table_id = _normalize_str(row.get("table_id"))
        if _should_keep_by_table_id(table_id):
            group_id = _normalize_int(row.get("time_series_group_id"))
            if group_id is not None:
                retained_ts_group_ids.add(group_id)
    result["time_series_group_id"] = retained_ts_group_ids

    # EventGroup -> event_group_id
    event_group_rows = rows_by_model.get("metadata.EventGroup", [])
    retained_event_group_ids: set[int] = set()
    for row in event_group_rows:
        table_id = _normalize_str(row.get("table_id"))
        if _should_keep_by_table_id(table_id):
            group_id = _normalize_int(row.get("event_group_id"))
            if group_id is not None:
                retained_event_group_ids.add(group_id)
    result["event_group_id"] = retained_event_group_ids

    return result


def _filter_metadata_rows_by_biz(
    rows_by_model: dict[str, list[RowDict]],
    biz_ids: set[int],
    mode: FilterMode,
    biz_tenant_mapping: dict[int, str] | None = None,
    default_tenant_id: str = "system",
    relation_rows_by_model: dict[str, list[RowDict]] | None = None,
) -> dict[str, list[RowDict]]:
    """按业务过滤 metadata 数据并替换租户ID

    exclude模式:
    1. 全局表直接保留，不做业务过滤
    2. 按 biz_ids 排除指定业务的数据
    3. 按 biz_tenant_mapping 替换租户ID
    4. 默认使用 default_tenant_id

    include模式:
    1. 全局表全部剔除
    2. 按 biz_ids 保留指定业务的数据
    3. 按 biz_tenant_mapping 替换租户ID
    4. 默认使用 default_tenant_id

    先生成业务ID与table_ids的映射，然后通过table_id确定数据的业务归属。

    """
    if biz_tenant_mapping is None:
        biz_tenant_mapping = {}

    relation_rows = relation_rows_by_model or rows_by_model

    normalized_biz_ids = {bid for bid in (_normalize_int(b) for b in biz_ids) if bid is not None}
    sorted_biz_ids = sorted(normalized_biz_ids)

    # 生成业务与 table_id 的映射（复用 get_table_ids_by_biz 的业务归属逻辑）
    biz_to_table_ids: dict[int, set[str]] = {
        biz_id: get_table_ids_by_biz({biz_id}, relation_rows) for biz_id in sorted_biz_ids
    }
    target_table_ids: set[str] = set().union(*biz_to_table_ids.values()) if biz_to_table_ids else set()

    # table_id -> biz_id 映射（用于租户替换）
    table_id_to_biz: dict[str, int] = {}
    for biz_id in sorted_biz_ids:
        for table_id in biz_to_table_ids.get(biz_id, set()):
            table_id_to_biz.setdefault(table_id, biz_id)

    # table_id -> biz_id（全量 ResultTable，用于补充租户替换）
    table_id_to_biz_all: dict[str, int] = {}
    for row in relation_rows.get("metadata.ResultTable", []):
        biz_id = _normalize_int(row.get("bk_biz_id"))
        table_id = _normalize_str(row.get("table_id"))
        if biz_id is not None and table_id:
            table_id_to_biz_all.setdefault(table_id, biz_id)

    def _should_keep_by_table_id(table_id: str | None) -> bool:
        if mode == "include":
            return bool(table_id) and table_id in target_table_ids
        return table_id is None or table_id not in target_table_ids

    # 基于 table_id 反推 data_id（用于 DataSource 等表）
    target_data_ids: set[int] = set()
    for row in relation_rows.get("metadata.DataSourceResultTable", []):
        table_id = _normalize_str(row.get("table_id"))
        data_id = _normalize_int(row.get("bk_data_id"))
        if table_id in target_table_ids and data_id is not None:
            target_data_ids.add(data_id)
    for model_label in ("metadata.TimeSeriesGroup", "metadata.EventGroup", "metadata.LogGroup"):
        for row in relation_rows.get(model_label, []):
            table_id = _normalize_str(row.get("table_id"))
            data_id = _normalize_int(row.get("bk_data_id"))
            if table_id in target_table_ids and data_id is not None:
                target_data_ids.add(data_id)

    data_id_to_biz_all: dict[int, int] = {}
    for row in relation_rows.get("metadata.DataSourceResultTable", []):
        table_id = _normalize_str(row.get("table_id"))
        data_id = _normalize_int(row.get("bk_data_id"))
        if data_id is None:
            continue
        biz_id = table_id_to_biz_all.get(table_id) if table_id else None
        if biz_id is not None:
            data_id_to_biz_all.setdefault(data_id, biz_id)

    # BCS 关联缓存
    bcs_data_id_fields = (
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
        "SystemLogDataID",
        "CustomLogDataID",
    )
    cluster_id_to_biz_all: dict[str, int] = {}
    target_cluster_ids: set[str] = set()
    for row in relation_rows.get("metadata.BCSClusterInfo", []):
        cluster_id = _normalize_str(row.get("cluster_id"))
        row_data_ids = {
            _normalize_int(row.get(field_name))
            for field_name in bcs_data_id_fields
            if _normalize_int(row.get(field_name)) is not None
        }
        if cluster_id and any(data_id in target_data_ids for data_id in row_data_ids):
            target_cluster_ids.add(cluster_id)

        biz_id = None
        for data_id in row_data_ids:
            if data_id in data_id_to_biz_all:
                biz_id = data_id_to_biz_all[data_id]
                break
        if biz_id is not None and cluster_id:
            cluster_id_to_biz_all.setdefault(cluster_id, biz_id)

    # DataLink 关联缓存
    data_link_name_to_biz_all: dict[str, int] = {}
    target_data_link_names: set[str] = set()
    for row in relation_rows.get("metadata.BkBaseResultTable", []):
        monitor_table_id = _normalize_str(row.get("monitor_table_id"))
        data_link_name = _normalize_str(row.get("data_link_name"))
        if not monitor_table_id or not data_link_name:
            continue
        biz_id = table_id_to_biz_all.get(monitor_table_id)
        if biz_id is not None:
            data_link_name_to_biz_all.setdefault(data_link_name, biz_id)
        if monitor_table_id in target_table_ids:
            target_data_link_names.add(data_link_name)

    # Space 关联缓存（仅支持 bkcc -> biz_id）
    space_key_to_biz_all: dict[tuple[str, str], int] = {}
    space_uid_to_biz_all: dict[str, int] = {}
    for row in relation_rows.get("metadata.Space", []):
        space_type_id = _normalize_str(row.get("space_type_id"))
        space_id = _normalize_str(row.get("space_id"))
        if not space_type_id or not space_id:
            continue
        if space_type_id == "bkcc":
            biz_id = _normalize_int(space_id)
            if biz_id is not None:
                space_key = (space_type_id, space_id)
                space_key_to_biz_all.setdefault(space_key, biz_id)
                space_uid_to_biz_all.setdefault(f"{space_type_id}__{space_id}", biz_id)

    # 二级关联表需要保留的 group_id
    retained_group_ids = _collect_retained_group_ids(relation_rows, normalized_biz_ids)
    group_id_to_biz_all: dict[int, int] = {}
    for model_label, id_field in (
        ("metadata.TimeSeriesGroup", "time_series_group_id"),
        ("metadata.EventGroup", "event_group_id"),
    ):
        for row in relation_rows.get(model_label, []):
            group_id = _normalize_int(row.get(id_field))
            biz_id = _normalize_int(row.get("bk_biz_id"))
            if group_id is not None and biz_id is not None:
                group_id_to_biz_all.setdefault(group_id, biz_id)

    result: dict[str, list[RowDict]] = {}

    for model_label, rows in rows_by_model.items():
        if not model_label.startswith("metadata."):
            result[model_label] = rows
            continue

        if model_label in METADATA_GLOBAL_TABLES:
            if mode == "exclude":
                for row in rows:
                    _replace_tenant_id_in_row(row, None, biz_tenant_mapping, default_tenant_id)
                result[model_label] = rows
            else:
                result[model_label] = []
            continue

        filtered_rows: list[RowDict] = []

        if model_label in METADATA_TABLES_WITH_BIZ_ID:
            for row in rows:
                biz_id = _normalize_int(row.get("bk_biz_id"))
                if not _should_keep_row(biz_id, normalized_biz_ids, mode):
                    continue
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        table_id_field = None
        for field_name, tables in METADATA_TABLES_BY_TABLE_ID.items():
            if model_label in tables:
                table_id_field = field_name
                break
        if table_id_field:
            for row in rows:
                table_id = _normalize_str(row.get(table_id_field))
                if not _should_keep_by_table_id(table_id):
                    continue
                biz_id = None
                if table_id:
                    biz_id = table_id_to_biz.get(table_id) or table_id_to_biz_all.get(table_id)
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        if model_label in METADATA_TABLES_BY_DATA_ID:
            for row in rows:
                data_id = _normalize_int(row.get("bk_data_id"))
                if mode == "include":
                    should_keep = data_id is not None and data_id in target_data_ids
                else:
                    should_keep = data_id is None or data_id not in target_data_ids
                if not should_keep:
                    continue
                biz_id = data_id_to_biz_all.get(data_id) if data_id is not None else None
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        space_fields = None
        for field_names, tables in METADATA_SPACE_TABLES.items():
            if model_label in tables:
                space_fields = field_names
                break
        if space_fields:
            for row in rows:
                space_type = _normalize_str(row.get(space_fields[0]))
                space_id = _normalize_str(row.get(space_fields[1]))
                biz_id = None
                if space_type and space_id:
                    space_key = (space_type, space_id)
                    biz_id = space_key_to_biz_all.get(space_key)
                if not _should_keep_row(biz_id, normalized_biz_ids, mode):
                    continue
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        if model_label in METADATA_SPACE_UID_TABLES:
            for row in rows:
                space_uid = _normalize_str(row.get("space_uid"))
                biz_id = space_uid_to_biz_all.get(space_uid) if space_uid else None
                if not _should_keep_row(biz_id, normalized_biz_ids, mode):
                    continue
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        bcs_field = None
        for field_name, tables in METADATA_BCS_TABLES.items():
            if model_label in tables:
                bcs_field = field_name
                break
        if bcs_field:
            for row in rows:
                cluster_id = _normalize_str(row.get(bcs_field))
                if mode == "include":
                    should_keep = cluster_id is not None and cluster_id in target_cluster_ids
                else:
                    should_keep = cluster_id is None or cluster_id not in target_cluster_ids
                if not should_keep:
                    continue
                biz_id = cluster_id_to_biz_all.get(cluster_id) if cluster_id else None
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        if model_label in METADATA_BCS_FEDERAL_TABLES:
            for row in rows:
                cluster_ids = (
                    _normalize_str(row.get("host_cluster_id")),
                    _normalize_str(row.get("sub_cluster_id")),
                    _normalize_str(row.get("fed_cluster_id")),
                )
                if mode == "include":
                    should_keep = any(cid in target_cluster_ids for cid in cluster_ids if cid)
                else:
                    should_keep = not any(cid in target_cluster_ids for cid in cluster_ids if cid)
                if not should_keep:
                    continue
                biz_id = None
                for cid in cluster_ids:
                    if cid in cluster_id_to_biz_all:
                        biz_id = cluster_id_to_biz_all[cid]
                        break
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        if model_label in METADATA_DATALINK_TABLES:
            for row in rows:
                data_link_name = _normalize_str(row.get("data_link_name"))
                if mode == "include":
                    should_keep = data_link_name is not None and data_link_name in target_data_link_names
                else:
                    should_keep = data_link_name is None or data_link_name not in target_data_link_names
                if not should_keep:
                    continue
                biz_id = data_link_name_to_biz_all.get(data_link_name) if data_link_name else None
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        if model_label in METADATA_SECONDARY_TABLES:
            relation_field, source_id_field = METADATA_SECONDARY_TABLES[model_label]
            retained_ids = retained_group_ids.get(source_id_field, set())
            for row in rows:
                source_id = _normalize_int(row.get(relation_field))
                if mode == "include":
                    should_keep = source_id is not None and source_id in retained_ids
                else:
                    should_keep = source_id is None or source_id not in retained_ids
                if not should_keep:
                    continue
                biz_id = group_id_to_biz_all.get(source_id) if source_id is not None else None
                _replace_tenant_id_in_row(row, biz_id, biz_tenant_mapping, default_tenant_id)
                filtered_rows.append(row)
            result[model_label] = filtered_rows
            continue

        # 未分类的 metadata 表：include 模式丢弃，exclude 模式保留
        if mode == "exclude":
            for row in rows:
                _replace_tenant_id_in_row(row, None, biz_tenant_mapping, default_tenant_id)
            result[model_label] = rows
        else:
            result[model_label] = []

    return result


def filter_metadata_by_biz(
    rows_by_model: dict[str, list[RowDict]],
    excluded_biz_ids: set[int] | None = None,
    biz_tenant_mapping: dict[int, str] | None = None,
    default_tenant_id: str = "system",
    relation_rows_by_model: dict[str, list[RowDict]] | None = None,
) -> dict[str, list[RowDict]]:
    """按业务排除 metadata 数据并替换租户ID（反向过滤）。

    处理逻辑：
    1. 全局表直接保留，不做业务过滤
    2. 按 excluded_biz_ids 排除指定业务的数据
    3. 按 biz_tenant_mapping 替换租户ID

    Args:
        rows_by_model: 预加载的模型数据（仅处理 metadata.* 表）
        excluded_biz_ids: 需要排除的业务ID集合
        biz_tenant_mapping: 业务ID到租户ID的映射
        default_tenant_id: 默认租户ID

    Returns:
        过滤并处理后的模型数据
    """
    return _filter_metadata_rows_by_biz(
        rows_by_model,
        biz_ids=excluded_biz_ids or set(),
        mode="exclude",
        biz_tenant_mapping=biz_tenant_mapping,
        default_tenant_id=default_tenant_id,
        relation_rows_by_model=relation_rows_by_model,
    )


def get_metadata_by_biz(
    rows_by_model: dict[str, list[RowDict]],
    biz_ids: set[int],
    biz_tenant_mapping: dict[int, str] | None = None,
    default_tenant_id: str = "system",
    relation_rows_by_model: dict[str, list[RowDict]] | None = None,
) -> dict[str, list[RowDict]]:
    """按业务获取 metadata 数据并替换租户ID（正向过滤）。

    处理逻辑：
    1. 全局表去掉（只取业务相关数据）
    2. 只保留指定业务的数据
    3. 按 biz_tenant_mapping 替换租户ID

    Args:
        rows_by_model: 预加载的模型数据（仅处理 metadata.* 表）
        biz_ids: 需要获取的业务ID集合
        biz_tenant_mapping: 业务ID到租户ID的映射
        default_tenant_id: 默认租户ID

    Returns:
        过滤并处理后的模型数据
    """
    return _filter_metadata_rows_by_biz(
        rows_by_model,
        biz_ids=biz_ids,
        mode="include",
        biz_tenant_mapping=biz_tenant_mapping,
        default_tenant_id=default_tenant_id,
        relation_rows_by_model=relation_rows_by_model,
    )


def get_global_metadata(
    rows_by_model: dict[str, list[RowDict]],
    all_biz_ids: set[int],
    biz_tenant_mapping: dict[int, str] | None = None,
    default_tenant_id: str = "system",
    relation_rows_by_model: dict[str, list[RowDict]] | None = None,
) -> dict[str, list[RowDict]]:
    """获取全局 metadata 数据（排除所有业务数据后的剩余数据）。

    Args:
        rows_by_model: 预加载的模型数据（仅处理 metadata.* 表）。
        all_biz_ids: 所有业务ID集合。
        biz_tenant_mapping: 业务ID到租户ID的映射。
        default_tenant_id: 默认租户ID。
        relation_rows_by_model: 用于关联推导的模型数据。

    Returns:
        过滤后的全局 metadata 数据。
    """
    return _filter_metadata_rows_by_biz(
        rows_by_model,
        biz_ids=all_biz_ids,
        mode="exclude",
        biz_tenant_mapping=biz_tenant_mapping,
        default_tenant_id=default_tenant_id,
        relation_rows_by_model=relation_rows_by_model,
    )
