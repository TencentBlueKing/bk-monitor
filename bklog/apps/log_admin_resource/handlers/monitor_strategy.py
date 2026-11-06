"""Resource Call handler for bounded monitor strategy snapshots."""

from __future__ import annotations

from typing import Any

from apps.api import MonitorApi
from apps.exceptions import ApiError
from apps.log_admin_resource.handlers.inspection import (
    reject_identity_params,
    require_biz_in_request_tenant,
    require_nonzero_int,
    require_positive_int,
    sanitize_json,
)
from apps.log_admin_resource.response_schema import object_schema
from apps.utils.local import get_request_tenant_id


FUNC_NAME = "bklog.monitor.strategy.snapshot"
FLOW_SNAPSHOT_FUNC = "bklog.bkdata.flow.snapshot"
STATUS_OK = "ok"
STATUS_NOT_FOUND = "not_found"
STATUS_UNKNOWN = "unknown"
SERVING_APPLICABLE = "applicable"
SERVING_NOT_APPLICABLE = "not_applicable"

NEXT_CALL_SCHEMA = object_schema(
    "func_name",
    "params",
    properties={
        "func_name": {"type": "string", "const": FLOW_SNAPSHOT_FUNC},
        "params": {
            "type": "object",
            "properties": {
                "bk_biz_id": {"type": "integer", "not": {"const": 0}},
                "flow_id": {"type": "integer", "minimum": 1},
            },
            "required": ["bk_biz_id", "flow_id"],
            "additionalProperties": False,
        },
    },
    additional_properties=False,
)

SERVING_FLOW_SCHEMA = object_schema(
    "applicability",
    "data_flow_id",
    "result_table_id",
    properties={
        "applicability": {"type": "string", "enum": [SERVING_APPLICABLE, SERVING_NOT_APPLICABLE]},
        "data_flow_id": {"type": ["integer", "null"]},
        "result_table_id": {"type": ["string", "null"]},
    },
    additional_properties=False,
)

RESPONSE_SCHEMA = object_schema(
    "status",
    "status_detail",
    "bk_biz_id",
    "strategy_id",
    "summary",
    "items",
    "notice",
    "serving_flow",
    "next_call",
    properties={
        "status": {"type": "string", "enum": [STATUS_OK, STATUS_NOT_FOUND, STATUS_UNKNOWN]},
        "status_detail": {"type": ["string", "null"]},
        "bk_biz_id": {"type": "integer", "not": {"const": 0}},
        "strategy_id": {"type": "integer", "minimum": 1},
        "summary": {"type": ["object", "null"]},
        "items": {"type": "array", "items": {"type": "object"}},
        "notice": {"type": ["object", "null"]},
        "serving_flow": SERVING_FLOW_SCHEMA,
        "next_call": {"anyOf": [NEXT_CALL_SCHEMA, {"type": "null"}]},
    },
    additional_properties=False,
)


def get_monitor_strategy_snapshot(params: dict[str, Any] | None) -> dict[str, Any]:
    """Fetch a bounded monitor strategy snapshot by business + strategy id."""

    params = params or {}
    reject_identity_params(params)
    bk_biz_id = require_biz_in_request_tenant(require_nonzero_int(params, "bk_biz_id"))
    strategy_id = require_positive_int(params, "strategy_id")

    request_params = {
        "bk_biz_id": bk_biz_id,
        "conditions": [{"key": "strategy_id", "value": [strategy_id]}],
        "page": 1,
        "page_size": 1,
        "with_notice_group": False,
        "with_notice_group_detail": False,
        "no_request": True,
    }
    tenant_id = get_request_tenant_id()
    if tenant_id:
        request_params["bk_tenant_id"] = tenant_id

    try:
        result_data = MonitorApi.search_alarm_strategy_v3(request_params)
    except ApiError as error:
        return _empty_snapshot(
            bk_biz_id=bk_biz_id,
            strategy_id=strategy_id,
            status=STATUS_UNKNOWN,
            status_detail=f"monitor strategy lookup failed: {error}",
        )

    strategy_list = (result_data or {}).get("strategy_config_list") or []
    strategy = _matched_strategy(strategy_list, strategy_id)
    if strategy is None:
        return _empty_snapshot(
            bk_biz_id=bk_biz_id,
            strategy_id=strategy_id,
            status=STATUS_NOT_FOUND,
            status_detail="strategy does not exist in the requested business",
        )
    items = [_serialize_item(item) for item in strategy.get("items") or [] if isinstance(item, dict)]
    serving_flow, next_call = _serving_flow_and_next_call(bk_biz_id=bk_biz_id, items=items)
    notice = strategy.get("notice") if isinstance(strategy.get("notice"), dict) else {}

    return {
        "status": STATUS_OK,
        "status_detail": None,
        "bk_biz_id": bk_biz_id,
        "strategy_id": strategy_id,
        "summary": {
            "name": strategy.get("name"),
            "is_enabled": strategy.get("is_enabled"),
            "scenario": strategy.get("scenario"),
            "source": strategy.get("source"),
            "labels": sanitize_json(strategy.get("labels") or [], redact_text=True),
            "update_time": strategy.get("update_time"),
            "create_time": strategy.get("create_time"),
            "bk_biz_id": strategy.get("bk_biz_id", bk_biz_id),
        },
        "items": items,
        "notice": {
            "user_groups": sanitize_json(notice.get("user_groups") or [], redact_text=True),
            "signal": notice.get("signal"),
        },
        "serving_flow": serving_flow,
        "next_call": next_call,
    }


def _matched_strategy(strategy_list: Any, strategy_id: int) -> dict[str, Any] | None:
    for strategy in strategy_list:
        if not isinstance(strategy, dict):
            continue
        try:
            returned_id = int(strategy.get("id"))
        except (TypeError, ValueError):
            continue
        if returned_id == strategy_id:
            return strategy
    return None


def _empty_snapshot(*, bk_biz_id: int, strategy_id: int, status: str, status_detail: str) -> dict[str, Any]:
    return {
        "status": status,
        "status_detail": status_detail,
        "bk_biz_id": bk_biz_id,
        "strategy_id": strategy_id,
        "summary": None,
        "items": [],
        "notice": None,
        "serving_flow": {
            "applicability": SERVING_NOT_APPLICABLE,
            "data_flow_id": None,
            "result_table_id": None,
        },
        "next_call": None,
    }


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    algorithms = []
    for algorithm in item.get("algorithms") or []:
        if not isinstance(algorithm, dict):
            continue
        algorithms.append(
            {
                "type": algorithm.get("type"),
                "level": algorithm.get("level"),
                "config": _bounded_algorithm_config(algorithm.get("config")),
            }
        )

    query_configs = []
    for query_config in item.get("query_configs") or []:
        if not isinstance(query_config, dict):
            continue
        query_configs.append(
            {
                "data_source_label": query_config.get("data_source_label"),
                "data_type_label": query_config.get("data_type_label"),
                "metric_id": query_config.get("metric_id"),
                "index_set_id": query_config.get("index_set_id"),
                "result_table_id": query_config.get("result_table_id"),
                "query_string": query_config.get("query_string"),
                "agg_interval": query_config.get("agg_interval"),
                "agg_dimension": sanitize_json(query_config.get("agg_dimension") or [], redact_text=True),
                "agg_condition": sanitize_json(query_config.get("agg_condition") or [], redact_text=True),
                "intelligent_detect": _serialize_intelligent_detect(query_config.get("intelligent_detect")),
            }
        )

    return {
        "name": item.get("name"),
        "expression": item.get("expression"),
        "algorithms": algorithms,
        "query_configs": query_configs,
    }


def _bounded_algorithm_config(config: Any) -> Any:
    if config is None:
        return None
    if not isinstance(config, dict):
        return sanitize_json(config, redact_text=True)
    bounded = {}
    for key in ("args", "detect_range", "threshold", "method", "floor", "ceil"):
        if key in config:
            bounded[key] = sanitize_json(config[key], redact_text=True)
    return bounded


def _serialize_intelligent_detect(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    data_flow_id = raw.get("data_flow_id")
    try:
        data_flow_id = int(data_flow_id) if data_flow_id not in (None, "") else None
    except (TypeError, ValueError):
        data_flow_id = None
    return {
        "status": raw.get("status"),
        "data_flow_id": data_flow_id,
        "result_table_id": raw.get("result_table_id"),
        "message": raw.get("message"),
        "use_sdk": raw.get("use_sdk"),
    }


def _serving_flow_and_next_call(*, bk_biz_id: int, items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict | None]:
    """Serving Flow is applicable only when a usable data_flow_id exists.

    SDK / NewSeries strategies may still carry intelligent_detect={use_sdk: True}
    without a serving DataFlow; those must stay not_applicable.
    """

    data_flow_id = None
    result_table_id = None
    for item in items:
        for query_config in item.get("query_configs") or []:
            intelligent_detect = query_config.get("intelligent_detect")
            if not intelligent_detect:
                continue
            candidate_flow_id = intelligent_detect.get("data_flow_id")
            if not candidate_flow_id:
                continue
            data_flow_id = candidate_flow_id
            result_table_id = intelligent_detect.get("result_table_id")
            break
        if data_flow_id:
            break

    if not data_flow_id:
        return (
            {
                "applicability": SERVING_NOT_APPLICABLE,
                "data_flow_id": None,
                "result_table_id": None,
            },
            None,
        )

    return (
        {
            "applicability": SERVING_APPLICABLE,
            "data_flow_id": data_flow_id,
            "result_table_id": result_table_id,
        },
        {
            "func_name": FLOW_SNAPSHOT_FUNC,
            "params": {"bk_biz_id": bk_biz_id, "flow_id": data_flow_id},
        },
    )


FUNCTIONS = {
    FUNC_NAME: {
        "func_name": FUNC_NAME,
        "description": (
            "Inspect a monitor alarm strategy by business and strategy ID. Returns bounded query/"
            "algorithm fields and IntelligentDetect serving Flow references when present."
        ),
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "bk_biz_id": {"type": "integer", "not": {"const": 0}},
                "strategy_id": {"type": "integer", "minimum": 1},
            },
            "required": ["bk_biz_id", "strategy_id"],
            "additionalProperties": False,
        },
        "response_schema": RESPONSE_SCHEMA,
        "examples": [
            {"params": {"bk_biz_id": 2, "strategy_id": 1001}},
            {"params": {"bk_biz_id": -4298, "strategy_id": 260806}},
        ],
        "error_codes": [
            "bk_biz_id is required",
            "strategy_id is required",
            "business does not belong to the current Resource Call tenant",
        ],
    }
}


HANDLERS = {FUNC_NAME: get_monitor_strategy_snapshot}
