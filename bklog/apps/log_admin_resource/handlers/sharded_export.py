from __future__ import annotations

from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.async_export import (
    MAX_PAGE_SIZE,
    MAX_REQUEST_SUMMARY_BYTES,
    _datetime,
    _iso,
    _limited_string,
    _positive_int,
    _sanitize_failure_reason,
)
from apps.log_admin_resource.handlers.inspection import sanitize_json
from apps.log_admin_resource.response_schema import diagnostic_schema, nullable_schema, object_schema, pagination_schema
from apps.log_search.constants import (
    ExportErrorCode,
    ExportJobStatus,
    ExportPartStatus,
    ExportSearchType,
    IndexSetType,
)
from apps.log_search.export.history import load_export_progress, sharded_job_history_item
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.export.state import leaf_stats

LIST_FUNC_NAME = "bklog.async_export.sharded_job.list"
DETAIL_FUNC_NAME = "bklog.async_export.sharded_job.detail"

DEFAULT_PART_LIMIT = 50
MAX_PART_LIMIT = 200
MAX_PART_ERROR_DETAIL = 500
MAX_POLICY_BYTES = 8 * 1024
MAX_TARGET_INDEX_SET_IDS = 100
SEARCH_SUMMARY_FIELDS = (
    "start_time",
    "end_time",
    "keyword",
    "addition",
    "sort_list",
    "export_fields",
    "is_desensitize",
    "table_id_conditions",
    "export_time_fields",
)
ORDERING_FIELDS = {"id", "created_at", "updated_at", "completed_at", "status"}
JOB_STATUSES = [status for status, _ in ExportJobStatus.CHOICES]
PART_STATUSES = [status for status, _ in ExportPartStatus.CHOICES]
PART_PRIORITY = (
    (ExportPartStatus.FAILED, 0),
    (ExportPartStatus.RUNNING, 1),
    (ExportPartStatus.UPLOADING, 1),
    (ExportPartStatus.DISPATCHED, 2),
    (ExportPartStatus.WAITING, 3),
)


def list_sharded_export_jobs(params):
    params = params or {}
    page = _positive_int(params.get("page", 1), "page")
    page_size = _positive_int(params.get("page_size", 20), "page_size", maximum=MAX_PAGE_SIZE)
    queryset = ExportJob.objects.all()
    filters = {
        "job_id": "id",
        "bk_biz_id": "bk_biz_id",
        "space_uid": "space_uid",
        "created_by": "created_by",
        "source_app_code": "source_app_code",
        "status": "status",
        "search_type": "search_type",
    }
    for param_name, field_name in filters.items():
        if params.get(param_name) not in (None, ""):
            queryset = queryset.filter(**{field_name: params[param_name]})
    if params.get("index_set_id") not in (None, ""):
        queryset = queryset.filter(index_set_ids=[_positive_int(params["index_set_id"], "index_set_id")])
    if params.get("index_set_ids"):
        queryset = queryset.filter(index_set_ids=list(params["index_set_ids"]))
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
    jobs = list(queryset[start : start + page_size])
    load_export_progress(jobs)
    return {
        "items": [_list_item(job) for job in jobs],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_sharded_export_job_detail(params):
    params = params or {}
    job_id = _positive_int(params.get("job_id"), "job_id")
    part_limit = _positive_int(params.get("part_limit", DEFAULT_PART_LIMIT), "part_limit", maximum=MAX_PART_LIMIT)
    part_statuses = params.get("part_status") or []
    unknown_statuses = sorted(set(part_statuses) - set(PART_STATUSES))
    if unknown_statuses:
        raise ValidationError(f"unsupported part_status: {', '.join(unknown_statuses)}")
    try:
        job = ExportJob.objects.get(id=job_id)
    except ExportJob.DoesNotExist:
        raise ValidationError(f"sharded export job does not exist: {job_id}")

    load_export_progress([job])
    stats = leaf_stats(job)
    current_plan = ExportPlan.objects.filter(job=job, plan_version=job.plan_version).first()
    now = timezone.now()
    duration_ms = None
    if job.created_at and job.completed_at:
        duration_ms = max(0, round((job.completed_at - job.created_at).total_seconds() * 1000, 2))
    return {
        **_job_identity(job),
        "request_summary": _search_summary(job.search_params),
        "query_range": {"start_time": job.start_time, "end_time": job.end_time},
        "policy": sanitize_json(job.policy or {}, max_bytes=MAX_POLICY_BYTES, redact_text=True),
        "plan": _plan_summary(job, current_plan),
        "progress": {
            **_progress_summary(job),
            "status_counts": dict(job.export_progress["status_counts"]),
            "stage_counts": dict(job.export_progress["stage_counts"]),
            "leaf_rows": stats["rows"],
        },
        "parts": _part_summary(job, part_statuses, part_limit),
        "times": {
            "created_at": _iso(job.created_at),
            "updated_at": _iso(job.updated_at),
            "started_at": _iso(job.started_at),
            "completed_at": _iso(job.completed_at),
            "last_dispatched_at": _iso(job.last_dispatched_at),
            "duration_ms": duration_ms,
        },
        "lifecycle": {
            "planning": {
                "enqueued_at": _iso(job.planning_enqueued_at),
                "started_at": _iso(job.planning_started_at),
                "attempts": job.planning_attempts,
            },
            "finalization": {
                "enqueued_at": _iso(job.finalization_enqueued_at),
                "started_at": _iso(job.finalization_started_at),
                "attempts": job.finalization_attempts,
            },
            "notification": {
                "enqueued_at": _iso(job.notify_enqueued_at),
                "notify_at": _iso(job.notify_at),
            },
        },
        "failure": {
            "error_code": job.error_code or None,
            "error_label": ExportErrorCode.label(job.error_code) or None,
            "error_detail": _sanitize_failure_reason(job.error_detail),
        },
        "artifact": {
            "merged": _artifact(job.merged_object_key, job.merged_bytes, job.merged_checksum),
            "manifest": _artifact(job.manifest_object_key, job.manifest_bytes, job.manifest_checksum),
            "expires_at": _iso(job.expires_at),
            "expired": job.expires_at <= now if job.expires_at else None,
        },
        "consistency_warnings": _consistency_warnings(job, stats, current_plan),
        "evidence_scope": "db_only",
    }


def _list_item(job):
    return {
        **_job_identity(job),
        "progress": _progress_summary(job),
        "created_at": _iso(job.created_at),
        "updated_at": _iso(job.updated_at),
        "completed_at": _iso(job.completed_at),
    }


def _job_identity(job):
    return {
        "job_id": job.id,
        "engine": "sharded",
        "bk_biz_id": job.bk_biz_id,
        "space_uid": job.space_uid,
        "created_by": job.created_by,
        "source_app_code": job.source_app_code,
        "is_external": job.is_external,
        "search_type": job.search_type,
        "target": _target_summary(job),
        "status": job.status,
        "user_export_status": sharded_job_history_item(job)["export_status"],
        "error_code": job.error_code or None,
        "estimated_total": job.estimated_total,
        "actual_total": job.actual_total,
    }


def _target_summary(job):
    index_set_ids = list(job.index_set_ids or [])[:MAX_TARGET_INDEX_SET_IDS]
    if job.search_type == ExportSearchType.SCENE:
        return {"type": "scene", "index_set_ids": index_set_ids}
    if job.index_set_type == IndexSetType.UNION.value:
        return {"type": "union", "index_set_ids": index_set_ids}
    return {"type": "single", "index_set_ids": index_set_ids}


def _search_summary(search_params):
    source = search_params if isinstance(search_params, dict) else {}
    summary = {key: source[key] for key in SEARCH_SUMMARY_FIELDS if key in source}
    limited = sanitize_json(summary, max_bytes=MAX_REQUEST_SUMMARY_BYTES, redact_text=True)
    return {
        "value": limited["value"],
        "truncated": limited["truncated"],
        "included_fields": sorted(summary),
        "omitted_field_count": max(0, len(source) - len(summary)),
    }


def _progress_summary(job):
    progress = job.export_progress
    return {
        "plan_version": progress["plan_version"],
        "planned_parts": progress["planned_parts"],
        "parts_total": progress["parts_total"],
        "parts_success": progress["parts_success"],
        "parts_failed": progress["parts_failed"],
    }


def _plan_summary(job, plan):
    return {
        "plan_version": job.plan_version,
        "plan_count": ExportPlan.objects.filter(job=job).count(),
        "current": None
        if plan is None
        else {
            "status": plan.status,
            "planned_parts": plan.planned_parts,
            "total_rows": plan.total_rows,
            "target_rows": plan.target_rows,
            "target_bytes": plan.target_bytes,
            "avg_row_bytes": plan.avg_row_bytes,
            "initial_interval_ms": plan.initial_interval_ms,
            "started_at": _iso(plan.started_at),
            "finished_at": _iso(plan.finished_at),
        },
    }


def _part_summary(job, part_statuses, part_limit):
    queryset = ExportPart.objects.filter(job=job)
    if part_statuses:
        queryset = queryset.filter(status__in=part_statuses)
    total = queryset.count()
    priority = Case(
        *[When(status=status, then=Value(rank)) for status, rank in PART_PRIORITY],
        default=Value(len(PART_PRIORITY)),
        output_field=IntegerField(),
    )
    parts = queryset.annotate(evidence_priority=priority).order_by(
        "evidence_priority", "plan_version", "part_no", "id"
    )[:part_limit]
    items = [_part_item(part) for part in parts]
    return {
        "items": items,
        "total": total,
        "returned_count": len(items),
        "truncated": total > len(items),
        "ordering": "failed, executing, dispatched, waiting, then other statuses; plan_version and part_no within",
    }


def _part_item(part):
    return {
        "part_id": part.id,
        "part_no": part.part_no,
        "plan_version": part.plan_version,
        "parent_part_id": part.parent_part_id,
        "start_time": part.start_time,
        "end_time": part.end_time,
        "oversized": part.oversized,
        "status": part.status,
        "stage": part.stage or None,
        "attempts": part.attempts,
        "celery_task_id": part.task_id or None,
        "estimated_rows": part.estimated_rows,
        "actual_rows": part.actual_rows,
        "actual_bytes": part.actual_bytes,
        "compressed_bytes": part.compressed_bytes,
        "artifact_present": bool(part.object_key and part.checksum),
        "started_at": _iso(part.started_at),
        "finished_at": _iso(part.finished_at),
        "updated_at": _iso(part.updated_at),
        "error_code": part.error_code or None,
        "error_detail": _limited_string(_sanitize_failure_reason(part.error_detail), MAX_PART_ERROR_DETAIL),
    }


def _artifact(object_key, size, checksum):
    return {
        "present": bool(object_key),
        "bytes": size,
        "checksum_present": bool(checksum),
    }


def _consistency_warnings(job, stats, current_plan):
    warnings = []
    terminal = job.status in ExportJobStatus.TERMINAL
    if job.status == ExportJobStatus.SUCCESS:
        if not (job.merged_object_key and job.merged_bytes is not None and job.merged_checksum):
            warnings.append(
                {"code": "SUCCESS_WITHOUT_MERGED_ARTIFACT", "message": "success job has no complete merged artifact"}
            )
        if not (job.manifest_object_key and job.manifest_checksum):
            warnings.append({"code": "SUCCESS_WITHOUT_MANIFEST", "message": "success job has no complete manifest"})
        if stats["success"] != stats["total"]:
            warnings.append(
                {"code": "SUCCESS_WITH_UNFINISHED_LEAF_PARTS", "message": "success job has leaf parts not in SUCCESS"}
            )
    if terminal and job.actual_total != stats["rows"]:
        warnings.append(
            {
                "code": "ACTUAL_TOTAL_MISMATCH_LEAF_ROWS",
                "message": "actual_total differs from the sum of leaf part actual_rows",
            }
        )
    if terminal and not job.completed_at:
        warnings.append({"code": "TERMINAL_WITHOUT_COMPLETED_AT", "message": "terminal job has no completed_at"})
    if not terminal and job.completed_at:
        warnings.append({"code": "NON_TERMINAL_WITH_COMPLETED_AT", "message": "non-terminal job has completed_at"})
    if job.created_at and job.completed_at and job.completed_at < job.created_at:
        warnings.append({"code": "COMPLETED_BEFORE_CREATED", "message": "completed_at is earlier than created_at"})
    if job.plan_version and current_plan is None:
        warnings.append(
            {"code": "CURRENT_PLAN_MISSING", "message": "job plan_version has no matching ExportPlan record"}
        )
    return warnings


TARGET_SCHEMA = object_schema(
    "type",
    "index_set_ids",
    properties={
        "type": {"type": "string", "enum": ["single", "union", "scene"]},
        "index_set_ids": {"type": "array", "items": {"type": "integer"}},
    },
)
PROGRESS_SUMMARY_PROPERTIES = {
    "plan_version": {"type": "integer", "minimum": 0},
    "planned_parts": nullable_schema("integer"),
    "parts_total": {"type": "integer", "minimum": 0},
    "parts_success": {"type": "integer", "minimum": 0},
    "parts_failed": {"type": "integer", "minimum": 0},
}
PROGRESS_SUMMARY_SCHEMA = object_schema(*PROGRESS_SUMMARY_PROPERTIES, properties=PROGRESS_SUMMARY_PROPERTIES)
JOB_IDENTITY_PROPERTIES = {
    "job_id": {"type": "integer", "minimum": 1},
    "engine": {"type": "string", "const": "sharded"},
    "bk_biz_id": nullable_schema("integer"),
    "space_uid": {"type": "string"},
    "created_by": {"type": "string"},
    "source_app_code": {"type": "string"},
    "is_external": {"type": "boolean"},
    "search_type": {"type": "string"},
    "target": TARGET_SCHEMA,
    "status": {"type": "string"},
    "user_export_status": nullable_schema("string"),
    "error_code": nullable_schema("string"),
    "estimated_total": nullable_schema("integer"),
    "actual_total": {"type": "integer", "minimum": 0},
}
LIST_ITEM_PROPERTIES = {
    **JOB_IDENTITY_PROPERTIES,
    "progress": PROGRESS_SUMMARY_SCHEMA,
    "created_at": nullable_schema("string"),
    "updated_at": nullable_schema("string"),
    "completed_at": nullable_schema("string"),
}
LIST_RESPONSE_SCHEMA = pagination_schema(object_schema(*LIST_ITEM_PROPERTIES, properties=LIST_ITEM_PROPERTIES))

PART_ITEM_PROPERTIES = {
    "part_id": {"type": "integer", "minimum": 1},
    "part_no": {"type": "integer", "minimum": 0},
    "plan_version": {"type": "integer", "minimum": 0},
    "parent_part_id": nullable_schema("integer"),
    "start_time": {"type": "integer"},
    "end_time": {"type": "integer"},
    "oversized": {"type": "boolean"},
    "status": {"type": "string"},
    "stage": nullable_schema("string"),
    "attempts": {"type": "integer", "minimum": 0},
    "celery_task_id": nullable_schema("string"),
    "estimated_rows": nullable_schema("integer"),
    "actual_rows": nullable_schema("integer"),
    "actual_bytes": nullable_schema("integer"),
    "compressed_bytes": nullable_schema("integer"),
    "artifact_present": {"type": "boolean"},
    "started_at": nullable_schema("string"),
    "finished_at": nullable_schema("string"),
    "updated_at": nullable_schema("string"),
    "error_code": nullable_schema("string"),
    "error_detail": nullable_schema("string"),
}
ARTIFACT_SCHEMA = object_schema(
    "present",
    "bytes",
    "checksum_present",
    properties={
        "present": {"type": "boolean"},
        "bytes": nullable_schema("integer"),
        "checksum_present": {"type": "boolean"},
    },
)
ATTEMPT_LIFECYCLE_SCHEMA = object_schema(
    "enqueued_at",
    "started_at",
    "attempts",
    properties={
        "enqueued_at": nullable_schema("string"),
        "started_at": nullable_schema("string"),
        "attempts": {"type": "integer", "minimum": 0},
    },
)
COUNT_MAP_SCHEMA = {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}}
DETAIL_RESPONSE_PROPERTIES = {
    **JOB_IDENTITY_PROPERTIES,
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
    "query_range": object_schema(
        "start_time",
        "end_time",
        properties={"start_time": {"type": "integer"}, "end_time": {"type": "integer"}},
    ),
    "policy": object_schema(
        "value",
        "truncated",
        properties={
            "value": {},
            "truncated": {"type": "boolean"},
            "original_size_bytes": {"type": "integer", "minimum": 0},
            "returned_size_bytes": {"type": "integer", "minimum": 0},
        },
    ),
    "plan": object_schema(
        "plan_version",
        "plan_count",
        "current",
        properties={
            "plan_version": {"type": "integer", "minimum": 0},
            "plan_count": {"type": "integer", "minimum": 0},
            "current": {
                "anyOf": [
                    object_schema(
                        "status",
                        "planned_parts",
                        "total_rows",
                        "target_rows",
                        "target_bytes",
                        "avg_row_bytes",
                        "initial_interval_ms",
                        "started_at",
                        "finished_at",
                        properties={
                            "status": {"type": "string"},
                            "planned_parts": nullable_schema("integer"),
                            "total_rows": nullable_schema("integer"),
                            "target_rows": nullable_schema("integer"),
                            "target_bytes": nullable_schema("integer"),
                            "avg_row_bytes": nullable_schema("integer"),
                            "initial_interval_ms": nullable_schema("integer"),
                            "started_at": nullable_schema("string"),
                            "finished_at": nullable_schema("string"),
                        },
                    ),
                    {"type": "null"},
                ]
            },
        },
    ),
    "progress": object_schema(
        *PROGRESS_SUMMARY_PROPERTIES,
        "status_counts",
        "stage_counts",
        "leaf_rows",
        properties={
            **PROGRESS_SUMMARY_PROPERTIES,
            "status_counts": COUNT_MAP_SCHEMA,
            "stage_counts": COUNT_MAP_SCHEMA,
            "leaf_rows": {"type": "integer", "minimum": 0},
        },
    ),
    "parts": object_schema(
        "items",
        "total",
        "returned_count",
        "truncated",
        "ordering",
        properties={
            "items": {"type": "array", "items": object_schema(*PART_ITEM_PROPERTIES, properties=PART_ITEM_PROPERTIES)},
            "total": {"type": "integer", "minimum": 0},
            "returned_count": {"type": "integer", "minimum": 0},
            "truncated": {"type": "boolean"},
            "ordering": {"type": "string"},
        },
    ),
    "times": object_schema(
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "last_dispatched_at",
        "duration_ms",
        properties={
            "created_at": nullable_schema("string"),
            "updated_at": nullable_schema("string"),
            "started_at": nullable_schema("string"),
            "completed_at": nullable_schema("string"),
            "last_dispatched_at": nullable_schema("string"),
            "duration_ms": nullable_schema("number"),
        },
    ),
    "lifecycle": object_schema(
        "planning",
        "finalization",
        "notification",
        properties={
            "planning": ATTEMPT_LIFECYCLE_SCHEMA,
            "finalization": ATTEMPT_LIFECYCLE_SCHEMA,
            "notification": object_schema(
                "enqueued_at",
                "notify_at",
                properties={"enqueued_at": nullable_schema("string"), "notify_at": nullable_schema("string")},
            ),
        },
    ),
    "failure": object_schema(
        "error_code",
        "error_label",
        "error_detail",
        properties={
            "error_code": nullable_schema("string"),
            "error_label": nullable_schema("string"),
            "error_detail": nullable_schema("string"),
        },
    ),
    "artifact": object_schema(
        "merged",
        "manifest",
        "expires_at",
        "expired",
        properties={
            "merged": ARTIFACT_SCHEMA,
            "manifest": ARTIFACT_SCHEMA,
            "expires_at": nullable_schema("string"),
            "expired": nullable_schema("boolean"),
        },
    ),
    "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
    "evidence_scope": {"type": "string", "const": "db_only"},
}
DETAIL_RESPONSE_SCHEMA = object_schema(*DETAIL_RESPONSE_PROPERTIES, properties=DETAIL_RESPONSE_PROPERTIES)


FUNCTIONS = {
    LIST_FUNC_NAME: {
        "func_name": LIST_FUNC_NAME,
        "description": (
            "Discover sharded async export jobs (ExportJob) through bounded read-only filters; "
            "legacy AsyncTask exports stay in bklog.async_export.list."
        ),
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "minimum": 1},
                "bk_biz_id": {"type": "integer"},
                "space_uid": {"type": "string", "maxLength": 256},
                "index_set_id": {"type": "integer", "minimum": 1},
                "index_set_ids": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1},
                    "minItems": 1,
                    "maxItems": MAX_TARGET_INDEX_SET_IDS,
                },
                "created_by": {"type": "string", "maxLength": 64},
                "source_app_code": {"type": "string", "maxLength": 32},
                "status": {"type": "string", "enum": JOB_STATUSES},
                "search_type": {"type": "string", "enum": [ExportSearchType.INDEX_SET, ExportSearchType.SCENE]},
                "created_from": {"type": "string", "maxLength": 64},
                "created_to": {"type": "string", "maxLength": 64},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE},
                "ordering": {"type": "string", "maxLength": 32},
            },
            "additionalProperties": False,
        },
        "response_schema": LIST_RESPONSE_SCHEMA,
        "examples": [{"params": {"bk_biz_id": 2, "status": ExportJobStatus.FAILED, "page": 1}}],
    },
    DETAIL_FUNC_NAME: {
        "func_name": DETAIL_FUNC_NAME,
        "description": (
            "Inspect a sharded async export job: plan, part progress, bounded part details, failure and "
            "artifact completeness from the database without downloading or probing object storage."
        ),
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "minimum": 1},
                "part_status": {
                    "type": "array",
                    "items": {"type": "string", "enum": PART_STATUSES},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "part_limit": {"type": "integer", "minimum": 1, "maximum": MAX_PART_LIMIT},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
        "response_schema": DETAIL_RESPONSE_SCHEMA,
        "examples": [{"params": {"job_id": 10001, "part_status": [ExportPartStatus.FAILED], "part_limit": 20}}],
    },
}

HANDLERS = {
    LIST_FUNC_NAME: list_sharded_export_jobs,
    DETAIL_FUNC_NAME: get_sharded_export_job_detail,
}
