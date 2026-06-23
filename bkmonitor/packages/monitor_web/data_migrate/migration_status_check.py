from __future__ import annotations

import enum
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.tenant import set_local_tenant_id
from constants.common import DEFAULT_TENANT_ID
from metadata import config as metadata_config

INVALID_DATA_ID_VALUES = {None, 0, -1}
DEFAULT_TIME_RANGE_SECONDS = 3600
DEFAULT_QUERY_INTERVAL = 60
DEFAULT_CHECK_WORKERS = 4
DEFAULT_ITEM_CHECK_WORKERS = 8


@dataclass(frozen=True)
class CheckContext:
    bk_tenant_id: str
    bk_biz_id: int
    start_time: int
    end_time: int
    with_detail: bool = False

    @property
    def start_time_ms(self) -> int:
        return self.start_time * 1000

    @property
    def end_time_ms(self) -> int:
        return self.end_time * 1000


def collect_migration_status(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    start_time: int | None = None,
    end_time: int | None = None,
    with_detail: bool = False,
) -> dict[str, Any]:
    """Collect post-migration status details for one business in current environment."""
    now = int(time.time())
    resolved_bk_tenant_id = _normalize_bk_tenant_id(bk_tenant_id)
    resolved_end_time = int(end_time or now)
    resolved_start_time = int(start_time or resolved_end_time - DEFAULT_TIME_RANGE_SECONDS)
    context = CheckContext(
        bk_tenant_id=resolved_bk_tenant_id,
        bk_biz_id=int(bk_biz_id),
        start_time=resolved_start_time,
        end_time=resolved_end_time,
        with_detail=with_detail,
    )

    set_local_tenant_id(resolved_bk_tenant_id)

    checks: dict[str, Callable[[], dict[str, Any]]] = {
        "host": lambda: check_host(context),
        "k8s": lambda: check_k8s(context),
        "uptime_check": lambda: check_uptime_check(context),
        "custom_report": lambda: check_custom_report(context),
        "plugin_collect": lambda: check_plugin_collect(context),
        "apm": lambda: check_apm(context),
        "strategy": lambda: check_strategy(context),
    }

    return {
        "bk_tenant_id": resolved_bk_tenant_id,
        "bk_biz_id": int(bk_biz_id),
        "time_range": {"start_time": resolved_start_time, "end_time": resolved_end_time},
        "checks": _run_named_checks_concurrently(checks),
        "errors": [],
    }


def _normalize_bk_tenant_id(bk_tenant_id: str | None) -> str:
    return str(bk_tenant_id or "").strip() or DEFAULT_TENANT_ID


def _run_concurrently(items: list[Any], func: Callable[[Any], Any], max_workers: int) -> list[Any]:
    if not items:
        return []

    worker_count = min(max_workers, len(items))
    if worker_count <= 1:
        return [func(item) for item in items]

    pool = ThreadPool(worker_count)
    try:
        return list(pool.imap(func, items))
    finally:
        pool.close()
        pool.join()


def _run_named_checks_concurrently(checks: dict[str, Callable[[], dict[str, Any]]]) -> dict[str, Any]:
    return dict(_run_concurrently(list(checks.items()), _run_named_check, DEFAULT_CHECK_WORKERS))


def _run_named_check(item: tuple[str, Callable[[], dict[str, Any]]]) -> tuple[str, dict[str, Any]]:
    check_name, check_func = item
    return check_name, safe_check(check_name, check_func)


def safe_check(check_name: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return _jsonable(func())
    except Exception as error:  # noqa: BLE001 - status checks must continue independently.
        return {"errors": [{"check": check_name, "message": str(error)}]}


def check_host(context: CheckContext) -> dict[str, Any]:
    promql_jobs = [
        (
            "host_metric",
            "sum by (bk_target_ip, bk_target_cloud_id) (count_over_time(system:cpu_summary:usage[5m]))",
        ),
        (
            "process_perf",
            "sum by (bk_target_ip, bk_target_cloud_id, display_name) (count_over_time(system:proc:cpu_usage_pct[5m]))",
        ),
        (
            "process_port",
            "sum by (bk_target_ip, bk_target_cloud_id, display_name) "
            "(count_over_time(system:proc_port:proc_exists[5m]))",
        ),
    ]
    promql_checks = dict(
        _run_concurrently(
            promql_jobs,
            lambda item: (item[0], _query_promql_host_count(context, promql=item[1])),
            DEFAULT_ITEM_CHECK_WORKERS,
        )
    )

    return {"promql_checks": promql_checks}


def check_k8s(context: CheckContext) -> dict[str, Any]:
    from metadata.models import BCSClusterInfo

    clusters = list(
        BCSClusterInfo.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_biz_id=context.bk_biz_id)
        .order_by("cluster_id")
        .iterator()
    )
    records = _run_concurrently(
        clusters,
        lambda cluster: _build_k8s_cluster_record(context, cluster),
        DEFAULT_ITEM_CHECK_WORKERS,
    )
    return {"clusters": records, "errors": []}


def check_uptime_check(context: CheckContext) -> dict[str, Any]:
    from bk_monitor_base.uptime_check import UptimeCheckTaskSubscription, list_tasks, refresh_task_status

    from core.drf_resource import resource

    tasks = list(
        list_tasks(
            bk_tenant_id=context.bk_tenant_id,
            bk_biz_id=context.bk_biz_id,
            fields=["id", "bk_biz_id", "name", "protocol", "status", "config", "node_ids", "group_ids"],
            order_by="id",
        )
    )
    task_ids = [task.id for task in tasks]
    subscription_map = _get_uptime_subscription_map(UptimeCheckTaskSubscription, task_ids, context.bk_biz_id)
    deploy_status_map = _safe_value(
        lambda: refresh_task_status(
            bk_tenant_id=context.bk_tenant_id,
            bk_biz_id=context.bk_biz_id,
            task_ids=task_ids,
        ),
        default={},
    )
    list_page_data = _safe_value(
        lambda: resource.uptime_check.uptime_check_task_list(
            task_data=[task.model_dump(exclude={"bk_tenant_id"}) for task in tasks],
            bk_biz_id=context.bk_biz_id,
            get_available=True,
            get_task_duration=True,
        ),
        default=[],
    )
    list_page_map = _build_uptime_list_page_map(list_page_data)
    promql_data_by_task = _query_uptime_promql_by_task(context, tasks)

    records = []
    for task in tasks:
        task_id = int(task.id)
        task_data = list_page_map.get(task_id, {})
        promql_data = promql_data_by_task.get(task_id, _empty_uptime_promql_data())
        status_value = _enum_value(task.status)
        protocol = str(_enum_value(task.protocol)).lower()
        period = int((getattr(task, "config", {}) or {}).get("period", 60))
        records.append(
            {
                "id": task_id,
                "name": task.name,
                "bk_biz_id": task.bk_biz_id,
                "protocol": protocol,
                "status": status_value,
                "period": period,
                "subscription_ids": subscription_map.get(task_id, []),
                "independent_dataid": bool(
                    getattr(task, "independent_dataid", False) or getattr(task, "indepentent_dataid", False)
                ),
                "deploy_status": {
                    "status": deploy_status_map.get(task_id, status_value),
                    "message": "",
                },
                "available": _resolve_uptime_metric_value(task_data.get("available"), promql_data, "available"),
                "task_duration": _resolve_uptime_metric_value(
                    task_data.get("task_duration"), promql_data, "task_duration"
                ),
                "promql_data": promql_data,
            }
        )
    return {"tasks": records, "errors": []}


def check_custom_report(context: CheckContext) -> dict[str, Any]:
    from monitor_web.models.custom_report import CustomEventGroup, CustomTSTable

    metric_tables = list(
        CustomTSTable.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_biz_id=context.bk_biz_id)
        .order_by("time_series_group_id")
        .iterator()
    )
    metrics = _run_concurrently(
        metric_tables,
        lambda table: _build_custom_metric_record(context, table),
        DEFAULT_ITEM_CHECK_WORKERS,
    )

    event_groups = list(
        CustomEventGroup.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_biz_id=context.bk_biz_id)
        .prefetch_related("event_info_list")
        .order_by("bk_event_group_id")
        .iterator(chunk_size=100)
    )
    events = _run_concurrently(
        event_groups,
        lambda group: _build_custom_event_record(context, group),
        DEFAULT_ITEM_CHECK_WORKERS,
    )
    return {"custom_metrics": metrics, "custom_events": events, "errors": []}


def check_plugin_collect(context: CheckContext) -> dict[str, Any]:
    from monitor_web.collecting.deploy import get_collect_installer
    from monitor_web.collecting.resources.status import CollectTargetStatusTopoResource
    from monitor_web.models import CollectConfigMeta, CollectorPluginMeta

    collect_configs = list(
        CollectConfigMeta.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_biz_id=context.bk_biz_id)
        .select_related(
            "deployment_config",
            "deployment_config__plugin_version",
        )
        .order_by("id")
        .iterator()
    )
    plugin_ids = sorted({config.plugin_id for config in collect_configs})
    plugins = list(CollectorPluginMeta.objects.filter(bk_tenant_id=context.bk_tenant_id, plugin_id__in=plugin_ids))
    plugin_map = {plugin.plugin_id: plugin for plugin in plugins}
    plugin_type_map = {plugin.plugin_id: plugin.plugin_type for plugin in plugins}
    configs = _run_concurrently(
        collect_configs,
        lambda config: _build_collect_config_record(
            context,
            config,
            get_collect_installer,
            CollectTargetStatusTopoResource,
            plugin_type_map,
            plugin_map,
        ),
        DEFAULT_ITEM_CHECK_WORKERS,
    )
    return {"configs": configs, "errors": []}


def check_apm(context: CheckContext) -> dict[str, Any]:
    from apm.models import ApmApplication

    applications = list(
        ApmApplication.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_biz_id=context.bk_biz_id)
        .order_by("app_name")
        .iterator()
    )
    records = _run_concurrently(
        applications,
        lambda app: _build_apm_application_record(context, app),
        DEFAULT_ITEM_CHECK_WORKERS,
    )
    return {"applications": records, "errors": []}


def check_strategy(context: CheckContext) -> dict[str, Any]:
    from bkmonitor.models.strategy import StrategyModel

    strategies = list(
        StrategyModel.objects.filter(bk_biz_id=context.bk_biz_id)
        .order_by("id")
        .values("id", "name", "bk_biz_id", "is_enabled", "is_invalid", "invalid_type")
    )
    return {"strategies": strategies, "errors": []}


def _build_k8s_cluster_record(context: CheckContext, cluster) -> dict[str, Any]:
    data_ids = {
        "k8s_metric": _build_data_id_record(context, field="K8sMetricDataID", data_id=cluster.K8sMetricDataID),
        "custom_metric": _build_detail_data_id_record(
            context, field="CustomMetricDataID", data_id=cluster.CustomMetricDataID
        ),
        "k8s_event": _build_data_id_record(context, field="K8sEventDataID", data_id=cluster.K8sEventDataID),
    }
    custom_metric_sample = _extract_k8s_custom_metric_sample(
        cluster_id=cluster.cluster_id,
        data_id_status=data_ids["custom_metric"],
    )
    _drop_internal_kafka_latest_data(data_ids["custom_metric"])
    data_ids["custom_metric"].update(custom_metric_sample)

    return {
        "cluster_id": cluster.cluster_id,
        "bcs_api_cluster_id": cluster.bcs_api_cluster_id,
        "bk_biz_id": cluster.bk_biz_id,
        "bk_tenant_id": cluster.bk_tenant_id,
        "project_id": cluster.project_id,
        "status": cluster.status,
        "bk_env": cluster.bk_env,
        "operator_ns": cluster.operator_ns,
        "data_ids": data_ids,
        "extra_data_ids": {
            "custom_event_data_id": cluster.CustomEventDataID,
            "system_log_data_id": cluster.SystemLogDataID,
            "custom_log_data_id": cluster.CustomLogDataID,
        },
        "cluster_connectivity": _check_k8s_cluster_connectivity(cluster),
        "k8s_metric_landing": _check_k8s_metric_landing(context, cluster.cluster_id),
        "custom_metric_landing": _check_k8s_custom_metric_landing(context, custom_metric_sample),
        "event_landing": _check_k8s_event_landing(context, data_ids["k8s_event"]),
    }


def _build_custom_metric_record(context: CheckContext, table) -> dict[str, Any]:
    metric_fields = _safe_value(lambda: _get_custom_metric_fields(context, table), default=[])
    sample_metric = metric_fields[0]["name"] if metric_fields else ""
    return {
        "time_series_group_id": table.time_series_group_id,
        "bk_biz_id": table.bk_biz_id,
        "name": table.name,
        "scenario": table.scenario,
        "bk_data_id": table.bk_data_id,
        "table_id": table.table_id,
        "data_label": table.data_label,
        "protocol": table.protocol,
        "token": _safe_value(lambda: _get_custom_metric_token(context, table), default=""),
        "metric_fields": metric_fields,
        "kafka_status": _check_data_id_status(context, table.bk_data_id),
        "table_sample": _query_time_series_metric(
            context,
            table.table_id,
            sample_metric,
            data_label=_get_primary_data_label(table.data_label),
        ),
    }


def _build_custom_event_record(context: CheckContext, group) -> dict[str, Any]:
    event_names = [event.custom_event_name for event in group.event_info_list.all()]
    return {
        "bk_event_group_id": group.bk_event_group_id,
        "bk_biz_id": group.bk_biz_id,
        "name": group.name,
        "scenario": group.scenario,
        "is_enable": group.is_enable,
        "bk_data_id": group.bk_data_id,
        "table_id": group.table_id,
        "type": group.type,
        "data_label": group.data_label,
        "token": _safe_value(lambda: _get_custom_event_token(context, group), default=""),
        "event_names": event_names,
        "dimensions": _get_custom_event_dimensions(group),
        "kafka_status": _check_data_id_status(context, group.bk_data_id),
        "table_sample": _query_event_table(context, group.table_id),
    }


def _build_collect_config_record(
    context: CheckContext,
    config,
    get_collect_installer_func,
    collect_target_status_topo_resource,
    plugin_type_map: dict[str, str],
    plugin_map: dict[str, Any],
) -> dict[str, Any]:
    _bind_collect_config_plugin(config, plugin_map)
    status_records = _get_collect_status_records(context, config, get_collect_installer_func)
    targets = _build_collect_targets(status_records)
    no_data_info = _safe_value(
        lambda: collect_target_status_topo_resource.nodata_test(config, targets),
        default={},
    )
    return {
        "id": config.id,
        "bk_biz_id": config.bk_biz_id,
        "name": config.name,
        "collect_type": config.collect_type,
        "plugin_id": config.plugin_id,
        "plugin_type": plugin_type_map.get(config.plugin_id, ""),
        "target_object_type": config.target_object_type,
        "last_operation": config.last_operation,
        "operation_result": config.operation_result,
        "deploy_status": _build_collect_deploy_status(config, status_records),
        "data_status": _build_collect_data_status(context, config, targets, no_data_info),
    }


def _build_apm_application_record(context: CheckContext, app) -> dict[str, Any]:
    enabled = {
        "trace": app.is_enabled_trace,
        "metric": app.is_enabled_metric,
        "log": app.is_enabled_log,
        "profiling": app.is_enabled_profiling,
    }
    return {
        "application_id": app.id,
        "bk_biz_id": app.bk_biz_id,
        "app_name": app.app_name,
        "app_alias": app.app_alias,
        "is_enabled": app.is_enabled,
        "enabled": enabled,
        "token": _safe_value(lambda: app.get_bk_data_token(), default=""),
        "datasources": {
            "trace": _build_apm_trace_status(context, app, enabled["trace"]),
            "metric": _build_apm_metric_status(context, app, enabled["metric"]),
            "log": _build_apm_log_status(context, app, enabled["log"]),
            "profiling": _build_apm_profile_status(context, app, enabled["profiling"]),
        },
    }


def query_result_table_recent_data_status(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    table_id: str,
    data_source_label: str,
    data_type_label: str,
    start_time: int,
    end_time: int,
) -> dict[str, Any]:
    from metadata.models import ResultTable

    exists = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).exists()
    if not exists:
        return {
            "table_id": table_id,
            "exists": False,
            "has_data": None,
            "latest_time": None,
            "sample": {},
            "message": "result table not found",
        }
    return {
        "table_id": table_id,
        "exists": True,
        "has_data": None,
        "latest_time": None,
        "sample": {},
        "message": f"unsupported query type: {data_source_label}/{data_type_label}",
    }


def _build_data_id_record(context: CheckContext, *, field: str, data_id: int | None) -> dict[str, Any]:
    status = _check_data_id_status(context, data_id)
    return {
        "field": field,
        "data_id": data_id or 0,
        "exists": status["exists"],
        "has_kafka_data": status["has_kafka_data"],
        "latest_time": status["latest_time"],
        "message": status["message"],
        "raw_status": status,
    }


def _build_detail_data_id_record(context: CheckContext, *, field: str, data_id: int | None) -> dict[str, Any]:
    status = _check_data_id_status(context, data_id, keep_internal_kafka_latest_data=True)
    return {
        "field": field,
        "data_id": data_id or 0,
        "exists": status["exists"],
        "has_kafka_data": status["has_kafka_data"],
        "latest_time": status["latest_time"],
        "message": status["message"],
        "raw_status": status,
    }


def _check_data_id_status(
    context: CheckContext,
    data_id: int | None,
    *,
    keep_internal_kafka_latest_data: bool = False,
) -> dict[str, Any]:
    if data_id in INVALID_DATA_ID_VALUES:
        return {
            "bk_data_id": data_id or 0,
            "data_name": "",
            "exists": False,
            "has_kafka_data": None,
            "latest_time": None,
            "message": "empty data_id",
        }

    return _check_data_id_status_by_gse_kafka_tail(
        context,
        data_id=int(data_id),
        keep_internal_kafka_latest_data=keep_internal_kafka_latest_data,
    )


def _check_data_id_status_by_gse_kafka_tail(
    context: CheckContext,
    *,
    data_id: int,
    keep_internal_kafka_latest_data: bool,
) -> dict[str, Any]:
    from core.drf_resource import api
    from metadata.models import DataSource

    data_source = DataSource.objects.filter(bk_tenant_id=context.bk_tenant_id, bk_data_id=data_id).first()
    result = {
        "bk_data_id": data_id,
        "data_name": data_source.data_name if data_source else "",
        "exists": bool(data_source),
        "has_kafka_data": None,
        "latest_time": None,
        "message": "" if data_source else "datasource not found",
        "bkbase_status": "",
        "finished": False,
    }

    try:
        kafka_latest_data = api.metadata.kafka_tail(
            bk_tenant_id=context.bk_tenant_id,
            bk_data_id=data_id,
            size=3,
            use_gse_config=True,
        )
    except Exception as kafka_error:  # noqa: BLE001
        result["has_kafka_data"] = None
        result["message"] = (
            f"{result['message']}; gse kafka_tail failed: {kafka_error}"
            if result["message"]
            else f"gse kafka_tail failed: {kafka_error}"
        )
        return result

    result["has_kafka_data"] = bool(kafka_latest_data)
    result["finished"] = True
    if keep_internal_kafka_latest_data:
        result["_internal_kafka_latest_data"] = kafka_latest_data
    return result


def _query_promql_host_count(
    context: CheckContext,
    *,
    promql: str,
    filter_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = {"promql": promql, "has_data": None, "host_count": 0, "message": ""}
    try:
        records = _query_promql(context, promql=promql, filter_dict=filter_dict)
    except Exception as error:  # noqa: BLE001
        status["message"] = str(error)
        return status

    status["has_data"] = bool(records)
    status["host_count"] = _count_unique_hosts(records)
    return status


def _query_promql_objects(
    context: CheckContext,
    *,
    promql: str,
    object_fields: list[str],
    filter_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = {"promql": promql, "has_data": None, "reported_objects": [], "message": ""}
    try:
        records = _query_promql(context, promql=promql, filter_dict=filter_dict)
    except Exception as error:  # noqa: BLE001
        status["message"] = str(error)
        return status

    status["has_data"] = bool(records)
    status["reported_objects"] = [_extract_object_record(record, object_fields) for record in records]
    return status


def _count_unique_hosts(records: list[dict[str, Any]]) -> int:
    host_keys = set()
    for index, record in enumerate(records):
        ip = record.get("bk_target_ip") or record.get("ip") or record.get("target")
        cloud_id = record.get("bk_target_cloud_id") or record.get("bk_cloud_id")
        if ip is None and cloud_id is None:
            host_keys.add(("record", index))
        else:
            host_keys.add((str(cloud_id or ""), str(ip or "")))
    return len(host_keys)


def _query_promql(
    context: CheckContext,
    *,
    promql: str,
    filter_dict: dict[str, Any] | None = None,
    interval: int = DEFAULT_QUERY_INTERVAL,
) -> list[dict[str, Any]]:
    from bkmonitor.data_source import UnifyQuery, load_data_source
    from constants.data_source import DataSourceLabel, DataTypeLabel

    data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
    data_source = data_source_class(
        bk_biz_id=context.bk_biz_id,
        promql=promql,
        filter_dict=filter_dict or {},
        interval=interval,
    )
    query = UnifyQuery(bk_biz_id=context.bk_biz_id, data_sources=[data_source], expression="")
    return _jsonable(query.query_data(start_time=context.start_time_ms, end_time=context.end_time_ms))


def _extract_object_record(record: dict[str, Any], object_fields: list[str]) -> dict[str, Any]:
    result = {field: record.get(field) for field in object_fields if field in record}
    result["value"] = _extract_record_value(record)
    result["latest_time"] = record.get("_time_") or record.get("time") or record.get("dtEventTimeStamp")
    return result


def _extract_record_value(record: dict[str, Any]) -> Any:
    for key in ("_result_", "a", "A", "value", "count"):
        if key in record:
            return record[key]
    return None


def _to_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check_k8s_cluster_connectivity(cluster) -> dict[str, Any]:
    from kubernetes import client as k8s_client

    expected_resource_names = sorted(
        register_info["datasource_name"].lower() for register_info in cluster.DATASOURCE_REGISTER_INFO.values()
    )
    result = {
        "api_versions_ok": None,
        "dataid_resource_query_ok": None,
        "dataid_resource_api_version": (
            f"{metadata_config.BCS_RESOURCE_GROUP_NAME}/{metadata_config.BCS_RESOURCE_VERSION}"
        ),
        "expected_resource_names": expected_resource_names,
        "existing_resource_names": [],
        "missing_resource_names": expected_resource_names,
        "error": "",
    }
    try:
        api_client = cluster.api_client
        k8s_client.ApisApi(api_client).get_api_versions()
        result["api_versions_ok"] = True
        custom_api = k8s_client.CustomObjectsApi(api_client)
        resources = custom_api.list_cluster_custom_object(
            group=metadata_config.BCS_RESOURCE_GROUP_NAME,
            version=metadata_config.BCS_RESOURCE_VERSION,
            plural=metadata_config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        )
        existing_names = sorted(item["metadata"]["name"] for item in resources.get("items", []))
        result.update(
            dataid_resource_query_ok=True,
            existing_resource_names=existing_names,
            missing_resource_names=sorted(set(expected_resource_names) - set(existing_names)),
        )
    except Exception as error:  # noqa: BLE001
        result["error"] = str(error)
        if result["api_versions_ok"] is None:
            result["api_versions_ok"] = False
        if result["dataid_resource_query_ok"] is None:
            result["dataid_resource_query_ok"] = False
    return result


def _check_k8s_metric_landing(context: CheckContext, cluster_id: str) -> dict[str, Any]:
    promql = f'avg(bkmonitor:container_cpu_usage_seconds_total{{bcs_cluster_id="{cluster_id}"}}) by (bcs_cluster_id)'
    result = _query_promql_objects(context, promql=promql, object_fields=["bcs_cluster_id"])
    return {
        "promql": promql,
        "has_data": result["has_data"],
        "value": _extract_first_value(result["reported_objects"]),
        "message": result.get("message", ""),
    }


def _extract_k8s_custom_metric_sample(cluster_id: str, data_id_status: dict[str, Any]) -> dict[str, Any]:
    for message in data_id_status.get("raw_status", {}).get("_internal_kafka_latest_data") or []:
        for item in _iter_data_items(message):
            dimension = item.get("dimension") or {}
            if dimension.get("bcs_cluster_id") != cluster_id:
                continue
            metrics = item.get("metrics") or {}
            if not metrics:
                continue
            metric_name = next(iter(metrics.keys()))
            return {
                "sample_metric": metric_name,
                "sample_bcs_cluster_id": cluster_id,
            }
    return {"sample_metric": "", "sample_bcs_cluster_id": ""}


def _drop_internal_kafka_latest_data(record: dict[str, Any]) -> None:
    raw_status = record.get("raw_status")
    if isinstance(raw_status, dict):
        raw_status.pop("_internal_kafka_latest_data", None)


def _iter_data_items(message: Any):
    if isinstance(message, list):
        for sub_message in message:
            yield from _iter_data_items(sub_message)
        return
    if not isinstance(message, dict):
        return
    data = message.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data


def _check_k8s_custom_metric_landing(context: CheckContext, sample: dict[str, Any]) -> dict[str, Any]:
    metric_name = sample.get("sample_metric") or ""
    cluster_id = sample.get("sample_bcs_cluster_id") or ""
    if not metric_name or not cluster_id:
        return {
            "sample_metric": metric_name,
            "sample_bcs_cluster_id": cluster_id,
            "promql": "",
            "has_data": None,
            "value": None,
            "message": "no kafka sample metric",
        }
    promql = f'topk(1, bkmonitor:{metric_name}{{bcs_cluster_id="{cluster_id}"}})'
    result = _query_promql_objects(context, promql=promql, object_fields=["bcs_cluster_id"])
    return {
        "sample_metric": metric_name,
        "sample_bcs_cluster_id": cluster_id,
        "promql": promql,
        "has_data": result["has_data"],
        "value": _extract_first_value(result["reported_objects"]),
        "message": result.get("message", ""),
    }


def _check_k8s_event_landing(context: CheckContext, data_id_record: dict[str, Any]) -> dict[str, Any]:
    result = {
        "has_kafka_event": data_id_record.get("has_kafka_data"),
        "has_query_event": None,
        "latest_time": data_id_record.get("latest_time"),
        "sample": {},
        "message": "",
    }
    table_id = _find_first_table_id(context.bk_tenant_id, data_id_record.get("data_id"))
    if not table_id:
        result["message"] = "event table not found"
        return result
    table_status = _query_event_table(context, table_id)
    result.update(
        has_query_event=table_status["has_data"],
        latest_time=table_status.get("latest_time") or result["latest_time"],
        sample=table_status.get("sample") or {},
        message=table_status.get("message", ""),
    )
    return result


def _find_first_table_id(bk_tenant_id: str, data_id: int | None) -> str:
    if data_id in INVALID_DATA_ID_VALUES:
        return ""
    from metadata.models import DataSourceResultTable

    return (
        DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)
        .values_list("table_id", flat=True)
        .first()
        or ""
    )


def _extract_first_value(records: list[dict[str, Any]]) -> Any:
    return records[0].get("value") if records else None


def _get_uptime_subscription_map(model_cls, task_ids: list[int], bk_biz_id: int) -> dict[int, list[int]]:
    if not task_ids:
        return {}
    subscription_map: dict[int, list[int]] = {}
    for task_id, subscription_id in (
        model_cls.objects.filter(
            is_deleted=False,
            uptimecheck_id__in=task_ids,
            bk_biz_id=bk_biz_id,
            subscription_id__gt=0,
        )
        .values_list("uptimecheck_id", "subscription_id")
        .order_by("uptimecheck_id", "subscription_id")
    ):
        subscription_map.setdefault(int(task_id), []).append(int(subscription_id))
    return subscription_map


def _build_uptime_list_page_map(list_page_data: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    task_map = {}
    for task in list_page_data:
        task_id = task.get("id")
        if task_id in (None, ""):
            continue
        try:
            task_map[int(task_id)] = task
        except (TypeError, ValueError):
            continue
    return task_map


def _resolve_uptime_metric_value(list_page_value: Any, promql_data: dict[str, dict[str, Any]], field: str) -> Any:
    if list_page_value is not None:
        return list_page_value

    metric_status = promql_data.get(field) or {}
    if not metric_status.get("has_data"):
        return None

    value = metric_status.get("value")
    if value is None:
        return None
    if field == "available":
        return float(value) * 100
    return value


def _query_uptime_promql_by_task(context: CheckContext, tasks: list[Any]) -> dict[int, dict[str, dict[str, Any]]]:
    result = {int(task.id): _empty_uptime_promql_data() for task in tasks}
    task_ids_by_query: dict[tuple[str, int], list[int]] = defaultdict(list)
    for task in tasks:
        protocol = str(_enum_value(task.protocol)).lower()
        period = int((getattr(task, "config", {}) or {}).get("period", 60))
        task_ids_by_query[(protocol, period)].append(int(task.id))

    query_jobs = []
    for (protocol, period), task_ids in task_ids_by_query.items():
        for field in ("available", "task_duration"):
            query_jobs.append((protocol, period, field, task_ids))

    for _, _, field, task_ids, promql, query_status in _run_concurrently(
        query_jobs,
        lambda job: _query_uptime_promql_status(context, job),
        DEFAULT_ITEM_CHECK_WORKERS,
    ):
        records_by_task_id = _group_promql_records_by_task_id(query_status.get("reported_objects") or [])
        for task_id in task_ids:
            record = records_by_task_id.get(task_id)
            result[task_id][field] = _build_uptime_task_promql_status(
                promql=promql,
                query_has_data=query_status.get("has_data"),
                message=query_status.get("message", ""),
                record=record,
            )
    return result


def _query_uptime_promql_status(
    context: CheckContext, job: tuple[str, int, str, list[int]]
) -> tuple[str, int, str, list[int], str, dict[str, Any]]:
    protocol, period, field, task_ids = job
    promql = _build_uptime_promql(protocol=protocol, period=period, field=field)
    query_status = _query_promql_objects(context, promql=promql, object_fields=["task_id"])
    return protocol, period, field, task_ids, promql, query_status


def _empty_uptime_promql_data() -> dict[str, dict[str, Any]]:
    return {
        "available": {"promql": "", "has_data": None, "value": None, "latest_time": None, "message": ""},
        "task_duration": {"promql": "", "has_data": None, "value": None, "latest_time": None, "message": ""},
    }


def _build_uptime_promql(
    *,
    protocol: str,
    period: int,
    field: str,
) -> str:
    metric_name = f"bkmonitor:uptimecheck_{protocol}:{field}"
    if field == "task_duration":
        return f"topk by (task_id) (1, max_over_time({metric_name}[{period}s]))"
    return f"bottomk by (task_id) (1, min_over_time({metric_name}[{period}s]))"


def _group_promql_records_by_task_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    records_by_task_id = {}
    for record in records:
        task_id = record.get("task_id")
        if task_id in (None, ""):
            continue
        try:
            records_by_task_id[int(task_id)] = record
        except (TypeError, ValueError):
            continue
    return records_by_task_id


def _build_uptime_task_promql_status(
    *,
    promql: str,
    query_has_data: bool | None,
    message: str,
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    if query_has_data is None:
        has_data = None
    else:
        has_data = bool(record)
    return {
        "promql": promql,
        "has_data": has_data,
        "value": record.get("value") if record else None,
        "latest_time": record.get("latest_time") if record else None,
        "message": message,
    }


def _get_custom_metric_fields(context: CheckContext, table) -> list[dict[str, Any]]:
    from core.drf_resource import api

    fields = []
    scope_list = api.metadata.query_time_series_scope(
        bk_tenant_id=context.bk_tenant_id,
        group_id=table.time_series_group_id,
        include_metrics=True,
    )
    for scope in scope_list:
        scope_name = scope.get("scope_name", "")
        for metric in scope.get("metric_list", []):
            metric_config = metric.get("field_config", {})
            if metric_config.get("disabled"):
                continue
            fields.append(
                {
                    "scope_name": scope_name,
                    "name": metric.get("metric_name", ""),
                    "unit": metric_config.get("unit", ""),
                    "aggregate_method": metric_config.get("aggregate_method", ""),
                }
            )
    return fields


def _get_custom_metric_token(context: CheckContext, table) -> str:
    from bkmonitor.utils.cipher import transform_data_id_to_token
    from core.drf_resource import api

    time_series_groups = api.metadata.get_time_series_group(
        time_series_group_id=table.time_series_group_id,
        bk_tenant_id=context.bk_tenant_id,
        with_result_table_info=False,
    )
    for time_series_group in time_series_groups:
        if time_series_group.get("token"):
            return time_series_group["token"]

    if table.protocol == "prometheus":
        return transform_data_id_to_token(
            metric_data_id=table.bk_data_id,
            bk_biz_id=table.bk_biz_id,
            app_name=table.name,
        )

    data_id_info = api.metadata.get_data_id(
        bk_tenant_id=context.bk_tenant_id,
        bk_data_id=table.bk_data_id,
        with_rt_info=False,
    )
    return data_id_info.get("token", "")


def _get_custom_event_token(context: CheckContext, group) -> str:
    from core.drf_resource import api

    event_group_info = api.metadata.get_event_group(
        bk_tenant_id=context.bk_tenant_id,
        event_group_id=group.bk_event_group_id,
        with_result_table_info=False,
        need_refresh=False,
        event_infos_limit=1,
    )
    if event_group_info.get("token"):
        return event_group_info["token"]

    data_id_info = api.metadata.get_data_id(
        bk_tenant_id=context.bk_tenant_id,
        bk_data_id=group.bk_data_id,
        with_rt_info=False,
    )
    return data_id_info.get("token", "")


def _get_custom_event_dimensions(group) -> list[dict[str, Any]]:
    dimensions = []
    for event in group.event_info_list.all():
        for dimension in event.dimension_list or []:
            dimensions.append({"event_name": event.custom_event_name, **dimension})
    return dimensions


def _get_primary_data_label(data_label: str | None) -> str:
    return (data_label or "").split(",")[0].strip()


def _query_time_series_metric(
    context: CheckContext, table_id: str, metric_name: str, data_label: str | None = None
) -> dict[str, Any]:
    if not table_id:
        return {"has_data": None, "latest_time": None, "value": None, "message": "empty table_id"}
    if not metric_name:
        return {"has_data": False, "latest_time": None, "value": None, "message": "empty metric field"}

    try:
        from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
        from constants.data_source import DataSourceLabel, DataTypeLabel

        q = (
            QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
            .table(table_id)
            .data_label(data_label)
            .metric(field=metric_name, method="AVG", alias="a")
        )
        records = list(
            UnifyQuerySet()
            .add_query(q)
            .scope(context.bk_biz_id)
            .start_time(context.start_time_ms)
            .end_time(context.end_time_ms)
            .time_align(False)
            .limit(1)
        )
    except Exception as error:  # noqa: BLE001
        return {"has_data": None, "latest_time": None, "value": None, "message": str(error)}

    first_record = records[0] if records else {}
    return {
        "has_data": bool(records),
        "latest_time": first_record.get("_time_") or first_record.get("time"),
        "value": _extract_record_value(first_record),
        "message": "",
    }


def _query_event_table(context: CheckContext, table_id: str) -> dict[str, Any]:
    if not table_id:
        return {"has_data": None, "latest_time": None, "sample": {}, "message": "empty table_id"}
    try:
        from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
        from constants.data_source import DataSourceLabel, DataTypeLabel

        q = (
            QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM))
            .table(table_id)
            .values("event_name")
            .order_by("-time")
        )
        records = list(
            UnifyQuerySet()
            .add_query(q)
            .scope(context.bk_biz_id)
            .start_time(context.start_time_ms)
            .end_time(context.end_time_ms)
            .time_align(False)
            .limit(1)
        )
    except Exception as error:  # noqa: BLE001
        return {"has_data": None, "latest_time": None, "sample": {}, "message": str(error)}

    first_record = records[0] if records else {}
    return {
        "has_data": bool(records),
        "latest_time": first_record.get("_time_") or first_record.get("time") or first_record.get("dtEventTimeStamp"),
        "sample": first_record,
        "message": "",
    }


def _get_collect_status_records(context: CheckContext, config, get_collect_installer_func) -> list[dict[str, Any]]:
    try:
        installer = get_collect_installer_func(config)
        if hasattr(installer, "_process_nodeman_task_result"):
            return _query_nodeman_collect_status_silently(context, config, installer)
        return _jsonable(installer.status(diff=False))
    except Exception as error:  # noqa: BLE001
        return [{"status": "UNKNOWN", "message": str(error), "child": []}]


def _query_nodeman_collect_status_silently(
    context: CheckContext,
    config,
    installer,
) -> list[dict[str, Any]]:
    subscription_id = config.deployment_config.subscription_id
    if not subscription_id:
        return []
    try:
        from core.drf_resource import api

        task_result = _call_with_local_tenant(
            context.bk_tenant_id,
            lambda: api.node_man.batch_task_result(subscription_id=subscription_id, need_detail=True),
        )
    except Exception as error:  # noqa: BLE001 - status checks should report errors without noisy logger side effects.
        return [
            {
                "status": "UNKNOWN",
                "message": f"query nodeman task result failed: {error}",
                "child": [],
            }
        ]
    instance_statuses = installer._process_nodeman_task_result(task_result)
    return [{"name": "default", "child": instance_statuses}]


def _call_with_local_tenant(bk_tenant_id: str, func: Callable[[], Any]) -> Any:
    from bkmonitor.utils.local import local
    from bkmonitor.utils.tenant import set_local_tenant_id

    preserved = getattr(local, "bk_tenant_id", None) if hasattr(local, "bk_tenant_id") else None
    had_value = hasattr(local, "bk_tenant_id")
    set_local_tenant_id(bk_tenant_id)
    try:
        return func()
    finally:
        if had_value:
            setattr(local, "bk_tenant_id", preserved)
        elif hasattr(local, "bk_tenant_id"):
            delattr(local, "bk_tenant_id")


def _build_collect_targets(status_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = []
    for node in status_records:
        for instance in node.get("child", []):
            if instance.get("service_instance_id"):
                targets.append({"bk_target_service_instance_id": instance["service_instance_id"]})
            elif instance.get("ip") and instance.get("bk_cloud_id") is not None:
                targets.append({"bk_target_ip": instance["ip"], "bk_target_cloud_id": instance["bk_cloud_id"]})
    return targets


def _build_collect_deploy_status(config, status_records: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = []
    abnormal_samples = []
    for node in status_records:
        for instance in node.get("child", []):
            status = instance.get("status", "")
            statuses.append(status)
            if status and status.upper() not in {"SUCCESS", "RUNNING"} and len(abnormal_samples) < 20:
                abnormal_samples.append(_extract_collect_instance_sample(instance))
    return {
        "status": config.task_status,
        "message": next((node.get("message", "") for node in status_records if node.get("message")), ""),
        "instance_status_counts": dict(Counter(statuses)),
        "abnormal_instance_samples": abnormal_samples,
    }


def _build_collect_data_status(
    context: CheckContext,
    config,
    targets: list[dict[str, Any]],
    no_data_info: dict[str, bool],
) -> dict[str, Any]:
    no_data_samples = []
    no_data_count = 0
    for target in targets:
        key = _target_key(target)
        if no_data_info.get(key):
            no_data_count += 1
            if len(no_data_samples) < 20:
                no_data_samples.append(target)
    transfer_count_status = {}
    if not targets:
        transfer_count_status = _query_collect_transfer_count_status(context, config)
        has_data = transfer_count_status.get("has_data")
        message = transfer_count_status.get("message", "")
    elif no_data_info:
        has_data = no_data_count < len(targets)
        message = ""
    else:
        has_data = None
        message = "no data check result"
    return {
        "has_data": has_data,
        "checked_instance_count": len(targets),
        "no_data_instance_count": no_data_count,
        "no_data_instance_samples": no_data_samples,
        "transfer_count_status": transfer_count_status,
        "message": message,
    }


def _query_collect_transfer_count_status(context: CheckContext, config) -> dict[str, Any]:
    status = {
        "method": "datalink.transfer_count_series",
        "interval_option": "minute",
        "has_data": None,
        "latest_time": None,
        "value": None,
        "message": "",
    }

    try:
        series = _query_collect_transfer_count_series(context, config)
    except Exception as error:  # noqa: BLE001
        status["message"] = str(error)
        return status

    datapoints = _extract_transfer_count_datapoints(series)
    latest_datapoint = next((datapoint for datapoint in reversed(datapoints) if datapoint[0] is not None), None)
    status["has_data"] = any((datapoint[0] or 0) > 0 for datapoint in datapoints)
    if latest_datapoint:
        status["latest_time"] = latest_datapoint[1]
        status["value"] = latest_datapoint[0]
    status["series_count"] = len(series)
    status["datapoint_count"] = len(datapoints)
    return status


def _query_collect_transfer_count_series(context: CheckContext, config) -> list[dict[str, Any]]:
    from core.drf_resource import resource

    return _call_with_local_tenant(
        context.bk_tenant_id,
        lambda: resource.datalink.transfer_count_series(
            bk_biz_id=context.bk_biz_id,
            collect_config_id=config.id,
            start_time=context.start_time,
            end_time=context.end_time,
            interval_option="minute",
        ),
    )


def _extract_transfer_count_datapoints(series: list[dict[str, Any]]) -> list[tuple[float | int | None, int | None]]:
    datapoints = []
    for item in series or []:
        for datapoint in item.get("datapoints") or []:
            if not isinstance(datapoint, list | tuple) or len(datapoint) < 2:
                continue
            datapoints.append((_to_number(datapoint[0]), datapoint[1]))
    return datapoints


def _bind_collect_config_plugin(config, plugin_map: dict[str, Any]) -> None:
    plugin = plugin_map.get(getattr(config, "plugin_id", ""))
    deployment_config = getattr(config, "deployment_config", None)
    plugin_version = getattr(deployment_config, "plugin_version", None) if deployment_config else None
    if plugin and plugin_version:
        plugin_version.plugin = plugin


def _target_key(target: dict[str, Any]) -> str:
    if "bk_target_service_instance_id" in target:
        return str(target["bk_target_service_instance_id"])
    return f"{target.get('bk_target_ip')}|{target.get('bk_target_cloud_id')}"


def _extract_collect_instance_sample(instance: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": instance.get("instance_id", ""),
        "ip": instance.get("ip", ""),
        "bk_cloud_id": instance.get("bk_cloud_id"),
        "service_instance_id": instance.get("service_instance_id"),
        "status": instance.get("status", ""),
        "message": instance.get("message", ""),
    }


def _base_apm_datasource_status(context: CheckContext, datasource, enabled: bool, method: str) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "exists": bool(datasource),
            "bk_data_id": getattr(datasource, "bk_data_id", 0) if datasource else 0,
            "result_table_id": getattr(datasource, "result_table_id", "") if datasource else "",
            "table_id": getattr(datasource, "table_id", "") if datasource else "",
            "data_name": getattr(datasource, "data_name", "") if datasource else "",
            "data_id_status": _disabled_data_id_status(),
            "data_status": _empty_apm_data_status(method, "disabled"),
        }
    if not datasource:
        return {
            "enabled": True,
            "exists": False,
            "bk_data_id": 0,
            "result_table_id": "",
            "table_id": "",
            "data_name": "",
            "data_id_status": _missing_data_id_status(),
            "data_status": _empty_apm_data_status(method, "datasource missing"),
        }
    return {
        "enabled": True,
        "exists": True,
        "bk_data_id": datasource.bk_data_id,
        "result_table_id": datasource.result_table_id,
        "table_id": datasource.table_id,
        "data_name": datasource.data_name,
        "data_id_status": _check_data_id_status(context, datasource.bk_data_id),
    }


def _build_apm_trace_status(context: CheckContext, app, enabled: bool) -> dict[str, Any]:
    datasource = app.trace_datasource
    status = _base_apm_datasource_status(context, datasource, enabled, "trace_query_guard")
    status.update(
        index_set_id=getattr(datasource, "index_set_id", None),
    )
    if enabled and datasource:
        status["data_status"] = _query_apm_trace(context, app, datasource)
    return status


def _build_apm_metric_status(context: CheckContext, app, enabled: bool) -> dict[str, Any]:
    datasource = app.metric_datasource
    status = _base_apm_datasource_status(context, datasource, enabled, "unify_query_time_series")
    status.update(
        time_series_group_id=getattr(datasource, "time_series_group_id", 0),
        sample_metric="",
    )
    if enabled and datasource:
        sample_metric = _pick_apm_metric_name() or ""
        status["sample_metric"] = sample_metric
        status["data_status"] = {
            "method": "unify_query_time_series",
            **_query_time_series_metric(context, datasource.result_table_id or datasource.table_id, sample_metric),
        }
    return status


def _build_apm_log_status(context: CheckContext, app, enabled: bool) -> dict[str, Any]:
    datasource = app.log_datasource
    status = _base_apm_datasource_status(context, datasource, enabled, "bk_log_search")
    status.update(
        index_set_id=getattr(datasource, "index_set_id", None),
    )
    if enabled and datasource:
        status["data_status"] = _query_apm_log(context, datasource)
    return status


def _build_apm_profile_status(context: CheckContext, app, enabled: bool) -> dict[str, Any]:
    datasource = app.profile_datasource
    status = _base_apm_datasource_status(context, datasource, enabled, "profile_query_template")
    if enabled and datasource:
        status["data_status"] = _query_apm_profile(context, app)
    return status


def _disabled_data_id_status() -> dict[str, Any]:
    return {"exists": None, "has_kafka_data": None, "latest_time": None, "message": "disabled"}


def _missing_data_id_status() -> dict[str, Any]:
    return {"exists": False, "has_kafka_data": None, "latest_time": None, "message": "datasource missing"}


def _empty_apm_data_status(method: str, message: str) -> dict[str, Any]:
    return {"method": method, "has_data": None, "latest_time": None, "message": message}


def _query_apm_trace(context: CheckContext, app, datasource) -> dict[str, Any]:
    try:
        from bkmonitor.data_source.unify_query.builder import UnifyQuerySet
        from bkmonitor.data_source.utils.apm import TraceDatasourceTarget, TraceQueryGuard
        from constants.apm import OtlpKey, ResourceAttributes

        target = TraceDatasourceTarget.build(
            app.bk_biz_id, app.app_name, datasource.result_table_id or datasource.table_id
        )
        q = (
            TraceQueryGuard.get_q([target])
            .time_field(OtlpKey.END_TIME)
            .values(OtlpKey.TRACE_ID, OtlpKey.SPAN_ID, OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME))
        )
        records = list(
            UnifyQuerySet()
            .add_query(q)
            .scope(context.bk_biz_id)
            .time_align(False)
            .start_time(context.start_time_ms)
            .end_time(context.end_time_ms)
            .limit(1)
        )
    except Exception as error:  # noqa: BLE001
        return {
            "method": "trace_query_guard",
            "has_data": None,
            "latest_time": None,
            "message": str(error),
        }

    first_record = records[0] if records else {}
    return {
        "method": "trace_query_guard",
        "has_data": bool(records),
        "latest_time": first_record.get("end_time") or first_record.get("dtEventTimeStamp") or first_record.get("time"),
        "message": "",
    }


def _query_apm_log(context: CheckContext, datasource) -> dict[str, Any]:
    if not datasource.index_set_id:
        return {
            "method": "bk_log_search",
            "has_data": None,
            "latest_time": None,
            "message": "empty index_set_id",
        }
    try:
        from core.drf_resource import api

        response = _call_with_local_tenant(
            context.bk_tenant_id,
            lambda: api.log_search.es_query_search(
                index_set_id=datasource.index_set_id,
                start_time=context.start_time,
                end_time=context.end_time,
                size=1,
                start=0,
            ),
        )
        hits = response.get("hits", {}).get("hits", [])
    except Exception as error:  # noqa: BLE001
        return {"method": "bk_log_search", "has_data": None, "latest_time": None, "message": str(error)}

    source = hits[0].get("_source", {}) if hits else {}
    return {
        "method": "bk_log_search",
        "has_data": bool(hits),
        "latest_time": source.get("dtEventTimeStamp") or source.get("time"),
        "message": "",
    }


def _query_apm_profile(context: CheckContext, app) -> dict[str, Any]:
    try:
        from apm_web.profile.doris.querier import QueryTemplate

        template = QueryTemplate(app.bk_biz_id, app.app_name)
        has_data = template.exist_data(context.start_time_ms, context.end_time_ms)
    except Exception as error:  # noqa: BLE001
        return {
            "method": "profile_query_template",
            "has_data": None,
            "latest_time": None,
            "message": str(error),
        }

    return {
        "method": "profile_query_template",
        "has_data": bool(has_data),
        "latest_time": None,
        "message": "",
    }


def _pick_apm_metric_name() -> str:
    return "request_count"


def _safe_value(func: Callable[[], Any], default: Any = None) -> Any:
    try:
        return _jsonable(func())
    except Exception:
        return default


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(sub_value) for key, sub_value in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, enum.Enum) else value
