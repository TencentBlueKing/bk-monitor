"""Reusable response-schema fragments for Agent-facing Resource Call handlers."""

from __future__ import annotations

from typing import Any


def object_schema(*required: str, properties: dict[str, Any] | None = None, additional_properties: bool = False):
    schema = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional_properties,
    }
    if required:
        schema["required"] = list(required)
    return schema


def nullable_schema(type_name: str):
    return {"type": [type_name, "null"]}


def diagnostic_schema():
    return object_schema(
        "code",
        "message",
        properties={
            "code": {"type": "string"},
            "message": {"type": "string"},
            "request_id": nullable_schema("string"),
            "retryable": {"type": "boolean"},
        },
        additional_properties=True,
    )


def probe_error_schema():
    return object_schema(
        "code",
        "message",
        "upstream_code",
        "upstream_message",
        "request_id",
        "retryable",
        properties={
            "code": {"type": "string"},
            "message": {"type": "string"},
            "upstream_code": nullable_schema("string"),
            "upstream_message": nullable_schema("string"),
            "request_id": nullable_schema("string"),
            "retryable": {"type": "boolean"},
        },
    )


def probe_schema(data_schema: dict[str, Any] | None = None):
    return object_schema(
        "probe_status",
        "exists",
        "empty",
        "observed_at",
        "duration_ms",
        "data",
        "error",
        "warnings",
        properties={
            "probe_status": {"type": "string", "enum": ["success", "failed", "skipped"]},
            "exists": nullable_schema("boolean"),
            "empty": nullable_schema("boolean"),
            "observed_at": {"type": "string", "format": "date-time"},
            "duration_ms": {"type": "number", "minimum": 0},
            "data": data_schema or {},
            "error": {"anyOf": [probe_error_schema(), {"type": "null"}]},
            "warnings": {"type": "array", "items": diagnostic_schema()},
        },
    )


def nullable_probe_schema(data_schema: dict[str, Any] | None = None):
    return {"anyOf": [probe_schema(data_schema), {"type": "null"}]}


def bounded_value_schema():
    return object_schema(
        "value",
        "truncated",
        "original_size_bytes",
        properties={
            "value": {},
            "truncated": {"type": "boolean"},
            "original_size_bytes": {"type": "integer", "minimum": 0},
        },
    )


def bounded_string_list_schema():
    return object_schema(
        "items",
        "count",
        "returned_count",
        "truncated",
        properties={
            "items": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer", "minimum": 0},
            "returned_count": {"type": "integer", "minimum": 0},
            "truncated": {"type": "boolean"},
        },
    )


def pagination_schema(item_schema: dict[str, Any]):
    return object_schema(
        "items",
        "page",
        "page_size",
        "total",
        properties={
            "items": {"type": "array", "items": item_schema},
            "page": {"type": "integer", "minimum": 1},
            "page_size": {"type": "integer", "minimum": 1},
            "total": {"type": "integer", "minimum": 0},
        },
    )
