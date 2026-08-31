from __future__ import annotations

import time

from django.conf import settings
from django.utils import timezone

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import get_collector_detail
from apps.log_admin_resource.handlers.inspection import (
    probe_failure,
    probe_skipped,
    probe_success,
    require_biz_in_request_tenant,
    sanitize_json,
)
from apps.log_admin_resource.handlers.platform_source import query_platform_source
from apps.log_admin_resource.response_schema import diagnostic_schema, object_schema, probe_schema
from apps.log_databus.handlers.collector.host import HostCollectorHandler
from apps.utils.local import get_request_tenant_id


MAX_RESPONSE_BYTES = 1024 * 1024


def get_collector_control_plane_snapshot(params):
    params = params or {}
    collector_config_id = _positive_int(params.get("collector_config_id"), "collector_config_id")
    source_env = _source_env()
    problem_env = _problem_env(params, source_env)
    observed_at = timezone.now().isoformat()
    started = time.monotonic()
    try:
        detail = get_collector_detail({"collector_config_id": collector_config_id})
        database = probe_success(_bounded(detail), started)
    except Exception as error:  # Preserve a stable evidence envelope for missing or unreadable records.
        database = probe_failure(error, started)
        return {
            "problem_env": problem_env,
            "source_env": source_env,
            "observed_at": observed_at,
            "collector_config_id": collector_config_id,
            "evidence_status": "unavailable",
            "effective_config": probe_skipped("DEPENDENCY_UNAVAILABLE", "collector database evidence is unavailable"),
            "database": database,
            "subscription_summary": probe_skipped(
                "DEPENDENCY_UNAVAILABLE", "collector database evidence is unavailable"
            ),
            "subscription_statistic": probe_skipped(
                "DEPENDENCY_UNAVAILABLE", "collector database evidence is unavailable"
            ),
            "subscription_instances": probe_skipped(
                "DEPENDENCY_UNAVAILABLE", "collector database evidence is unavailable"
            ),
            "consistency_warnings": [],
        }

    subscription_id = detail.get("chain", {}).get("subscription_id")
    effective_config = probe_success(_bounded(_build_effective_snapshot(detail, problem_env, source_env)))
    consistency_warnings = list(effective_config.get("data", {}).get("value", {}).get("conflicts", []))
    if not subscription_id:
        skipped = probe_skipped("RESOURCE_NOT_CONFIGURED", "collector has no subscription_id")
        return {
            "problem_env": problem_env,
            "source_env": source_env,
            "observed_at": observed_at,
            "collector_config_id": collector_config_id,
            "evidence_status": "partial",
            "effective_config": effective_config,
            "database": database,
            "subscription_summary": skipped,
            "subscription_statistic": probe_skipped("RESOURCE_NOT_CONFIGURED", "collector has no subscription_id"),
            "subscription_instances": probe_skipped("RESOURCE_NOT_CONFIGURED", "collector has no subscription_id"),
            "consistency_warnings": consistency_warnings
            + [{"code": "MISSING_SUBSCRIPTION_ID", "message": "collector configuration has no NodeMan subscription"}],
        }

    result = {
        "problem_env": problem_env,
        "source_env": source_env,
        "observed_at": observed_at,
        "collector_config_id": collector_config_id,
        "effective_config": effective_config,
        "database": database,
        "subscription_summary": _platform_probe(
            "nodeman", "get_subscription_summary", {"subscription_id_list": [subscription_id]}
        ),
        "subscription_statistic": _platform_probe(
            "nodeman", "fetch_subscription_statistic", {"subscription_id_list": [subscription_id]}
        ),
        "subscription_instances": _platform_probe(
            "nodeman", "get_subscription_instance_status", {"subscription_id_list": [subscription_id]}
        ),
        "consistency_warnings": consistency_warnings,
    }
    result["evidence_status"] = _evidence_status(result)
    return result


def get_collector_host_snapshot(params):
    params = params or {}
    source_env = _source_env()
    problem_env = _problem_env(params, source_env)
    resolved, query, cmdb = _resolve_host_input(params)
    result = {
        "problem_env": problem_env,
        "source_env": source_env,
        "observed_at": timezone.now().isoformat(),
        "query": query,
        "cmdb": cmdb,
        "collector_runtime": None,
        "collector_configs": None,
        "host_plugin_status": None,
        "subscription_summary": None,
        "subscription_statistic": None,
        "subscription_instances": None,
        "consistency_warnings": [],
    }
    if not isinstance(resolved, dict) or resolved.get("resolution_status") != "resolved":
        reason = resolved.get("resolution_status") if isinstance(resolved, dict) else "provider_unavailable"
        skipped = probe_skipped(
            "HOST_NOT_RESOLVED", f"collector lookup requires one resolved CMDB host; resolution={reason}"
        )
        for key in _HOST_DEPENDENT_PROBES:
            result[key] = skipped
        result["evidence_status"] = "partial" if cmdb.get("probe_status") == "success" else "unavailable"
        return result

    host = resolved.get("host") or {}
    bk_host_id = host.get("bk_host_id")
    bk_biz_id = host.get("bk_biz_id")
    if not bk_host_id or not bk_biz_id:
        skipped = probe_skipped("HOST_CONTEXT_INCOMPLETE", "resolved CMDB host is missing bk_host_id or bk_biz_id")
        for key in _HOST_DEPENDENT_PROBES:
            result[key] = skipped
        result["consistency_warnings"].append(
            {"code": "HOST_CONTEXT_INCOMPLETE", "message": "CMDB result cannot identify the host business context"}
        )
        result["evidence_status"] = "partial"
        return result

    request_params = {"bk_host_id": bk_host_id, "bk_biz_id": bk_biz_id}
    if host.get("bk_cloud_id") is not None:
        request_params["bk_cloud_id"] = host["bk_cloud_id"]
    started = time.monotonic()
    try:
        collectors = HostCollectorHandler().list_collectors_by_host(request_params)
        result["collector_runtime"] = probe_success(_bounded(collectors), started)
        if not collectors:
            result["consistency_warnings"].append(
                {"code": "NO_ACTIVE_COLLECTOR", "message": "no active collector subscription was found for the host"}
            )
    except Exception as error:
        result["collector_runtime"] = probe_failure(error, started)
        skipped = probe_skipped("DEPENDENCY_UNAVAILABLE", "active collector lookup is unavailable")
        result["collector_configs"] = skipped
        result["subscription_summary"] = skipped
        result["subscription_statistic"] = skipped
        result["subscription_instances"] = skipped

    result["host_plugin_status"] = _platform_probe("nodeman", "search_host_plugin_status", {"bk_host_id": [bk_host_id]})
    if result["collector_runtime"].get("probe_status") == "success":
        collectors = result["collector_runtime"].get("data", {}).get("value") or []
        collector_configs, subscription_ids, config_warnings = _collector_config_evidence(collectors)
        result["collector_configs"] = probe_success(_bounded(collector_configs), warnings=config_warnings)
        result["consistency_warnings"].extend(config_warnings)
        if subscription_ids:
            subscription_params = {"subscription_id_list": subscription_ids}
            result["subscription_summary"] = _platform_probe("nodeman", "get_subscription_summary", subscription_params)
            result["subscription_statistic"] = _platform_probe(
                "nodeman", "fetch_subscription_statistic", subscription_params
            )
            result["subscription_instances"] = _platform_probe(
                "nodeman", "get_subscription_instance_status", subscription_params
            )
        else:
            skipped = probe_skipped("RESOURCE_NOT_CONFIGURED", "active collectors have no subscription_id")
            result["subscription_summary"] = skipped
            result["subscription_statistic"] = skipped
            result["subscription_instances"] = skipped
    result["evidence_status"] = _evidence_status(result)
    return result


def _platform_probe(domain, operation, params):
    started = time.monotonic()
    try:
        result = query_platform_source({"mode": "invoke", "domain": domain, "operation": operation, "params": params})
    except Exception as error:
        return probe_failure(error, started)
    return _platform_result_to_probe(result, started)


def _platform_result_to_probe(result, started=None):
    return probe_success(result.get("result"), started, warnings=result.get("warnings") or [])


def _resolve_host_input(params):
    ip = params.get("ip")
    has_direct = params.get("bk_host_id") is not None or params.get("bk_biz_id") is not None
    if has_direct:
        if ip not in (None, ""):
            raise ValidationError("use either bk_host_id with bk_biz_id or ip, not both")
        bk_host_id = _positive_int(params.get("bk_host_id"), "bk_host_id")
        bk_biz_id = _positive_int(params.get("bk_biz_id"), "bk_biz_id")
        require_biz_in_request_tenant(bk_biz_id)
        bk_cloud_id = None
        if params.get("bk_cloud_id") is not None:
            bk_cloud_id = _nonnegative_int(params["bk_cloud_id"], "bk_cloud_id")
        host = {
            "bk_host_id": bk_host_id,
            "bk_biz_id": bk_biz_id,
            "bk_cloud_id": bk_cloud_id,
            "bk_tenant_id": get_request_tenant_id(),
        }
        resolved = {"resolution_status": "resolved", "candidate_count": 1, "host": host, "candidates": [host]}
        query = {"bk_host_id": bk_host_id, "bk_biz_id": bk_biz_id, "bk_cloud_id": bk_cloud_id}
        return resolved, query, probe_skipped("NOT_REQUIRED", "host identity was provided directly")

    if not isinstance(ip, str) or not ip.strip():
        raise ValidationError("ip or bk_host_id with bk_biz_id is required")
    resolve_params = {"ip": ip.strip()}
    if params.get("bk_cloud_id") is not None:
        resolve_params["bk_cloud_id"] = _nonnegative_int(params["bk_cloud_id"], "bk_cloud_id")
    started = time.monotonic()
    try:
        cmdb_result = query_platform_source(
            {"mode": "invoke", "domain": "cmdb", "operation": "resolve_host", "params": resolve_params}
        )
        return cmdb_result.get("result"), resolve_params, _platform_result_to_probe(cmdb_result, started)
    except Exception as error:
        return None, resolve_params, probe_failure(error, started)


def _collector_config_evidence(collectors):
    configs = []
    subscription_ids = []
    warnings = []
    for collector in collectors[:100]:
        collector_config_id = collector.get("collector_config_id") if isinstance(collector, dict) else None
        if not collector_config_id:
            continue
        try:
            detail = get_collector_detail({"collector_config_id": collector_config_id})
        except Exception:
            warnings.append(
                {
                    "code": "COLLECTOR_CONFIG_UNAVAILABLE",
                    "collector_config_id": collector_config_id,
                    "message": "persisted collector detail is unavailable",
                }
            )
            continue
        configs.append(_build_effective_snapshot(detail, None, _source_env()))
        subscription_id = detail.get("chain", {}).get("subscription_id")
        if subscription_id:
            subscription_ids.append(subscription_id)
    return configs, list(dict.fromkeys(subscription_ids)), warnings


def _build_effective_snapshot(detail, problem_env, source_env):
    collector = detail.get("collector") or {}
    chain = detail.get("chain") or {}
    raw = detail.get("raw") or {}
    missing = [
        key
        for key, value in {
            "bk_data_id": chain.get("bk_data_id"),
            "result_table_id": chain.get("table_id"),
            "subscription_id": chain.get("subscription_id"),
            "index_set_id": chain.get("primary_index_set_id"),
        }.items()
        if value in (None, "", [])
    ]
    return {
        "collector_config_id": collector.get("collector_config_id"),
        "target": {
            "bk_biz_id": collector.get("bk_biz_id"),
            "target_object_type": collector.get("target_object_type"),
            "target_nodes": raw.get("target_nodes") or [],
            "environment": raw.get("environment"),
            "bcs_cluster_id": raw.get("bcs_cluster_id"),
        },
        "collection": {
            "params": raw.get("params") or {},
            "yaml_config_enabled": raw.get("yaml_config_enabled"),
            "rule_id": raw.get("rule_id"),
        },
        "processing": {
            "etl_config": chain.get("etl_config"),
            "bkdata_clean": (detail.get("relations") or {}).get("bkdata_clean") or [],
        },
        "delivery": {
            "bk_data_id": chain.get("bk_data_id"),
            "result_table_id": chain.get("table_id"),
            "index_set_id": chain.get("primary_index_set_id"),
            "storage": detail.get("storage") or {},
            "data_link": (detail.get("relations") or {}).get("data_link"),
        },
        "versions": {
            "collector_updated_at": collector.get("updated_at"),
            "enable_v4": raw.get("enable_v4"),
        },
        "evidence": {
            "source": "bklog.persisted_collector_detail",
            "problem_env": problem_env,
            "source_env": source_env,
            "source_updated_at": collector.get("updated_at"),
            "observed_at": timezone.now().isoformat(),
        },
        "missing": missing,
        "conflicts": detail.get("warnings") or [],
    }


def _evidence_status(result):
    statuses = [
        value.get("probe_status")
        for value in result.values()
        if isinstance(value, dict)
        and value.get("probe_status")
        and not (value.get("probe_status") == "skipped" and (value.get("error") or {}).get("code") == "NOT_REQUIRED")
    ]
    if statuses and all(status == "success" for status in statuses):
        return "complete"
    if any(status == "success" for status in statuses):
        return "partial"
    return "unavailable"


def _bounded(value):
    limited = sanitize_json(value, max_bytes=MAX_RESPONSE_BYTES, redact_text=True)
    return {
        "value": limited["value"],
        "truncated": limited["truncated"],
        "original_size_bytes": limited["original_size_bytes"],
        "returned_size_bytes": limited["returned_size_bytes"],
    }


def _source_env():
    return getattr(settings, "ENVIRONMENT", None) or getattr(settings, "RUN_VER", None) or "unknown"


def _problem_env(params, source_env):
    value = params.get("problem_env")
    if value is None:
        return source_env
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("problem_env must be a non-empty string")
    return value.strip()


def _positive_int(value, name):
    value = _nonnegative_int(value, name)
    if value < 1:
        raise ValidationError(f"{name} must be positive")
    return value


def _nonnegative_int(value, name):
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer")
    if value < 0:
        raise ValidationError(f"{name} must not be negative")
    return value


_HOST_DEPENDENT_PROBES = (
    "collector_runtime",
    "collector_configs",
    "host_plugin_status",
    "subscription_summary",
    "subscription_statistic",
    "subscription_instances",
)


EVIDENCE_STATUS_SCHEMA = {"type": "string", "enum": ["complete", "partial", "unavailable"]}
COLLECTOR_CONTROL_PLANE_RESPONSE_SCHEMA = object_schema(
    "problem_env",
    "source_env",
    "observed_at",
    "collector_config_id",
    "evidence_status",
    "effective_config",
    "database",
    "subscription_summary",
    "subscription_statistic",
    "subscription_instances",
    "consistency_warnings",
    properties={
        "problem_env": {"type": "string"},
        "source_env": {"type": "string"},
        "observed_at": {"type": "string", "format": "date-time"},
        "collector_config_id": {"type": "integer", "minimum": 1},
        "evidence_status": EVIDENCE_STATUS_SCHEMA,
        "effective_config": probe_schema(),
        "database": probe_schema(),
        "subscription_summary": probe_schema(),
        "subscription_statistic": probe_schema(),
        "subscription_instances": probe_schema(),
        "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
    },
)
COLLECTOR_HOST_RESPONSE_SCHEMA = object_schema(
    "problem_env",
    "source_env",
    "observed_at",
    "query",
    "cmdb",
    "collector_runtime",
    "collector_configs",
    "host_plugin_status",
    "subscription_summary",
    "subscription_statistic",
    "subscription_instances",
    "consistency_warnings",
    "evidence_status",
    properties={
        "problem_env": {"type": "string"},
        "source_env": {"type": "string"},
        "observed_at": {"type": "string", "format": "date-time"},
        "query": {"type": "object"},
        "cmdb": probe_schema(),
        "collector_runtime": probe_schema(),
        "collector_configs": probe_schema(),
        "host_plugin_status": probe_schema(),
        "subscription_summary": probe_schema(),
        "subscription_statistic": probe_schema(),
        "subscription_instances": probe_schema(),
        "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
        "evidence_status": EVIDENCE_STATUS_SCHEMA,
    },
)


FUNCTIONS = {
    "bklog.collector.control_plane.snapshot": {
        "func_name": "bklog.collector.control_plane.snapshot",
        "description": "Inspect persisted collector control-plane state and independent NodeMan evidence.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "collector_config_id": {"type": "integer", "minimum": 1},
                "problem_env": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "required": ["collector_config_id"],
            "additionalProperties": False,
        },
        "response_schema": COLLECTOR_CONTROL_PLANE_RESPONSE_SCHEMA,
        "examples": [{"params": {"collector_config_id": 1001}}],
    },
    "bklog.collector.host_snapshot": {
        "func_name": "bklog.collector.host_snapshot",
        "description": "Resolve an exact host through CMDB and inspect its active collector subscriptions.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "ip": {"type": "string", "minLength": 1, "maxLength": 64},
                "bk_cloud_id": {"type": "integer", "minimum": 0},
                "bk_host_id": {"type": "integer", "minimum": 1},
                "bk_biz_id": {"type": "integer", "minimum": 1},
                "problem_env": {"type": "string", "minLength": 1, "maxLength": 64},
            },
            "additionalProperties": False,
        },
        "response_schema": COLLECTOR_HOST_RESPONSE_SCHEMA,
        "examples": [
            {"params": {"ip": "127.0.0.1", "bk_cloud_id": 0}},
            {"params": {"bk_host_id": 101, "bk_biz_id": 2}},
        ],
    },
}

HANDLERS = {
    "bklog.collector.control_plane.snapshot": get_collector_control_plane_snapshot,
    "bklog.collector.host_snapshot": get_collector_host_snapshot,
}
