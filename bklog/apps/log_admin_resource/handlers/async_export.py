from __future__ import annotations

from django.utils.dateparse import parse_datetime

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import sanitize_json, sanitize_sensitive_text
from apps.log_admin_resource.response_schema import diagnostic_schema, nullable_schema, object_schema, pagination_schema
from apps.log_search.constants import ASYNC_EXPORT_SCENE_ID, ExportStatus, IndexSetType
from apps.log_search.models import AsyncTask


MAX_PAGE_SIZE = 100
MAX_FAILURE_REASON = 2000
MAX_REQUEST_SUMMARY_BYTES = 16 * 1024
REQUEST_SUMMARY_FIELDS = (
    "start_time",
    "end_time",
    "size",
    "query_string",
    "search_mode",
    "time_field",
    "scenario_id",
    "scene_id",
    "table_id_conditions",
)
ORDERING_FIELDS = {"id", "created_at", "updated_at", "completed_at", "export_status", "exported_count"}
PHASES = {
    None: "record_created",
    "": "record_created",
    ExportStatus.DOWNLOAD_LOG: "querying_and_packaging",
    ExportStatus.EXPORT_PACKAGE: "uploading",
    ExportStatus.EXPORT_UPLOAD: "finalizing",
    ExportStatus.SUCCESS: "completed",
    ExportStatus.FAILED: "failed",
    ExportStatus.DOWNLOAD_EXPIRED: "artifact_expired",
}


def list_async_exports(params):
    params = params or {}
    page = _positive_int(params.get("page", 1), "page")
    page_size = _positive_int(params.get("page_size", 20), "page_size", maximum=MAX_PAGE_SIZE)
    queryset = AsyncTask.objects.all()
    filters = {
        "task_id": "id",
        "bk_biz_id": "bk_biz_id",
        "index_set_id": "index_set_id",
        "created_by": "created_by",
        "source_app_code": "source_app_code",
        "export_status": "export_status",
        "index_set_type": "index_set_type",
    }
    for param_name, field_name in filters.items():
        if params.get(param_name) not in (None, ""):
            queryset = queryset.filter(**{field_name: params[param_name]})
    if params.get("created_from"):
        queryset = queryset.filter(created_at__gte=_datetime(params["created_from"], "created_from"))
    if params.get("created_to"):
        queryset = queryset.filter(created_at__lte=_datetime(params["created_to"], "created_to"))

    ordering = params.get("ordering") or "-created_at"
    ordering_field = ordering[1:] if ordering.startswith("-") else ordering
    if ordering_field not in ORDERING_FIELDS:
        raise ValidationError(f"unsupported ordering: {ordering}")
    queryset = queryset.order_by(ordering, "-id")
    total = queryset.count()
    start = (page - 1) * page_size
    return {
        "items": [_list_item(task) for task in queryset[start : start + page_size]],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_async_export_detail(params):
    params = params or {}
    task_id = _positive_int(params.get("task_id"), "task_id")
    try:
        task = AsyncTask.objects.get(id=task_id)
    except AsyncTask.DoesNotExist:
        raise ValidationError(f"async export task does not exist: {task_id}")

    progress_ratio = None
    if task.export_total_count and task.export_total_count > 0:
        progress_ratio = round(task.exported_count / task.export_total_count, 6)
    duration_ms = None
    if task.created_at and task.completed_at:
        duration_ms = max(0, round((task.completed_at - task.created_at).total_seconds() * 1000, 2))
    raw_status = task.export_status
    return {
        "task_id": task.id,
        "bk_biz_id": task.bk_biz_id,
        "created_by": task.created_by,
        "source_app_code": task.source_app_code,
        "target": _target_summary(task),
        "request_summary": _request_summary(task.request_param),
        "raw_status": raw_status,
        "effective_status": raw_status,
        "phase": _phase(raw_status),
        "progress": {
            "exported_count": task.exported_count,
            "total": task.export_total_count,
            "ratio": progress_ratio,
        },
        "times": {
            "created_at": _iso(task.created_at),
            "updated_at": _iso(task.updated_at),
            "completed_at": _iso(task.completed_at),
            "query_start_time": task.start_time,
            "query_end_time": task.end_time,
            "duration_ms": duration_ms,
        },
        "failure": {
            "stage": "unknown" if raw_status == ExportStatus.FAILED else None,
            "reason": _sanitize_failure_reason(task.failed_reason),
        },
        "artifact": {
            "file_name": _limited_string(task.file_name, 256),
            "file_size": task.file_size,
            "download_entry_present": bool(task.download_url),
            "is_clean": task.is_clean,
            "download_count": task.download_count,
        },
        "consistency_warnings": _consistency_warnings(task),
        "evidence_scope": "db_and_artifact",
        "mcp_correlation": {
            "task_id": task.id,
            "created_at": _iso(task.created_at),
            "completed_at": _iso(task.completed_at),
            "source_app_code": task.source_app_code,
        },
    }


def _list_item(task):
    return {
        "task_id": task.id,
        "bk_biz_id": task.bk_biz_id,
        "created_by": task.created_by,
        "source_app_code": task.source_app_code,
        "target": _target_summary(task),
        "raw_status": task.export_status,
        "phase": _phase(task.export_status),
        "exported_count": task.exported_count,
        "total": task.export_total_count,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "completed_at": _iso(task.completed_at),
    }


def _target_summary(task):
    if task.scenario_id == ASYNC_EXPORT_SCENE_ID:
        return {"type": "scene", "scenario_id": task.scenario_id, "index_set_id": task.index_set_id}
    if task.index_set_type == IndexSetType.UNION.value:
        return {"type": "union", "index_set_ids": list(task.index_set_ids or [])[:100]}
    return {"type": "single", "index_set_id": task.index_set_id, "scenario_id": task.scenario_id}


def _request_summary(request_param):
    source = request_param if isinstance(request_param, dict) else {}
    summary = {key: source[key] for key in REQUEST_SUMMARY_FIELDS if key in source}
    limited = sanitize_json(summary, max_bytes=MAX_REQUEST_SUMMARY_BYTES, redact_text=True)
    return {
        "value": limited["value"],
        "truncated": limited["truncated"],
        "included_fields": sorted(summary),
        "omitted_field_count": max(0, len(source) - len(summary)),
    }


def _consistency_warnings(task):
    warnings = []
    if task.export_status == ExportStatus.SUCCESS and not task.download_url:
        warnings.append({"code": "SUCCESS_WITHOUT_DOWNLOAD_ENTRY", "message": "success task has no download entry"})
    if task.exported_count > task.export_total_count >= 0:
        warnings.append({"code": "EXPORTED_COUNT_EXCEEDS_TOTAL", "message": "exported_count is greater than total"})
    if task.created_at and task.completed_at and task.completed_at < task.created_at:
        warnings.append({"code": "COMPLETED_BEFORE_CREATED", "message": "completed_at is earlier than created_at"})
    terminal = {ExportStatus.SUCCESS, ExportStatus.FAILED, ExportStatus.DOWNLOAD_EXPIRED}
    if task.completed_at and task.export_status not in terminal:
        warnings.append({"code": "NON_TERMINAL_WITH_COMPLETED_AT", "message": "non-terminal task has completed_at"})
    if task.export_status == ExportStatus.DOWNLOAD_EXPIRED and task.download_url and not task.is_clean:
        warnings.append(
            {
                "code": "EXPIRED_WITH_ACTIVE_ARTIFACT_REFERENCE",
                "message": "expired task still has a download entry and is not marked clean",
            }
        )
    return warnings


def _phase(status):
    return PHASES.get(status, "unknown")


def _sanitize_failure_reason(value):
    if not value:
        return None
    redacted = sanitize_sensitive_text(value, maximum=None)
    return _limited_string(redacted, MAX_FAILURE_REASON)


def _limited_string(value, maximum):
    if value is None:
        return None
    value = str(value)
    return value if len(value) <= maximum else value[: maximum - 3] + "..."


def _positive_int(value, name, maximum=None):
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer")
    if value < 1:
        raise ValidationError(f"{name} must be positive")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{name} must be at most {maximum}")
    return value


def _datetime(value, name):
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValidationError(f"{name} must be an ISO-8601 datetime")
    return parsed


def _iso(value):
    return value.isoformat() if value else None


ASYNC_TARGET_SCHEMA = object_schema(
    "type",
    properties={
        "type": {"type": "string", "enum": ["single", "union", "scene"]},
        "scenario_id": nullable_schema("string"),
        "index_set_id": nullable_schema("integer"),
        "index_set_ids": {"type": "array", "items": {"type": "integer"}},
    },
)
ASYNC_LIST_ITEM_SCHEMA = object_schema(
    "task_id",
    "bk_biz_id",
    "created_by",
    "source_app_code",
    "target",
    "raw_status",
    "phase",
    "exported_count",
    "total",
    "created_at",
    "updated_at",
    "completed_at",
    properties={
        "task_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": nullable_schema("integer"),
        "created_by": {"type": "string"},
        "source_app_code": {"type": "string"},
        "target": ASYNC_TARGET_SCHEMA,
        "raw_status": nullable_schema("string"),
        "phase": {"type": "string"},
        "exported_count": {"type": "integer", "minimum": 0},
        "total": {"type": "integer", "minimum": 0},
        "created_at": nullable_schema("string"),
        "updated_at": nullable_schema("string"),
        "completed_at": nullable_schema("string"),
    },
)
ASYNC_EXPORT_LIST_RESPONSE_SCHEMA = pagination_schema(ASYNC_LIST_ITEM_SCHEMA)
ASYNC_EXPORT_DETAIL_RESPONSE_SCHEMA = object_schema(
    "task_id",
    "bk_biz_id",
    "created_by",
    "source_app_code",
    "target",
    "request_summary",
    "raw_status",
    "effective_status",
    "phase",
    "progress",
    "times",
    "failure",
    "artifact",
    "consistency_warnings",
    "evidence_scope",
    "mcp_correlation",
    properties={
        "task_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": nullable_schema("integer"),
        "created_by": {"type": "string"},
        "source_app_code": {"type": "string"},
        "target": ASYNC_TARGET_SCHEMA,
        "request_summary": object_schema(
            "value",
            "truncated",
            "included_fields",
            "omitted_field_count",
            properties={
                "value": {},
                "truncated": {"type": "boolean"},
                "included_fields": {"type": "array", "items": {"type": "string"}},
                "omitted_field_count": {"type": "integer", "minimum": 0},
            },
        ),
        "raw_status": nullable_schema("string"),
        "effective_status": nullable_schema("string"),
        "phase": {"type": "string"},
        "progress": object_schema(
            "exported_count",
            "total",
            "ratio",
            properties={
                "exported_count": {"type": "integer", "minimum": 0},
                "total": {"type": "integer"},
                "ratio": nullable_schema("number"),
            },
        ),
        "times": object_schema(
            "created_at",
            "updated_at",
            "completed_at",
            "query_start_time",
            "query_end_time",
            "duration_ms",
            properties={
                "created_at": nullable_schema("string"),
                "updated_at": nullable_schema("string"),
                "completed_at": nullable_schema("string"),
                "query_start_time": nullable_schema("string"),
                "query_end_time": nullable_schema("string"),
                "duration_ms": nullable_schema("number"),
            },
        ),
        "failure": object_schema(
            "stage",
            "reason",
            properties={
                "stage": nullable_schema("string"),
                "reason": nullable_schema("string"),
            },
        ),
        "artifact": object_schema(
            "file_name",
            "file_size",
            "download_entry_present",
            "is_clean",
            "download_count",
            properties={
                "file_name": nullable_schema("string"),
                "file_size": nullable_schema("number"),
                "download_entry_present": {"type": "boolean"},
                "is_clean": {"type": "boolean"},
                "download_count": {"type": "integer", "minimum": 0},
            },
        ),
        "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
        "evidence_scope": {"type": "string"},
        "mcp_correlation": object_schema(
            "task_id",
            "created_at",
            "completed_at",
            "source_app_code",
            properties={
                "task_id": {"type": "integer", "minimum": 1},
                "created_at": nullable_schema("string"),
                "completed_at": nullable_schema("string"),
                "source_app_code": {"type": "string"},
            },
        ),
    },
)


FUNCTIONS = {
    "bklog.async_export.list": {
        "func_name": "bklog.async_export.list",
        "description": "Discover async export tasks through bounded read-only filters.",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "minimum": 1},
                "bk_biz_id": {"type": "integer"},
                "index_set_id": {"type": "integer", "minimum": 1},
                "created_by": {"type": "string", "maxLength": 32},
                "source_app_code": {"type": "string", "maxLength": 32},
                "export_status": {"type": "string", "maxLength": 128},
                "index_set_type": {"type": "string", "enum": ["single", "union"]},
                "created_from": {"type": "string", "maxLength": 64},
                "created_to": {"type": "string", "maxLength": 64},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE},
                "ordering": {"type": "string", "maxLength": 32},
            },
            "additionalProperties": False,
        },
        "response_schema": ASYNC_EXPORT_LIST_RESPONSE_SCHEMA,
        "examples": [{"params": {"bk_biz_id": 2, "export_status": "failed", "page": 1}}],
    },
    "bklog.async_export.detail": {
        "func_name": "bklog.async_export.detail",
        "description": "Inspect persisted async export progress, failure and artifact evidence without downloading.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer", "minimum": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "response_schema": ASYNC_EXPORT_DETAIL_RESPONSE_SCHEMA,
        "examples": [{"params": {"task_id": 10001}}],
    },
}

HANDLERS = {
    "bklog.async_export.list": list_async_exports,
    "bklog.async_export.detail": get_async_export_detail,
}
