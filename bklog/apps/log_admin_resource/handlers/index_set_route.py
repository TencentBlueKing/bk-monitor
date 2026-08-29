from __future__ import annotations

import time

from django.conf import settings
from django.utils import timezone

from apps.api import TransferApi
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.index_set import get_index_set_detail
from apps.log_admin_resource.handlers.inspection import probe_failure, probe_skipped, probe_success, sanitize_json
from apps.log_admin_resource.handlers.platform_source import _project_result_table, _project_storage_status_item
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_search.handlers.index_set import BaseIndexSetHandler, IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.utils.local import get_request_tenant_id


MAX_ROUTE_TABLES = 100
MAX_ROUTE_BYTES = 128 * 1024
DEFAULT_TIMEOUT_SECONDS = 10
ROUTE_STATUS_PRIORITY = {
    "consistent": 0,
    "route_missing": 1,
    "route_mismatch": 2,
    "runtime_unavailable": 3,
    "ambiguous": 4,
}


def get_index_set_storage_route_snapshot(params):
    params = params or {}
    index_set_id = _positive_int(params.get("index_set_id"), "index_set_id")
    observed_at = timezone.now().isoformat()
    try:
        index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
        database = probe_success(sanitize_json(get_index_set_detail({"index_set_id": index_set_id}), redact_text=True))
    except Exception as error:
        return {
            "source_env": _source_env(),
            "observed_at": observed_at,
            "index_set_id": index_set_id,
            "database": probe_failure(error),
            "expected_route": probe_skipped("DEPENDENCY_UNAVAILABLE", "index set database evidence is unavailable"),
            "metadata_route": probe_skipped("DEPENDENCY_UNAVAILABLE", "expected route cannot be derived"),
            "physical_storage": probe_skipped("DEPENDENCY_UNAVAILABLE", "expected route cannot be derived"),
            "consistency_warnings": [],
        }

    started = time.monotonic()
    try:
        expected = _build_expected_routes(index_set)
        expected_route = probe_success(expected, started)
    except Exception as error:
        return {
            "source_env": _source_env(),
            "observed_at": observed_at,
            "index_set_id": index_set_id,
            "database": database,
            "expected_route": probe_failure(error, started),
            "metadata_route": probe_skipped("DEPENDENCY_UNAVAILABLE", "expected route cannot be derived"),
            "physical_storage": probe_skipped("DEPENDENCY_UNAVAILABLE", "expected route cannot be derived"),
            "consistency_warnings": [],
        }

    table_ids = _route_table_ids(expected)
    metadata_route = _probe_metadata_routes(table_ids)
    physical_storage = _probe_physical_storage(table_ids)
    return {
        "source_env": _source_env(),
        "observed_at": observed_at,
        "index_set_id": index_set_id,
        "database": database,
        "expected_route": expected_route,
        "metadata_route": metadata_route,
        "physical_storage": physical_storage,
        "consistency_warnings": _consistency_warnings(table_ids, metadata_route, physical_storage),
    }


def get_index_set_route_snapshot(params):
    """Compare the existing BKLog route builder with Monitor runtime evidence."""

    params = params or {}
    resolution, index_set = _resolve_index_set(params)
    result = {
        "source_env": _source_env(),
        "bk_tenant_id": get_request_tenant_id(),
        "observed_at": timezone.now().isoformat(),
        "query": resolution["query"],
        "resolution": resolution,
        "index_set_id": getattr(index_set, "index_set_id", None),
        "status": resolution["status"],
        "database": None,
        "expected_route": None,
        "runtime_route": None,
        "routes": [],
        "warnings": list(resolution.get("warnings") or []),
        "truncation": {"truncated": False, "original_route_count": 0, "returned_route_count": 0},
    }
    if resolution["status"] != "resolved":
        return result

    started = time.monotonic()
    try:
        detail = get_index_set_detail({"index_set_id": index_set.index_set_id})
        result["database"] = probe_success(sanitize_json(detail, redact_text=True), started)
    except Exception as error:
        result["database"] = probe_failure(error, started)

    started = time.monotonic()
    try:
        expected = _build_expected_routes(index_set)
        result["expected_route"] = probe_success(expected, started)
    except Exception as error:
        result["expected_route"] = probe_failure(error, started)
        result["status"] = "runtime_unavailable"
        return result

    expected_items = _flatten_expected_routes(expected)
    original_route_count = sum(
        route.get("original_table_count", len(route.get("table_info", []))) for route in expected
    )
    result["truncation"] = {
        "truncated": any(route.get("truncated") for route in expected),
        "original_route_count": original_route_count,
        "returned_route_count": len(expected_items),
    }
    if not expected_items:
        result["status"] = "route_missing"
        result["runtime_route"] = probe_success({"items": []})
        result["warnings"].append(
            {"code": "EXPECTED_ROUTE_MISSING", "message": "the existing route builder produced no route"}
        )
        return result

    started = time.monotonic()
    table_ids = [item["table_id"] for _, item in expected_items]
    try:
        runtime = TransferApi.get_result_table_storage_status(
            params={"table_ids": table_ids, "no_request": True},
            timeout=DEFAULT_TIMEOUT_SECONDS,
            request_cookies=False,
            bk_tenant_id=result["bk_tenant_id"],
        )
        result["runtime_route"] = probe_success(_project_runtime_response(runtime), started)
        runtime_items = runtime.get("items", []) if isinstance(runtime, dict) else []
        runtime_by_table = {
            item.get("table_id"): item for item in runtime_items if isinstance(item, dict) and item.get("table_id")
        }
        result["routes"] = [
            _compare_route(route_meta, expected_item, runtime_by_table.get(expected_item["table_id"]))
            for route_meta, expected_item in expected_items
        ]
    except Exception as error:
        result["runtime_route"] = _runtime_probe_failure(error, started)
        result["routes"] = [
            _runtime_unavailable_route(route_meta, expected_item, error) for route_meta, expected_item in expected_items
        ]

    result["status"] = _overall_status(result["routes"])
    for route in result["routes"]:
        result["warnings"].extend(route.get("warnings") or [])
    return result


def _resolve_index_set(params):
    has_index_set = params.get("index_set_id") not in (None, "")
    has_result_table = params.get("result_table_id") not in (None, "")
    if has_index_set == has_result_table:
        raise ValidationError("provide exactly one of index_set_id or result_table_id")

    if has_index_set:
        index_set_id = _positive_int(params.get("index_set_id"), "index_set_id")
        query = {"index_set_id": index_set_id}
        try:
            index_set = LogIndexSet.objects.get(index_set_id=index_set_id)
        except LogIndexSet.DoesNotExist:
            return _missing_resolution(query, "INDEX_SET_NOT_FOUND", "index set does not exist"), None
        return _resolved_resolution(query, [index_set]), index_set

    result_table_id = params.get("result_table_id")
    if not isinstance(result_table_id, str) or not result_table_id.strip():
        raise ValidationError("result_table_id must be a non-empty string")
    result_table_id = result_table_id.strip()
    query = {"result_table_id": result_table_id}
    candidate_ids = list(
        dict.fromkeys(
            LogIndexSetData.objects.filter(result_table_id=result_table_id).values_list("index_set_id", flat=True)
        )
    )
    index_sets = list(LogIndexSet.objects.filter(index_set_id__in=candidate_ids).order_by("index_set_id"))
    if not index_sets:
        return _missing_resolution(query, "RESULT_TABLE_ROUTE_NOT_FOUND", "result table has no index set"), None
    if len(index_sets) > 1:
        return {
            "status": "ambiguous",
            "query": query,
            "candidate_count": len(index_sets),
            "candidates": [_index_set_candidate(item) for item in index_sets],
            "warnings": [
                {
                    "code": "AMBIGUOUS_RESULT_TABLE",
                    "message": "result table belongs to multiple index sets; no candidate was selected",
                }
            ],
        }, None
    return _resolved_resolution(query, index_sets), index_sets[0]


def _resolved_resolution(query, index_sets):
    return {
        "status": "resolved",
        "query": query,
        "candidate_count": len(index_sets),
        "candidates": [_index_set_candidate(item) for item in index_sets],
        "warnings": [],
    }


def _missing_resolution(query, code, message):
    return {
        "status": "route_missing",
        "query": query,
        "candidate_count": 0,
        "candidates": [],
        "warnings": [{"code": code, "message": message}],
    }


def _index_set_candidate(index_set):
    return {
        "index_set_id": index_set.index_set_id,
        "index_set_name": index_set.index_set_name,
        "space_uid": index_set.space_uid,
        "scenario_id": index_set.scenario_id,
        "is_group": index_set.is_group,
    }


def _build_expected_routes(index_set):
    rt_alias_mappings = None
    if index_set.query_alias_settings:
        rt_alias_mappings, _ = IndexSetHandler.get_rt_alias_settings(
            index_set.index_set_id, index_set.query_alias_settings
        )

    routes = []
    for is_analysis in (False, True):
        data_label = BaseIndexSetHandler.get_data_label(index_set.index_set_id)
        if is_analysis:
            data_label = f"{data_label}_analysis"
        table_info = []
        if index_set.is_group:
            child_ids = index_set.get_child_index_set_ids()
            child_map = {item.index_set_id: item for item in LogIndexSet.objects.filter(index_set_id__in=child_ids)}
            for child_id in child_ids:
                child = child_map.get(child_id)
                if child is None:
                    continue
                table_info.extend(
                    BaseIndexSetHandler.get_index_set_table_info_list(
                        index_set=child,
                        is_analysis=is_analysis,
                        parent_index_set=index_set,
                        rt_alias_mappings=rt_alias_mappings,
                    )
                )
        else:
            table_info = BaseIndexSetHandler.get_index_set_table_info_list(
                index_set=index_set,
                is_analysis=is_analysis,
                rt_alias_mappings=rt_alias_mappings,
            )
        if not table_info:
            continue
        original_table_count = len(table_info)
        table_info = table_info[:MAX_ROUTE_TABLES]
        route = {
            "data_label": data_label,
            "route_kind": "analysis" if is_analysis else "default",
            "space_id": index_set.space_uid.split("__")[-1],
            "space_type": index_set.space_uid.split("__")[0],
            "table_info": sanitize_json(table_info, redact_text=True),
            "original_table_count": original_table_count,
            "returned_table_count": len(table_info),
            "truncated": original_table_count > len(table_info),
        }
        BaseIndexSetHandler._set_table_info_is_enabled(route)
        routes.append(route)
    return routes


def _probe_metadata_routes(table_ids):
    started = time.monotonic()
    items = []
    for table_id in table_ids:
        item_started = time.monotonic()
        try:
            data = TransferApi.get_result_table(
                params={"table_id": table_id, "no_request": True},
                timeout=DEFAULT_TIMEOUT_SECONDS,
                request_cookies=False,
            )
            projected = _project_result_table(data, {})
            items.append({"table_id": table_id, "probe": probe_success(projected, item_started)})
        except Exception as error:
            items.append({"table_id": table_id, "probe": probe_failure(error, item_started)})
    return probe_success({"items": items, "item_count": len(items)}, started)


def _probe_physical_storage(table_ids):
    started = time.monotonic()
    items = []
    for table_id in table_ids:
        item_started = time.monotonic()
        try:
            indices = StorageHandler.get_result_table_indices(table_id)
            projected = sanitize_json(indices, redact_text=True)
            items.append({"table_id": table_id, "probe": probe_success(projected, item_started)})
        except Exception as error:
            items.append({"table_id": table_id, "probe": probe_failure(error, item_started)})
    return probe_success({"items": items, "item_count": len(items)}, started)


def _route_table_ids(routes):
    return list(
        dict.fromkeys(
            item.get("table_id")
            for route in routes
            for item in route.get("table_info", [])
            if isinstance(item, dict) and item.get("table_id")
        )
    )


def _consistency_warnings(expected_table_ids, metadata_route, physical_storage):
    warnings = []
    metadata_items = metadata_route.get("data", {}).get("items", [])
    physical_items = physical_storage.get("data", {}).get("items", [])
    metadata_by_table = {item["table_id"]: item["probe"] for item in metadata_items}
    physical_by_table = {item["table_id"]: item["probe"] for item in physical_items}
    for table_id in expected_table_ids:
        metadata_probe = metadata_by_table.get(table_id)
        if not metadata_probe or metadata_probe.get("probe_status") != "success" or metadata_probe.get("empty"):
            warnings.append(
                {
                    "code": "METADATA_ROUTE_MISSING",
                    "table_id": table_id,
                    "message": "expected virtual route is not confirmed by Metadata",
                }
            )
        physical_probe = physical_by_table.get(table_id)
        if physical_probe and physical_probe.get("probe_status") == "success" and physical_probe.get("empty"):
            warnings.append(
                {
                    "code": "PHYSICAL_STORAGE_EMPTY",
                    "table_id": table_id,
                    "message": "no physical index evidence was returned",
                }
            )
    return warnings


def _flatten_expected_routes(routes):
    return [
        (route, item)
        for route in routes
        for item in route.get("table_info", [])
        if isinstance(item, dict) and item.get("table_id")
    ]


def _compare_route(route_meta, expected, actual):
    route = _route_base(route_meta, expected)
    if actual is None:
        route["status"] = "route_missing"
        route["warnings"].append(
            {
                "code": "RUNTIME_ROUTE_MISSING",
                "table_id": expected["table_id"],
                "message": "Monitor returned no storage status for the expected route",
            }
        )
        return route

    bounded_actual = sanitize_json(_project_runtime_item(actual), max_bytes=MAX_ROUTE_BYTES)
    route["actual"] = bounded_actual["value"]
    route["truncation"] = {
        "truncated": bounded_actual["truncated"],
        "original_size_bytes": bounded_actual["original_size_bytes"],
        "returned_size_bytes": bounded_actual["returned_size_bytes"],
    }
    if actual.get("error"):
        route["status"] = "runtime_unavailable"
        route["errors"].append(_project_runtime_error(actual.get("error")))
        return route

    data = actual.get("data") or {}
    storage_configs = data.get("storage_configs") or {}
    expected_storage = expected.get("storage_type") or STORAGE_CLUSTER_TYPE
    default_storage = (data.get("result_table") or {}).get("default_storage")
    configured_storage = {key for key, value in storage_configs.items() if value}
    if default_storage is None and len(configured_storage) == 1:
        default_storage = next(iter(configured_storage))
    actual_storage_config = storage_configs.get(expected_storage) or {}

    if expected_storage not in configured_storage:
        route["status"] = "route_missing"
        route["warnings"].append(
            {
                "code": "STORAGE_ROUTE_MISSING",
                "table_id": expected["table_id"],
                "storage_type": expected_storage,
                "message": "expected storage type is absent from the runtime route",
            }
        )
        return route

    expected_cluster = expected.get("cluster_id")
    actual_cluster = actual_storage_config.get("storage_cluster_id")
    if default_storage != expected_storage or (
        expected_cluster is not None and str(expected_cluster) != str(actual_cluster)
    ):
        route["status"] = "route_mismatch"
        route["warnings"].append(
            {
                "code": "ROUTE_MISMATCH",
                "table_id": expected["table_id"],
                "expected_storage_type": expected_storage,
                "actual_default_storage": default_storage,
                "expected_cluster_id": expected_cluster,
                "actual_cluster_id": actual_cluster,
                "message": "runtime storage route differs from the BKLog route builder",
            }
        )
        return route

    cluster_results = data.get("cluster_results") or {}
    cluster_result = cluster_results.get(str(actual_cluster)) or cluster_results.get(actual_cluster) or {}
    route["warnings"].extend(_project_runtime_warning(warning) for warning in cluster_result.get("warnings") or [])
    route["errors"].extend(_project_runtime_error(error) for error in cluster_result.get("errors") or [])
    if cluster_result.get("runtime_skipped") or route["errors"]:
        route["status"] = "runtime_unavailable"
    return route


def _runtime_unavailable_route(route_meta, expected, error):
    route = _route_base(route_meta, expected)
    route["status"] = "runtime_unavailable"
    route["errors"].append(
        {
            "code": "RUNTIME_PROVIDER_UNAVAILABLE",
            "message": "Monitor runtime route provider is unavailable",
        }
    )
    return route


def _project_runtime_response(runtime):
    """Keep only the fixed storage-status projection used for route comparison."""

    if not isinstance(runtime, dict):
        return {"items": [], "invalid_response": True}
    items = runtime.get("items")
    if not isinstance(items, list):
        return {"items": [], "invalid_response": True}
    return {
        "items": [_project_runtime_item(item) for item in items if isinstance(item, dict)],
        "invalid_response": False,
    }


def _project_runtime_item(item):
    return sanitize_json(_project_storage_status_item(item), redact_text=True)


def _project_runtime_error(error):
    if not isinstance(error, dict):
        return {"code": "RUNTIME_ROUTE_ERROR", "message": "Monitor runtime route probe failed"}
    return {
        "code": str(error.get("code") or "RUNTIME_ROUTE_ERROR"),
        "message": "Monitor runtime route probe failed",
        "request_id": error.get("request_id"),
        "retryable": bool(error.get("retryable")),
    }


def _project_runtime_warning(warning):
    if not isinstance(warning, dict):
        return {"code": "RUNTIME_ROUTE_WARNING", "message": "Monitor runtime route warning"}
    return {
        "code": str(warning.get("code") or "RUNTIME_ROUTE_WARNING"),
        "message": "Monitor runtime route warning",
        "request_id": warning.get("request_id"),
        "retryable": bool(warning.get("retryable")),
    }


def _runtime_probe_failure(error, started):
    failure = probe_failure(error, started)
    failure["error"]["upstream_message"] = None
    return failure


def _route_base(route_meta, expected):
    return {
        "data_label": route_meta.get("data_label"),
        "route_kind": route_meta.get("route_kind"),
        "table_id": expected.get("table_id"),
        "expected": expected,
        "actual": None,
        "status": "consistent",
        "warnings": [],
        "errors": [],
        "truncation": {"truncated": False, "original_size_bytes": 0, "returned_size_bytes": 0},
    }


def _overall_status(routes):
    return max((route["status"] for route in routes), key=lambda item: ROUTE_STATUS_PRIORITY[item])


def _positive_int(value, name):
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer")
    if value < 1:
        raise ValidationError(f"{name} must be positive")
    return value


def _source_env():
    return getattr(settings, "ENVIRONMENT", None) or getattr(settings, "RUN_VER", None) or "unknown"


FUNCTIONS = {
    "bklog.index_set.route_snapshot": {
        "func_name": "bklog.index_set.route_snapshot",
        "description": "Compare BKLog expected routes with Monitor storage-route runtime evidence.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "index_set_id": {"type": "integer", "minimum": 1},
                "result_table_id": {"type": "string", "minLength": 1, "maxLength": 255},
            },
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [
            {"params": {"index_set_id": 16462}},
            {"params": {"result_table_id": "2_bklog.demo"}},
        ],
    },
    "bklog.index_set.storage_route.snapshot": {
        "func_name": "bklog.index_set.storage_route.snapshot",
        "description": "Compare BKLog expected virtual routes, Metadata routes and physical storage evidence.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"index_set_id": {"type": "integer", "minimum": 1}},
            "required": ["index_set_id"],
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [{"params": {"index_set_id": 16462}}],
        "deprecated": True,
        "replacement": "bklog.index_set.route_snapshot",
    },
}

HANDLERS = {
    "bklog.index_set.route_snapshot": get_index_set_route_snapshot,
    "bklog.index_set.storage_route.snapshot": get_index_set_storage_route_snapshot,
}
