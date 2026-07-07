from __future__ import annotations

import re
import shutil
from collections import OrderedDict
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apm.models import (
    ApdexConfig,
    ApmApplication,
    ApmInstanceDiscover,
    ApmMetricDimension,
    ApmTopoDiscoverRule,
    BcsClusterDefaultApplicationRelation,
    BkdataFlowConfig,
    CustomServiceConfig,
    DbConfig,
    EbpfApplicationConfig,
    LicenseConfig,
    LogDataSource,
    MetricDataSource,
    NormalTypeValueConfig,
    ProbeConfig,
    ProfileDataSource,
    ProfileService,
    QpsConfig,
    RemoteServiceDiscover,
    SamplerConfig,
    SubscriptionConfig,
    TraceDataSource,
)
from apm_web.models import (
    ApdexServiceRelation,
    ApmMetaConfig,
    Application as ApmWebApplication,
    ApplicationCustomService,
    ApplicationRelationInfo,
    AppServiceRelation,
    CMDBServiceRelation,
    CodeRedefinedConfigRelation,
    EventServiceRelation,
    LogServiceRelation,
    ProfileUploadRecord,
    StrategyInstance,
    StrategyTemplate,
    TraceComparison,
    UriServiceRelation,
)
from metadata.models import (
    BCSClusterInfo,
    ClusterInfo,
    DataSource,
    DataSourceResultTable,
    EventGroup,
    ResultTable,
    StorageClusterRecord,
    TimeSeriesGroup,
)
from metadata.models.bcs.cluster import BcsFederalClusterInfo
from metadata.models.bcs.resource import LogCollectorInfo, PodMonitorInfo, ServiceMonitorInfo
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.storage import ESStorage
from monitor_web.data_migrate.constants import DEFAULT_ENCODING
from monitor_web.data_migrate.data_export import (
    _build_cluster_export_refs,
    _build_data_source_export_refs,
    _build_scope_export_stats,
    _build_table_export_refs,
    _iter_fetcher_objects,
    _peek_export_objects,
    _track_scope_model_counts,
    _write_fixture_file,
)
from monitor_web.data_migrate.data_import import import_biz_data_from_directory
from monitor_web.data_migrate.data_rebuilder import (
    DEFAULT_ES_CLUSTER_NAMES,
    DEFAULT_KAFKA_CLUSTER_NAMES,
    _register_data_source,
    get_data_id_to_cluster_name,
    rebuild_event_group,
    rebuild_time_series_group,
)
from monitor_web.data_migrate.fetcher.base import FetcherResultType
from monitor_web.data_migrate.fetcher.metadata.data_source import (
    get_metadata_data_source_fetcher,
    get_metadata_result_table_fetcher,
)
from monitor_web.data_migrate.fetcher.metadata.storage import get_metadata_storage_by_table_ids_fetcher
from monitor_web.data_migrate.utils import read_json_file, write_json_file
from monitor_web.models.custom_report import (
    CustomEventGroup,
    CustomEventItem,
    CustomTSField,
    CustomTSGroupingRule,
    CustomTSItem,
    CustomTSTable,
)

INVALID_DATA_ID_VALUES = {None, 0, -1}
INVALID_TABLE_ID_VALUES = {None, ""}
PARTIAL_DATA_ID_INFOS_FILE = "partial_data_id_infos.json"
APM_APPLICATION_STORAGE_CONFIG_KEYS = (
    ApmWebApplication.APPLICATION_DATASOURCE_CONFIG_KEY,
    ApmWebApplication.APPLICATION_LOG_DATASOURCE_CONFIG_KEY,
)


@dataclass
class PartialMigrationContext:
    """局部迁移解析结果。"""

    module_fetchers: OrderedDict[str, list[FetcherResultType]]
    manifest_scope: dict[str, Any]
    refs: dict[str, dict[str, Any]]


def _normalize_ints(values: Sequence[int] | None) -> list[int]:
    normalized_values: list[int] = []
    seen: set[int] = set()
    for value in values or []:
        normalized_value = int(value)
        if normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)
    return normalized_values


def _normalize_strings(values: Sequence[str] | None) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        normalized_value = str(value).strip()
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)
    return normalized_values


def _add_valid_data_ids(container: set[int], values: Sequence[int | None]) -> None:
    for value in values:
        if value not in INVALID_DATA_ID_VALUES:
            container.add(int(value))


def _add_valid_table_ids(container: set[str], values: Sequence[str | None]) -> None:
    for value in values:
        if value not in INVALID_TABLE_ID_VALUES:
            container.add(str(value))


def _get_table_ids_by_data_ids(bk_tenant_id: str, data_ids: Sequence[int]) -> set[str]:
    table_ids = set(
        DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id__in=list(data_ids),
        )
        .values_list("table_id", flat=True)
        .distinct()
    )
    if not table_ids:
        return table_ids

    table_ids.update(
        ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id__in=table_ids)
        .exclude(table_id__in=table_ids)
        .values_list("table_id", flat=True)
        .distinct()
    )
    return table_ids


def _build_data_id_infos(bk_tenant_id: str, data_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
    normalized_data_ids = _normalize_ints([data_id for data_id in data_ids if data_id not in INVALID_DATA_ID_VALUES])
    if not normalized_data_ids:
        return {}

    data_id_to_topic_name = {
        data_source.bk_data_id: data_source.mq_config.topic
        for data_source in DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id__in=normalized_data_ids,
        )
    }
    data_id_to_cluster_name = get_data_id_to_cluster_name(
        bk_tenant_id=bk_tenant_id,
        bk_data_ids=list(data_id_to_topic_name.keys()),
    )
    return {
        data_id: {
            "data_id": data_id,
            "topic_name": data_id_to_topic_name[data_id],
            "kafka_cluster_name": data_id_to_cluster_name[data_id],
        }
        for data_id in normalized_data_ids
        if data_id in data_id_to_topic_name and data_id in data_id_to_cluster_name
    }


def _collect_current_partial_data_ids(
    bk_tenant_id: str,
    bk_biz_id: int,
    refs: dict[str, dict[str, Any]],
    table_ids: Sequence[str],
) -> list[int]:
    data_ids: set[int] = set()
    normalized_table_ids = _normalize_strings(table_ids)
    if normalized_table_ids:
        _add_valid_data_ids(
            data_ids,
            list(
                DataSourceResultTable.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    table_id__in=normalized_table_ids,
                )
                .values_list("bk_data_id", flat=True)
                .distinct()
            ),
        )

    bcs_refs = refs.get("bcs") or {}
    cluster_ids = _normalize_strings(bcs_refs.get("cluster_ids") or [])
    if cluster_ids:
        for cluster in BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            cluster_id__in=cluster_ids,
        ):
            _add_valid_data_ids(
                data_ids,
                [
                    cluster.K8sMetricDataID,
                    cluster.CustomMetricDataID,
                    cluster.K8sEventDataID,
                    cluster.CustomEventDataID,
                    cluster.SystemLogDataID,
                    cluster.CustomLogDataID,
                ],
            )

    custom_refs = refs.get("custom_report") or {}
    time_series_group_ids = _normalize_ints(custom_refs.get("time_series_group_ids") or [])
    if time_series_group_ids:
        _add_valid_data_ids(
            data_ids,
            list(
                TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    time_series_group_id__in=time_series_group_ids,
                ).values_list("bk_data_id", flat=True)
            ),
        )
        _add_valid_data_ids(
            data_ids,
            list(
                CustomTSTable.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    time_series_group_id__in=time_series_group_ids,
                ).values_list("bk_data_id", flat=True)
            ),
        )

    event_group_ids = _normalize_ints(custom_refs.get("event_group_ids") or [])
    if event_group_ids:
        _add_valid_data_ids(
            data_ids,
            list(
                EventGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    event_group_id__in=event_group_ids,
                ).values_list("bk_data_id", flat=True)
            ),
        )
        _add_valid_data_ids(
            data_ids,
            list(
                CustomEventGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    bk_event_group_id__in=event_group_ids,
                ).values_list("bk_data_id", flat=True)
            ),
        )

    apm_refs = refs.get("apm") or {}
    app_names = _normalize_strings(apm_refs.get("app_names") or [])
    if app_names:
        for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
            _add_valid_data_ids(
                data_ids,
                list(
                    model.objects.filter(
                        bk_biz_id=bk_biz_id,
                        app_name__in=app_names,
                    ).values_list("bk_data_id", flat=True)
                ),
            )

    return sorted(data_ids)


def _build_bcs_refs_and_fetchers(
    bk_tenant_id: str,
    bk_biz_id: int,
    bcs_cluster_ids: Sequence[str],
) -> tuple[dict[str, Any], list[FetcherResultType]]:
    cluster_ids = _normalize_strings(bcs_cluster_ids)
    if not cluster_ids:
        return {}, []

    clusters = list(
        BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            cluster_id__in=cluster_ids,
        )
    )
    found_cluster_ids = {cluster.cluster_id for cluster in clusters}
    missing_cluster_ids = sorted(set(cluster_ids) - found_cluster_ids)
    if missing_cluster_ids:
        raise ValueError(f"未找到这些 BCS 集群: {missing_cluster_ids}")

    metric_data_ids: set[int] = set()
    event_data_ids: set[int] = set()
    log_data_ids: set[int] = set()
    for cluster in clusters:
        _add_valid_data_ids(metric_data_ids, [cluster.K8sMetricDataID, cluster.CustomMetricDataID])
        _add_valid_data_ids(event_data_ids, [cluster.K8sEventDataID, cluster.CustomEventDataID])
        _add_valid_data_ids(log_data_ids, [cluster.SystemLogDataID, cluster.CustomLogDataID])

    federal_cluster_ids = BcsFederalClusterInfo.objects.filter(
        Q(fed_cluster_id__in=cluster_ids) | Q(host_cluster_id__in=cluster_ids) | Q(sub_cluster_id__in=cluster_ids)
    ).values_list("id", flat=True)
    fetchers: list[FetcherResultType] = [
        (BCSClusterInfo, {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "cluster_id__in": cluster_ids}, None),
        (BcsFederalClusterInfo, {"id__in": federal_cluster_ids}, None),
        (ServiceMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (PodMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (LogCollectorInfo, {"cluster_id__in": cluster_ids}, None),
    ]
    return (
        {
            "cluster_ids": sorted(found_cluster_ids),
            "metric_data_ids": sorted(metric_data_ids),
            "event_data_ids": sorted(event_data_ids),
            "log_data_ids": sorted(log_data_ids),
        },
        fetchers,
    )


def _build_custom_report_refs_and_fetchers(
    bk_tenant_id: str,
    bk_biz_id: int,
    custom_report_data_ids: Sequence[int],
) -> tuple[dict[str, Any], list[FetcherResultType]]:
    data_ids = _normalize_ints(custom_report_data_ids)
    if not data_ids:
        return {}, []

    ts_tables = list(
        CustomTSTable.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_id__in=data_ids,
        )
    )
    event_groups = list(
        CustomEventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_id__in=data_ids,
        )
    )
    found_data_ids = {ts_table.bk_data_id for ts_table in ts_tables} | {
        event_group.bk_data_id for event_group in event_groups
    }
    missing_data_ids = sorted(set(data_ids) - found_data_ids)
    if missing_data_ids:
        raise ValueError(f"未找到这些自定义上报 Data ID: {missing_data_ids}")

    time_series_group_ids = [ts_table.time_series_group_id for ts_table in ts_tables]
    event_group_ids = [event_group.bk_event_group_id for event_group in event_groups]
    table_ids: set[str] = set()
    _add_valid_table_ids(table_ids, [ts_table.table_id for ts_table in ts_tables])
    _add_valid_table_ids(table_ids, [event_group.table_id for event_group in event_groups])
    table_ids.update(_get_table_ids_by_data_ids(bk_tenant_id=bk_tenant_id, data_ids=sorted(found_data_ids)))

    fetchers: list[FetcherResultType] = [
        (CustomEventGroup, {"bk_event_group_id__in": event_group_ids}, None),
        (CustomEventItem, {"bk_event_group_id__in": event_group_ids}, None),
        (CustomTSTable, {"time_series_group_id__in": time_series_group_ids}, None),
        (CustomTSField, {"time_series_group_id__in": time_series_group_ids}, None),
        (CustomTSItem, {"table_id__in": time_series_group_ids}, None),
        (CustomTSGroupingRule, {"time_series_group_id__in": time_series_group_ids}, None),
    ]
    return (
        {
            "data_ids": sorted(found_data_ids),
            "metric_data_ids": sorted({ts_table.bk_data_id for ts_table in ts_tables}),
            "event_data_ids": sorted({event_group.bk_data_id for event_group in event_groups}),
            "time_series_group_ids": sorted(time_series_group_ids),
            "event_group_ids": sorted(event_group_ids),
            "table_ids": sorted(table_ids),
        },
        fetchers,
    )


def _build_apm_refs_and_fetchers(
    bk_tenant_id: str,
    bk_biz_id: int,
    app_names: Sequence[str],
) -> tuple[dict[str, Any], OrderedDict[str, list[FetcherResultType]]]:
    normalized_app_names = _normalize_strings(app_names)
    if not normalized_app_names:
        return {}, OrderedDict()

    apm_applications = list(
        ApmApplication.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            app_name__in=normalized_app_names,
        )
    )
    found_app_names = {application.app_name for application in apm_applications}
    missing_app_names = sorted(set(normalized_app_names) - found_app_names)
    if missing_app_names:
        raise ValueError(f"未找到这些 APM 应用: {missing_app_names}")

    apm_application_ids = [application.id for application in apm_applications]
    apm_web_applications = list(
        ApmWebApplication.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            app_name__in=normalized_app_names,
        )
    )
    apm_web_application_ids = [application.application_id for application in apm_web_applications]

    data_ids: set[int] = set()
    table_ids: set[str] = set()
    metric_data_ids: set[int] = set()
    trace_log_data_ids: set[int] = set()
    profile_data_ids: set[int] = set()
    for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
        queryset = model.objects.filter(bk_biz_id=bk_biz_id, app_name__in=normalized_app_names)
        model_data_ids = set(queryset.values_list("bk_data_id", flat=True))
        _add_valid_data_ids(data_ids, list(model_data_ids))
        _add_valid_table_ids(table_ids, list(queryset.values_list("result_table_id", flat=True)))
        if model is MetricDataSource:
            _add_valid_data_ids(metric_data_ids, list(model_data_ids))
        elif model is ProfileDataSource:
            _add_valid_data_ids(profile_data_ids, list(model_data_ids))
        else:
            _add_valid_data_ids(trace_log_data_ids, list(model_data_ids))

    table_ids.update(_get_table_ids_by_data_ids(bk_tenant_id=bk_tenant_id, data_ids=sorted(data_ids)))

    app_filters = {"bk_biz_id": bk_biz_id, "app_name__in": normalized_app_names}
    apm_fetchers: list[FetcherResultType] = [
        (ApmApplication, {**app_filters, "bk_tenant_id": bk_tenant_id}, None),
        (EbpfApplicationConfig, {"bk_biz_id": bk_biz_id, "application_id__in": apm_application_ids}, None),
        (BcsClusterDefaultApplicationRelation, app_filters, None),
        (ProfileService, app_filters, None),
        (SubscriptionConfig, app_filters, None),
        (MetricDataSource, app_filters, None),
        (LogDataSource, app_filters, None),
        (TraceDataSource, app_filters, None),
        (ProfileDataSource, app_filters, None),
        (BkdataFlowConfig, app_filters, None),
        (ApmTopoDiscoverRule, app_filters, None),
        (ApmInstanceDiscover, app_filters, None),
        (ApmMetricDimension, app_filters, None),
        (RemoteServiceDiscover, app_filters, None),
        (ApdexConfig, app_filters, None),
        (SamplerConfig, app_filters, None),
        (CustomServiceConfig, app_filters, None),
        (NormalTypeValueConfig, app_filters, None),
        (QpsConfig, app_filters, None),
        (LicenseConfig, app_filters, None),
        (DbConfig, app_filters, None),
        (ProbeConfig, app_filters, None),
    ]

    app_name_pattern = "|".join(re.escape(app_name) for app_name in normalized_app_names)
    apm_web_fetchers: list[FetcherResultType] = [
        (ApmWebApplication, {**app_filters, "bk_tenant_id": bk_tenant_id}, None),
        (ApplicationRelationInfo, {"application_id__in": apm_web_application_ids}, None),
        (ApplicationCustomService, app_filters, None),
        (CMDBServiceRelation, app_filters, None),
        (EventServiceRelation, app_filters, None),
        (LogServiceRelation, app_filters, None),
        (AppServiceRelation, app_filters, None),
        (UriServiceRelation, app_filters, None),
        (ApdexServiceRelation, app_filters, None),
        (CodeRedefinedConfigRelation, app_filters, None),
        (StrategyTemplate, app_filters, None),
        (StrategyInstance, app_filters, None),
        (ProfileUploadRecord, app_filters, None),
        (TraceComparison, app_filters, None),
        (
            ApmMetaConfig,
            {"config_level": ApmMetaConfig.APPLICATION_LEVEL, "level_key__in": apm_web_application_ids},
            None,
        ),
        (
            ApmMetaConfig,
            {
                "config_level": ApmMetaConfig.SERVICE_LEVEL,
                "level_key__regex": f"^{bk_biz_id}-({app_name_pattern})-",
            },
            None,
        ),
    ]

    return (
        {
            "app_names": sorted(found_app_names),
            "data_ids": sorted(data_ids),
            "metric_data_ids": sorted(metric_data_ids),
            "trace_log_data_ids": sorted(trace_log_data_ids),
            "profile_data_ids": sorted(profile_data_ids),
            "table_ids": sorted(table_ids),
            "apm_application_ids": sorted(apm_application_ids),
            "apm_web_application_ids": sorted(apm_web_application_ids),
        },
        OrderedDict(
            [
                ("apm", apm_fetchers),
                ("apm_web", apm_web_fetchers),
            ]
        ),
    )


def build_partial_migration_context(
    bk_tenant_id: str,
    bk_biz_id: int,
    bcs_cluster_ids: Sequence[str] | None = None,
    custom_report_data_ids: Sequence[int] | None = None,
    app_names: Sequence[str] | None = None,
) -> PartialMigrationContext:
    selectors = {
        "bcs_cluster_ids": _normalize_strings(bcs_cluster_ids),
        "custom_report_data_ids": _normalize_ints(custom_report_data_ids),
        "app_names": _normalize_strings(app_names),
    }
    if not any(selectors.values()):
        raise ValueError("局部迁移必须至少提供 bcs_cluster_ids/custom_report_data_ids/app_names 之一")

    refs: dict[str, dict[str, Any]] = {}
    module_fetchers: OrderedDict[str, list[FetcherResultType]] = OrderedDict()
    table_ids: set[str] = set()
    data_ids: set[int] = set()

    bcs_refs, bcs_fetchers = _build_bcs_refs_and_fetchers(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        bcs_cluster_ids=selectors["bcs_cluster_ids"],
    )
    if bcs_refs:
        refs["bcs"] = bcs_refs
        module_fetchers["metadata_bcs"] = bcs_fetchers
        bcs_data_ids = bcs_refs["metric_data_ids"] + bcs_refs["event_data_ids"] + bcs_refs["log_data_ids"]
        _add_valid_data_ids(data_ids, bcs_data_ids)
        table_ids.update(_get_table_ids_by_data_ids(bk_tenant_id=bk_tenant_id, data_ids=bcs_data_ids))

    custom_refs, custom_fetchers = _build_custom_report_refs_and_fetchers(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        custom_report_data_ids=selectors["custom_report_data_ids"],
    )
    if custom_refs:
        refs["custom_report"] = custom_refs
        module_fetchers["custom_report"] = custom_fetchers
        _add_valid_data_ids(data_ids, custom_refs["data_ids"])
        _add_valid_table_ids(table_ids, custom_refs["table_ids"])

    apm_refs, apm_fetchers = _build_apm_refs_and_fetchers(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        app_names=selectors["app_names"],
    )
    if apm_refs:
        refs["apm"] = apm_refs
        module_fetchers.update(apm_fetchers)
        _add_valid_data_ids(data_ids, apm_refs["data_ids"])
        _add_valid_table_ids(table_ids, apm_refs["table_ids"])

    normalized_data_ids = sorted(data_ids)
    normalized_table_ids = sorted(table_ids)
    if normalized_data_ids:
        module_fetchers["metadata_data_source"] = get_metadata_data_source_fetcher(normalized_data_ids)
    if normalized_table_ids:
        module_fetchers["metadata_result_table"] = get_metadata_result_table_fetcher(normalized_table_ids)
        module_fetchers["metadata_storage"] = get_metadata_storage_by_table_ids_fetcher(normalized_table_ids)

    manifest_scope = {
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": bk_biz_id,
        "selectors": selectors,
        "refs": refs,
        "data_ids": normalized_data_ids,
        "table_ids": normalized_table_ids,
    }
    return PartialMigrationContext(module_fetchers=module_fetchers, manifest_scope=manifest_scope, refs=refs)


def export_partial_data_to_directory(
    directory_path: str | Path,
    bk_tenant_id: str,
    bk_biz_id: int,
    bcs_cluster_ids: Sequence[str] | None = None,
    custom_report_data_ids: Sequence[int] | None = None,
    app_names: Sequence[str] | None = None,
    format: str = "json",
    indent: int = 2,
) -> Path:
    target_directory = Path(directory_path)
    target_directory.mkdir(parents=True, exist_ok=True)
    context = build_partial_migration_context(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        bcs_cluster_ids=bcs_cluster_ids,
        custom_report_data_ids=custom_report_data_ids,
        app_names=app_names,
    )

    manifest: dict[str, Any] = {
        "version": 1,
        "format": format,
        "exported_at": timezone.now().isoformat(),
        "bk_biz_ids": [bk_biz_id],
        "global_files": [],
        "biz_files": {str(bk_biz_id): []},
        "export_stats": {},
        "partial": context.manifest_scope,
    }
    biz_stats = _build_scope_export_stats(
        "partial_biz",
        tables=_build_table_export_refs(context.manifest_scope["table_ids"]),
        datasources=_build_data_source_export_refs(context.manifest_scope["data_ids"]),
        clusters=_build_cluster_export_refs(context.manifest_scope["table_ids"], context.manifest_scope["data_ids"]),
    )
    biz_relative_files: list[str] = []
    for module_name, fetchers in context.module_fetchers.items():
        module_objects = _peek_export_objects(
            _iter_fetcher_objects(fetchers, context=f"partial:{bk_biz_id}:{module_name}")
        )
        if module_objects is None:
            continue
        relative_file_path = Path("biz") / str(bk_biz_id) / f"{module_name}.{format}"
        _write_fixture_file(
            target_directory / relative_file_path,
            _track_scope_model_counts(module_objects, biz_stats["model_counts"]),
            format=format,
            indent=indent,
        )
        biz_relative_files.append(relative_file_path.as_posix())

    manifest["biz_files"][str(bk_biz_id)] = biz_relative_files
    manifest["export_stats"][str(bk_biz_id)] = biz_stats
    write_json_file(target_directory / "manifest.json", manifest, encoding=DEFAULT_ENCODING)
    return target_directory


def load_partial_scope_from_directory(directory_path: str | Path) -> dict[str, Any]:
    manifest = read_json_file(Path(directory_path) / "manifest.json", encoding=DEFAULT_ENCODING)
    partial_scope = manifest.get("partial")
    if not isinstance(partial_scope, dict):
        raise ValueError("导入目录 manifest.json 中不存在 partial 局部迁移信息")
    return partial_scope


def _iter_import_fixture_records(directory_path: Path, manifest: dict[str, Any], bk_biz_ids: Sequence[int] | None):
    format = manifest.get("format", "json")
    if format != "json":
        raise ValueError("局部导入预检查仅支持 json 格式的导出目录")

    target_bk_biz_ids = _normalize_ints(bk_biz_ids if bk_biz_ids is not None else manifest.get("bk_biz_ids", []))
    for bk_biz_id in target_bk_biz_ids:
        for relative_file_path in manifest.get("biz_files", {}).get(str(bk_biz_id), []):
            file_records = read_json_file(directory_path / relative_file_path, encoding=DEFAULT_ENCODING)
            for record in file_records:
                yield relative_file_path, record


def _has_existing(queryset) -> bool:
    return queryset.exists()


def _append_conflict(
    conflicts: list[dict[str, Any]],
    *,
    source_file: str,
    record: dict[str, Any],
    existing_model: str,
    field: str,
    value: Any,
    lookup: dict[str, Any],
) -> None:
    conflicts.append(
        {
            "source_file": source_file,
            "model": record.get("model"),
            "pk": record.get("pk"),
            "existing_model": existing_model,
            "field": field,
            "value": value,
            "lookup": lookup,
        }
    )


def _append_invalid_record(
    conflicts: list[dict[str, Any]],
    *,
    source_file: str,
    record: dict[str, Any],
    field: str,
    reason: str,
) -> None:
    conflicts.append(
        {
            "source_file": source_file,
            "model": record.get("model"),
            "pk": record.get("pk"),
            "field": field,
            "value": (record.get("fields") or {}).get(field),
            "reason": reason,
        }
    )


def _get_required_bk_tenant_id(
    source_file: str,
    record: dict[str, Any],
    conflicts: list[dict[str, Any]],
) -> str | None:
    raw_bk_tenant_id = (record.get("fields") or {}).get("bk_tenant_id")
    bk_tenant_id = str(raw_bk_tenant_id or "").strip()
    if not bk_tenant_id:
        _append_invalid_record(
            conflicts,
            source_file=source_file,
            record=record,
            field="bk_tenant_id",
            reason="fixture record missing required bk_tenant_id",
        )
        return None
    return bk_tenant_id


def _check_data_source_conflicts(source_file: str, record: dict[str, Any], conflicts: list[dict[str, Any]]) -> None:
    if str(record.get("model") or "").lower() != DataSource._meta.label_lower:
        return

    fields = record.get("fields") or {}
    pk = record.get("pk")
    if pk and _has_existing(DataSource.objects.filter(pk=pk)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=DataSource._meta.label,
            field="bk_data_id",
            value=pk,
            lookup={"pk": pk},
        )

    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    data_name = fields.get("data_name")
    if data_name and _has_existing(DataSource.objects.filter(bk_tenant_id=bk_tenant_id, data_name=data_name)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=DataSource._meta.label,
            field="data_name",
            value=data_name,
            lookup={"bk_tenant_id": bk_tenant_id, "data_name": data_name},
        )


def _check_result_table_conflicts(source_file: str, record: dict[str, Any], conflicts: list[dict[str, Any]]) -> None:
    if str(record.get("model") or "").lower() != ResultTable._meta.label_lower:
        return

    fields = record.get("fields") or {}
    pk = record.get("pk")
    if pk and _has_existing(ResultTable.objects.filter(pk=pk)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=ResultTable._meta.label,
            field="id",
            value=pk,
            lookup={"pk": pk},
        )

    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    table_id = fields.get("table_id")
    if table_id and _has_existing(ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=ResultTable._meta.label,
            field="table_id",
            value=table_id,
            lookup={"bk_tenant_id": bk_tenant_id, "table_id": table_id},
        )


def _check_group_conflicts(source_file: str, record: dict[str, Any], conflicts: list[dict[str, Any]]) -> None:
    fields = record.get("fields") or {}
    model_label = str(record.get("model") or "").lower()
    group_checks = {
        TimeSeriesGroup._meta.label_lower: (
            TimeSeriesGroup,
            "time_series_group_id",
            "time_series_group_name",
        ),
        EventGroup._meta.label_lower: (EventGroup, "event_group_id", "event_group_name"),
    }
    if model_label not in group_checks:
        return

    model_cls, id_field, name_field = group_checks[model_label]
    group_id = record.get("pk") or fields.get(id_field)
    if group_id and _has_existing(model_cls.objects.filter(pk=group_id)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=model_cls._meta.label,
            field=id_field,
            value=group_id,
            lookup={"pk": group_id},
        )

    group_name = fields.get(name_field)
    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    bk_biz_id = fields.get("bk_biz_id")
    if group_name and bk_biz_id is not None:
        lookup = {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, name_field: group_name}
        if _has_existing(model_cls.objects.filter(**lookup)):
            _append_conflict(
                conflicts,
                source_file=source_file,
                record=record,
                existing_model=model_cls._meta.label,
                field=name_field,
                value=group_name,
                lookup=lookup,
            )


def _check_custom_report_conflicts(source_file: str, record: dict[str, Any], conflicts: list[dict[str, Any]]) -> None:
    fields = record.get("fields") or {}
    model_label = str(record.get("model") or "").lower()
    model_map = {
        CustomTSTable._meta.label_lower: CustomTSTable,
        CustomEventGroup._meta.label_lower: CustomEventGroup,
    }
    model_cls = model_map.get(model_label)
    if model_cls is None:
        return

    pk = record.get("pk")
    if pk and _has_existing(model_cls.objects.filter(pk=pk)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=model_cls._meta.label,
            field="pk",
            value=pk,
            lookup={"pk": pk},
        )

    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    for field in ("bk_data_id", "table_id"):
        value = fields.get(field)
        if value in INVALID_DATA_ID_VALUES or value in INVALID_TABLE_ID_VALUES:
            continue
        lookup = {"bk_tenant_id": bk_tenant_id, field: value}
        if _has_existing(model_cls.objects.filter(**lookup)):
            _append_conflict(
                conflicts,
                source_file=source_file,
                record=record,
                existing_model=model_cls._meta.label,
                field=field,
                value=value,
                lookup=lookup,
            )


def _check_bcs_cluster_conflicts(source_file: str, record: dict[str, Any], conflicts: list[dict[str, Any]]) -> None:
    if str(record.get("model") or "").lower() != BCSClusterInfo._meta.label_lower:
        return
    fields = record.get("fields") or {}
    cluster_id = fields.get("cluster_id")
    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    bk_biz_id = fields.get("bk_biz_id")
    if not cluster_id or bk_biz_id is None:
        return
    lookup = {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "cluster_id": cluster_id}
    if _has_existing(BCSClusterInfo.objects.filter(**lookup)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=BCSClusterInfo._meta.label,
            field="cluster_id",
            value=cluster_id,
            lookup=lookup,
        )


def _check_apm_application_conflicts(
    source_file: str,
    record: dict[str, Any],
    conflicts: list[dict[str, Any]],
) -> None:
    fields = record.get("fields") or {}
    model_label = str(record.get("model") or "").lower()
    model_map = {
        ApmApplication._meta.label_lower: ApmApplication,
        ApmWebApplication._meta.label_lower: ApmWebApplication,
    }
    model_cls = model_map.get(model_label)
    if model_cls is None:
        return

    app_name = fields.get("app_name")
    bk_biz_id = fields.get("bk_biz_id")
    bk_tenant_id = _get_required_bk_tenant_id(source_file, record, conflicts)
    if bk_tenant_id is None:
        return

    if not app_name or bk_biz_id is None:
        return
    lookup = {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "app_name": app_name}
    if _has_existing(model_cls.objects.filter(**lookup)):
        _append_conflict(
            conflicts,
            source_file=source_file,
            record=record,
            existing_model=model_cls._meta.label,
            field="app_name",
            value=app_name,
            lookup=lookup,
        )


def precheck_partial_import_directory(
    directory_path: str | Path,
    bk_biz_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    target_directory = Path(directory_path)
    manifest = read_json_file(target_directory / "manifest.json", encoding=DEFAULT_ENCODING)
    conflicts: list[dict[str, Any]] = []
    checked_files: set[str] = set()
    checked_records = 0

    for source_file, record in _iter_import_fixture_records(target_directory, manifest, bk_biz_ids):
        checked_files.add(source_file)
        checked_records += 1
        _check_data_source_conflicts(source_file, record, conflicts)
        _check_result_table_conflicts(source_file, record, conflicts)
        _check_group_conflicts(source_file, record, conflicts)
        _check_custom_report_conflicts(source_file, record, conflicts)
        _check_bcs_cluster_conflicts(source_file, record, conflicts)
        _check_apm_application_conflicts(source_file, record, conflicts)

    return {
        "result": not conflicts,
        "checked": {
            "files": len(checked_files),
            "records": checked_records,
        },
        "conflicts": conflicts,
    }


def import_partial_data_from_directory(
    directory_path: str | Path,
    bk_biz_ids: Sequence[int] | None = None,
    atomic: bool = True,
) -> dict[str, Any]:
    atomic_context = transaction.atomic() if atomic else nullcontext()
    with atomic_context:
        precheck_result = precheck_partial_import_directory(directory_path=directory_path, bk_biz_ids=bk_biz_ids)
        if not precheck_result["result"]:
            raise ValueError(f"局部导入预检查失败: {precheck_result['conflicts']}")

        imported_objects = import_biz_data_from_directory(
            directory_path=directory_path,
            bk_biz_ids=bk_biz_ids,
            atomic=atomic,
            cleanup_existing=False,
            sync_close_records=False,
            migrate_builtin_system_event_strategy=False,
            migrate_builtin_gather_up_strategy=False,
            repair_plugin_strategy=False,
        )
    return {
        "precheck": precheck_result,
        "imported_count": len(imported_objects),
    }


def _get_cluster_name(cluster_name: str | None, default_cluster_name: str) -> str:
    normalized_cluster_name = str(cluster_name or "").strip()
    return normalized_cluster_name or default_cluster_name


def _get_time_series_group_ids_by_data_ids(bk_tenant_id: str, bk_biz_id: int, data_ids: Sequence[int]) -> list[int]:
    if not data_ids:
        return []
    return list(
        TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_data_id__in=list(data_ids),
        ).values_list("time_series_group_id", flat=True)
    )


def _get_event_group_ids_by_data_ids(bk_tenant_id: str, data_ids: Sequence[int]) -> list[int]:
    if not data_ids:
        return []
    return list(
        EventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id__in=list(data_ids),
        ).values_list("event_group_id", flat=True)
    )


def _replace_apm_storage_config_value(config_value: Any, storage_cluster_id: int) -> tuple[Any, bool]:
    if not isinstance(config_value, dict):
        return config_value, False

    updated_config = {**config_value}
    changed = False
    for field_name in (ApmWebApplication.DatasourceConfig.ES_STORAGE_CLUSTER,):
        if updated_config.get(field_name) == storage_cluster_id:
            continue
        updated_config[field_name] = storage_cluster_id
        changed = True
    return updated_config, changed


def _rebuild_partial_apm_application_storage_config(
    bk_tenant_id: str,
    bk_biz_id: int,
    app_names: Sequence[str],
    es_cluster_id: int,
) -> int:
    application_ids = list(
        ApmWebApplication.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            app_name__in=list(app_names),
        ).values_list("application_id", flat=True)
    )
    if not application_ids:
        return 0

    updated_count = 0
    for apm_config in ApmMetaConfig.objects.filter(
        config_level=ApmMetaConfig.APPLICATION_LEVEL,
        level_key__in=[str(application_id) for application_id in application_ids],
        config_key__in=APM_APPLICATION_STORAGE_CONFIG_KEYS,
    ):
        config_value, changed = _replace_apm_storage_config_value(apm_config.config_value, es_cluster_id)
        if not changed:
            continue
        apm_config.config_value = config_value
        apm_config.save(update_fields=["config_value"])
        updated_count += 1
    return updated_count


def _rebuild_partial_apm_log_data_source_route(
    bk_tenant_id: str,
    bk_biz_id: int,
    app_names: Sequence[str],
    kafka_cluster_name: str,
    es_cluster_name: str,
    apm_kafka_cluster_name: str | None = None,
    apm_es_cluster_name: str | None = None,
) -> dict[str, Any]:
    kafka_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=kafka_cluster_name)
    es_cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=es_cluster_name)
    apm_kafka_cluster = (
        ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=apm_kafka_cluster_name)
        if apm_kafka_cluster_name
        else kafka_cluster
    )
    apm_es_cluster = (
        ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=apm_es_cluster_name)
        if apm_es_cluster_name
        else es_cluster
    )

    trace_data_sources = TraceDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name__in=list(app_names))
    log_data_sources = LogDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name__in=list(app_names))
    data_ids: set[int] = set()
    table_ids: set[str] = set()
    _add_valid_data_ids(data_ids, list(trace_data_sources.values_list("bk_data_id", flat=True)))
    _add_valid_data_ids(data_ids, list(log_data_sources.values_list("bk_data_id", flat=True)))
    _add_valid_table_ids(table_ids, list(trace_data_sources.values_list("result_table_id", flat=True)))
    _add_valid_table_ids(table_ids, list(log_data_sources.values_list("result_table_id", flat=True)))

    virtual_table_ids = list(
        ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id__in=table_ids)
        .exclude(table_id__in=table_ids)
        .values_list("table_id", flat=True)
    )
    all_table_ids = sorted(table_ids | set(virtual_table_ids))
    if all_table_ids:
        ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).update(
            storage_cluster_id=apm_es_cluster.cluster_id
        )
        ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=virtual_table_ids).update(
            need_create_index=False,
            storage_cluster_id=apm_es_cluster.cluster_id,
        )
        StorageClusterRecord.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=all_table_ids).update(
            cluster_id=apm_es_cluster.cluster_id
        )

    DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids).update(
        mq_cluster_id=apm_kafka_cluster.cluster_id
    )
    registered_data_ids = []
    for data_source in DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids):
        if not data_source.is_enable:
            continue
        _register_data_source(
            bk_biz_id=bk_biz_id,
            data_source=data_source,
            need_register_to_bkbase=data_source.created_from == DataIdCreatedFromSystem.BKDATA.value,
        )
        registered_data_ids.append(data_source.bk_data_id)

    trace_table_ids = list(trace_data_sources.values_list("result_table_id", flat=True))
    for trace_table in ResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        table_id__in=trace_table_ids,
    ):
        trace_table.modify(operator="system", is_enable=True)

    updated_config_count = _rebuild_partial_apm_application_storage_config(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        app_names=app_names,
        es_cluster_id=apm_es_cluster.cluster_id,
    )
    return {
        "data_ids": sorted(data_ids),
        "table_ids": all_table_ids,
        "registered_data_ids": sorted(registered_data_ids),
        "updated_application_storage_config_count": updated_config_count,
    }


def rebuild_partial_data(
    bk_tenant_id: str,
    bk_biz_id: int,
    bcs_cluster_ids: Sequence[str] | None = None,
    custom_report_data_ids: Sequence[int] | None = None,
    app_names: Sequence[str] | None = None,
    metric_kafka_cluster_name: str = DEFAULT_KAFKA_CLUSTER_NAMES["metric"],
    log_kafka_cluster_name: str = DEFAULT_KAFKA_CLUSTER_NAMES["log"],
    event_kafka_cluster_name: str = DEFAULT_KAFKA_CLUSTER_NAMES["event"],
    log_es_cluster_name: str = DEFAULT_ES_CLUSTER_NAMES["log"],
    event_es_cluster_name: str = DEFAULT_ES_CLUSTER_NAMES["event"],
    apm_kafka_cluster_name: str | None = None,
    apm_es_cluster_name: str | None = None,
) -> dict[str, Any]:
    context = build_partial_migration_context(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        bcs_cluster_ids=bcs_cluster_ids,
        custom_report_data_ids=custom_report_data_ids,
        app_names=app_names,
    )
    metric_kafka = _get_cluster_name(metric_kafka_cluster_name, DEFAULT_KAFKA_CLUSTER_NAMES["metric"])
    event_kafka = _get_cluster_name(event_kafka_cluster_name, DEFAULT_KAFKA_CLUSTER_NAMES["event"])
    log_kafka = _get_cluster_name(log_kafka_cluster_name, DEFAULT_KAFKA_CLUSTER_NAMES["log"])
    log_es = _get_cluster_name(log_es_cluster_name, DEFAULT_ES_CLUSTER_NAMES["log"])
    event_es = _get_cluster_name(event_es_cluster_name, DEFAULT_ES_CLUSTER_NAMES["event"])

    operations: list[dict[str, Any]] = []
    bcs_refs = context.refs.get("bcs") or {}
    if bcs_refs:
        time_series_group_ids = _get_time_series_group_ids_by_data_ids(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            data_ids=bcs_refs.get("metric_data_ids", []),
        )
        if time_series_group_ids:
            rebuild_time_series_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=metric_kafka,
                time_series_group_ids=time_series_group_ids,
            )
        event_group_ids = _get_event_group_ids_by_data_ids(
            bk_tenant_id=bk_tenant_id,
            data_ids=bcs_refs.get("event_data_ids", []),
        )
        if event_group_ids:
            rebuild_event_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=event_kafka,
                es_cluster_name=event_es,
                event_group_ids=event_group_ids,
            )
        operations.append(
            {
                "scope": "bcs",
                "cluster_ids": bcs_refs.get("cluster_ids", []),
                "time_series_group_ids": time_series_group_ids,
                "event_group_ids": event_group_ids,
            }
        )

    custom_refs = context.refs.get("custom_report") or {}
    if custom_refs:
        if custom_refs.get("time_series_group_ids"):
            rebuild_time_series_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=metric_kafka,
                time_series_group_ids=custom_refs["time_series_group_ids"],
            )
        if custom_refs.get("event_group_ids"):
            rebuild_event_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=event_kafka,
                es_cluster_name=event_es,
                event_group_ids=custom_refs["event_group_ids"],
            )
        operations.append(
            {
                "scope": "custom_report",
                "data_ids": custom_refs.get("data_ids", []),
                "time_series_group_ids": custom_refs.get("time_series_group_ids", []),
                "event_group_ids": custom_refs.get("event_group_ids", []),
            }
        )

    apm_refs = context.refs.get("apm") or {}
    if apm_refs:
        apm_log_result = _rebuild_partial_apm_log_data_source_route(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            app_names=apm_refs["app_names"],
            kafka_cluster_name=log_kafka,
            es_cluster_name=log_es,
            apm_kafka_cluster_name=apm_kafka_cluster_name,
            apm_es_cluster_name=apm_es_cluster_name,
        )
        apm_metric_group_ids = _get_time_series_group_ids_by_data_ids(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            data_ids=apm_refs.get("metric_data_ids", []),
        )
        if apm_metric_group_ids:
            rebuild_time_series_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                kafka_cluster_name=apm_kafka_cluster_name or metric_kafka,
                time_series_group_ids=apm_metric_group_ids,
            )
        operations.append(
            {
                "scope": "apm",
                "app_names": apm_refs["app_names"],
                "log_route": apm_log_result,
                "metric_time_series_group_ids": apm_metric_group_ids,
            }
        )

    rebuilt_data_ids = _collect_current_partial_data_ids(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        refs=context.refs,
        table_ids=context.manifest_scope["table_ids"],
    )
    data_id_infos = _build_data_id_infos(
        bk_tenant_id=bk_tenant_id,
        data_ids=rebuilt_data_ids,
    )
    return {
        "partial": context.manifest_scope,
        "operations": operations,
        "rebuilt_data_ids": rebuilt_data_ids,
        "data_id_infos": data_id_infos,
    }


def make_partial_export_archive(export_directory: Path, output_directory: str | Path) -> Path:
    target_output_directory = Path(output_directory)
    target_output_directory.mkdir(parents=True, exist_ok=True)
    archive_path = shutil.make_archive(
        base_name=str(export_directory),
        format="zip",
        root_dir=export_directory.parent,
        base_dir=export_directory.name,
    )
    target_archive_path = target_output_directory / f"{export_directory.name}.zip"
    if target_archive_path.exists():
        target_archive_path.unlink()
    shutil.move(archive_path, target_archive_path)
    return target_archive_path
