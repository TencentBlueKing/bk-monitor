"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import Q

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from kernel_api.rpc.functions.admin.uptime_check import (
    _load_subscription_infos,
    _load_subscription_status_detail,
    _sanitize_subscription_detail_value,
    _summarize_subscription,
)
from apm.models.subscription_config import SubscriptionConfig as ApmSubscriptionConfig
from metadata.models.custom_report.subscription_config import CustomReportSubscription, LogSubscriptionConfig
from metadata.models.ping_server import PingServerSubscriptionConfig

FUNC_CONFIG_DELIVERY_RUNTIME_SETTINGS = "admin.config_delivery.runtime_settings"
FUNC_CONFIG_DELIVERY_PROXY_LIST = "admin.config_delivery.proxy_list"
FUNC_CONFIG_DELIVERY_PING_SERVER_LIST = "admin.config_delivery.ping_server_list"
FUNC_CONFIG_DELIVERY_PING_SERVER_DETAIL = "admin.config_delivery.ping_server_detail"
FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_LIST = "admin.config_delivery.custom_report_list"
FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_DETAIL = "admin.config_delivery.custom_report_detail"
FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_LIST = "admin.config_delivery.log_subscription_list"
FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_DETAIL = "admin.config_delivery.log_subscription_detail"
FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_LIST = "admin.config_delivery.apm_subscription_list"
FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_DETAIL = "admin.config_delivery.apm_subscription_detail"
FUNC_CONFIG_DELIVERY_SUBSCRIPTION_DETAIL = "admin.config_delivery.subscription_detail"
FUNC_CONFIG_DELIVERY_BATCH_STATUS = "admin.config_delivery.batch_status"

SUMMARY_SAMPLE_SIZE = 3
APM_SUBSCRIPTION_TYPES = {"all", "platform", "application"}
CONFIG_TARGET_IP_KEYS = {
    "ip",
    "inner_ip",
    "inner_ipv6",
    "outer_ip",
    "outer_ipv6",
    "login_ip",
    "data_ip",
    "bk_host_innerip",
    "bk_host_innerip_v6",
    "bk_host_outerip",
    "bk_host_outerip_v6",
    "proxy_ip",
}
NODE_MAN_DETAIL_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "auth_config",
    "headers",
}


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
    normalized = str(value).strip()
    return normalized or None


def _normalize_int_list(value: Any, field_name: str) -> list[int]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values = [item.strip() for item in value.split(",")]
    elif isinstance(value, list | tuple | set):
        raw_values = list(value)
    else:
        raw_values = [value]

    results: list[int] = []
    for raw_value in raw_values:
        if raw_value in (None, ""):
            continue
        try:
            results.append(int(raw_value))
        except (TypeError, ValueError) as error:
            raise CustomException(message=f"{field_name} 必须是整数列表") from error
    return sorted(set(results))


def _paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


def _setting_value(key: str, default: Any = None) -> Any:
    return getattr(settings, key, default)


def _summarize_list(value: Any) -> dict[str, Any]:
    values = value if isinstance(value, list) else []
    return {"count": len(values), "samples": values[:SUMMARY_SAMPLE_SIZE]}


def _is_node_man_detail_sensitive_key(key: Any) -> bool:
    normalized_key = str(key).strip().lower().replace("-", "_")
    if normalized_key in NODE_MAN_DETAIL_SENSITIVE_KEYS:
        return True
    return any(token in normalized_key for token in ("password", "passwd", "token", "secret", "authorization"))


def _sanitize_full_node_man_detail_value(value: Any, *, key: Any = None) -> Any:
    if key is not None and _is_node_man_detail_sensitive_key(key):
        return "***"

    if isinstance(value, dict):
        return {
            item_key: _sanitize_full_node_man_detail_value(item_value, key=item_key)
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [_sanitize_full_node_man_detail_value(item) for item in value]

    return serialize_value(value)


def _build_full_node_man_subscription_detail_payload(
    *, info: dict[str, Any] | None, relation: dict[str, Any], status_detail: Any
) -> dict[str, Any]:
    payload = _summarize_subscription(info, relation)
    payload["relation"] = _sanitize_full_node_man_detail_value(relation)
    payload["config_detail"] = _sanitize_full_node_man_detail_value(info) if info else None
    payload["status_detail"] = (
        _sanitize_full_node_man_detail_value(status_detail) if status_detail is not None else None
    )
    return payload


def _extract_data_ids(value: Any) -> list[int]:
    data_ids: set[int] = set()

    def walk(item: Any, key: str | None = None) -> None:
        if isinstance(item, dict):
            for item_key, item_value in item.items():
                walk(item_value, str(item_key))
            return
        if isinstance(item, list):
            for child in item:
                walk(child, key)
            return
        if key and key.lower() in {"dataid", "data_id", "bk_data_id", "metric_data_id", "trace_data_id"}:
            try:
                data_id = int(item)
            except (TypeError, ValueError):
                return
            if data_id > 0:
                data_ids.add(data_id)

    walk(value)
    return sorted(data_ids)


def _extract_config_contexts(config: Any) -> list[dict[str, Any]]:
    if not isinstance(config, dict):
        return []

    contexts: list[dict[str, Any]] = []
    params = config.get("params") if isinstance(config.get("params"), dict) else {}
    context = params.get("context") if isinstance(params, dict) else None
    if isinstance(context, dict):
        contexts.append(context)

    steps = config.get("steps") if isinstance(config.get("steps"), list) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_params = step.get("params") if isinstance(step.get("params"), dict) else {}
        step_context = step_params.get("context") if isinstance(step_params, dict) else None
        if isinstance(step_context, dict):
            contexts.append(step_context)
    return contexts


def _summarize_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {
            "config_status": "missing",
            "plugin_names": [],
            "template_names": [],
            "data_ids": [],
            "scope_summary": None,
            "target_hosts_summary": None,
            "context_summary": None,
            "target": {"node_count": 0, "target_host_count": 0},
        }

    steps = config.get("steps") if isinstance(config.get("steps"), list) else []
    plugin_names: set[str] = set()
    template_names: set[str] = set()
    top_config = config.get("config") if isinstance(config.get("config"), dict) else {}
    top_plugin_name = top_config.get("plugin_name") or config.get("id")
    if top_plugin_name:
        plugin_names.add(str(top_plugin_name))
    for template in top_config.get("config_templates") or []:
        if isinstance(template, dict) and template.get("name"):
            template_names.add(str(template["name"]))

    for step in steps:
        if not isinstance(step, dict):
            continue
        step_config = step.get("config") if isinstance(step.get("config"), dict) else {}
        plugin_name = step_config.get("plugin_name") or step.get("id")
        if plugin_name:
            plugin_names.add(str(plugin_name))
        for template in step_config.get("config_templates") or []:
            if isinstance(template, dict) and template.get("name"):
                template_names.add(str(template["name"]))

    target_hosts = config.get("target_hosts")
    scope = config.get("scope")
    scope_nodes = scope.get("nodes", []) if isinstance(scope, dict) else []
    contexts = _extract_config_contexts(config)
    return {
        "config_status": "available",
        "plugin_names": sorted(plugin_names),
        "template_names": sorted(template_names),
        "data_ids": _extract_data_ids(config),
        "scope_summary": _summarize_subscription({"scope": scope}, {"subscription_id": 0, "bk_biz_id": None}).get(
            "scope_summary"
        )
        if scope
        else None,
        "target_hosts_summary": _summarize_list(target_hosts),
        "target": {
            "node_count": len(scope_nodes) if isinstance(scope_nodes, list) else 0,
            "target_host_count": len(target_hosts) if isinstance(target_hosts, list) else 0,
        },
        "context_summary": _sanitize_subscription_detail_value(contexts[0]) if len(contexts) == 1 else None,
    }


def _summarize_ping_targets(config: Any) -> dict[str, Any]:
    ip_to_items = _extract_ping_ip_to_items(config)

    target_count = 0
    source_host_count = 0
    samples: list[dict[str, Any]] = []

    def append_sample(source_host_id: str | None, item: Any) -> None:
        if len(samples) >= SUMMARY_SAMPLE_SIZE:
            return
        sample = _sanitize_subscription_detail_value(item)
        if isinstance(sample, dict):
            samples.append({"source_host_id": source_host_id, **sample})
        else:
            samples.append({"source_host_id": source_host_id, "target": sample})

    if isinstance(ip_to_items, dict):
        for source_host_id, items in ip_to_items.items():
            source_host_id_text = str(source_host_id)
            if isinstance(items, list):
                if items:
                    source_host_count += 1
                target_count += len(items)
                for item in items:
                    append_sample(source_host_id_text, item)
            elif items not in (None, ""):
                source_host_count += 1
                target_count += 1
                append_sample(source_host_id_text, items)
    elif isinstance(ip_to_items, list):
        source_host_count = 1 if ip_to_items else 0
        target_count = len(ip_to_items)
        for item in ip_to_items:
            append_sample(None, item)

    return {
        "target_count": target_count,
        "source_host_count": source_host_count,
        "samples": samples,
    }


def _extract_ping_ip_to_items(config: Any) -> Any:
    for context in _extract_config_contexts(config):
        if "ip_to_items" in context:
            return context.get("ip_to_items")
    return None


def _serialize_ping_target_item(sequence: int, source_host_id: str | None, item: Any) -> dict[str, Any]:
    sanitized_item = _sanitize_subscription_detail_value(item)
    if isinstance(sanitized_item, dict):
        row = dict(sanitized_item)
    else:
        row = {"target": sanitized_item}
    return {
        "index": sequence,
        "source_host_id": source_host_id,
        **row,
    }


def _paginate_ping_targets(config: Any, *, page: int, page_size: int) -> dict[str, Any]:
    ip_to_items = _extract_ping_ip_to_items(config)
    offset = (page - 1) * page_size
    limit = offset + page_size
    total = 0
    source_host_count = 0
    page_items: list[dict[str, Any]] = []

    def append_if_in_page(source_host_id: str | None, item: Any) -> None:
        nonlocal total
        total += 1
        if offset <= total - 1 < limit:
            page_items.append(_serialize_ping_target_item(total, source_host_id, item))

    if isinstance(ip_to_items, dict):
        for source_host_id, items in ip_to_items.items():
            source_host_id_text = str(source_host_id)
            if isinstance(items, list):
                if items:
                    source_host_count += 1
                for item in items:
                    append_if_in_page(source_host_id_text, item)
            elif items not in (None, ""):
                source_host_count += 1
                append_if_in_page(source_host_id_text, items)
    elif isinstance(ip_to_items, list):
        source_host_count = 1 if ip_to_items else 0
        for item in ip_to_items:
            append_if_in_page(None, item)

    return {
        "items": page_items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "source_host_count": source_host_count,
    }


def _extract_ping_expected_status(config: Any) -> str | None:
    if not isinstance(config, dict):
        return None
    return _normalize_string(config.get("status"))


def _infer_custom_report_protocol(template_names: list[str], config: Any) -> str | None:
    if "bk-collector-application.conf" in template_names:
        return "prometheus"
    if "bk-collector-report-v2.conf" in template_names:
        return "json"
    if isinstance(config, dict):
        data_ids = _extract_data_ids(config)
        if data_ids:
            try:
                return CustomReportSubscription.get_protocol(data_ids[0])
            except Exception:  # noqa: BLE001
                return None
    return None


def _ping_collect_state(bk_cloud_id: int) -> dict[str, Any]:
    global_enabled = bool(_setting_value("ENABLE_PING_ALARM", False))
    direct_enabled = bool(_setting_value("ENABLE_DIRECT_AREA_PING_COLLECT", False))
    if bk_cloud_id < 0:
        reason = "特殊云区域不参与常规 Ping 下发"
    elif not global_enabled:
        reason = "ENABLE_PING_ALARM=false"
    elif bk_cloud_id == 0 and not direct_enabled:
        reason = "ENABLE_DIRECT_AREA_PING_COLLECT=false"
    else:
        reason = ""
    return {
        "global_ping_enabled": global_enabled,
        "direct_area_ping_collect_enabled": direct_enabled,
        "collect_disabled": bool(reason),
        "disabled_reason": reason,
    }


def _serialize_ping_server_config(record: PingServerSubscriptionConfig) -> dict[str, Any]:
    config_summary = _summarize_config(record.config)
    ping_target_summary = _summarize_ping_targets(record.config)
    expected_status = _extract_ping_expected_status(record.config)
    config_summary["ping_target_summary"] = ping_target_summary
    config_summary["target"] = {
        **config_summary["target"],
        "ping_target_count": ping_target_summary["target_count"],
        "ping_source_host_count": ping_target_summary["source_host_count"],
    }
    cloud_area_type = (
        "special_area" if record.bk_cloud_id < 0 else "direct_area" if record.bk_cloud_id == 0 else "proxy_area"
    )
    collect_state = _ping_collect_state(record.bk_cloud_id)
    return {
        "source_type": "ping_server",
        "bk_tenant_id": record.bk_tenant_id,
        "subscription_id": record.subscription_id,
        "bk_cloud_id": record.bk_cloud_id,
        "cloud_area_type": cloud_area_type,
        "direct_area": record.bk_cloud_id == 0,
        "special_area": record.bk_cloud_id < 0,
        "ip": record.ip,
        "bk_host_id": record.bk_host_id,
        "plugin_name": record.plugin_name,
        "config_status": config_summary["config_status"],
        "plugin_names": config_summary["plugin_names"],
        "template_names": config_summary["template_names"],
        "expected_status": expected_status,
        "data_ids": config_summary["data_ids"],
        "scope_summary": config_summary["scope_summary"],
        "target_hosts_summary": config_summary["target_hosts_summary"],
        "target": config_summary["target"],
        "target_count": ping_target_summary["target_count"],
        "ping_target_summary": ping_target_summary,
        "config_summary": config_summary,
        "collect_state": collect_state,
        "collect_disabled": collect_state["collect_disabled"],
        "global_ping_disabled": not collect_state["global_ping_enabled"],
        "direct_area_disabled": record.bk_cloud_id == 0 and not collect_state["direct_area_ping_collect_enabled"],
    }


def _extract_proxy_filter(
    *, bk_tenant_id: str | None, bk_biz_id: int | None
) -> tuple[set[int], set[int], list[dict[str, Any]]]:
    if bk_biz_id is None:
        return set(), set(), []
    if bk_tenant_id is None:
        return set(), set(), [{"code": "PING_BIZ_FILTER_NEEDS_TENANT", "message": "业务过滤需要指定租户"}]

    from core.drf_resource import api

    try:
        proxies = api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id) or []
    except Exception as error:  # noqa: BLE001
        return set(), set(), [{"code": "LOAD_BIZ_PROXIES_FAILED", "message": str(error)}]

    host_ids: set[int] = set()
    cloud_ids: set[int] = set()
    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        host_id = proxy.get("bk_host_id") or proxy.get("host_id")
        cloud_id = proxy.get("bk_cloud_id") or proxy.get("cloud_id")
        try:
            if host_id not in (None, ""):
                host_ids.add(int(host_id))
            if cloud_id not in (None, ""):
                cloud_ids.add(int(cloud_id))
        except (TypeError, ValueError):
            continue
    return host_ids, cloud_ids, []


def _read_dict_int(value: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key not in value:
            continue
        try:
            raw_value = value.get(key)
            if raw_value not in (None, ""):
                return int(raw_value)
        except (TypeError, ValueError):
            continue
    return None


def _read_dict_text(value: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        raw_value = value.get(key)
        if raw_value not in (None, ""):
            return str(raw_value).strip()
    return ""


def _read_object_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _proxy_ip_candidates(proxy: dict[str, Any]) -> list[str]:
    ips = [
        _read_dict_text(proxy, ["inner_ip", "bk_host_innerip", "ip"]),
        _read_dict_text(proxy, ["inner_ipv6", "bk_host_innerip_v6", "ipv6"]),
        _read_dict_text(proxy, ["outer_ip", "bk_host_outerip"]),
        _read_dict_text(proxy, ["outer_ipv6", "bk_host_outerip_v6"]),
        _read_dict_text(proxy, ["login_ip"]),
        _read_dict_text(proxy, ["data_ip"]),
    ]
    return list(dict.fromkeys([ip for ip in ips if ip]))


def _proxy_primary_ip(proxy: dict[str, Any]) -> str:
    candidates = _proxy_ip_candidates(proxy)
    return candidates[0] if candidates else ""


def _proxy_cloud_area_type(bk_cloud_id: int | None) -> str:
    if bk_cloud_id is None:
        return "unknown"
    if bk_cloud_id < 0:
        return "special_area"
    if bk_cloud_id == 0:
        return "direct_area"
    return "proxy_area"


def _proxy_key(*, bk_cloud_id: int | None, ip: str | None) -> tuple[int | None, str]:
    return bk_cloud_id, str(ip or "").strip()


def _extract_collector_status_from_plugin_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plugin_status = payload.get("plugin_status")
    if not isinstance(plugin_status, list):
        plugin_status = payload.get("plugins") if isinstance(payload.get("plugins"), list) else []

    collector = next(
        (
            item
            for item in plugin_status
            if isinstance(item, dict) and str(item.get("name") or item.get("plugin_name") or "") == "bk-collector"
        ),
        None,
    )
    if not collector:
        return {
            "collector_installed": False,
            "collector_status": "not_installed",
            "collector_version": None,
            "collector_status_source": "plugin_search",
        }

    raw_status = collector.get("status") or collector.get("proc_status") or collector.get("status_display")
    status = str(raw_status or "unknown").strip() or "unknown"
    installed = str(status).upper() not in {"0", "NOT_REGISTED", "NOT_REGISTERED", "NOT_INSTALLED"}
    return {
        "collector_installed": installed,
        "collector_status": status,
        "collector_version": collector.get("version") or collector.get("plugin_version"),
        "collector_status_source": "plugin_search",
    }


def _unknown_collector_status(reason: str) -> dict[str, Any]:
    return {
        "collector_installed": None,
        "collector_status": "unknown",
        "collector_version": None,
        "collector_status_source": "cmdb" if reason == "missing_host_id" else "node_man",
        "collector_status_message": reason,
    }


def _resolve_proxy_host_ids(
    *, bk_tenant_id: str, proxies: list[dict[str, Any]]
) -> tuple[dict[tuple[int | None, str], int], list[dict[str, Any]]]:
    from core.drf_resource import api

    warnings: list[dict[str, Any]] = []
    host_id_by_cloud_ip: dict[tuple[int | None, str], int] = {}
    grouped_ips: dict[int, list[dict[str, Any]]] = {}

    for proxy in proxies:
        bk_cloud_id = _read_dict_int(proxy, ["bk_cloud_id", "cloud_id"])
        proxy_biz_id = _read_dict_int(proxy, ["bk_biz_id"]) or 0
        ip = _read_dict_text(proxy, ["inner_ip", "bk_host_innerip", "ip"]) or _read_dict_text(
            proxy, ["inner_ipv6", "bk_host_innerip_v6", "ipv6"]
        )
        if bk_cloud_id is None or not ip:
            continue
        grouped_ips.setdefault(proxy_biz_id, []).append({"ip": ip, "bk_cloud_id": bk_cloud_id})

    for proxy_biz_id, ips in grouped_ips.items():
        try:
            hosts = api.cmdb.get_host_by_ip(bk_tenant_id=bk_tenant_id, ips=ips, bk_biz_id=proxy_biz_id) or []
        except TypeError:
            try:
                hosts = api.cmdb.get_host_by_ip(ips=ips, bk_biz_id=proxy_biz_id) or []
            except Exception as error:  # noqa: BLE001
                warnings.append(
                    {
                        "code": "RESOLVE_PROXY_HOST_ID_FAILED",
                        "message": f"业务 {proxy_biz_id} 代理主机解析失败: {error}",
                    }
                )
                continue
        except Exception as error:  # noqa: BLE001
            warnings.append(
                {
                    "code": "RESOLVE_PROXY_HOST_ID_FAILED",
                    "message": f"业务 {proxy_biz_id} 代理主机解析失败: {error}",
                }
            )
            continue

        for host in hosts:
            bk_host_id = _read_object_value(host, "bk_host_id")
            bk_cloud_id = _read_object_value(host, "bk_cloud_id")
            if bk_host_id in (None, "") or bk_cloud_id in (None, ""):
                continue
            for key in ["bk_host_innerip", "bk_host_innerip_v6", "ip", "ipv6"]:
                ip = _read_object_value(host, key)
                if ip:
                    try:
                        host_id_by_cloud_ip[_proxy_key(bk_cloud_id=int(bk_cloud_id), ip=str(ip))] = int(bk_host_id)
                    except (TypeError, ValueError):
                        continue

    return host_id_by_cloud_ip, warnings


def _load_collector_status_by_host_id(
    *, bk_tenant_id: str, bk_host_ids: list[int]
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    if not bk_host_ids:
        return {}, []

    from core.drf_resource import api

    try:
        plugin_result = api.node_man.plugin_search(
            bk_tenant_id=bk_tenant_id,
            page=1,
            pagesize=len(bk_host_ids),
            conditions=[],
            bk_host_id=bk_host_ids,
        )
    except Exception as error:  # noqa: BLE001
        return {}, [{"code": "LOAD_COLLECTOR_STATUS_FAILED", "message": str(error)}]

    status_by_host_id: dict[int, dict[str, Any]] = {}
    for plugin in plugin_result.get("list", []):
        if not isinstance(plugin, dict):
            continue
        host_id = _read_dict_int(plugin, ["bk_host_id", "host_id"])
        if host_id is None:
            continue
        status_by_host_id[host_id] = _extract_collector_status_from_plugin_payload(plugin)
    return status_by_host_id, []


def _extract_config_target_host_ids(config: Any) -> set[int]:
    host_ids: set[int] = set()

    def append_host_id(raw_value: Any) -> None:
        try:
            if raw_value not in (None, ""):
                host_ids.add(int(raw_value))
        except (TypeError, ValueError):
            return

    if not isinstance(config, dict):
        return host_ids

    scope = config.get("scope") if isinstance(config.get("scope"), dict) else {}
    nodes = scope.get("nodes") if isinstance(scope.get("nodes"), list) else []
    for node in nodes:
        if isinstance(node, dict):
            append_host_id(node.get("bk_host_id") or node.get("host_id") or node.get("id"))

    target_hosts = config.get("target_hosts") if isinstance(config.get("target_hosts"), list) else []
    for host in target_hosts:
        if isinstance(host, dict):
            append_host_id(host.get("bk_host_id") or host.get("host_id") or host.get("id"))

    return host_ids


def _extract_config_target_ips(config: Any) -> set[str]:
    target_ips: set[str] = set()

    def append_ip(raw_value: Any) -> None:
        text = _normalize_string(raw_value)
        if not text:
            return
        for ip in text.replace(",", " ").split():
            normalized_ip = ip.strip()
            if normalized_ip:
                target_ips.add(normalized_ip)

    def collect_from_host(host: Any) -> None:
        if not isinstance(host, dict):
            return
        for key in CONFIG_TARGET_IP_KEYS:
            append_ip(host.get(key))

    if not isinstance(config, dict):
        return target_ips

    scope = config.get("scope") if isinstance(config.get("scope"), dict) else {}
    nodes = scope.get("nodes") if isinstance(scope.get("nodes"), list) else []
    for node in nodes:
        collect_from_host(node)

    target_hosts = config.get("target_hosts") if isinstance(config.get("target_hosts"), list) else []
    for host in target_hosts:
        collect_from_host(host)

    for context in _extract_config_contexts(config):
        append_ip(context.get("proxy_ip"))

    return target_ips


def _record_matches_proxy_target(record: Any, params: dict[str, Any]) -> bool:
    bk_host_id = _normalize_int(params.get("bk_host_id"), "bk_host_id")
    proxy_ip = _normalize_string(params.get("proxy_ip"))
    if bk_host_id is None and not proxy_ip:
        return True

    config = getattr(record, "config", None)
    if bk_host_id is not None and bk_host_id in _extract_config_target_host_ids(config):
        return True
    return bool(proxy_ip and proxy_ip in _extract_config_target_ips(config))


def _filter_records_by_proxy_target(records: list[Any], params: dict[str, Any]) -> list[Any]:
    if _normalize_int(params.get("bk_host_id"), "bk_host_id") is None and not _normalize_string(params.get("proxy_ip")):
        return records
    return [record for record in records if _record_matches_proxy_target(record, params)]


def _compact_related_config_item(item: dict[str, Any], relation: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_type": item.get("source_type"),
        "subscription_id": item.get("subscription_id"),
        "bk_biz_id": item.get("bk_biz_id"),
        "config_status": item.get("config_status"),
        "target_count": item.get("target_count"),
        "relation": relation,
    }
    for key in [
        "bk_data_id",
        "log_data_id",
        "log_name",
        "app_name",
        "subscription_type",
        "plugin_name",
        "bk_cloud_id",
        "ip",
    ]:
        if item.get(key) not in (None, ""):
            result[key] = item.get(key)
    return result


def _empty_related_config_summary() -> dict[str, Any]:
    return {"count": 0, "subscription_ids": [], "matched_target_count": 0, "items": []}


def _append_related_config(
    summary: dict[str, Any], item: dict[str, Any], *, relation: str, matched_target: bool
) -> None:
    summary["count"] += 1
    summary["subscription_ids"].append(item.get("subscription_id"))
    if matched_target:
        summary["matched_target_count"] += 1
    summary["items"].append(_compact_related_config_item(item, relation))


def _build_proxy_related_configs(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    proxy: dict[str, Any],
    proxy_host_id: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    bk_cloud_id = _read_dict_int(proxy, ["bk_cloud_id", "cloud_id"])
    proxy_ips = set(_proxy_ip_candidates(proxy))
    related = {
        "ping_server": _empty_related_config_summary(),
        "custom_report": _empty_related_config_summary(),
        "log_subscription": _empty_related_config_summary(),
        "apm_subscription": _empty_related_config_summary(),
    }

    ping_queryset = filter_by_bk_tenant_id(PingServerSubscriptionConfig.objects.all(), bk_tenant_id)
    if bk_cloud_id is not None:
        ping_queryset = ping_queryset.filter(bk_cloud_id=bk_cloud_id)
    for record in ping_queryset:
        item = _serialize_ping_server_config(record)
        matched_host = proxy_host_id is not None and record.bk_host_id == proxy_host_id
        matched_ip = bool(record.ip and record.ip in proxy_ips)
        if matched_host or matched_ip:
            _append_related_config(
                related["ping_server"],
                item,
                relation="target_host" if matched_host else "cloud_ip",
                matched_target=True,
            )

    custom_records = list(_build_custom_report_queryset({"bk_biz_id": bk_biz_id}))
    filtered_custom_records, custom_warnings = _filter_custom_report_records_by_tenant(custom_records, bk_tenant_id)
    warnings.extend(custom_warnings)
    for record in filtered_custom_records:
        item = _serialize_custom_report_subscription(record, bk_tenant_id)
        target_host_ids = _extract_config_target_host_ids(record.config)
        target_ips = _extract_config_target_ips(record.config)
        matched_target = (proxy_host_id is not None and proxy_host_id in target_host_ids) or bool(
            proxy_ips & target_ips
        )
        _append_related_config(
            related["custom_report"],
            item,
            relation="target_host" if matched_target else "biz",
            matched_target=matched_target,
        )

    for record in _build_log_subscription_queryset({"bk_biz_id": bk_biz_id}, bk_tenant_id):
        item = _serialize_log_subscription(record)
        target_host_ids = _extract_config_target_host_ids(record.config)
        target_ips = _extract_config_target_ips(record.config)
        matched_target = (proxy_host_id is not None and proxy_host_id in target_host_ids) or bool(
            proxy_ips & target_ips
        )
        _append_related_config(
            related["log_subscription"],
            item,
            relation="target_host" if matched_target else "biz",
            matched_target=matched_target,
        )

    apm_queryset = filter_by_bk_tenant_id(
        _apm_subscription_model().objects.filter(Q(bk_biz_id=bk_biz_id) | Q(bk_biz_id=0, app_name="")),
        bk_tenant_id,
    )
    for record in apm_queryset:
        item = _serialize_apm_subscription(record)
        target_host_ids = _extract_config_target_host_ids(record.config)
        target_ips = _extract_config_target_ips(record.config)
        matched_target = (proxy_host_id is not None and proxy_host_id in target_host_ids) or bool(
            proxy_ips & target_ips
        )
        relation = "platform" if item.get("is_platform") else "target_host" if matched_target else "biz"
        _append_related_config(
            related["apm_subscription"],
            item,
            relation=relation,
            matched_target=matched_target,
        )

    return related, warnings


def _serialize_proxy_row(
    *,
    bk_tenant_id: str,
    bk_biz_id: int,
    proxy: dict[str, Any],
    proxy_host_id: int | None,
    collector_status: dict[str, Any] | None,
    include_related_configs: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bk_cloud_id = _read_dict_int(proxy, ["bk_cloud_id", "cloud_id"])
    proxy_ip = _proxy_primary_ip(proxy)
    related_configs, warnings = (
        _build_proxy_related_configs(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            proxy=proxy,
            proxy_host_id=proxy_host_id,
        )
        if include_related_configs
        else ({}, [])
    )
    collector = collector_status or _unknown_collector_status("missing_host_id")
    return {
        "source_type": "proxy",
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": bk_biz_id,
        "proxy_biz_id": _read_dict_int(proxy, ["bk_biz_id"]) or bk_biz_id,
        "bk_cloud_id": bk_cloud_id,
        "cloud_area_type": _proxy_cloud_area_type(bk_cloud_id),
        "direct_area": bk_cloud_id == 0,
        "special_area": bk_cloud_id is not None and bk_cloud_id < 0,
        "bk_host_id": proxy_host_id,
        "ip": proxy_ip,
        "inner_ip": _read_dict_text(proxy, ["inner_ip", "bk_host_innerip", "ip"]),
        "inner_ipv6": _read_dict_text(proxy, ["inner_ipv6", "bk_host_innerip_v6", "ipv6"]),
        "outer_ip": _read_dict_text(proxy, ["outer_ip", "bk_host_outerip"]),
        "outer_ipv6": _read_dict_text(proxy, ["outer_ipv6", "bk_host_outerip_v6"]),
        "login_ip": _read_dict_text(proxy, ["login_ip"]),
        "data_ip": _read_dict_text(proxy, ["data_ip"]),
        "bk_addressing": _read_dict_text(proxy, ["bk_addressing"]),
        "status": _read_dict_text(proxy, ["status"]) or None,
        "collector": collector,
        "collector_installed": collector.get("collector_installed"),
        "collector_status": collector.get("collector_status"),
        "collector_version": collector.get("collector_version"),
        "collector_status_source": collector.get("collector_status_source"),
        "related_configs": related_configs,
        "raw_proxy": _sanitize_subscription_detail_value(proxy),
    }, warnings


def _build_proxy_rows(
    *, bk_tenant_id: str, bk_biz_id: int, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from core.drf_resource import api

    warnings: list[dict[str, Any]] = []
    try:
        raw_proxies = api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id) or []
    except Exception as error:  # noqa: BLE001
        return [], [{"code": "LOAD_BIZ_PROXIES_FAILED", "message": str(error)}]

    proxies = [proxy for proxy in raw_proxies if isinstance(proxy, dict)]
    host_id_by_cloud_ip, host_warnings = _resolve_proxy_host_ids(bk_tenant_id=bk_tenant_id, proxies=proxies)
    warnings.extend(host_warnings)

    host_ids: set[int] = set()
    proxy_host_id_by_index: dict[int, int] = {}
    for index, proxy in enumerate(proxies):
        bk_cloud_id = _read_dict_int(proxy, ["bk_cloud_id", "cloud_id"])
        host_id = _read_dict_int(proxy, ["bk_host_id", "host_id"])
        if host_id is None:
            for ip in _proxy_ip_candidates(proxy):
                host_id = host_id_by_cloud_ip.get(_proxy_key(bk_cloud_id=bk_cloud_id, ip=ip))
                if host_id is not None:
                    break
        if host_id is not None:
            proxy_host_id_by_index[index] = host_id
            host_ids.add(host_id)

    collector_status_by_host_id, collector_warnings = _load_collector_status_by_host_id(
        bk_tenant_id=bk_tenant_id,
        bk_host_ids=sorted(host_ids),
    )
    warnings.extend(collector_warnings)

    rows: list[dict[str, Any]] = []
    for index, proxy in enumerate(proxies):
        host_id = proxy_host_id_by_index.get(index)
        collector_status = collector_status_by_host_id.get(host_id) if host_id is not None else None
        row, row_warnings = _serialize_proxy_row(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            proxy=proxy,
            proxy_host_id=host_id,
            collector_status=collector_status,
        )
        rows.append(row)
        warnings.extend(row_warnings)

    bk_cloud_id = _normalize_int(params.get("bk_cloud_id"), "bk_cloud_id")
    if bk_cloud_id is not None:
        rows = [row for row in rows if row.get("bk_cloud_id") == bk_cloud_id]
    ip = _normalize_string(params.get("ip"))
    if ip:
        rows = [
            row
            for row in rows
            if ip
            in {
                row.get("ip"),
                row.get("inner_ip"),
                row.get("inner_ipv6"),
                row.get("outer_ip"),
                row.get("outer_ipv6"),
                row.get("login_ip"),
                row.get("data_ip"),
            }
        ]
    collector_installed = _normalize_string(params.get("collector_installed"))
    if collector_installed in {"true", "false"}:
        expected = collector_installed == "true"
        rows = [row for row in rows if row.get("collector_installed") is expected]

    return sorted(rows, key=lambda row: (row.get("bk_cloud_id") or -999999, row.get("ip") or "")), warnings


def _build_ping_server_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> tuple[Any, list[dict[str, Any]]]:
    queryset = filter_by_bk_tenant_id(PingServerSubscriptionConfig.objects.all(), bk_tenant_id)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id")
    if subscription_id is not None:
        queryset = queryset.filter(subscription_id=subscription_id)
    bk_cloud_id = _normalize_int(params.get("bk_cloud_id"), "bk_cloud_id")
    if bk_cloud_id is not None:
        queryset = queryset.filter(bk_cloud_id=bk_cloud_id)
    bk_host_id = _normalize_int(params.get("bk_host_id"), "bk_host_id")
    if bk_host_id is not None:
        queryset = queryset.filter(bk_host_id=bk_host_id)
    plugin_name = _normalize_string(params.get("plugin_name"))
    if plugin_name:
        queryset = queryset.filter(plugin_name=plugin_name)
    ip = _normalize_string(params.get("ip"))
    if ip:
        queryset = queryset.filter(ip=ip)
    proxy_ip = _normalize_string(params.get("proxy_ip"))
    if proxy_ip:
        queryset = queryset.filter(ip=proxy_ip)

    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    proxy_host_ids, proxy_cloud_ids, warnings = _extract_proxy_filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    if bk_biz_id is not None:
        if proxy_host_ids:
            queryset = queryset.filter(bk_host_id__in=proxy_host_ids)
        elif proxy_cloud_ids:
            queryset = queryset.filter(bk_cloud_id__in=proxy_cloud_ids)
        else:
            queryset = queryset.none()

    return queryset.order_by("bk_cloud_id", "bk_host_id", "subscription_id"), warnings


def _custom_report_biz_matches_tenant(bk_biz_id: int, bk_tenant_id: str | None) -> bool:
    if bk_tenant_id is None:
        return True
    if bk_biz_id <= 0:
        return bk_tenant_id == DEFAULT_TENANT_ID
    return bk_biz_id_to_bk_tenant_id(bk_biz_id) == bk_tenant_id


def _filter_custom_report_records_by_tenant(
    records: list[CustomReportSubscription], bk_tenant_id: str | None
) -> tuple[list[CustomReportSubscription], list[dict[str, Any]]]:
    if bk_tenant_id is None:
        return records, []
    filtered: list[CustomReportSubscription] = []
    warnings: list[dict[str, Any]] = []
    failed_biz_ids: set[int] = set()
    tenant_cache: dict[int, bool] = {}
    for record in records:
        if record.bk_biz_id not in tenant_cache:
            try:
                tenant_cache[record.bk_biz_id] = _custom_report_biz_matches_tenant(record.bk_biz_id, bk_tenant_id)
            except Exception as error:  # noqa: BLE001
                tenant_cache[record.bk_biz_id] = False
                failed_biz_ids.add(record.bk_biz_id)
                warnings.append(
                    {
                        "code": "RESOLVE_BIZ_TENANT_FAILED",
                        "message": f"业务 {record.bk_biz_id} 租户归属查询失败: {error}",
                    }
                )
        if tenant_cache[record.bk_biz_id]:
            filtered.append(record)
    if failed_biz_ids:
        warnings.append({"code": "CUSTOM_REPORT_TENANT_FILTER_PARTIAL", "message": "部分业务租户归属查询失败"})
    return filtered, warnings


def _build_custom_report_queryset(params: dict[str, Any]) -> Any:
    queryset = CustomReportSubscription.objects.all()
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id")
    if subscription_id is not None:
        queryset = queryset.filter(subscription_id=subscription_id)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    if bk_data_id is not None:
        queryset = queryset.filter(bk_data_id=bk_data_id)
    return queryset.order_by("bk_biz_id", "bk_data_id")


def _serialize_custom_report_subscription(
    record: CustomReportSubscription, bk_tenant_id: str | None = DEFAULT_TENANT_ID
) -> dict[str, Any]:
    config_summary = _summarize_config(record.config)
    protocol = _infer_custom_report_protocol(config_summary["template_names"], record.config)
    config_data_ids = config_summary["data_ids"]
    return {
        "source_type": "custom_report",
        "bk_tenant_id": bk_tenant_id or DEFAULT_TENANT_ID,
        "bk_biz_id": record.bk_biz_id,
        "subscription_id": record.subscription_id,
        "bk_data_id": record.bk_data_id,
        "config_bk_data_id": config_data_ids[0] if config_data_ids else None,
        "data_id_consistent": not config_data_ids or record.bk_data_id in config_data_ids,
        "protocol": protocol,
        "template_names": config_summary["template_names"],
        "plugin_names": config_summary["plugin_names"],
        "data_ids": config_summary["data_ids"],
        "config_status": config_summary["config_status"],
        "scope_summary": config_summary["scope_summary"],
        "target_hosts_summary": config_summary["target_hosts_summary"],
        "target": config_summary["target"],
        "target_count": config_summary["target"]["node_count"],
        "config_summary": config_summary,
    }


def _filter_custom_report_items_by_protocol(
    items: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    protocol = str(params.get("protocol") or "").strip().lower()
    if not protocol:
        return items
    return [item for item in items if str(item.get("protocol") or "").strip().lower() == protocol]


def _extract_context_from_config(config: Any) -> dict[str, Any]:
    contexts = _extract_config_contexts(config)
    return contexts[0] if contexts else {}


def _build_log_subscription_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> Any:
    queryset = filter_by_bk_tenant_id(LogSubscriptionConfig.objects.all(), bk_tenant_id)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id")
    if subscription_id is not None:
        queryset = queryset.filter(subscription_id=subscription_id)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    log_name = _normalize_string(params.get("log_name"))
    if log_name:
        queryset = queryset.filter(log_name__icontains=log_name)
    return queryset.order_by("bk_biz_id", "log_name", "subscription_id")


def _filter_log_subscription_records_by_data_id(
    records: list[LogSubscriptionConfig], bk_data_id: int | None
) -> list[LogSubscriptionConfig]:
    if bk_data_id is None:
        return records
    filtered: list[LogSubscriptionConfig] = []
    for record in records:
        context = _extract_context_from_config(record.config)
        if _normalize_int(context.get("log_data_id"), "log_data_id") == bk_data_id:
            filtered.append(record)
    return filtered


def _serialize_log_subscription(record: LogSubscriptionConfig) -> dict[str, Any]:
    config_summary = _summarize_config(record.config)
    context = _extract_context_from_config(record.config)
    qps_config = context.get("qps_config") if isinstance(context.get("qps_config"), dict) else None
    return {
        "source_type": "log_subscription",
        "bk_tenant_id": record.bk_tenant_id,
        "bk_biz_id": record.bk_biz_id,
        "subscription_id": record.subscription_id,
        "log_name": record.log_name,
        "bk_data_id": _normalize_int(context.get("log_data_id"), "log_data_id"),
        "log_data_id": _normalize_int(context.get("log_data_id"), "log_data_id"),
        "bk_app_name": context.get("bk_app_name"),
        "has_token": bool(context.get("bk_data_token")),
        "qps": qps_config.get("qps") if qps_config else None,
        "qps_config": _sanitize_subscription_detail_value(qps_config),
        "template_names": config_summary["template_names"],
        "plugin_names": config_summary["plugin_names"],
        "data_ids": config_summary["data_ids"],
        "config_status": config_summary["config_status"],
        "scope_summary": config_summary["scope_summary"],
        "target_hosts_summary": config_summary["target_hosts_summary"],
        "target": config_summary["target"],
        "target_count": config_summary["target"]["node_count"],
        "config_summary": config_summary,
    }


def _apm_subscription_type(record: ApmSubscriptionConfig) -> str:
    return "platform" if record.bk_biz_id == 0 and record.app_name == "" else "application"


def _apm_subscription_model() -> Any:
    return ApmSubscriptionConfig


def _build_apm_subscription_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> Any:
    queryset = filter_by_bk_tenant_id(_apm_subscription_model().objects.all(), bk_tenant_id)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id")
    if subscription_id is not None:
        queryset = queryset.filter(subscription_id=subscription_id)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    if "app_name" in params:
        queryset = queryset.filter(app_name=str(params.get("app_name") or "").strip())
    subscription_type = _normalize_string(params.get("subscription_type")) or "all"
    if subscription_type not in APM_SUBSCRIPTION_TYPES:
        raise CustomException(message=f"不支持的 subscription_type: {subscription_type}")
    if subscription_type == "platform":
        queryset = queryset.filter(bk_biz_id=0, app_name="")
    elif subscription_type == "application":
        queryset = queryset.exclude(Q(bk_biz_id=0) & Q(app_name=""))
    return queryset.order_by("bk_biz_id", "app_name", "subscription_id")


def _build_apm_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> Any:
    return _build_apm_subscription_queryset(params, bk_tenant_id)


def _serialize_apm_subscription(record: ApmSubscriptionConfig) -> dict[str, Any]:
    config_summary = _summarize_config(record.config)
    subscription_type = _apm_subscription_type(record)
    return {
        "source_type": "apm_subscription",
        "subscription_type": subscription_type,
        "is_platform": subscription_type == "platform",
        "bk_tenant_id": record.bk_tenant_id,
        "bk_biz_id": record.bk_biz_id,
        "app_name": record.app_name,
        "subscription_id": record.subscription_id,
        "template_names": config_summary["template_names"],
        "plugin_names": config_summary["plugin_names"],
        "data_ids": config_summary["data_ids"],
        "config_status": config_summary["config_status"],
        "scope_summary": config_summary["scope_summary"],
        "target_hosts_summary": config_summary["target_hosts_summary"],
        "target": config_summary["target"],
        "target_count": config_summary["target"]["node_count"],
        "config_summary": config_summary,
    }


def _with_config_detail(item: dict[str, Any], config: Any) -> dict[str, Any]:
    return {**item, "config_detail": _sanitize_subscription_detail_value(config)}


def _build_relation(source_type: str, subscription_id: int, bk_biz_id: int | None = None) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "subscription_id": subscription_id,
        "bk_biz_id": bk_biz_id,
        "is_deleted": False,
        "create_time": None,
        "update_time": None,
    }


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_RUNTIME_SETTINGS,
    summary="Admin 查询配置下发运行时配置",
    description="只读查询 Ping、自定义上报、APM 配置下发相关的关键开关和默认目标。",
    params_schema={"bk_tenant_id": PAGE_LIST_TENANT_SCHEMA},
    example_params={"bk_tenant_id": "system"},
)
def get_runtime_settings(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    raw = {
        "ENABLE_PING_ALARM": _setting_value("ENABLE_PING_ALARM", False),
        "ENABLE_DIRECT_AREA_PING_COLLECT": _setting_value("ENABLE_DIRECT_AREA_PING_COLLECT", False),
        "IS_AUTO_DEPLOY_CUSTOM_REPORT_SERVER": _setting_value("IS_AUTO_DEPLOY_CUSTOM_REPORT_SERVER", False),
        "CUSTOM_REPORT_DEFAULT_PROXY_IP": _setting_value("CUSTOM_REPORT_DEFAULT_PROXY_IP", []),
        "CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER": _setting_value("CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER", []),
        "APM_APP_QPS": _setting_value("APM_APP_QPS", None),
        "APM_SAMPLING_PERCENTAGE": _setting_value("APM_SAMPLING_PERCENTAGE", None),
    }
    items = [
        {
            "key": key,
            "value": serialize_value(value),
            "summary": _summarize_list(value) if isinstance(value, list) else None,
        }
        for key, value in raw.items()
    ]
    return build_response(
        operation="config_delivery.runtime_settings",
        func_name=FUNC_CONFIG_DELIVERY_RUNTIME_SETTINGS,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "raw": raw},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_PROXY_LIST,
    summary="Admin 查询业务 Proxy 与配置下发关联",
    description=(
        "只读查询指定业务下 NodeMan Proxy 云区域、IP、解析到的 bk_host_id、bk-collector 安装状态，"
        "并关联 PingServer、自定义上报、日志上报和 APM 四类下发配置。"
    ),
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "必填，业务 ID；通过 NodeMan get_proxies_by_biz 查询业务下 Proxy",
        "bk_cloud_id": "可选，云区域 ID",
        "ip": "可选，Proxy IP 精确匹配，支持 inner/outer/login/data IP",
        "collector_installed": "可选，true / false，过滤已安装或未安装 bk-collector 的 Proxy",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 19078, "page": 1, "page_size": 20},
)
def list_proxy_delivery_overview(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    page, page_size = normalize_pagination(params)
    rows, warnings = _build_proxy_rows(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, params=params)
    page_items, total = _paginate_items(rows, page=page, page_size=page_size)
    return build_response(
        operation="config_delivery.proxy_list",
        func_name=FUNC_CONFIG_DELIVERY_PROXY_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": page_items, "page": page, "page_size": page_size, "total": total},
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_PING_SERVER_LIST,
    summary="Admin 查询 PingServer 配置下发列表",
    description="只读分页查询 PingServerSubscriptionConfig。业务过滤通过 NodeMan get_proxies_by_biz 反查代理主机。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID；通过 NodeMan 代理主机做后过滤",
        "bk_cloud_id": "可选，云区域 ID",
        "plugin_name": "可选，插件名",
        "ip": "可选，代理 IP 精确匹配",
        "proxy_ip": "可选，Proxy IP 精确匹配；等价于 ip，便于从 Proxy 关联跳转",
        "bk_host_id": "可选，主机 ID",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "page": 1, "page_size": 20},
)
def list_ping_server_configs(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    queryset, warnings = _build_ping_server_queryset(params, bk_tenant_id)
    records, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_ping_server_config(record) for record in records]
    return build_response(
        operation="config_delivery.ping_server_list",
        func_name=FUNC_CONFIG_DELIVERY_PING_SERVER_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_PING_SERVER_DETAIL,
    summary="Admin 查询 PingServer 配置下发详情",
    description="只读查询单个 PingServerSubscriptionConfig 数据库记录、配置摘要和 ip_to_items 拨测目标分页，不自动查询 NodeMan 实时状态。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "subscription_id": "必填，NodeMan 订阅 ID",
        "ping_target_page": "可选，ip_to_items 目标分页页码，默认 1",
        "ping_target_page_size": "可选，ip_to_items 目标分页大小，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "subscription_id": 1001, "ping_target_page": 1},
)
def get_ping_server_config_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id", required=True)
    ping_target_page, ping_target_page_size = normalize_pagination(
        {"page": params.get("ping_target_page"), "page_size": params.get("ping_target_page_size")}
    )
    record = PingServerSubscriptionConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, subscription_id=subscription_id
    ).first()
    if not record:
        raise CustomException(message=f"未找到 PingServer 订阅配置: subscription_id={subscription_id}")
    item = _with_config_detail(_serialize_ping_server_config(record), record.config)
    item["ping_targets"] = _paginate_ping_targets(record.config, page=ping_target_page, page_size=ping_target_page_size)
    return build_response(
        operation="config_delivery.ping_server_detail",
        func_name=FUNC_CONFIG_DELIVERY_PING_SERVER_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"record": item, "ping_targets": item["ping_targets"]},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_LIST,
    summary="Admin 查询自定义上报配置下发列表",
    description="只读分页查询 CustomReportSubscription。模型无租户字段，先按候选记录收窄，再按业务归属做租户后过滤。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID",
        "bk_data_id": "可选，DataID 精确匹配",
        "protocol": "可选，协议过滤，支持 json / prometheus",
        "proxy_ip": "可选，按配置目标中的 Proxy IP 过滤",
        "bk_host_id": "可选，按配置目标中的 bk_host_id 过滤",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={
        "bk_tenant_id": "system",
        "bk_data_id": 50010,
        "protocol": "json",
        "page": 1,
        "page_size": 20,
    },
)
def list_custom_report_subscriptions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    records = list(_build_custom_report_queryset(params))
    filtered_records, warnings = _filter_custom_report_records_by_tenant(records, bk_tenant_id)
    filtered_records = _filter_records_by_proxy_target(filtered_records, params)
    filtered_items = _filter_custom_report_items_by_protocol(
        [_serialize_custom_report_subscription(record, bk_tenant_id) for record in filtered_records],
        params,
    )
    page_records, total = _paginate_items(
        filtered_items,
        page=page,
        page_size=page_size,
    )
    return build_response(
        operation="config_delivery.custom_report_list",
        func_name=FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": page_records, "page": page, "page_size": page_size, "total": total},
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_DETAIL,
    summary="Admin 查询自定义上报配置下发详情",
    description="只读查询单个 CustomReportSubscription 数据库记录和配置摘要，不自动查询 NodeMan 实时状态。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "bk_biz_id": "可选，业务 ID",
        "bk_data_id": "可选，DataID",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "bk_data_id": 50010},
)
def get_custom_report_subscription_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    records = list(_build_custom_report_queryset(params))
    filtered_records, warnings = _filter_custom_report_records_by_tenant(records, bk_tenant_id)
    record = filtered_records[0] if filtered_records else None
    if not record:
        raise CustomException(message="未找到自定义上报订阅配置")
    item = _with_config_detail(_serialize_custom_report_subscription(record, bk_tenant_id), record.config)
    return build_response(
        operation="config_delivery.custom_report_detail",
        func_name=FUNC_CONFIG_DELIVERY_CUSTOM_REPORT_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"record": item},
        warnings=warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_LIST,
    summary="Admin 查询日志上报配置下发列表",
    description="只读分页查询 LogSubscriptionConfig。日志 DataID 位于订阅配置 context.log_data_id，按 DataID 查询时采用候选记录后过滤。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID",
        "bk_data_id": "可选，日志 DataID；通过 config steps[].params.context.log_data_id 后过滤",
        "log_name": "可选，日志名称模糊匹配",
        "proxy_ip": "可选，按配置目标中的 Proxy IP 过滤",
        "bk_host_id": "可选，按配置目标中的 bk_host_id 过滤",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50020, "page": 1, "page_size": 20},
)
def list_log_subscriptions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    records = list(_build_log_subscription_queryset(params, bk_tenant_id))
    filtered_records = _filter_log_subscription_records_by_data_id(records, bk_data_id)
    filtered_records = _filter_records_by_proxy_target(filtered_records, params)
    page_items, total = _paginate_items(
        [_serialize_log_subscription(record) for record in filtered_records],
        page=page,
        page_size=page_size,
    )
    return build_response(
        operation="config_delivery.log_subscription_list",
        func_name=FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": page_items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_DETAIL,
    summary="Admin 查询日志上报配置下发详情",
    description="只读查询单个 LogSubscriptionConfig 数据库记录和配置摘要，不自动查询 NodeMan 实时状态。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "bk_biz_id": "可选，业务 ID",
        "bk_data_id": "可选，日志 DataID",
        "log_name": "可选，日志名称",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "bk_data_id": 50020},
)
def get_log_subscription_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_data_id = _normalize_int(params.get("bk_data_id"), "bk_data_id")
    records = list(_build_log_subscription_queryset(params, bk_tenant_id))
    filtered_records = _filter_log_subscription_records_by_data_id(records, bk_data_id)
    record = filtered_records[0] if filtered_records else None
    if not record:
        raise CustomException(message="未找到日志上报订阅配置")
    item = _with_config_detail(_serialize_log_subscription(record), record.config)
    return build_response(
        operation="config_delivery.log_subscription_detail",
        func_name=FUNC_CONFIG_DELIVERY_LOG_SUBSCRIPTION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"record": item},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_LIST,
    summary="Admin 查询 APM 配置下发列表",
    description="只读分页查询 APM SubscriptionConfig，并区分平台配置与应用配置。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID",
        "app_name": "可选，应用名精确匹配",
        "subscription_id": "可选，NodeMan 订阅 ID",
        "subscription_type": "可选，all / platform / application",
        "proxy_ip": "可选，按配置目标中的 Proxy IP 过滤",
        "bk_host_id": "可选，按配置目标中的 bk_host_id 过滤",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "app_name": "checkout", "subscription_type": "application"},
)
def list_apm_subscriptions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    queryset = _build_apm_queryset(params, bk_tenant_id)
    if _normalize_int(params.get("bk_host_id"), "bk_host_id") is not None or _normalize_string(params.get("proxy_ip")):
        records = _filter_records_by_proxy_target(list(queryset), params)
        items, total = _paginate_items(
            [_serialize_apm_subscription(record) for record in records],
            page=page,
            page_size=page_size,
        )
    else:
        records, total = paginate_queryset(queryset, page=page, page_size=page_size)
        items = [_serialize_apm_subscription(record) for record in records]
    return build_response(
        operation="config_delivery.apm_subscription_list",
        func_name=FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_DETAIL,
    summary="Admin 查询 APM 配置下发详情",
    description="只读查询单个 APM SubscriptionConfig 数据库记录和配置摘要，不自动查询 NodeMan 实时状态。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "subscription_id": "必填，NodeMan 订阅 ID"},
    example_params={"bk_tenant_id": "system", "subscription_id": 1002},
)
def get_apm_subscription_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id", required=True)
    record = ApmSubscriptionConfig.objects.filter(bk_tenant_id=bk_tenant_id, subscription_id=subscription_id).first()
    if not record:
        raise CustomException(message=f"未找到 APM 订阅配置: subscription_id={subscription_id}")
    item = _with_config_detail(_serialize_apm_subscription(record), record.config)
    return build_response(
        operation="config_delivery.apm_subscription_detail",
        func_name=FUNC_CONFIG_DELIVERY_APM_SUBSCRIPTION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"record": item},
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_SUBSCRIPTION_DETAIL,
    summary="Admin 实时查询配置下发订阅详情",
    description="只读懒加载单个 NodeMan 订阅状态和订阅配置 JSON。返回前会遮罩敏感字段，不截断实例状态列表。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "source_type": "可选，ping_server / custom_report / log_subscription / apm_subscription",
        "subscription_id": "必填，NodeMan 订阅 ID",
        "bk_biz_id": "可选，业务 ID",
    },
    example_params={"bk_tenant_id": "system", "source_type": "custom_report", "subscription_id": 1001},
)
def get_subscription_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    subscription_id = _normalize_int(params.get("subscription_id"), "subscription_id", required=True)
    source_type = _normalize_string(params.get("source_type")) or "config_delivery"
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    relation = _build_relation(source_type, subscription_id, bk_biz_id)
    info_map, info_warnings = _load_subscription_infos(bk_tenant_id=bk_tenant_id, subscription_ids=[subscription_id])
    status_detail, status_warnings = _load_subscription_status_detail(
        bk_tenant_id=bk_tenant_id,
        subscription_id=subscription_id,
    )
    subscription = _build_full_node_man_subscription_detail_payload(
        info=info_map.get(subscription_id),
        relation=relation,
        status_detail=status_detail,
    )
    return build_response(
        operation="config_delivery.subscription_detail",
        func_name=FUNC_CONFIG_DELIVERY_SUBSCRIPTION_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"subscription": subscription},
        warnings=info_warnings + status_warnings,
    )


@KernelRPCRegistry.register(
    FUNC_CONFIG_DELIVERY_BATCH_STATUS,
    summary="Admin 批量实时查询配置下发订阅状态",
    description="只读批量查询 NodeMan 订阅实例状态；用于列表页用户显式选择后的异步查询。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "subscription_ids": "必填，NodeMan 订阅 ID 列表"},
    example_params={"bk_tenant_id": "system", "subscription_ids": [1001, 1002]},
)
def get_batch_status(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    subscription_ids = _normalize_int_list(params.get("subscription_ids"), "subscription_ids")
    if not subscription_ids:
        raise CustomException(message="subscription_ids 为必填项")

    items: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for subscription_id in subscription_ids:
        status_detail, status_warnings = _load_subscription_status_detail(
            bk_tenant_id=bk_tenant_id,
            subscription_id=subscription_id,
        )
        items.append(
            {
                "subscription_id": subscription_id,
                "status_detail": _sanitize_full_node_man_detail_value(status_detail),
                "success": status_detail is not None and not status_warnings,
                "warnings": status_warnings,
            }
        )
        warnings.extend(status_warnings)
    return build_response(
        operation="config_delivery.batch_status",
        func_name=FUNC_CONFIG_DELIVERY_BATCH_STATUS,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "total": len(items)},
        warnings=warnings,
    )
