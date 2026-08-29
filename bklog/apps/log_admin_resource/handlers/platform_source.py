from __future__ import annotations

import ipaddress
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone as datetime_timezone
from typing import Any
from collections.abc import Callable

from apps.api import CCApi, NodeApi, TransferApi
from apps.exceptions import BaseException as BklogBaseException
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import extract_event_time_evidence, sanitize_json
from apps.log_databus.constants import LogPluginInfo
from apps.utils.local import get_request_tenant_id


logger = logging.getLogger(__name__)

MAX_LIST_ITEMS = 1000
MAX_KAFKA_SAMPLES = 20
DEFAULT_KAFKA_SAMPLES = 5
DEFAULT_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 512 * 1024
CATALOG_REVISION = "2026-08-30.1"


class PlatformSourceError(BklogBaseException):
    """Stable error surfaced through the existing Resource Call envelope."""


@dataclass(frozen=True)
class OperationSpec:
    domain: str
    operation: str
    summary: str
    params_schema: dict[str, Any]
    example_params: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    projector: Callable[[Any, dict[str, Any]], Any]
    notes: str = ""
    safety_level: str = "read"
    limits: dict[str, Any] = field(default_factory=dict)
    projection: dict[str, Any] = field(default_factory=lambda: {"mode": "field_allowlist_and_recursive_redaction"})
    catalog_revision: str = CATALOG_REVISION

    @property
    def key(self):
        return self.domain, self.operation


def query_platform_source(params):
    params = params or {}
    mode = str(params.get("mode") or "discover").strip().lower()
    domain = str(params.get("domain") or "").strip().lower()
    operation = str(params.get("operation") or "").strip()

    if mode == "discover":
        return _discover(domain)
    if mode == "describe":
        return _describe(domain, operation)
    if mode == "invoke":
        return _invoke(domain, operation, params.get("params"))
    _raise_platform_error("INVALID_ARGUMENT", f"unsupported mode: {mode}", {"mode": "discover"})


def _discover(domain):
    if not domain:
        domains = []
        for domain_id in sorted({spec.domain for spec in OPERATIONS.values()}):
            domains.append(
                {
                    "id": domain_id,
                    "operation_count": sum(1 for spec in OPERATIONS.values() if spec.domain == domain_id),
                    "safety_levels": sorted(
                        {spec.safety_level for spec in OPERATIONS.values() if spec.domain == domain_id}
                    ),
                }
            )
        return _success(
            "domain_catalog",
            result={"domains": domains},
            next_call={"mode": "discover", "domain": "<domain.id>"},
        )

    operations = [
        {
            "id": spec.operation,
            "summary": spec.summary,
            "required_params": list(spec.params_schema.get("required") or []),
            "safety_level": spec.safety_level,
            "catalog_revision": spec.catalog_revision,
        }
        for spec in sorted(OPERATIONS.values(), key=lambda item: item.operation)
        if spec.domain == domain
    ]
    if not operations:
        _raise_platform_error("DOMAIN_NOT_FOUND", f"unknown domain: {domain}", {"mode": "discover"})
    return _success(
        "operation_catalog",
        domain=domain,
        result={"operations": operations},
        next_call={"mode": "describe", "domain": domain, "operation": "<operation.id>"},
    )


def _describe(domain, operation):
    spec = _get_operation(domain, operation, invoke=False)
    return _success(
        "operation_schema",
        domain=domain,
        operation=operation,
        result={
            "summary": spec.summary,
            "safety_level": spec.safety_level,
            "params_schema": spec.params_schema,
            "limits": _operation_limits(spec),
            "projection": spec.projection,
            "examples": [{"params": spec.example_params}],
            "notes": spec.notes,
            "catalog_revision": spec.catalog_revision,
        },
        next_call={"mode": "invoke", "domain": domain, "operation": operation, "params": spec.example_params},
    )


def _invoke(domain, operation, invoke_params):
    spec = _get_operation(domain, operation, invoke=True)
    if not isinstance(invoke_params, dict):
        _raise_platform_error("INVALID_ARGUMENT", "invoke params must be an object")
    try:
        normalized = _validate_operation_params(spec, invoke_params)
    except ValidationError as error:
        _raise_platform_error("INVALID_ARGUMENT", error.message)

    try:
        raw = spec.handler(normalized)
    except ValidationError as error:
        _raise_platform_error("INVALID_ARGUMENT", error.message)
    except Exception as error:  # Keep provider details in server logs, not in Resource output.
        code = "PROVIDER_TIMEOUT" if _is_timeout_error(error) else "PROVIDER_UNAVAILABLE"
        logger.exception("platform source failed: domain=%s operation=%s", domain, operation)
        _raise_platform_error(
            code,
            "platform source provider timed out"
            if code == "PROVIDER_TIMEOUT"
            else "platform source provider is unavailable",
        )

    try:
        data = spec.projector(raw, normalized)
        sanitized = sanitize_json(data)
    except Exception:
        logger.exception("platform source projection failed: domain=%s operation=%s", domain, operation)
        _raise_platform_error("RESPONSE_PROJECTION_FAILED", "platform source response projection failed")

    warnings = []
    if isinstance(sanitized, dict):
        sanitized = dict(sanitized)
        warnings.extend(sanitized.pop("warnings", []) or [])
    bounded = sanitize_json(sanitized, max_bytes=MAX_RESPONSE_BYTES)
    if bounded["truncated"]:
        warnings.append(
            {
                "code": "RESPONSE_TRUNCATED",
                "message": f"projected response was truncated to {bounded['returned_size_bytes']} bytes",
            }
        )
    return _success(
        "operation_result",
        domain=domain,
        operation=operation,
        result=bounded["value"],
        warnings=warnings,
        truncation={
            "truncated": bounded["truncated"],
            "original_size_bytes": bounded["original_size_bytes"],
            "returned_size_bytes": bounded["returned_size_bytes"],
        },
    )


def _validate_operation_params(spec, params):
    schema = spec.params_schema
    properties = schema.get("properties") or {}
    unknown = sorted(set(params) - set(properties))
    if unknown:
        raise ValidationError(f"unsupported params: {', '.join(unknown)}")
    missing = [key for key in schema.get("required") or [] if params.get(key) in (None, "", [])]
    if missing:
        raise ValidationError(f"missing required params: {', '.join(missing)}")
    normalized = dict(params)
    for key, field_schema in properties.items():
        if key not in normalized:
            if "default" in field_schema:
                normalized[key] = field_schema["default"]
            continue
        value = normalized[key]
        field_type = field_schema.get("type")
        if field_type == "integer":
            if isinstance(value, bool):
                raise ValidationError(f"{key} must be an integer")
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise ValidationError(f"{key} must be an integer")
            if value < field_schema.get("minimum", value):
                raise ValidationError(f"{key} is below the minimum")
            if value > field_schema.get("maximum", value):
                raise ValidationError(f"{key} exceeds the maximum")
            normalized[key] = value
        elif field_type == "array":
            if not isinstance(value, list) or not value:
                raise ValidationError(f"{key} must be a non-empty array")
            maximum = field_schema.get("maxItems")
            if maximum is not None and len(value) > maximum:
                raise ValidationError(f"{key} contains more than {maximum} items")
            if field_schema.get("items", {}).get("type") == "integer":
                try:
                    normalized[key] = [int(item) for item in value if not isinstance(item, bool)]
                except (TypeError, ValueError):
                    raise ValidationError(f"{key} items must be integers")
                if len(normalized[key]) != len(value) or any(item < 1 for item in normalized[key]):
                    raise ValidationError(f"{key} items must be positive integers")
            elif field_schema.get("items", {}).get("type") == "string":
                if any(not isinstance(item, str) or not item.strip() for item in value):
                    raise ValidationError(f"{key} items must be non-empty strings")
                normalized[key] = [item.strip() for item in value]
        elif field_type == "string":
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{key} must be a non-empty string")
            normalized[key] = value.strip()
    return normalized


def _get_operation(domain, operation, *, invoke):
    known_domains = {spec.domain for spec in OPERATIONS.values()}
    if domain not in known_domains:
        _raise_platform_error("DOMAIN_NOT_FOUND", f"unknown domain: {domain}", {"mode": "discover"})
    spec = OPERATIONS.get((domain, operation))
    if spec:
        return spec
    code = "OPERATION_NOT_ALLOWED" if invoke and operation else "OPERATION_NOT_FOUND"
    _raise_platform_error(
        code,
        f"operation is not in the read-only catalog: {domain}.{operation}",
        {"mode": "discover", "domain": domain},
    )


def _raise_platform_error(code, message, next_call=None):
    data = {"next_call": next_call} if next_call else None
    raise PlatformSourceError(message, code=code, data=data)


def _success(kind, *, result, domain=None, operation=None, warnings=None, next_call=None, truncation=None):
    response = {
        "kind": kind,
        "domain": domain,
        "operation": operation,
        "result": result,
        "catalog_revision": CATALOG_REVISION,
        "observed_at": datetime.now(tz=datetime_timezone.utc).isoformat(),
        "warnings": warnings or [],
    }
    if next_call:
        response["next_call"] = next_call
    if truncation:
        response["truncation"] = truncation
    return response


def _operation_limits(spec):
    return {
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "max_response_bytes": MAX_RESPONSE_BYTES,
        **spec.limits,
    }


def _is_timeout_error(error):
    if isinstance(error, TimeoutError):
        return True
    class_name = error.__class__.__name__.lower()
    message = str(getattr(error, "message", None) or error).lower()
    return "timeout" in class_name or "timed out" in message or "timeout" in message


def _call(api, params):
    return api(
        params={**params, "no_request": True},
        timeout=DEFAULT_TIMEOUT_SECONDS,
        request_cookies=False,
        bk_tenant_id=get_request_tenant_id(),
    )


def _subscription_summary(params):
    return _call(NodeApi.get_subscription_info, {"subscription_id_list": params["subscription_id_list"]})


def _subscription_statistic(params):
    return _call(
        NodeApi.subscription_statistic,
        {"subscription_id_list": params["subscription_id_list"], "plugin_name": LogPluginInfo.NAME},
    )


def _subscription_instance_status(params):
    return _call(
        NodeApi.get_subscription_instance_status,
        {"subscription_id_list": params["subscription_id_list"], "show_task_detail": False},
    )


def _subscription_task_instances(params):
    request_params = {
        "subscription_id": params["subscription_id"],
        "need_detail": False,
        "need_aggregate_all_tasks": "task_id_list" not in params,
        "need_out_of_scope_snapshots": False,
        "page": params.get("page", 1),
        "pagesize": params.get("pagesize", 100),
    }
    if "task_id_list" in params:
        request_params["task_id_list"] = params["task_id_list"]
    return _call(NodeApi.get_subscription_task_status, request_params)


def _host_plugin_status(params):
    return _call(
        NodeApi.plugin_search,
        {
            "conditions": [],
            "bk_host_id": params["bk_host_id"],
            "page": params.get("page", 1),
            "pagesize": params.get("pagesize", 100),
        },
    )


def _metadata_call(api_name, key_map):
    def caller(params):
        request_params = {target: params[source] for source, target in key_map.items() if source in params}
        api = getattr(TransferApi, api_name)
        return _call(api, request_params)

    return caller


def _kafka_sample(params):
    return _call(TransferApi.list_kafka_tail, {"bk_data_id": params["bk_data_id"], "namespace": "bklog"})


def _resolve_host(params):
    try:
        ip = ipaddress.ip_address(params["ip"])
    except ValueError:
        raise ValidationError("ip must be a valid IPv4 or IPv6 address")
    ip_field = "bk_host_innerip_v6" if ip.version == 6 else "bk_host_innerip"
    rules = [{"field": ip_field, "operator": "equal", "value": str(ip)}]
    if "bk_cloud_id" in params:
        rules.append({"field": "bk_cloud_id", "operator": "equal", "value": params["bk_cloud_id"]})
    request_params = {
        "page": {"start": 0, "limit": 100},
        "fields": list(HOST_FIELDS),
        "host_property_filter": {"condition": "AND", "rules": rules},
    }
    return _call(CCApi.list_hosts_without_biz, request_params)


def _project_subscription_summary(raw, _params):
    result = []
    for subscription in raw if isinstance(raw, list) else []:
        if not isinstance(subscription, dict):
            continue
        item = _pick(subscription, "id", "name", "enable", "category", "plugin_name", "bk_biz_scope", "pid")
        scope = subscription.get("scope") if isinstance(subscription.get("scope"), dict) else {}
        item["scope"] = {
            **_pick(scope, "bk_biz_id", "object_type", "node_type"),
            "node_count": len(scope.get("nodes")) if isinstance(scope.get("nodes"), list) else 0,
        }
        item["target_host_count"] = (
            len(subscription.get("target_hosts", [])) if isinstance(subscription.get("target_hosts"), list) else 0
        )
        item["steps"] = []
        for step in subscription.get("steps", []) if isinstance(subscription.get("steps"), list) else []:
            if not isinstance(step, dict):
                continue
            config = step.get("config") if isinstance(step.get("config"), dict) else {}
            item["steps"].append(
                {
                    **_pick(step, "id", "type"),
                    "config": {
                        **_pick(config, "job_type", "plugin_name", "plugin_version", "is_version_sensitive"),
                        "config_templates": [
                            _pick(template, "name", "version", "os", "cpu_arch", "is_main")
                            for template in config.get("config_templates", [])
                            if isinstance(template, dict)
                        ],
                    },
                }
            )
        result.append(item)
    return result


def _project_subscription_statistic(raw, _params):
    return [
        {
            **_pick(item, "subscription_id", "instances"),
            "status": [_pick(row, "status", "count") for row in item.get("status", []) if isinstance(row, dict)],
            "versions": [
                _pick(row, "name", "version", "count") for row in item.get("versions", []) if isinstance(row, dict)
            ],
        }
        for item in (raw if isinstance(raw, list) else [])
        if isinstance(item, dict)
    ]


def _project_subscription_instance_status(raw, _params):
    result = []
    for subscription in raw if isinstance(raw, list) else []:
        if not isinstance(subscription, dict):
            continue
        instances = []
        for item in subscription.get("instances", []) if isinstance(subscription.get("instances"), list) else []:
            if not isinstance(item, dict):
                continue
            instances.append(
                {
                    **_pick(item, "instance_id", "status", "create_time"),
                    "instance_info": _project_instance_info(item.get("instance_info")),
                    "running_task": _pick(item.get("running_task"), "id", "is_auto_trigger") or None,
                    "last_task": _pick(item.get("last_task"), "id") or None,
                    "host_statuses": [
                        _pick(status, "name", "status", "version")
                        for status in item.get("host_statuses", [])
                        if isinstance(status, dict)
                    ],
                }
            )
        result.append({"subscription_id": subscription.get("subscription_id"), "instances": instances})
    return result


def _project_subscription_tasks(raw, _params):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "total": raw.get("total", 0),
        "status_counter": _pick(
            raw.get("status_counter"),
            "SUCCESS",
            "PENDING",
            "FAILED",
            "RUNNING",
            "PART_FAILED",
            "TERMINATED",
            "REMOVED",
            "FILTERED",
            "IGNORED",
            "total",
        ),
        "list": [
            {
                **_pick(
                    item,
                    "task_id",
                    "record_id",
                    "instance_id",
                    "create_time",
                    "start_time",
                    "finish_time",
                    "status",
                    "pipeline_id",
                ),
                "instance_info": _project_instance_info(item.get("instance_info")),
            }
            for item in raw.get("list", [])
            if isinstance(item, dict)
        ],
    }


def _project_host_plugin_status(raw, _params):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "total": raw.get("total", 0),
        "list": [
            {
                **_pick(host, *HOST_PLUGIN_FIELDS),
                "plugin_status": [
                    _pick(plugin, "name", "status", "version", "host_id")
                    for plugin in host.get("plugin_status", [])
                    if isinstance(plugin, dict)
                ],
            }
            for host in raw.get("list", [])
            if isinstance(host, dict)
        ],
    }


def _project_metadata(raw, _params):
    return sanitize_json(raw)


def _project_kafka_sample(raw, params):
    rows = raw if isinstance(raw, list) else []
    selected = rows[: params.get("sample_limit", DEFAULT_KAFKA_SAMPLES)]
    time_rows = [_kafka_time_row(row) for row in selected]
    time_evidence = extract_event_time_evidence(time_rows)
    selected_time = time_evidence.get("selected") or {}
    latest_business_time = selected_time.get("parsed_time")
    data_age_seconds = _data_age_seconds(latest_business_time)
    warnings = []
    if len(rows) > len(selected):
        warnings.append({"code": "SAMPLE_TRUNCATED", "message": "more samples were returned by metadata"})
    if selected and not latest_business_time:
        warnings.append({"code": "EVENT_TIME_NOT_FOUND", "message": "no business time was found in samples"})
    return {
        "has_data": bool(rows),
        "count": len(selected),
        "items": sanitize_json(selected),
        "latest_business_time": latest_business_time,
        "data_age_seconds": data_age_seconds,
        "warnings": warnings,
    }


def _project_resolved_host(raw, params):
    hosts = raw.get("info", []) if isinstance(raw, dict) else []
    candidates = [_pick(host, *HOST_FIELDS) for host in hosts if isinstance(host, dict)]
    status = "resolved" if len(candidates) == 1 else "not_found" if not candidates else "ambiguous"
    return {
        "query": {
            "ip": params["ip"],
            "bk_cloud_id": params.get("bk_cloud_id"),
            "bk_tenant_id": get_request_tenant_id(),
        },
        "resolution_status": status,
        "candidate_count": len(candidates),
        "host": candidates[0] if len(candidates) == 1 else None,
        "candidates": candidates,
        "warnings": (
            [{"code": "AMBIGUOUS_HOST", "message": "multiple exact host candidates; no candidate was selected"}]
            if len(candidates) > 1
            else []
        ),
    }


def _kafka_time_row(row):
    if not isinstance(row, dict):
        return row
    result = dict(row)
    items = row.get("items") if isinstance(row.get("items"), list) else []
    decoded_items = []
    for item in items:
        if not isinstance(item, dict):
            decoded_items.append(item)
            continue
        decoded = dict(item)
        value = item.get("data")
        if isinstance(value, str):
            try:
                decoded["decoded_data"] = json.loads(value)
            except (TypeError, ValueError):
                pass
        decoded_items.append(decoded)
    result["items"] = decoded_items
    return result


def _data_age_seconds(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return max(0, round(time.time() - parsed.timestamp(), 3))


def _project_instance_info(value):
    value = value if isinstance(value, dict) else {}
    host = _pick(value.get("host"), *HOST_FIELDS)
    cloud = host.get("bk_cloud_id")
    if isinstance(cloud, list) and cloud and isinstance(cloud[0], dict):
        host["bk_cloud_id"] = cloud[0].get("id")
    return {"host": host, "service": _pick(value.get("service"), "id", "name", "bk_module_id", "bk_host_id")}


def _pick(value, *keys):
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in keys if key in value}


HOST_FIELDS = (
    "bk_host_id",
    "bk_biz_id",
    "bk_biz_name",
    "bk_host_name",
    "bk_host_innerip",
    "bk_host_innerip_v6",
    "bk_cloud_id",
    "bk_cloud_name",
    "bk_supplier_account",
    "bk_tenant_id",
)
HOST_PLUGIN_FIELDS = (
    "bk_biz_id",
    "bk_host_id",
    "bk_cloud_id",
    "bk_host_name",
    "inner_ip",
    "inner_ipv6",
    "os_type",
    "cpu_arch",
    "node_type",
    "node_from",
    "status",
    "version",
    "status_display",
    "bk_cloud_name",
    "bk_biz_name",
)


def _id_list_schema(name, maximum=100):
    return {
        "type": "object",
        "properties": {name: {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": maximum}},
        "required": [name],
        "additionalProperties": False,
    }


def _id_schema(name):
    return {
        "type": "object",
        "properties": {name: {"type": "integer", "minimum": 1}},
        "required": [name],
        "additionalProperties": False,
    }


OPERATIONS = {}


def _register(spec):
    OPERATIONS[spec.key] = spec


for _spec in (
    OperationSpec(
        "nodeman",
        "get_subscription_summary",
        "查询订阅安全摘要",
        _id_list_schema("subscription_id_list"),
        {"subscription_id_list": [10001]},
        _subscription_summary,
        _project_subscription_summary,
        "不返回目标主机、渲染参数或安装凭据。",
    ),
    OperationSpec(
        "nodeman",
        "fetch_subscription_statistic",
        "统计订阅实例状态与插件版本",
        _id_list_schema("subscription_id_list"),
        {"subscription_id_list": [10001]},
        _subscription_statistic,
        _project_subscription_statistic,
    ),
    OperationSpec(
        "nodeman",
        "get_subscription_instance_status",
        "查询订阅实例部署状态",
        _id_list_schema("subscription_id_list"),
        {"subscription_id_list": [10001]},
        _subscription_instance_status,
        _project_subscription_instance_status,
        "固定关闭任务详情并投影响应字段。",
    ),
    OperationSpec(
        "nodeman",
        "get_subscription_task_instances",
        "分页查询订阅实例任务状态",
        {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "integer", "minimum": 1},
                "task_id_list": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 100},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "pagesize": {"type": "integer", "minimum": 1, "maximum": MAX_LIST_ITEMS, "default": 100},
            },
            "required": ["subscription_id"],
            "additionalProperties": False,
        },
        {"subscription_id": 10001, "page": 1, "pagesize": 100},
        _subscription_task_instances,
        _project_subscription_tasks,
        "固定关闭步骤、日志、渲染输入和越界快照。",
    ),
    OperationSpec(
        "nodeman",
        "search_host_plugin_status",
        "按主机 ID 查询 Agent 与插件状态",
        {
            "type": "object",
            "properties": {
                "bk_host_id": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 100},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "pagesize": {"type": "integer", "minimum": 1, "maximum": MAX_LIST_ITEMS, "default": 100},
            },
            "required": ["bk_host_id"],
            "additionalProperties": False,
        },
        {"bk_host_id": [101]},
        _host_plugin_status,
        _project_host_plugin_status,
    ),
    OperationSpec(
        "metadata",
        "get_data_source",
        "查询 DataID 元数据",
        _id_schema("bk_data_id"),
        {"bk_data_id": 1500001},
        _metadata_call("get_data_id", {"bk_data_id": "bk_data_id"}),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "get_result_table",
        "查询结果表元数据",
        {
            "type": "object",
            "properties": {"result_table_id": {"type": "string"}},
            "required": ["result_table_id"],
            "additionalProperties": False,
        },
        {"result_table_id": "2_bklog.demo"},
        _metadata_call("get_result_table", {"result_table_id": "table_id"}),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "get_result_table_storage",
        "查询结果表存储绑定",
        {
            "type": "object",
            "properties": {"result_table_id": {"type": "string"}, "storage_type": {"type": "string"}},
            "required": ["result_table_id"],
            "additionalProperties": False,
        },
        {"result_table_id": "2_bklog.demo", "storage_type": "elasticsearch"},
        _metadata_call(
            "get_result_table_storage", {"result_table_id": "result_table_list", "storage_type": "storage_type"}
        ),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "get_result_table_storage_status",
        "查询结果表物理存储状态",
        {
            "type": "object",
            "properties": {
                "result_table_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 100,
                }
            },
            "required": ["result_table_ids"],
            "additionalProperties": False,
        },
        {"result_table_ids": ["2_bklog.demo"]},
        _metadata_call("get_result_table_storage_status", {"result_table_ids": "table_ids"}),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "get_storage_cluster",
        "按集群 ID 查询存储集群",
        _id_schema("cluster_id"),
        {"cluster_id": 11},
        _metadata_call("get_cluster_info", {"cluster_id": "cluster_id"}),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "get_storage_cluster_status",
        "查询存储集群连通性与容量状态",
        {
            "type": "object",
            "properties": {
                "bk_biz_id": {"type": "integer", "minimum": 1},
                "cluster_ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 20},
            },
            "required": ["bk_biz_id", "cluster_ids"],
            "additionalProperties": False,
        },
        {"bk_biz_id": 2, "cluster_ids": [11]},
        _metadata_call("get_cluster_status", {"bk_biz_id": "bk_biz_id", "cluster_ids": "cluster_ids"}),
        _project_metadata,
    ),
    OperationSpec(
        "metadata",
        "kafka_sample",
        "查询 DataID 对应 Kafka 尾部样本",
        {
            "type": "object",
            "properties": {
                "bk_data_id": {"type": "integer", "minimum": 1},
                "sample_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_KAFKA_SAMPLES,
                    "default": DEFAULT_KAFKA_SAMPLES,
                },
            },
            "required": ["bk_data_id"],
            "additionalProperties": False,
        },
        {"bk_data_id": 1500001, "sample_limit": 5},
        _kafka_sample,
        _project_kafka_sample,
        "最多返回 20 条样本，不返回 broker 或凭据。",
        safety_level="inspect",
        limits={"default_sample_limit": DEFAULT_KAFKA_SAMPLES, "max_sample_limit": MAX_KAFKA_SAMPLES},
    ),
    OperationSpec(
        "cmdb",
        "resolve_host",
        "按精确 IPv4/IPv6 定位主机与业务",
        {
            "type": "object",
            "properties": {"ip": {"type": "string"}, "bk_cloud_id": {"type": "integer", "minimum": 0}},
            "required": ["ip"],
            "additionalProperties": False,
        },
        {"ip": "127.0.0.1", "bk_cloud_id": 0},
        _resolve_host,
        _project_resolved_host,
        "多候选时返回 ambiguous，绝不自动选择第一条。",
    ),
):
    _register(_spec)


FUNCTIONS = {
    "bklog.platform_source.query": {
        "func_name": "bklog.platform_source.query",
        "description": "Discover, describe and invoke a fixed catalog of read-only platform sources.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["discover", "describe", "invoke"]},
                "domain": {"type": "string"},
                "operation": {"type": "string"},
                "params": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [
            {"params": {"mode": "discover"}},
            {"params": {"mode": "discover", "domain": "nodeman"}},
            {"params": {"mode": "describe", "domain": "cmdb", "operation": "resolve_host"}},
        ],
    }
}

HANDLERS = {"bklog.platform_source.query": query_platform_source}
