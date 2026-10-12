"""Shared Resource Call protocol schemas for asynchronous collector inspections."""

from apps.log_admin_resource.response_schema import diagnostic_schema, nullable_schema, object_schema


TASK_STATUS_SCHEMA = {
    "type": "string",
    "enum": ["pending", "running", "success", "partial", "failed", "timed_out", "expired", "not_found"],
}

RUNTIME_LOG_OPTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "maxItems": 20,
            "items": {"type": "string", "minLength": 1, "maxLength": 256},
        },
        "match": {"type": "string", "enum": ["any", "all"]},
        "case_sensitive": {"type": "boolean"},
        "context_lines": {"type": "integer", "minimum": 0, "maximum": 20},
    },
    "additionalProperties": False,
}

INSPECTION_PROBE_SCHEMA = object_schema(
    "status",
    "code",
    "summary",
    "evidence",
    "warnings",
    "started_at",
    "finished_at",
    "duration_ms",
    properties={
        "status": {"type": "string", "enum": ["success", "warning", "failed", "skipped"]},
        "code": {"type": "string"},
        "summary": {"type": "string"},
        "evidence": {},
        "warnings": {"type": "array", "items": diagnostic_schema()},
        "started_at": nullable_schema("string"),
        "finished_at": nullable_schema("string"),
        "duration_ms": {"type": "number", "minimum": 0},
    },
    additional_properties=True,
)

INSPECTION_PROBE_SUMMARY_SCHEMA = object_schema(
    "status",
    "code",
    "summary",
    "started_at",
    "finished_at",
    "duration_ms",
    properties={
        "status": {"type": "string", "enum": ["success", "warning", "failed", "skipped"]},
        "code": {"type": "string"},
        "summary": {"type": "string"},
        "started_at": nullable_schema("string"),
        "finished_at": nullable_schema("string"),
        "duration_ms": {"type": "number", "minimum": 0},
    },
)
