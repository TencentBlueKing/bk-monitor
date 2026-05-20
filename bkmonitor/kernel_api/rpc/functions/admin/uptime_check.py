"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from enum import Enum
from typing import Any

from django.db.models import Count, Q

from bk_monitor_base.uptime_check import (
    BEAT_STATUS,
    UptimeCheckNode,
    UptimeCheckNodeModel,
    UptimeCheckNodeIPType,
    UptimeCheckTask,
    UptimeCheckTaskModel,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
    UptimeCheckTaskSubscription,
    list_groups,
)
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    serialize_value,
)

FUNC_UPTIME_CHECK_NODE_LIST = "admin.uptime_check.node_list"
FUNC_UPTIME_CHECK_NODE_DETAIL = "admin.uptime_check.node_detail"
FUNC_UPTIME_CHECK_TASK_LIST = "admin.uptime_check.task_list"
FUNC_UPTIME_CHECK_TASK_DETAIL = "admin.uptime_check.task_detail"

NODE_ORDERING_FIELDS = {
    "id",
    "bk_biz_id",
    "name",
    "ip",
    "bk_host_id",
    "plat_id",
    "carrieroperator",
    "create_time",
    "update_time",
}

TASK_ORDERING_FIELDS = {
    "id",
    "bk_biz_id",
    "name",
    "protocol",
    "status",
    "check_interval",
    "create_time",
    "update_time",
}

DATA_ID_CONTEXT_KEYS = {"data_id", "dataid", "bk_data_id"}
SENSITIVE_CONTEXT_KEYS = {"password", "passwd", "token", "secret", "authorization", "auth_config", "headers"}
LARGE_CONTEXT_KEYS = {"tasks", "node_list", "target_host_list", "config_hosts", "nodes", "target_hosts"}
TASK_LIST_VALUE_FIELDS = (
    "id",
    "bk_biz_id",
    "name",
    "protocol",
    "status",
    "indepentent_dataid",
    "check_interval",
    "is_deleted",
    "create_user",
    "create_time",
    "update_user",
    "update_time",
)
TASK_DETAIL_MODEL_FIELDS = TASK_LIST_VALUE_FIELDS
NODE_MODEL_ONLY_FIELDS = (
    "id",
    "bk_tenant_id",
    "bk_biz_id",
    "name",
    "ip",
    "bk_host_id",
    "plat_id",
    "ip_type",
    "location",
    "carrieroperator",
    "is_common",
    "biz_scope",
    "create_user",
    "create_time",
    "update_user",
    "update_time",
)
MAX_DETAIL_RELATION_ITEMS = 200
SUMMARY_SAMPLE_SIZE = 3


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _normalize_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_protocol(value: Any) -> UptimeCheckTaskProtocol | None:
    if value in (None, ""):
        return None
    try:
        return UptimeCheckTaskProtocol(str(value).upper())
    except ValueError as error:
        raise CustomException(message=f"不支持的 protocol: {value}") from error


def _normalize_task_status(value: Any) -> UptimeCheckTaskStatus | None:
    if value in (None, ""):
        return None
    try:
        return UptimeCheckTaskStatus(str(value))
    except ValueError as error:
        raise CustomException(message=f"不支持的 status: {value}") from error


def _normalize_ip_type(value: Any) -> UptimeCheckNodeIPType | None:
    if value in (None, ""):
        return None
    try:
        return UptimeCheckNodeIPType(int(value))
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"不支持的 ip_type: {value}") from error


def _paginate_items(items: list[Any], *, page: int, page_size: int) -> tuple[list[Any], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


def _is_node_visible_for_biz(node: Any, bk_biz_id: int | None) -> bool:
    if bk_biz_id is None or node.bk_biz_id == bk_biz_id:
        return True
    if not node.is_common:
        return False
    return not node.biz_scope or bk_biz_id in node.biz_scope


def _paginate_node_queryset(
    queryset: Any,
    *,
    bk_biz_id: int | None,
    page: int,
    page_size: int,
    needs_scope_filter: bool,
) -> tuple[list[UptimeCheckNodeModel], int]:
    offset = (page - 1) * page_size
    if not needs_scope_filter:
        total = queryset.count()
        return list(queryset[offset : offset + page_size]), total

    total = 0
    page_nodes: list[UptimeCheckNodeModel] = []
    for node in queryset.iterator(chunk_size=1000):
        if not _is_node_visible_for_biz(node, bk_biz_id):
            continue
        if total >= offset and len(page_nodes) < page_size:
            page_nodes.append(node)
        total += 1
    return page_nodes, total


def _serialize_define_datetime(value: Any) -> Any:
    return serialize_value(value) if value else None


def _build_node_query(params: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    node_id = _normalize_int(params.get("node_id"), "node_id")
    if node_id is not None:
        query["node_id"] = node_id
    bk_host_id = _normalize_int(params.get("bk_host_id"), "bk_host_id")
    if bk_host_id is not None:
        query["bk_host_ids"] = [bk_host_id]
    plat_id = _normalize_int(params.get("plat_id"), "plat_id")
    if plat_id is not None:
        query["plat_id"] = plat_id
    ip = _normalize_string(params.get("ip"))
    if ip:
        query["ip"] = ip
    name = _normalize_string(params.get("name"))
    if name:
        query["name"] = name
    carrieroperator = _normalize_string(params.get("carrieroperator"))
    if carrieroperator:
        query["carrieroperator"] = carrieroperator
    ip_type = _normalize_ip_type(params.get("ip_type"))
    if ip_type is not None:
        query["ip_type"] = ip_type
    is_common = normalize_optional_bool(params.get("is_common"), "is_common")
    if is_common is not None:
        query["is_common"] = is_common
    include_common = normalize_optional_bool(params.get("include_common"), "include_common")
    if include_common is not None:
        query["include_common"] = include_common
    return query


def _build_node_queryset(
    *,
    bk_tenant_id: str,
    bk_biz_id: int | None,
    params: dict[str, Any],
    ordering: str,
) -> tuple[Any, bool]:
    include_common = normalize_optional_bool(params.get("include_common"), "include_common")
    queryset = UptimeCheckNodeModel.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    needs_scope_filter = False
    if bk_biz_id is not None:
        if include_common:
            queryset = queryset.filter(Q(bk_biz_id=bk_biz_id) | Q(is_common=True))
            needs_scope_filter = True
        else:
            queryset = queryset.filter(bk_biz_id=bk_biz_id)

    node_id = _normalize_int(params.get("node_id"), "node_id")
    if node_id is not None:
        queryset = queryset.filter(pk=node_id)
    bk_host_id = _normalize_int(params.get("bk_host_id"), "bk_host_id")
    if bk_host_id is not None:
        queryset = queryset.filter(bk_host_id=bk_host_id)
    plat_id = _normalize_int(params.get("plat_id"), "plat_id")
    if plat_id is not None:
        queryset = queryset.filter(plat_id=plat_id)
    ip = _normalize_string(params.get("ip"))
    if ip:
        queryset = queryset.filter(ip=ip)
    name = _normalize_string(params.get("name"))
    if name:
        queryset = queryset.filter(name__icontains=name)
    carrieroperator = _normalize_string(params.get("carrieroperator"))
    if carrieroperator:
        queryset = queryset.filter(carrieroperator=carrieroperator)
    ip_type = _normalize_ip_type(params.get("ip_type"))
    if ip_type is not None:
        queryset = queryset.filter(ip_type=ip_type.value)
    is_common = normalize_optional_bool(params.get("is_common"), "is_common")
    if is_common is not None:
        queryset = queryset.filter(is_common=is_common)
        needs_scope_filter = needs_scope_filter and is_common is not False

    return queryset.only(*NODE_MODEL_ONLY_FIELDS).order_by(ordering), needs_scope_filter


def _build_task_query(params: dict[str, Any]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    task_id = _normalize_int(params.get("task_id"), "task_id")
    if task_id is not None:
        query["task_id"] = task_id
    name = _normalize_string(params.get("name"))
    if name:
        query["name"] = name
    protocol = _normalize_protocol(params.get("protocol"))
    if protocol is not None:
        query["protocol"] = protocol
    status = _normalize_task_status(params.get("status"))
    if status is not None:
        query["status"] = status
    node_id = _normalize_int(params.get("node_id"), "node_id")
    if node_id is not None:
        query["node_ids"] = [node_id]
    group_id = _normalize_int(params.get("group_id"), "group_id")
    if group_id is not None:
        query["group_ids"] = [group_id]
    return query


def _build_task_queryset(
    *, bk_biz_id: int | None, params: dict[str, Any], ordering: str
) -> Any:
    queryset = UptimeCheckTaskModel.objects.all()
    include_deleted = normalize_optional_bool(params.get("include_deleted"), "include_deleted")
    is_deleted = normalize_optional_bool(params.get("is_deleted"), "is_deleted")
    if is_deleted is not None:
        queryset = queryset.filter(is_deleted=is_deleted)
    elif not include_deleted:
        queryset = queryset.filter(is_deleted=False)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)

    task_id = _normalize_int(params.get("task_id"), "task_id")
    if task_id is not None:
        queryset = queryset.filter(pk=task_id)
    name = _normalize_string(params.get("name"))
    if name:
        queryset = queryset.filter(name__icontains=name)
    protocol = _normalize_protocol(params.get("protocol"))
    if protocol is not None:
        queryset = queryset.filter(protocol=protocol.value)
    status = _normalize_task_status(params.get("status"))
    if status is not None:
        queryset = queryset.filter(status=status.value)
    node_id = _normalize_int(params.get("node_id"), "node_id")
    if node_id is not None:
        queryset = queryset.filter(nodes__id=node_id)
    group_id = _normalize_int(params.get("group_id"), "group_id")
    if group_id is not None:
        queryset = queryset.filter(groups__id=group_id)
    if node_id is not None or group_id is not None:
        queryset = queryset.distinct()

    return queryset.annotate(
        node_count=Count("nodes", distinct=True),
        group_count=Count("groups", distinct=True),
    ).order_by(ordering)


def _paginate_task_rows(queryset: Any, *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = queryset.count()
    offset = (page - 1) * page_size
    rows = list(
        queryset.values(
            *TASK_LIST_VALUE_FIELDS,
            "node_count",
            "group_count",
        )[offset : offset + page_size]
    )
    return rows, total


def _count_tasks_by_node(node_ids: list[int]) -> dict[int, int]:
    if not node_ids:
        return {}
    return {
        item["nodes"]: item["total"]
        for item in UptimeCheckTaskModel.objects.filter(nodes__id__in=node_ids, is_deleted=False)
        .values("nodes")
        .annotate(total=Count("id"))
    }


def _host_key(*, ip: str | None, bk_cloud_id: int | str | None) -> str:
    from bkmonitor.utils.common_utils import host_key

    return host_key(ip=ip or "", bk_cloud_id=str(bk_cloud_id or 0))


def _get_by_node(node: UptimeCheckNode, data_map: dict[Any, Any], default: Any = None) -> Any:
    key: Any = node.bk_host_id
    if not key:
        key = _host_key(ip=node.ip, bk_cloud_id=node.plat_id)
    return data_map.get(key, default)


def _load_node_runtime(
    *, bk_tenant_id: str, bk_biz_id: int | None, nodes: list[UptimeCheckNode]
) -> tuple[dict[int, Any], dict[Any, dict[str, Any]], dict[Any, str], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    if not nodes:
        return {}, {}, {}, warnings

    from core.drf_resource import api, resource
    from monitor_web.uptime_check.resources import get_node_host_dict

    try:
        node_to_host = get_node_host_dict(bk_tenant_id=bk_tenant_id, nodes=nodes)
    except Exception as error:  # noqa: BLE001
        return {}, {}, {}, [{"code": "LOAD_HOST_FAILED", "message": str(error)}]

    hosts_by_id = {host.bk_host_id: host for host in node_to_host.values() if getattr(host, "bk_host_id", None)}
    bk_host_ids = sorted(hosts_by_id.keys())
    beat_versions: dict[Any, str] = {}
    if bk_host_ids:
        try:
            plugin_result = api.node_man.plugin_search(
                bk_tenant_id=bk_tenant_id,
                page=1,
                pagesize=len(bk_host_ids),
                conditions=[],
                bk_host_id=bk_host_ids,
            )
            for plugin in plugin_result.get("list", []):
                beat_plugin = [
                    item
                    for item in plugin.get("plugin_status", [])
                    if isinstance(item, dict) and item.get("name") == "bkmonitorbeat"
                ]
                if not beat_plugin:
                    continue
                version = str(beat_plugin[0].get("version") or "").strip()
                bk_host_id = plugin.get("bk_host_id")
                if bk_host_id:
                    beat_versions[int(bk_host_id)] = version
                inner_ip = plugin.get("inner_ip")
                if inner_ip:
                    beat_versions[_host_key(ip=inner_ip, bk_cloud_id=plugin.get("bk_cloud_id"))] = version
        except Exception as error:  # noqa: BLE001
            warnings.append({"code": "LOAD_BKMONITORBEAT_VERSION_FAILED", "message": str(error)})

    node_status: dict[Any, dict[str, Any]] = {}
    hosts = list(hosts_by_id.values())
    if hosts:
        try:
            status_params: dict[str, Any] = {"bk_tenant_id": bk_tenant_id, "hosts": hosts}
            if bk_biz_id:
                status_params["bk_biz_id"] = bk_biz_id
            node_status = resource.uptime_check.uptime_check_beat.return_with_dict(**status_params)
        except Exception as error:  # noqa: BLE001
            warnings.append({"code": "LOAD_BKMONITORBEAT_STATUS_FAILED", "message": str(error)})

    return hosts_by_id, node_status, beat_versions, warnings


def _serialize_node(
    node: UptimeCheckNode,
    *,
    hosts_by_id: dict[int, Any],
    node_status_map: dict[Any, dict[str, Any]],
    beat_versions: dict[Any, str],
    task_count_map: dict[int, int],
    include_runtime: bool = True,
) -> dict[str, Any]:
    host = _get_by_node(node, hosts_by_id)
    if not include_runtime:
        status = {"gse_status": None, "status": None}
        display_ip = node.ip
    elif not host:
        status = {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["INVALID"]}
        display_ip = node.ip
    else:
        status = _get_by_node(
            node,
            node_status_map,
            {"gse_status": BEAT_STATUS["DOWN"], "status": BEAT_STATUS["DOWN"]},
        )
        display_ip = getattr(host, "display_name", None) or getattr(host, "bk_host_innerip", None) or node.ip

    version = str(status.get("version") or _get_by_node(node, beat_versions, "") or "")
    return {
        "id": node.id,
        "bk_tenant_id": node.bk_tenant_id,
        "bk_biz_id": node.bk_biz_id,
        "name": node.name,
        "ip": node.ip,
        "display_ip": display_ip,
        "bk_host_id": node.bk_host_id,
        "plat_id": node.plat_id,
        "ip_type": _enum_value(node.ip_type),
        "country": (node.location or {}).get("country"),
        "province": (node.location or {}).get("city"),
        "location": node.location or {},
        "carrieroperator": node.carrieroperator,
        "is_common": node.is_common,
        "biz_scope": node.biz_scope or [],
        "task_num": task_count_map.get(int(node.id or 0), 0),
        "gse_status": status.get("gse_status", BEAT_STATUS["DOWN"]),
        "status": status.get("status", BEAT_STATUS["DOWN"]),
        "bkmonitorbeat_version": version,
        "version": version,
        "create_user": node.create_user,
        "create_time": _serialize_define_datetime(node.create_time),
        "update_user": node.update_user,
        "update_time": _serialize_define_datetime(node.update_time),
    }


def _extract_data_ids_from_context(value: Any) -> list[int]:
    data_ids: list[int] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key)
            if normalized_key in DATA_ID_CONTEXT_KEYS:
                try:
                    parsed = int(item)
                except (TypeError, ValueError):
                    parsed = None
                if parsed is not None:
                    data_ids.append(parsed)
                continue
            if normalized_key in LARGE_CONTEXT_KEYS:
                continue
            data_ids.extend(_extract_data_ids_from_context(item))
    elif isinstance(value, list):
        for item in value[:SUMMARY_SAMPLE_SIZE]:
            data_ids.extend(_extract_data_ids_from_context(item))
    return data_ids


def _mask_scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return None
    return serialize_value(value)


def _summarize_task_context_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": serialize_value(item)}
    summary: dict[str, Any] = {}
    for key in (
        "task_id",
        "bk_biz_id",
        "period",
        "timeout",
        "target_port",
        "dns_check_mode",
        "target_ip_type",
        "response_format",
        "available_duration",
    ):
        if key in item:
            summary[key] = _mask_scalar(item.get(key))
    for key in ("node_list", "target_host_list", "output_fields"):
        value = item.get(key)
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
            summary[f"{key}_samples"] = value[:SUMMARY_SAMPLE_SIZE]
    return summary


def _summarize_context(context: Any) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"value": serialize_value(context)}

    summary: dict[str, Any] = {}
    for key in (
        "data_id",
        "dataid",
        "bk_data_id",
        "task_id",
        "bk_biz_id",
        "period",
        "timeout",
        "max_timeout",
        "target_port",
        "custom_report",
        "send_interval",
        "response_format",
        "available_duration",
    ):
        if key in context:
            summary[key] = _mask_scalar(context.get(key))

    tasks = context.get("tasks")
    if isinstance(tasks, list):
        summary["tasks_count"] = len(tasks)
        summary["tasks_samples"] = [_summarize_task_context_item(item) for item in tasks[:SUMMARY_SAMPLE_SIZE]]

    for key in ("node_list", "target_host_list", "config_hosts", "output_fields"):
        value = context.get(key)
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
            summary[f"{key}_samples"] = value[:SUMMARY_SAMPLE_SIZE]

    labels = context.get("labels")
    if isinstance(labels, dict):
        summary["labels_keys"] = sorted(labels.keys())[:20]
    return summary


def _summarize_scope(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    summary: dict[str, Any] = {}
    for key in ("bk_biz_id", "object_type", "node_type"):
        if key in value:
            summary[key] = _mask_scalar(value.get(key))
    nodes = value.get("nodes")
    if isinstance(nodes, list):
        summary["nodes_count"] = len(nodes)
        summary["nodes_samples"] = nodes[:SUMMARY_SAMPLE_SIZE]
    return summary


def _summarize_target_hosts(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, list):
        return None
    return {"count": len(value), "samples": value[:SUMMARY_SAMPLE_SIZE]}


def _load_subscription_infos(
    *, bk_tenant_id: str, subscription_ids: list[int]
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    if not subscription_ids:
        return {}, []

    from core.drf_resource import api

    try:
        infos = api.node_man.subscription_info(
            bk_tenant_id=bk_tenant_id,
            subscription_id_list=subscription_ids,
        )
    except Exception as error:  # noqa: BLE001
        return {}, [{"code": "LOAD_SUBSCRIPTION_INFO_FAILED", "message": str(error)}]

    info_map: dict[int, dict[str, Any]] = {}
    for info in infos or []:
        if not isinstance(info, dict):
            continue
        subscription_id = _normalize_int(info.get("id"), "subscription_id")
        if subscription_id is not None:
            info_map[subscription_id] = info
    return info_map, []


def _load_task_subscription_relations(task_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not task_ids:
        return {}
    relation_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    queryset = UptimeCheckTaskSubscription.objects.filter(uptimecheck_id__in=task_ids)
    for item in (
        queryset
        .order_by("uptimecheck_id", "bk_biz_id", "subscription_id")
        .values("uptimecheck_id", "subscription_id", "bk_biz_id", "is_deleted", "create_time", "update_time")
    ):
        relation_map[item["uptimecheck_id"]].append(
            {
                "task_id": item["uptimecheck_id"],
                "subscription_id": item["subscription_id"],
                "bk_biz_id": item["bk_biz_id"],
                "is_deleted": item["is_deleted"],
                "create_time": serialize_value(item["create_time"]),
                "update_time": serialize_value(item["update_time"]),
            }
        )
    return relation_map


def _summarize_subscription_relation(relation: dict[str, Any]) -> dict[str, Any]:
    return {
        "subscription_id": relation["subscription_id"],
        "bk_biz_id": relation["bk_biz_id"],
        "enable": None,
        "is_deleted": relation.get("is_deleted", False),
        "config_status": "not_loaded",
        "category": None,
        "plugin_name": None,
        "scope": None,
        "scope_summary": None,
        "target_hosts": None,
        "target_hosts_summary": None,
        "data_ids": [],
        "steps": [],
        "create_time": relation.get("create_time"),
        "update_time": relation.get("update_time"),
    }


def _summarize_subscription(info: dict[str, Any] | None, relation: dict[str, Any]) -> dict[str, Any]:
    steps = info.get("steps", []) if info else []
    step_summaries: list[dict[str, Any]] = []
    data_ids: list[int] = []
    for index, step in enumerate(steps if isinstance(steps, list) else []):
        if not isinstance(step, dict):
            continue
        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        context = params.get("context") if isinstance(params, dict) else None
        step_data_ids = _extract_data_ids_from_context(context)
        data_ids.extend(step_data_ids)
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        step_summaries.append(
            {
                "index": index,
                "id": step.get("id"),
                "type": step.get("type"),
                "plugin_name": config.get("plugin_name"),
                "plugin_version": config.get("plugin_version"),
                "config_templates": config.get("config_templates", []),
                "data_ids": sorted(set(step_data_ids)),
                "context_summary": _summarize_context(context),
            }
        )

    scope = info.get("scope") if info else None
    target_hosts = info.get("target_hosts") if info else None
    return {
        "subscription_id": relation["subscription_id"],
        "bk_biz_id": relation["bk_biz_id"],
        "enable": info.get("enable") if info else None,
        "is_deleted": relation.get("is_deleted", False),
        "config_status": "available" if info else "missing",
        "category": info.get("category") if info else None,
        "plugin_name": info.get("plugin_name") if info else None,
        "scope": _summarize_scope(scope),
        "scope_summary": _summarize_scope(scope),
        "target_hosts": _summarize_target_hosts(target_hosts),
        "target_hosts_summary": _summarize_target_hosts(target_hosts),
        "data_ids": sorted(set(data_ids)),
        "steps": step_summaries,
        "create_time": relation.get("create_time"),
        "update_time": relation.get("update_time"),
    }


def _build_task_subscription_payloads(
    *, bk_tenant_id: str, task_ids: list[int]
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    relations_by_task = _load_task_subscription_relations(task_ids)
    subscription_ids = sorted(
        {relation["subscription_id"] for relations in relations_by_task.values() for relation in relations}
    )
    info_map, warnings = _load_subscription_infos(bk_tenant_id=bk_tenant_id, subscription_ids=subscription_ids)
    payloads: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task_id, relations in relations_by_task.items():
        for relation in relations:
            payloads[task_id].append(_summarize_subscription(info_map.get(relation["subscription_id"]), relation))
    return payloads, warnings


def _build_light_task_subscription_payloads(task_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    relations_by_task = _load_task_subscription_relations(task_ids)
    payloads: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task_id, relations in relations_by_task.items():
        for relation in relations:
            payloads[task_id].append(_summarize_subscription_relation(relation))
    return payloads


def _serialize_task_row(
    row: dict[str, Any],
    *,
    bk_tenant_id: str,
    subscriptions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": row["bk_biz_id"],
        "name": row["name"],
        "protocol": row["protocol"],
        "status": row["status"],
        "indepentent_dataid": row["indepentent_dataid"],
        "independent_dataid": row["indepentent_dataid"],
        "is_deleted": row["is_deleted"],
        "check_interval": row["check_interval"],
        "period": None,
        "location": {},
        "labels": {},
        "node_ids": [],
        "group_ids": [],
        "node_count": row.get("node_count", 0),
        "group_count": row.get("group_count", 0),
        "subscription_ids": [sub["subscription_id"] for sub in subscriptions],
        "subscriptions": subscriptions,
        "effective_data_ids": [],
        "effective_data_id": None,
        "create_user": row["create_user"],
        "create_time": serialize_value(row["create_time"]),
        "update_user": row["update_user"],
        "update_time": serialize_value(row["update_time"]),
    }


def _serialize_task_model(
    task: UptimeCheckTaskModel,
    *,
    bk_tenant_id: str,
    subscriptions: list[dict[str, Any]],
    node_ids: list[int],
    group_ids: list[int],
    node_count: int,
    group_count: int,
    node_summaries: list[dict[str, Any]] | None = None,
    group_summaries: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    effective_data_ids = sorted({data_id for sub in subscriptions for data_id in sub.get("data_ids", [])})
    data: dict[str, Any] = {
        "id": task.pk,
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": task.bk_biz_id,
        "name": task.name,
        "protocol": task.protocol,
        "status": task.status,
        "indepentent_dataid": task.indepentent_dataid,
        "independent_dataid": task.indepentent_dataid,
        "is_deleted": task.is_deleted,
        "check_interval": task.check_interval,
        "period": None,
        "location": {},
        "labels": {},
        "node_ids": node_ids,
        "group_ids": group_ids,
        "node_count": node_count,
        "group_count": group_count,
        "node_relation_limit": MAX_DETAIL_RELATION_ITEMS,
        "nodes_truncated": node_count > len(node_ids),
        "groups_truncated": group_count > len(group_ids),
        "subscription_ids": [sub["subscription_id"] for sub in subscriptions],
        "subscriptions": subscriptions,
        "effective_data_ids": effective_data_ids,
        "effective_data_id": effective_data_ids[0] if len(effective_data_ids) == 1 else None,
        "create_user": task.create_user,
        "create_time": _serialize_define_datetime(task.create_time),
        "update_user": task.update_user,
        "update_time": _serialize_define_datetime(task.update_time),
    }
    if not effective_data_ids and subscriptions:
        warnings.append(
            {
                "code": "EFFECTIVE_DATA_ID_NOT_FOUND",
                "message": f"任务 {task.id} 已有关联订阅，但未能从订阅 steps.params.context 中解析出 dataid",
            }
        )
    data["nodes"] = node_summaries or []
    data["groups"] = group_summaries or []
    return data, warnings


def _load_node_summaries(bk_tenant_id: str, bk_biz_id: int, node_ids: list[int]) -> list[dict[str, Any]]:
    if not node_ids:
        return []
    nodes = [
        node
        for node in UptimeCheckNodeModel.objects.filter(
            pk__in=node_ids,
            bk_tenant_id=bk_tenant_id,
            is_deleted=False,
        ).only(*NODE_MODEL_ONLY_FIELDS)
        if _is_node_visible_for_biz(node, bk_biz_id)
    ]
    node_order = {node_id: index for index, node_id in enumerate(node_ids)}
    nodes.sort(key=lambda node: node_order.get(int(node.id), len(node_order)))
    return [
        {
            "id": node.id,
            "bk_biz_id": node.bk_biz_id,
            "name": node.name,
            "ip": node.ip,
            "bk_host_id": node.bk_host_id,
            "plat_id": node.plat_id,
            "is_common": node.is_common,
            "carrieroperator": node.carrieroperator,
            "location": node.location or {},
        }
        for node in nodes
    ]


def _load_group_summaries(bk_tenant_id: str, bk_biz_id: int, group_ids: list[int]) -> list[dict[str, Any]]:
    if not group_ids:
        return []
    groups = list_groups(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, query={"group_ids": group_ids})
    return [
        {
            "id": group.id,
            "bk_biz_id": group.bk_biz_id,
            "name": group.name,
        }
        for group in groups
    ]


@KernelRPCRegistry.register(
    FUNC_UPTIME_CHECK_NODE_LIST,
    summary="Admin 查询拨测节点列表",
    description="只读分页查询拨测节点。默认补充 bkmonitorbeat 版本、Agent/GSE 状态；include_runtime=false 时只返回轻量节点字段。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "可选，业务 ID；传入 include_common=true 时会包含当前业务可见的公共节点",
        "node_id": "可选，节点 ID 精确匹配",
        "name": "可选，节点名称包含匹配",
        "ip": "可选，节点 IP 精确匹配",
        "bk_host_id": "可选，主机 ID 精确匹配",
        "plat_id": "可选，云区域 ID 精确匹配",
        "ip_type": "可选，0 / 4 / 6",
        "is_common": "可选，是否公共节点",
        "include_common": "可选，是否包含公共节点",
        "include_runtime": "可选，是否补充 Agent/GSE 状态和 bkmonitorbeat 版本，默认 true",
        "carrieroperator": "可选，运营商原始值",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(NODE_ORDERING_FIELDS))}，默认 name",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "include_common": True, "page": 1, "page_size": 20},
)
def list_uptime_check_nodes(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), NODE_ORDERING_FIELDS, default="name")
    include_runtime = normalize_optional_bool(params.get("include_runtime"), "include_runtime")
    if include_runtime is None:
        include_runtime = True

    queryset, needs_scope_filter = _build_node_queryset(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        params=params,
        ordering=ordering,
    )
    page_nodes, total = _paginate_node_queryset(
        queryset,
        bk_biz_id=bk_biz_id,
        page=page,
        page_size=page_size,
        needs_scope_filter=needs_scope_filter,
    )
    node_ids = [int(node.id) for node in page_nodes if node.id is not None]
    task_count_map = _count_tasks_by_node(node_ids)
    if include_runtime:
        hosts_by_id, node_status_map, beat_versions, runtime_warnings = _load_node_runtime(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, nodes=page_nodes
        )
    else:
        hosts_by_id, node_status_map, beat_versions, runtime_warnings = {}, {}, {}, []
    items = [
        _serialize_node(
            node,
            hosts_by_id=hosts_by_id,
            node_status_map=node_status_map,
            beat_versions=beat_versions,
            task_count_map=task_count_map,
            include_runtime=include_runtime,
        )
        for node in page_nodes
    ]

    return build_response(
        operation="uptime_check.node_list",
        func_name=FUNC_UPTIME_CHECK_NODE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
        warnings=runtime_warnings,
    )


@KernelRPCRegistry.register(
    FUNC_UPTIME_CHECK_NODE_DETAIL,
    summary="Admin 查询拨测节点详情",
    description="只读查询单个拨测节点详情，补充 bkmonitorbeat 版本、Agent/GSE 状态及关联任务摘要。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "node_id": "必填，节点 ID",
        "bk_biz_id": "可选，业务 ID；用于租户校验和公共节点可见性过滤",
    },
    example_params={"bk_tenant_id": "system", "node_id": 1, "bk_biz_id": 2},
)
def get_uptime_check_node_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    node_id = _normalize_int(params.get("node_id"), "node_id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    node_model = (
        UptimeCheckNodeModel.objects.filter(pk=node_id, bk_tenant_id=bk_tenant_id, is_deleted=False)
        .only(*NODE_MODEL_ONLY_FIELDS)
        .first()
    )
    if not node_model or not _is_node_visible_for_biz(node_model, bk_biz_id):
        raise CustomException(message=f"未找到拨测节点: node_id={node_id}")

    task_count_map = _count_tasks_by_node([node_id])
    hosts_by_id, node_status_map, beat_versions, runtime_warnings = _load_node_runtime(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, nodes=[node_model]
    )
    node = _serialize_node(
        node_model,
        hosts_by_id=hosts_by_id,
        node_status_map=node_status_map,
        beat_versions=beat_versions,
        task_count_map=task_count_map,
    )

    return build_response(
        operation="uptime_check.node_detail",
        func_name=FUNC_UPTIME_CHECK_NODE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"node": node, "related_tasks": []},
        warnings=runtime_warnings,
    )


@KernelRPCRegistry.register(
    FUNC_UPTIME_CHECK_TASK_LIST,
    summary="Admin 查询拨测任务列表",
    description=(
        "只读分页查询拨测任务。列表接口只返回轻量任务字段和订阅 ID，避免加载庞大的任务 config "
        "或 NodeMan 订阅配置；实际 dataid 请在任务详情中解析。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "可选，业务 ID",
        "task_id": "可选，任务 ID 精确匹配",
        "name": "可选，任务名称包含匹配",
        "protocol": "可选，HTTP / TCP / UDP / ICMP",
        "status": "可选，任务状态原始值",
        "is_deleted": "可选，是否只查询已删除 / 未删除任务；默认 false",
        "include_deleted": "可选，是否同时返回已删除和未删除任务；is_deleted 为空时生效，默认 false",
        "node_id": "可选，关联节点 ID",
        "group_id": "可选，关联分组 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(TASK_ORDERING_FIELDS))}，默认 -update_time",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "protocol": "HTTP", "page": 1, "page_size": 20},
)
def list_uptime_check_tasks(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), TASK_ORDERING_FIELDS, default="-update_time")
    queryset = _build_task_queryset(bk_biz_id=bk_biz_id, params=params, ordering=ordering)
    page_tasks, total = _paginate_task_rows(queryset, page=page, page_size=page_size)
    task_ids = [int(task["id"]) for task in page_tasks]
    subscriptions_by_task = _build_light_task_subscription_payloads(task_ids)
    items = [
        _serialize_task_row(
            task,
            bk_tenant_id=bk_tenant_id,
            subscriptions=subscriptions_by_task.get(int(task["id"]), []),
        )
        for task in page_tasks
    ]

    return build_response(
        operation="uptime_check.task_list",
        func_name=FUNC_UPTIME_CHECK_TASK_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
        warnings=[],
    )


@KernelRPCRegistry.register(
    FUNC_UPTIME_CHECK_TASK_DETAIL,
    summary="Admin 查询拨测任务详情",
    description="只读查询拨测任务详情、节点/分组摘要、节点管理订阅参数以及订阅配置中实际下发的 dataid。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "task_id": "必填，任务 ID",
        "bk_biz_id": "可选，业务 ID；用于租户校验",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "task_id": 1},
)
def get_uptime_check_task_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    task_id = _normalize_int(params.get("task_id"), "task_id", required=True)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    task_queryset = UptimeCheckTaskModel.objects.filter(pk=task_id).only(*TASK_DETAIL_MODEL_FIELDS)
    if bk_biz_id is not None:
        task_queryset = task_queryset.filter(bk_biz_id=bk_biz_id)
    task = task_queryset.first()
    if not task:
        raise CustomException(message=f"未找到拨测任务: task_id={task_id}")

    node_relation = task.nodes.order_by("id").values_list("id", flat=True)
    group_relation = task.groups.order_by("id").values_list("id", flat=True)
    node_count = node_relation.count()
    group_count = group_relation.count()
    node_ids = list(node_relation[:MAX_DETAIL_RELATION_ITEMS])
    group_ids = list(group_relation[:MAX_DETAIL_RELATION_ITEMS])
    subscriptions_by_task, subscription_warnings = _build_task_subscription_payloads(
        bk_tenant_id=bk_tenant_id,
        task_ids=[task_id],
    )
    node_summaries = _load_node_summaries(bk_tenant_id, task.bk_biz_id, node_ids)
    group_summaries = _load_group_summaries(bk_tenant_id, task.bk_biz_id, group_ids)
    task_payload, task_warnings = _serialize_task_model(
        task,
        bk_tenant_id=bk_tenant_id,
        subscriptions=subscriptions_by_task.get(task_id, []),
        node_ids=node_ids,
        group_ids=group_ids,
        node_count=node_count,
        group_count=group_count,
        node_summaries=node_summaries,
        group_summaries=group_summaries,
    )

    return build_response(
        operation="uptime_check.task_detail",
        func_name=FUNC_UPTIME_CHECK_TASK_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"task": task_payload},
        warnings=subscription_warnings + task_warnings,
    )
