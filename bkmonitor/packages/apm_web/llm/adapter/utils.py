"""Adapter 共用的值解析和原始 Span 归一工具。"""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from typing import Any


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _depth(value: Any, current: int = 0) -> int:
    if current > 20:
        return current
    if isinstance(value, dict):
        return max((_depth(item, current + 1) for item in value.values()), default=current)
    if isinstance(value, list | tuple):
        return max((_depth(item, current + 1) for item in value), default=current)
    return current


def safe_parse(value: Any) -> Any:
    """解析 JSON/Python 字面量；无法解析时保留原值。"""
    if not isinstance(value, str):
        return deepcopy(value)
    if len(value.encode()) > 256 * 1024:
        return value
    stripped = value.strip()
    if not stripped:
        return value
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(stripped)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return value
    if _depth(parsed) > 20:
        return value
    return parsed


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_events(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(raw.get("events"), list):
        return [
            {
                "name": str(event.get("name", "")),
                "timestamp": _as_int(event.get("timestamp")),
                "attributes": deepcopy(event.get("attributes")) if isinstance(event.get("attributes"), dict) else {},
            }
            for event in raw["events"]
            if isinstance(event, dict)
        ]

    flat = {key.removeprefix("events."): value for key, value in raw.items() if key.startswith("events.")}
    if not flat:
        return []
    count = max(len(value) if isinstance(value, list) else 1 for value in flat.values())
    events: list[dict[str, Any]] = []
    for index in range(count):
        event: dict[str, Any] = {"name": "", "timestamp": 0, "attributes": {}}
        for field, raw_value in flat.items():
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            value = values[index] if index < len(values) else None
            if field == "name":
                event["name"] = str(value or "")
            elif field == "timestamp":
                event["timestamp"] = _as_int(value)
            elif field.startswith("attributes."):
                event["attributes"][field.removeprefix("attributes.")] = value
        events.append(event)
    return events


def normalize_span(raw: dict[str, Any]) -> dict[str, Any]:
    attributes_raw = raw.get("attributes")
    attributes: dict[str, Any] = deepcopy(attributes_raw) if isinstance(attributes_raw, dict) else {}
    resource_raw = raw.get("resource")
    resource: dict[str, Any] = deepcopy(resource_raw) if isinstance(resource_raw, dict) else {}
    for key, value in raw.items():
        if key.startswith("attributes."):
            attributes[key.removeprefix("attributes.")] = value
        elif key.startswith("resource."):
            resource[key.removeprefix("resource.")] = value

    status_raw = raw.get("status")
    status: dict[str, Any] = status_raw if isinstance(status_raw, dict) else {}
    code: Any = status.get("code", raw.get("status.code", 0))
    if isinstance(code, str):
        code = {"UNSET": 0, "OK": 1, "ERROR": 2, "STATUS_CODE_ERROR": 2}.get(code.upper(), _as_int(code))
    span_id = str(raw.get("span_id", ""))
    start_time = _as_int(raw.get("start_time"))
    end_time = _as_int(raw.get("end_time"), start_time)
    elapsed_time = _as_int(raw.get("elapsed_time"), max(0, end_time - start_time))
    events = normalize_events(raw)
    if attributes.get("error.type") or any(event["name"] == "exception" for event in events):
        code = 2
    return {
        "trace_id": str(raw.get("trace_id", "")),
        "span_id": span_id,
        "parent_span_id": str(raw.get("parent_span_id") or "") or None,
        "span_name": str(raw.get("span_name", raw.get("name", ""))),
        "start_time": start_time,
        "end_time": end_time,
        "elapsed_time": max(0, elapsed_time),
        "status": {
            "code": code if code in (0, 1, 2) else 0,
            "message": str(status.get("message", raw.get("status.message", "")) or ""),
        },
        "attributes": attributes,
        "events": events,
        "resource": resource,
    }
