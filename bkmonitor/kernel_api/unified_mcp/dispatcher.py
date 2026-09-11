"""将 Unified MCP 工具显式分发到现有 Resource 实现。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from apm_web.metric.resources import CalculateByRangeResource
from apm_web.models import Application
from apm_web.service.resources import ServiceListResource
from rest_framework.exceptions import ValidationError

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource import resource
from kernel_api.resource.apm import (
    GetApmSearchFiltersResource,
    GetProfileApplicationServiceResource,
    GetProfileLabelResource,
    GetProfileTypeResource,
    ListApmApplicationResource,
    ListApmSpanResource,
    QueryApmSpanDetailResource,
    QueryApmTraceDetailResource,
    QueryGraphProfileResource,
)
from kernel_api.resource.alert import (
    CreateAlarmShieldResource,
    CreateAlarmStrategyResource,
    CreateNoticeGroupResource,
    DeleteAlarmAssignGroupResource,
    DisableAlarmShieldResource,
    GetAlarmShieldResource,
    GetAlarmStrategyResource,
    GetMCPActionConfigResource,
    ListAlertEventTagDetailResource,
    ListAlertEventTSResource,
    ListAlertEventsResource,
    ListAlertHostTargetResource,
    ListAlertK8sTargetResource,
    ListAlertLogRelationsResource,
    ListAlertResource,
    ListAlertTopNResource,
    ListAlertTracesResource,
    ListStrategySnapshotResource,
    SaveAlarmAssignGroupResource,
    SearchActionConfigsResource,
    SearchAlarmAssignGroupsResource,
    SearchAlarmShieldsResource,
    SearchAlarmStrategiesResource,
    SearchNoticeGroupsResource,
    UpdateAlarmShieldResource,
    UpdateAlarmStrategyResource,
    UpdateMCPActionConfigResource,
    UpdateNoticeGroupResource,
)
from kernel_api.resource.event import GetEventViewConfigResource, ListEventsResource, SearchEventLogResource
from kernel_api.resource.grafana import CreateDashboardResource, UpdateDashboardResource
from kernel_api.resource.log_collection import (
    GetLogCollectorResource,
    GetLogIndexSetResource,
    ListLogCollectorsResource,
)
from kernel_api.resource.log_collection_clean_config import UpdateLogCollectorCleanConfigResource
from kernel_api.resource.log_collection_create import FastCreateLogCollectorResource
from kernel_api.resource.log_collection_discovery import ListResultTablesResource, ListThirdPartyESClustersResource
from kernel_api.resource.log_collection_etl_preview import PreviewLogEtlResource
from kernel_api.resource.log_collection_special_create import (
    CreateBkDataResource,
    CreateCustomReportResource,
    CreateThirdPartyESResource,
)
from kernel_api.resource.log_collection_special_update import (
    UpdateBkDataResource,
    UpdateCustomReportResource,
    UpdateThirdPartyESResource,
)
from kernel_api.resource.log_collection_status import GetLogCollectorStatusResource
from kernel_api.resource.log_collection_update import FastUpdateLogCollectorResource
from kernel_api.resource.log_extract import (
    CreateLogExtractTaskResource,
    GetLogExtractDownloadUrlResource,
    GetLogExtractTaskResource,
    ListLogExtractAllowedPathsResource,
    ListLogExtractTopologyResource,
    SearchLogExtractFilesResource,
    SearchLogExtractHostsResource,
)
from kernel_api.resource.log_index_set import ListLogIndexSetGroupsResource
from kernel_api.resource.log_search import (
    FieldAnalyzeResource,
    GetIndexSetFieldListResource,
    GetIndexSetListResource,
    GetSceneLogFieldsResource,
    ListLogScenesResource,
    ListSceneDimensionValuesResource,
    SearchIndexSetContextResource,
    SearchLogClusteringPatternResource,
    SearchLogResource,
)
from kernel_api.resource.metrics import ExecuteRangeQueryResource, ExecuteSQLQueryResource, TimeSeriesGroupListResource
from kernel_api.resource.operation import (
    GetOperationMetricResource,
    GetOperationOverviewResource,
    ListOperationMetricsResource,
)
from kernel_api.resource.relation import QueryMultiResourceRelationRangeResource, QueryMultiResourceRelationResource
from metadata.models import DataSource, TimeSeriesGroup
from metadata.resources import GetTimeSeriesMetricsResource, ListBCSClusterInfoByBizResource, ListSpacesResource
from monitor_web.grafana.resources.manage import GetDashboardDetail, GetDirectoryTree
from monitor_web.strategies.resources.v2 import GetStrategyV2Resource

ToolExecutor = Callable[[dict[str, Any]], Any]


def _resource_executor(resource_class) -> ToolExecutor:
    """把标准 Resource 包装成统一的 ``dict -> result`` 执行器。"""
    return lambda tool_args: resource_class().request(**tool_args)


def _ensure_time_series_table_belongs_to_biz(tool_args: dict[str, Any]) -> None:
    """执行指标明细查询前，确认结果表属于目标业务或平台数据源。"""
    bk_tenant_id = get_request_tenant_id()
    group = TimeSeriesGroup.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id=tool_args["table_id"],
        is_delete=False,
    ).first()
    if group is None:
        raise ValidationError({"table_id": "The time-series table does not exist."})
    if int(group.bk_biz_id) == int(tool_args["bk_biz_id"]):
        return
    is_platform = DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=group.bk_data_id,
        is_platform_data_id=True,
    ).exists()
    if not is_platform:
        raise ValidationError({"table_id": "The time-series table does not belong to the target space."})


def _time_series_metrics(tool_args: dict[str, Any]):
    _ensure_time_series_table_belongs_to_biz(tool_args)
    return GetTimeSeriesMetricsResource().request(
        bk_tenant_id=get_request_tenant_id(),
        table_id=tool_args["table_id"],
    )


def _time_series_sql(tool_args: dict[str, Any]):
    _ensure_time_series_table_belongs_to_biz(tool_args)
    return ExecuteSQLQueryResource().request(**tool_args)


def _index_set_ids(result: Any) -> set[str]:
    """兼容日志目录的历史返回形态，提取可见索引集 ID。"""
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = next(
            (result[key] for key in ("list", "data", "results", "index_sets") if isinstance(result.get(key), list)),
            [],
        )
    else:
        items = []
    return {
        str(item.get("index_set_id", item.get("id")))
        for item in items
        if isinstance(item, dict) and item.get("index_set_id", item.get("id")) is not None
    }


def _ensure_index_set_belongs_to_biz(tool_args: dict[str, Any]) -> None:
    """调用日志 Resource 前确认索引集在目标业务目录中可见。"""
    index_set_id = tool_args.get("index_set_id")
    if index_set_id is None:
        return
    result = GetIndexSetListResource().request(bk_biz_id=tool_args["bk_biz_id"])
    if str(index_set_id) not in _index_set_ids(result):
        raise ValidationError({"index_set_id": "The log index set does not belong to the target space."})


def _log_resource_executor(resource_class) -> ToolExecutor:
    """为索引集类日志工具统一补充业务归属校验。"""

    def execute(tool_args: dict[str, Any]):
        _ensure_index_set_belongs_to_biz(tool_args)
        return resource_class().request(**tool_args)

    return execute


def _ensure_event_table_belongs_to_biz(tool_args: dict[str, Any]) -> None:
    """按事件源或 APM 应用确认事件表属于目标业务。"""
    if tool_args.get("app_name") and tool_args.get("service_name"):
        _ensure_apm_application_permission(tool_args)
        return
    event_sources = ListEventsResource().request(
        bk_biz_id=tool_args["bk_biz_id"],
        data_source_label=tool_args["data_source_label"],
        data_type_label=tool_args["data_type_label"],
        return_dimensions=False,
    )
    if str(tool_args["table"]) not in {str(item.get("id")) for item in event_sources if isinstance(item, dict)}:
        raise ValidationError({"table": "The event table does not belong to the target space."})


def _event_resource_executor(resource_class) -> ToolExecutor:
    """为事件详情和检索工具统一补充事件表归属校验。"""

    def execute(tool_args: dict[str, Any]):
        _ensure_event_table_belongs_to_biz(tool_args)
        return resource_class().request(**tool_args)

    return execute


def _ensure_apm_application_permission(tool_args: dict[str, Any]) -> None:
    """把应用名解析为当前业务 APM 实例，并执行实例权限校验。"""
    application_id = (
        Application.objects.filter(bk_biz_id=tool_args["bk_biz_id"], app_name=tool_args["app_name"])
        .values_list("application_id", flat=True)
        .first()
    )
    if application_id is None:
        raise ValidationError({"app_name": "The APM application does not belong to the target space."})
    Permission().is_allowed(
        ActionEnum.VIEW_APM_APPLICATION,
        [ResourceEnum.APM_APPLICATION.create_simple_instance(application_id)],
        raise_exception=True,
    )


def _apm_application_resource_executor(resource_class) -> ToolExecutor:
    """为 APM 应用级工具统一补充实例归属与权限校验。"""

    def execute(tool_args: dict[str, Any]):
        _ensure_apm_application_permission(tool_args)
        return resource_class().request(**tool_args)

    return execute


def _alert_detail(tool_args: dict[str, Any]):
    return resource.alert.alert_detail.request(**tool_args)


def _list_alerts(tool_args: dict[str, Any]):
    request_data = dict(tool_args)
    request_data["bk_biz_ids"] = [request_data["bk_biz_id"]]
    return ListAlertResource().request(**request_data)


def _alert_top_n(tool_args: dict[str, Any]):
    request_data = dict(tool_args)
    request_data["bk_biz_ids"] = [request_data["bk_biz_id"]]
    return ListAlertTopNResource().request(**request_data)


TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    # 指标查询
    "list_time_series_groups": _resource_executor(TimeSeriesGroupListResource),
    "list_time_series_metrics": _time_series_metrics,
    "execute_range_query": _resource_executor(ExecuteRangeQueryResource),
    "execute_sql_query": _time_series_sql,
    # 日志查询
    "list_index_sets": _resource_executor(GetIndexSetListResource),
    "get_index_set_fields": _log_resource_executor(GetIndexSetFieldListResource),
    "search_logs": _log_resource_executor(SearchLogResource),
    "search_index_set_context": _log_resource_executor(SearchIndexSetContextResource),
    "list_log_scenes": _resource_executor(ListLogScenesResource),
    "list_scene_dimension_values": _resource_executor(ListSceneDimensionValuesResource),
    "get_scene_log_fields": _resource_executor(GetSceneLogFieldsResource),
    "analyze_field": _log_resource_executor(FieldAnalyzeResource),
    "search_log_clustering_pattern": _log_resource_executor(SearchLogClusteringPatternResource),
    # 告警查询
    "list_alerts": _list_alerts,
    "get_alert_top_n": _alert_top_n,
    "get_strategy_snapshot": _resource_executor(ListStrategySnapshotResource),
    "get_strategy_detail": _resource_executor(GetStrategyV2Resource),
    "get_alert_info": _alert_detail,
    "get_alert_events": _resource_executor(ListAlertEventsResource),
    "get_alert_event_ts": _resource_executor(ListAlertEventTSResource),
    "get_alert_event_tag_detail": _resource_executor(ListAlertEventTagDetailResource),
    "get_alert_k8s_target": _resource_executor(ListAlertK8sTargetResource),
    "get_alert_host_target": _resource_executor(ListAlertHostTargetResource),
    "get_alert_traces": _resource_executor(ListAlertTracesResource),
    "get_alert_log_relations": _resource_executor(ListAlertLogRelationsResource),
    # 告警处理
    "search_alarm_strategies": _resource_executor(SearchAlarmStrategiesResource),
    "get_alarm_strategy": _resource_executor(GetAlarmStrategyResource),
    "create_alarm_strategy": _resource_executor(CreateAlarmStrategyResource),
    "update_alarm_strategy": _resource_executor(UpdateAlarmStrategyResource),
    "search_alarm_shields": _resource_executor(SearchAlarmShieldsResource),
    "get_alarm_shield": _resource_executor(GetAlarmShieldResource),
    "create_alarm_shield": _resource_executor(CreateAlarmShieldResource),
    "update_alarm_shield": _resource_executor(UpdateAlarmShieldResource),
    "disable_alarm_shield": _resource_executor(DisableAlarmShieldResource),
    "search_alarm_notice_groups": _resource_executor(SearchNoticeGroupsResource),
    "create_alarm_notice_group": _resource_executor(CreateNoticeGroupResource),
    "update_alarm_notice_group": _resource_executor(UpdateNoticeGroupResource),
    "search_alarm_action_configs": _resource_executor(SearchActionConfigsResource),
    "get_alarm_action_config": _resource_executor(GetMCPActionConfigResource),
    "update_alarm_action_config": _resource_executor(UpdateMCPActionConfigResource),
    "search_alarm_assign_groups": _resource_executor(SearchAlarmAssignGroupsResource),
    "save_alarm_assign_group": _resource_executor(SaveAlarmAssignGroupResource),
    "delete_alarm_assign_group": _resource_executor(DeleteAlarmAssignGroupResource),
    # 事件查询
    "list_events": _resource_executor(ListEventsResource),
    "get_event_view_config": _event_resource_executor(GetEventViewConfigResource),
    "search_event_log": _event_resource_executor(SearchEventLogResource),
    # APM 链路与性能分析
    "list_apm_applications": _resource_executor(ListApmApplicationResource),
    "get_apm_filter_fields": _resource_executor(GetApmSearchFiltersResource),
    "search_spans": _resource_executor(ListApmSpanResource),
    "get_trace_detail": _resource_executor(QueryApmTraceDetailResource),
    "get_span_detail": _resource_executor(QueryApmSpanDetailResource),
    "get_profile_application_service": _resource_executor(GetProfileApplicationServiceResource),
    "get_profile_type": _resource_executor(GetProfileTypeResource),
    "get_profile_label": _resource_executor(GetProfileLabelResource),
    "query_graph_profile": _resource_executor(QueryGraphProfileResource),
    "calculate_by_range": _apm_application_resource_executor(CalculateByRangeResource),
    "list_apm_services": _apm_application_resource_executor(ServiceListResource),
    # 仪表盘
    "get_dashboard_tree_list": _resource_executor(GetDirectoryTree),
    "get_dashboard_detail_by_uid": _resource_executor(GetDashboardDetail),
    "create_dashboard": _resource_executor(CreateDashboardResource),
    "update_dashboard": _resource_executor(UpdateDashboardResource),
    # 资源关联
    "find_relations": _resource_executor(QueryMultiResourceRelationResource),
    "find_relations_range": _resource_executor(QueryMultiResourceRelationRangeResource),
    # 日志采集
    "list_log_collectors": _resource_executor(ListLogCollectorsResource),
    "get_log_collector": _resource_executor(GetLogCollectorResource),
    "get_log_index_set": _resource_executor(GetLogIndexSetResource),
    "update_log_collector_clean_config": _resource_executor(UpdateLogCollectorCleanConfigResource),
    "fast_create_log_collector": _resource_executor(FastCreateLogCollectorResource),
    "list_third_party_es_clusters": _resource_executor(ListThirdPartyESClustersResource),
    "list_result_tables": _resource_executor(ListResultTablesResource),
    "preview_log_etl": _resource_executor(PreviewLogEtlResource),
    "list_log_index_set_groups": _resource_executor(ListLogIndexSetGroupsResource),
    "create_custom_report": _resource_executor(CreateCustomReportResource),
    "create_bkdata_index_set": _resource_executor(CreateBkDataResource),
    "create_third_party_es": _resource_executor(CreateThirdPartyESResource),
    "update_custom_report": _resource_executor(UpdateCustomReportResource),
    "update_third_party_es": _resource_executor(UpdateThirdPartyESResource),
    "update_bkdata_index_set": _resource_executor(UpdateBkDataResource),
    "get_log_collector_status": _resource_executor(GetLogCollectorStatusResource),
    "fast_update_log_collector": _resource_executor(FastUpdateLogCollectorResource),
    # 日志提取
    "list_log_extract_topology": _resource_executor(ListLogExtractTopologyResource),
    "search_log_extract_hosts": _resource_executor(SearchLogExtractHostsResource),
    "list_log_extract_allowed_paths": _resource_executor(ListLogExtractAllowedPathsResource),
    "search_log_extract_files": _resource_executor(SearchLogExtractFilesResource),
    "create_log_extract_task": _resource_executor(CreateLogExtractTaskResource),
    "get_log_extract_task": _resource_executor(GetLogExtractTaskResource),
    "get_log_extract_download_url": _resource_executor(GetLogExtractDownloadUrlResource),
    # 元数据
    "list_bcs_clusters": _resource_executor(ListBCSClusterInfoByBizResource),
    "search_spaces": _resource_executor(ListSpacesResource),
    # 平台运营数据
    "list_operation_metrics": _resource_executor(ListOperationMetricsResource),
    "get_operation_metric": _resource_executor(GetOperationMetricResource),
    "get_operation_overview": _resource_executor(GetOperationOverviewResource),
}


def dispatch_tool(tool_name: str, tool_args: dict[str, Any]):
    """按工具名调用原 Resource，并记录不含业务参数的统一分发日志。"""
    try:
        executor = TOOL_EXECUTORS[tool_name]
    except KeyError as exc:
        raise KeyError(f"no executor registered for unified MCP tool: {tool_name}") from exc

    from kernel_api.unified_mcp.permissions import log_mcp_tool_event
    from kernel_api.unified_mcp.registry import get_tool_registry

    # 从同一 Registry 取得审计元信息，避免日志与实际工具路由使用两份配置。
    tool = get_tool_registry().get(tool_name)
    started_at = time.monotonic()
    log_mcp_tool_event(
        "dispatch_started",
        tool=tool_name,
        category=tool.category,
        risk=tool.risk,
        backend_method=tool.backend_method,
        backend_path=tool.backend_path,
    )
    try:
        # 业务参数只传给执行器，禁止写入 MCP_TOOL 日志。
        result = executor(tool_args)
    except Exception as exc:
        log_mcp_tool_event(
            "dispatch_finished",
            level=logging.WARNING,
            tool=tool_name,
            category=tool.category,
            decision="failed",
            error_type=type(exc).__name__,
            duration_ms=round((time.monotonic() - started_at) * 1000),
        )
        raise
    log_mcp_tool_event(
        "dispatch_finished",
        tool=tool_name,
        category=tool.category,
        decision="succeeded",
        result_type=type(result).__name__,
        duration_ms=round((time.monotonic() - started_at) * 1000),
    )
    return result
