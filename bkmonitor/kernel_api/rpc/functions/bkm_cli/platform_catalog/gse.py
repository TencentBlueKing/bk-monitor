"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

platform-source catalog domain：GSE 当前路由与接收端只读查询。

只接受一个正整数定位参数；平台名与操作人由后端固定下发，调用方不能覆盖。
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

from core.drf_resource import api
from metadata import config

from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog

QUERY_ROUTE_ALLOWED_KEYS = frozenset({"channel_id"})
QUERY_STREAM_TO_ALLOWED_KEYS = frozenset({"stream_to_id"})

_POSITIVE_INTEGER_STRING_RE = re.compile(r"^[0-9]+$")
_MISSING = object()
_ROUTE_SINK_TYPES = ("kafka", "redis", "pulsar")
_STREAM_REPORT_MODES = frozenset({"kafka", "redis", "pulsar", "file"})


def _guard_query(params: Any, *, param_name: str, allowed_keys: frozenset[str], operation_id: str) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ParamsGuardRejected(f"{operation_id} 参数必须是对象")

    unknown_keys = sorted(str(key) for key in params if key not in allowed_keys)
    if unknown_keys:
        raise ParamsGuardRejected(f"{operation_id} 仅接受参数 {sorted(allowed_keys)}，拒绝未声明参数: {unknown_keys}")

    value = params.get(param_name)
    if isinstance(value, bool):
        raise ParamsGuardRejected(f"{param_name} 必须是正整数或十进制数字字符串")
    if isinstance(value, int):
        normalized = value
    elif isinstance(value, str) and _POSITIVE_INTEGER_STRING_RE.fullmatch(value):
        normalized = int(value)
    else:
        raise ParamsGuardRejected(f"{param_name} 必须是正整数或十进制数字字符串")
    if normalized <= 0:
        raise ParamsGuardRejected(f"{param_name} 必须大于 0")

    return {
        "condition": {
            param_name: normalized,
            "plat_name": config.DEFAULT_GSE_API_PLAT_NAME,
        },
        "operation": {"operator_name": settings.COMMON_USERNAME},
    }


def guard_query_route(params: Any) -> dict[str, Any]:
    return _guard_query(
        params,
        param_name="channel_id",
        allowed_keys=QUERY_ROUTE_ALLOWED_KEYS,
        operation_id="query_route",
    )


def guard_query_stream_to(params: Any) -> dict[str, Any]:
    return _guard_query(
        params,
        param_name="stream_to_id",
        allowed_keys=QUERY_STREAM_TO_ALLOWED_KEYS,
        operation_id="query_stream_to",
    )


def _positive_integer_schema(param_name: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            param_name: {
                "oneOf": [
                    {"type": "integer", "minimum": 1},
                    {"type": "string", "pattern": "^[0-9]+$"},
                ],
                "description": f"{param_name}，正整数或十进制数字字符串",
            }
        },
        "required": [param_name],
        "additionalProperties": False,
    }


def _new_projection_meta() -> dict[str, Any]:
    return {"is_partial": False, "dropped_items": 0, "reasons": []}


def _record_drop(meta: dict[str, Any], reason: str) -> None:
    meta["is_partial"] = True
    meta["dropped_items"] += 1
    if reason not in meta["reasons"]:
        meta["reasons"].append(reason)


def _project_positive_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and _POSITIVE_INTEGER_STRING_RE.fullmatch(value):
        normalized = int(value)
        return normalized if normalized > 0 else None
    return None


def _project_route(route: Any, meta: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(route, dict):
        _record_drop(meta, "invalid_route")
        return None

    name = route.get("name")
    if not isinstance(name, str):
        _record_drop(meta, "invalid_route_name")
        return None

    stream_to = route.get("stream_to")
    if not isinstance(stream_to, dict):
        _record_drop(meta, "invalid_stream_to")
        return None

    stream_to_id = _project_positive_integer(stream_to.get("stream_to_id"))
    if stream_to_id is None:
        _record_drop(meta, "invalid_stream_to_id")
        return None

    configured_sinks = [sink_type for sink_type in _ROUTE_SINK_TYPES if sink_type in stream_to]
    if len(configured_sinks) != 1:
        _record_drop(meta, "invalid_sink_config")
        return None
    sink_type = configured_sinks[0]
    sink_config = stream_to[sink_type]
    if not isinstance(sink_config, dict):
        _record_drop(meta, "invalid_sink_config")
        return None

    topic_name: str | None = None
    if sink_type == "kafka":
        topic_name = sink_config.get("topic_name")
    elif sink_type == "pulsar":
        topic_name = sink_config.get("topic_name", sink_config.get("name"))
    if sink_type != "redis" and not isinstance(topic_name, str):
        _record_drop(meta, "invalid_topic_name")
        return None

    return {
        "name": name,
        "stream_to_id": stream_to_id,
        "sink_type": sink_type,
        "topic_name": topic_name,
    }


def project_query_route(raw: Any, _fields: list[str] | None) -> dict[str, Any]:
    """固定投影当前路由；畸形结构必须显式标记为不完整。"""
    meta = _new_projection_meta()
    route_groups: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        _record_drop(meta, "invalid_top_level")
        return {
            "configuration_scope": "current",
            "projection_meta": meta,
            "route_groups": route_groups,
        }

    for group in raw:
        if not isinstance(group, dict):
            _record_drop(meta, "invalid_route_group")
            continue

        metadata = group.get("metadata", _MISSING)
        if metadata is _MISSING:
            channel_id_value = group.get("channel_id")
        elif isinstance(metadata, dict):
            channel_id_value = metadata.get("channel_id", group.get("channel_id"))
        else:
            _record_drop(meta, "invalid_route_group_metadata")
            channel_id_value = group.get("channel_id")

        channel_id = _project_positive_integer(channel_id_value)
        if channel_id is None:
            _record_drop(meta, "invalid_channel_id")
            continue

        routes = group.get("route", _MISSING)
        if not isinstance(routes, list):
            _record_drop(meta, "invalid_routes")
            routes = []

        projected_routes = []
        for route in routes:
            projected = _project_route(route, meta)
            if projected is not None:
                projected_routes.append(projected)
        route_groups.append({"channel_id": channel_id, "routes": projected_routes})

    return {
        "configuration_scope": "current",
        "projection_meta": meta,
        "route_groups": route_groups,
    }


def project_query_stream_to(raw: Any, _fields: list[str] | None) -> dict[str, Any]:
    """兼容嵌套与扁平响应，只输出接收端逻辑摘要。"""
    meta = _new_projection_meta()
    summaries: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        _record_drop(meta, "invalid_top_level")
        return {
            "configuration_scope": "current",
            "projection_meta": meta,
            "stream_to_summaries": summaries,
        }

    for item in raw:
        if not isinstance(item, dict):
            _record_drop(meta, "invalid_stream_to_summary")
            continue

        metadata = item.get("metadata", _MISSING)
        if metadata is not _MISSING and not isinstance(metadata, dict):
            _record_drop(meta, "invalid_stream_to_metadata")
            metadata = {}
        elif metadata is _MISSING:
            metadata = {}

        stream_to = item.get("stream_to", _MISSING)
        if stream_to is _MISSING:
            stream_to = item
        elif not isinstance(stream_to, dict):
            _record_drop(meta, "invalid_stream_to")
            continue

        stream_to_id_value = metadata.get(
            "stream_to_id",
            item.get("stream_to_id", stream_to.get("stream_to_id")),
        )
        stream_to_id = _project_positive_integer(stream_to_id_value)
        if stream_to_id is None:
            _record_drop(meta, "invalid_stream_to_id")
            continue

        name = stream_to.get("name")
        if not isinstance(name, str):
            _record_drop(meta, "invalid_stream_to_name")
            continue

        report_mode = stream_to.get("report_mode", _MISSING)
        if report_mode is _MISSING:
            configured_sinks = [sink_type for sink_type in _ROUTE_SINK_TYPES if sink_type in stream_to]
            report_mode = (
                configured_sinks[0]
                if len(configured_sinks) == 1 and isinstance(stream_to[configured_sinks[0]], dict)
                else None
            )
        if not isinstance(report_mode, str) or report_mode not in _STREAM_REPORT_MODES:
            _record_drop(meta, "invalid_report_mode")
            continue

        summaries.append(
            {
                "stream_to_id": stream_to_id,
                "name": name,
                "report_mode": report_mode,
            }
        )

    return {
        "configuration_scope": "current",
        "projection_meta": meta,
        "stream_to_summaries": summaries,
    }


def register() -> None:
    PlatformSourceCatalog.register_domain(
        id="gse",
        summary="GSE 当前路由与接收端配置只读查询",
        audit_tags=["readonly", "gse"],
        operations=[
            OperationSpec(
                id="query_route",
                summary="按 channel_id 查询当前 GSE 路由安全摘要",
                handler=api.gse.query_route,
                params_guard=guard_query_route,
                response_postprocess=project_query_route,
                params_schema_override=_positive_integer_schema("channel_id"),
                example_params={"channel_id": 101},
                required_params=["channel_id"],
                audit_tags=["readonly", "gse"],
                notes=("只回答当前控制面配置，不代表事故时刻的历史路由；路由存在也不代表数据已投递、确认或消费。"),
            ),
            OperationSpec(
                id="query_stream_to",
                summary="按 stream_to_id 查询当前 GSE 接收端安全摘要",
                handler=api.gse.query_stream_to,
                params_guard=guard_query_stream_to,
                response_postprocess=project_query_stream_to,
                params_schema_override=_positive_integer_schema("stream_to_id"),
                example_params={"stream_to_id": 101},
                required_params=["stream_to_id"],
                audit_tags=["readonly", "gse"],
                notes=("只回答当前控制面配置；name 是逻辑名称，不是稳定集群标识；结果不证明接收端已收到或消费数据。"),
            ),
        ],
    )


register()
