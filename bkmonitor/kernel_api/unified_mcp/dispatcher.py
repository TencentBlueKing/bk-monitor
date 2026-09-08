"""Dispatch unified MCP calls to the existing Resource implementations."""

from __future__ import annotations

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
)
from kernel_api.resource.event import GetEventViewConfigResource, ListEventsResource, SearchEventLogResource
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
from kernel_api.resource.relation import QueryMultiResourceRelationRangeResource, QueryMultiResourceRelationResource
from metadata.models import DataSource, TimeSeriesGroup
from metadata.resources import GetTimeSeriesMetricsResource
from monitor_web.grafana.resources.manage import GetDashboardDetail, GetDirectoryTree
from monitor_web.strategies.resources.v2 import GetStrategyV2Resource

ToolExecutor = Callable[[dict[str, Any]], Any]


def _resource_executor(resource_class) -> ToolExecutor:
    return lambda tool_args: resource_class().request(**tool_args)


def _ensure_time_series_table_belongs_to_biz(tool_args: dict[str, Any]) -> None:
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
    index_set_id = tool_args.get("index_set_id")
    if index_set_id is None:
        return
    result = GetIndexSetListResource().request(bk_biz_id=tool_args["bk_biz_id"])
    if str(index_set_id) not in _index_set_ids(result):
        raise ValidationError({"index_set_id": "The log index set does not belong to the target space."})


def _log_resource_executor(resource_class) -> ToolExecutor:
    def execute(tool_args: dict[str, Any]):
        _ensure_index_set_belongs_to_biz(tool_args)
        return resource_class().request(**tool_args)

    return execute


def _ensure_event_table_belongs_to_biz(tool_args: dict[str, Any]) -> None:
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
    def execute(tool_args: dict[str, Any]):
        _ensure_event_table_belongs_to_biz(tool_args)
        return resource_class().request(**tool_args)

    return execute


def _ensure_apm_application_permission(tool_args: dict[str, Any]) -> None:
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
    # Metrics
    "list_time_series_groups": _resource_executor(TimeSeriesGroupListResource),
    "list_time_series_metrics": _time_series_metrics,
    "execute_range_query": _resource_executor(ExecuteRangeQueryResource),
    "execute_sql_query": _time_series_sql,
    # Logs
    "list_index_sets": _resource_executor(GetIndexSetListResource),
    "get_index_set_fields": _log_resource_executor(GetIndexSetFieldListResource),
    "search_logs": _log_resource_executor(SearchLogResource),
    "search_index_set_context": _log_resource_executor(SearchIndexSetContextResource),
    "list_log_scenes": _resource_executor(ListLogScenesResource),
    "list_scene_dimension_values": _resource_executor(ListSceneDimensionValuesResource),
    "get_scene_log_fields": _resource_executor(GetSceneLogFieldsResource),
    "analyze_field": _log_resource_executor(FieldAnalyzeResource),
    "search_log_clustering_pattern": _log_resource_executor(SearchLogClusteringPatternResource),
    # Alerts
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
    # Events
    "list_events": _resource_executor(ListEventsResource),
    "get_event_view_config": _event_resource_executor(GetEventViewConfigResource),
    "search_event_log": _event_resource_executor(SearchEventLogResource),
    # APM tracing and profiling
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
    # Dashboards
    "get_dashboard_tree_list": _resource_executor(GetDirectoryTree),
    "get_dashboard_detail_by_uid": _resource_executor(GetDashboardDetail),
    # Resource relations
    "find_relations": _resource_executor(QueryMultiResourceRelationResource),
    "find_relations_range": _resource_executor(QueryMultiResourceRelationRangeResource),
}


def dispatch_tool(tool_name: str, tool_args: dict[str, Any]):
    try:
        executor = TOOL_EXECUTORS[tool_name]
    except KeyError as exc:
        raise KeyError(f"no executor registered for unified MCP tool: {tool_name}") from exc
    return executor(tool_args)
