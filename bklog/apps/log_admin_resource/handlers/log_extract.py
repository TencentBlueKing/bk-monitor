from __future__ import annotations

import os
import time
from datetime import datetime

from bkstorages.backends.bkrepo import BKRepoStorage
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pipeline.service import task_service
from qcloud_cos import CosServiceError

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import (
    probe_failure,
    probe_skipped,
    probe_success,
    sanitize_json,
    sanitize_sensitive_text,
)
from apps.log_admin_resource.response_schema import (
    bounded_string_list_schema,
    bounded_value_schema,
    diagnostic_schema,
    nullable_schema,
    object_schema,
    pagination_schema,
    probe_schema,
)
from apps.log_extract.constants import DownloadStatus, PIPELINE_TIME_FORMAT
from apps.log_extract.models import ExtractLink, Tasks
from apps.utils.cos import QcloudCos


MAX_PAGE_SIZE = 100
MAX_HOSTS = 200
MAX_PATHS = 100
MAX_PATH_LENGTH = 1024
MAX_TARGET_BYTES = 128 * 1024
MAX_FILTER_BYTES = 16 * 1024
MAX_FAILURE_REASON = 2000
ORDERING_FIELDS = {"task_id", "created_at", "updated_at", "expiration_date", "download_status"}
PHASES = {
    DownloadStatus.INIT.value: "record_created",
    DownloadStatus.PIPELINE.value: "workflow_submitting",
    DownloadStatus.PACKING.value: "source_packaging",
    DownloadStatus.DISTRIBUTING.value: "transferring",
    DownloadStatus.DISTRIBUTING_PACKING.value: "transferring",
    DownloadStatus.UPLOADING.value: "artifact_uploading",
    DownloadStatus.CSTONE_UPLOADING.value: "artifact_uploading",
    DownloadStatus.COS_UPLOAD.value: "artifact_uploading",
    DownloadStatus.DOWNLOADABLE.value: "completed",
    DownloadStatus.EXPIRED.value: "artifact_expired",
    DownloadStatus.FAILED.value: "failed",
}
TERMINAL_STATUSES = {
    DownloadStatus.DOWNLOADABLE.value,
    DownloadStatus.EXPIRED.value,
    DownloadStatus.FAILED.value,
}


def list_log_extract_tasks(params):
    params = params or {}
    page = _positive_int(params.get("page", 1), "page")
    page_size = _positive_int(params.get("page_size", 20), "page_size", maximum=MAX_PAGE_SIZE)
    queryset = Tasks.objects.all()
    filters = {
        "task_id": "task_id",
        "bk_biz_id": "bk_biz_id",
        "created_by": "created_by",
        "source_app_code": "source_app_code",
        "download_status": "download_status",
        "target_node_type": "target_node_type",
        "link_id": "link_id",
    }
    for param_name, field_name in filters.items():
        if params.get(param_name) not in (None, ""):
            queryset = queryset.filter(**{field_name: params[param_name]})
    if params.get("link_type"):
        link_ids = ExtractLink.objects.filter(link_type=params["link_type"]).values_list("link_id", flat=True)
        queryset = queryset.filter(link_id__in=link_ids)
    if params.get("created_from"):
        queryset = queryset.filter(created_at__gte=_datetime(params["created_from"], "created_from"))
    if params.get("created_to"):
        queryset = queryset.filter(created_at__lte=_datetime(params["created_to"], "created_to"))
    ordering = params.get("ordering") or "-created_at"
    ordering_field = ordering[1:] if ordering.startswith("-") else ordering
    if ordering_field not in ORDERING_FIELDS:
        raise ValidationError(f"unsupported ordering: {ordering}")
    queryset = queryset.order_by(ordering, "-task_id")
    total = queryset.count()
    start = (page - 1) * page_size
    tasks = list(queryset[start : start + page_size])
    link_map = {
        link.link_id: link
        for link in ExtractLink.objects.filter(link_id__in={task.link_id for task in tasks if task.link_id})
    }
    return {
        "items": [_list_item(task, link_map.get(task.link_id)) for task in tasks],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_log_extract_detail(params):
    task = _get_task(params)
    link = ExtractLink.objects.filter(link_id=task.link_id).first() if task.link_id else None
    pipeline = _pipeline_probe(task)
    hosts = _bounded_strings(task.ip_list or [], MAX_HOSTS)
    paths = _bounded_strings(task.file_path or [], MAX_PATHS)
    targets = sanitize_json(task.target_nodes or [], max_bytes=MAX_TARGET_BYTES, redact_text=True)
    filters = sanitize_json(task.filter_content, max_bytes=MAX_FILTER_BYTES, redact_text=True)
    effective_status = _effective_status(task)
    result = {
        "task_id": task.task_id,
        "bk_biz_id": task.bk_biz_id,
        "created_by": task.created_by,
        "source_app_code": task.source_app_code,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "expiration_date": _iso(task.expiration_date),
        "target": {
            "target_node_type": task.target_node_type,
            "hosts": hosts,
            "target_nodes": {
                "value": targets["value"],
                "truncated": targets["truncated"],
                "original_size_bytes": targets["original_size_bytes"],
            },
            "file_paths": paths,
        },
        "filter": {
            "type": task.filter_type,
            "content": {
                "value": filters["value"],
                "truncated": filters["truncated"],
                "original_size_bytes": filters["original_size_bytes"],
            },
        },
        "link": _link_summary(task, link),
        "raw_status": task.download_status,
        "effective_status": effective_status,
        "phase": PHASES.get(effective_status, "unknown"),
        "pipeline_id": task.pipeline_id,
        "job_task_id": task.job_task_id,
        "cos_file_name_present": bool(task.cos_file_name),
        "artifact_reference_present": bool(task.cos_file_name),
        "file_statistics": _file_statistics(task.ex_data),
        "failure_reason": _sanitize_text(task.task_process_info or task.remark),
        "failure_category": "unknown" if task.download_status == DownloadStatus.FAILED.value else None,
        "pipeline": pipeline,
        "consistency_warnings": [],
        "evidence_scope": {
            "database": "available",
            "pipeline": "available" if task.pipeline_id else "mcp_required",
            "artifact": "probe_required" if task.cos_file_name else "unavailable",
            "mcp_required": not bool(task.pipeline_id) or (link and link.link_type == "bk_repo"),
        },
        "mcp_correlation": {
            "task_id": task.task_id,
            "pipeline_id": task.pipeline_id,
            "job_task_id": task.job_task_id,
            "link_type": link.link_type if link else None,
            "created_at": _iso(task.created_at),
            "expiration_date": _iso(task.expiration_date),
        },
    }
    result["consistency_warnings"] = _detail_warnings(task, link, pipeline)
    return result


def probe_log_extract_artifact(params):
    task = _get_task(params)
    link = ExtractLink.objects.filter(link_id=task.link_id).first() if task.link_id else None
    link_type = link.link_type if link else None
    if not task.cos_file_name:
        probe = probe_skipped("ARTIFACT_REFERENCE_MISSING", "task has no persisted artifact reference")
    elif link is None:
        probe = probe_skipped("EXTRACT_LINK_MISSING", "task extract link does not exist")
    elif link_type == "common":
        probe = _probe_local_artifact(task.cos_file_name)
    elif link_type == "qcloud_cos":
        probe = _probe_cos_artifact(link, task.cos_file_name)
    elif link_type == "bk_repo":
        probe = _probe_bkrepo_artifact(task.cos_file_name)
    else:
        probe = probe_skipped("UNSUPPORTED_LINK_TYPE", f"unsupported extract link type: {link_type}")
    warnings = []
    if task.download_status == DownloadStatus.DOWNLOADABLE.value and probe.get("exists") is False:
        warnings.append(
            {"code": "DOWNLOADABLE_ARTIFACT_MISSING", "message": "task is downloadable but artifact does not exist"}
        )
    return {
        "task_id": task.task_id,
        "link_type": link_type,
        "raw_status": task.download_status,
        "artifact": probe,
        "consistency_warnings": warnings,
    }


def _pipeline_probe(task):
    link = ExtractLink.objects.filter(link_id=task.link_id).first() if task.link_id else None
    if not task.pipeline_id:
        if link and link.link_type == "bk_repo":
            return probe_skipped(
                "CELERY_RUNTIME_NOT_PERSISTED",
                "bk_repo execution does not persist a Celery task id; use MCP for queue and worker evidence",
            )
        return probe_skipped("PIPELINE_ID_MISSING", "task has no persisted pipeline_id")
    started = time.monotonic()
    try:
        state = task_service.get_state(task.pipeline_id)
        return probe_success(_project_pipeline_state(state, task.pipeline_components_id), started)
    except Exception as error:
        return probe_failure(error, started)


def _project_pipeline_state(state, component_tree):
    state = state if isinstance(state, dict) else {}
    activity_meta = component_tree.get("activities", {}) if isinstance(component_tree, dict) else {}
    children = state.get("children", {}) if isinstance(state.get("children"), dict) else {}
    components = []
    failed_component_ids = []
    elapsed_seconds = 0
    for component_id, meta in activity_meta.items():
        child = children.get(component_id)
        if not isinstance(child, dict):
            continue
        component_state = child.get("state")
        if component_state == "FAILED":
            failed_component_ids.append(component_id)
        elapsed_seconds += _component_elapsed(child.get("start_time"), child.get("finish_time"))
        components.append(
            {
                "component_id": component_id,
                "name": meta.get("name") if isinstance(meta, dict) else None,
                "state": component_state,
                "start_time": child.get("start_time"),
                "finish_time": child.get("finish_time"),
                "retry_count": child.get("retry_count"),
            }
        )
    return {
        "state": state.get("state"),
        "components": components,
        "failed_component_ids": failed_component_ids,
        "elapsed_seconds": elapsed_seconds,
    }


def _probe_local_artifact(file_name):
    started = time.monotonic()
    try:
        base = os.path.realpath(settings.EXTRACT_SAAS_STORE_DIR)
        target = os.path.realpath(os.path.join(base, file_name))
        if os.path.commonpath([base, target]) != base:
            raise ValidationError("artifact reference escapes the configured extract directory")
        exists = os.path.isfile(target)
        return _artifact_success(exists, os.path.getsize(target) if exists else None, started)
    except Exception as error:
        return probe_failure(error, started)


def _probe_cos_artifact(link, file_name):
    started = time.monotonic()
    try:
        metadata = QcloudCos(
            link.qcloud_secret_id,
            link.qcloud_secret_key,
            link.qcloud_cos_region,
            link.qcloud_cos_bucket,
        ).head_object(file_name)
        size = metadata.get("Content-Length") if isinstance(metadata, dict) else None
        return _artifact_success(True, _optional_int(size), started)
    except CosServiceError as error:
        if error.get_status_code() == 404 or error.get_error_code() in {"NoSuchKey", "NoSuchObject"}:
            return _artifact_success(False, None, started)
        return probe_failure(error, started)
    except Exception as error:
        return probe_failure(error, started)


def _probe_bkrepo_artifact(file_name):
    started = time.monotonic()
    try:
        storage = BKRepoStorage()
        exists = storage.exists(file_name)
        return _artifact_success(exists, storage.size(file_name) if exists else None, started)
    except Exception as error:
        return probe_failure(error, started)


def _artifact_success(exists, size, started):
    probe = probe_success({"size": size}, started)
    probe["exists"] = bool(exists)
    probe["empty"] = not bool(exists)
    return probe


def _detail_warnings(task, link, pipeline):
    warnings = []
    if task.download_status == DownloadStatus.DOWNLOADABLE.value and not task.cos_file_name:
        warnings.append(
            {
                "code": "DOWNLOADABLE_WITHOUT_ARTIFACT_REFERENCE",
                "message": "task is downloadable without an artifact reference",
            }
        )
    if (
        task.download_status == DownloadStatus.DOWNLOADABLE.value
        and task.expiration_date
        and task.expiration_date <= timezone.now()
    ):
        warnings.append(
            {
                "code": "DOWNLOADABLE_PAST_EXPIRATION",
                "message": "task is past expiration but database status is still downloadable",
            }
        )
    pipeline_data = pipeline.get("data") if pipeline.get("probe_status") == "success" else {}
    pipeline_state = pipeline_data.get("state") if isinstance(pipeline_data, dict) else None
    if pipeline_state == "FAILED" and task.download_status not in TERMINAL_STATUSES:
        warnings.append(
            {
                "code": "PIPELINE_FAILED_WITH_NON_TERMINAL_TASK",
                "message": "Pipeline failed while task remains non-terminal",
            }
        )
    if pipeline_state == "FINISHED" and task.download_status not in TERMINAL_STATUSES:
        warnings.append(
            {
                "code": "PIPELINE_FINISHED_WITH_NON_TERMINAL_TASK",
                "message": "Pipeline finished while task remains non-terminal",
            }
        )
    if link and link.link_type != "bk_repo" and not task.pipeline_id:
        warnings.append({"code": "PIPELINE_ID_MISSING", "message": "non-bk_repo task has no pipeline_id"})
    if link and link.link_type == "bk_repo" and not task.pipeline_id:
        warnings.append(
            {"code": "CELERY_RUNTIME_NOT_PERSISTED", "message": "bk_repo task has no persisted Celery runtime id"}
        )
    return warnings


def _list_item(task, link):
    return {
        "task_id": task.task_id,
        "bk_biz_id": task.bk_biz_id,
        "created_by": task.created_by,
        "source_app_code": task.source_app_code,
        "raw_status": task.download_status,
        "phase": PHASES.get(task.download_status, "unknown"),
        "target_node_type": task.target_node_type,
        "host_count": len(task.ip_list or []),
        "file_count": len(task.file_path or []),
        "link_type": link.link_type if link else None,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "expiration_date": _iso(task.expiration_date),
    }


def _link_summary(task, link):
    return {
        "link_id": task.link_id,
        "name": link.name if link else None,
        "link_type": link.link_type if link else None,
        "is_enable": link.is_enable if link else None,
    }


def _file_statistics(ex_data):
    rows = ex_data.values() if isinstance(ex_data, dict) else []
    return {
        "host_count": len(ex_data) if isinstance(ex_data, dict) else 0,
        "file_count": sum(_safe_int(row.get("file_count")) for row in rows if isinstance(row, dict)),
        "original_size": sum(_safe_int(row.get("all_origin_file_size")) for row in rows if isinstance(row, dict)),
        "packed_size": sum(_safe_int(row.get("all_pack_file_size")) for row in rows if isinstance(row, dict)),
    }


def _bounded_strings(values, maximum):
    values = list(values or [])
    selected = [_limited_string(value, MAX_PATH_LENGTH) for value in values[:maximum]]
    return {
        "items": selected,
        "count": len(values),
        "returned_count": len(selected),
        "truncated": len(values) > maximum,
    }


def _effective_status(task):
    if (
        task.download_status == DownloadStatus.DOWNLOADABLE.value
        and task.expiration_date
        and task.expiration_date <= timezone.now()
    ):
        return DownloadStatus.EXPIRED.value
    return task.download_status


def _sanitize_text(value):
    if not value:
        return None
    value = sanitize_sensitive_text(value, maximum=None)
    return _limited_string(value, MAX_FAILURE_REASON)


def _component_elapsed(start_time, finish_time):
    if not start_time or not finish_time:
        return 0
    try:
        return max(
            0,
            int(
                (
                    datetime.strptime(finish_time, PIPELINE_TIME_FORMAT)
                    - datetime.strptime(start_time, PIPELINE_TIME_FORMAT)
                ).total_seconds()
            ),
        )
    except (TypeError, ValueError):
        return 0


def _get_task(params):
    params = params or {}
    task_id = _positive_int(params.get("task_id"), "task_id")
    try:
        return Tasks.objects.get(task_id=task_id)
    except Tasks.DoesNotExist:
        raise ValidationError(f"log extract task does not exist: {task_id}")


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


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _limited_string(value, maximum):
    value = str(value)
    return value if len(value) <= maximum else value[: maximum - 3] + "..."


def _iso(value):
    return value.isoformat() if value else None


LOG_EXTRACT_LIST_ITEM_SCHEMA = object_schema(
    "task_id",
    "bk_biz_id",
    "created_by",
    "source_app_code",
    "raw_status",
    "phase",
    "target_node_type",
    "host_count",
    "file_count",
    "link_type",
    "created_at",
    "updated_at",
    "expiration_date",
    properties={
        "task_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": {"type": "integer"},
        "created_by": {"type": "string"},
        "source_app_code": {"type": "string"},
        "raw_status": nullable_schema("string"),
        "phase": {"type": "string"},
        "target_node_type": {"type": "string"},
        "host_count": {"type": "integer", "minimum": 0},
        "file_count": {"type": "integer", "minimum": 0},
        "link_type": nullable_schema("string"),
        "created_at": nullable_schema("string"),
        "updated_at": nullable_schema("string"),
        "expiration_date": nullable_schema("string"),
    },
)
LOG_EXTRACT_LIST_RESPONSE_SCHEMA = pagination_schema(LOG_EXTRACT_LIST_ITEM_SCHEMA)
LOG_EXTRACT_DETAIL_RESPONSE_SCHEMA = object_schema(
    "task_id",
    "bk_biz_id",
    "created_by",
    "source_app_code",
    "created_at",
    "updated_at",
    "expiration_date",
    "target",
    "filter",
    "link",
    "raw_status",
    "effective_status",
    "phase",
    "pipeline_id",
    "job_task_id",
    "cos_file_name_present",
    "artifact_reference_present",
    "file_statistics",
    "failure_reason",
    "failure_category",
    "pipeline",
    "consistency_warnings",
    "evidence_scope",
    "mcp_correlation",
    properties={
        "task_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": {"type": "integer"},
        "created_by": {"type": "string"},
        "source_app_code": {"type": "string"},
        "created_at": nullable_schema("string"),
        "updated_at": nullable_schema("string"),
        "expiration_date": nullable_schema("string"),
        "target": object_schema(
            "target_node_type",
            "hosts",
            "target_nodes",
            "file_paths",
            properties={
                "target_node_type": {"type": "string"},
                "hosts": bounded_string_list_schema(),
                "target_nodes": bounded_value_schema(),
                "file_paths": bounded_string_list_schema(),
            },
        ),
        "filter": object_schema(
            "type",
            "content",
            properties={
                "type": nullable_schema("string"),
                "content": bounded_value_schema(),
            },
        ),
        "link": object_schema(
            "link_id",
            "name",
            "link_type",
            "is_enable",
            properties={
                "link_id": nullable_schema("integer"),
                "name": nullable_schema("string"),
                "link_type": nullable_schema("string"),
                "is_enable": nullable_schema("boolean"),
            },
        ),
        "raw_status": nullable_schema("string"),
        "effective_status": nullable_schema("string"),
        "phase": {"type": "string"},
        "pipeline_id": nullable_schema("string"),
        "job_task_id": nullable_schema("integer"),
        "cos_file_name_present": {"type": "boolean"},
        "artifact_reference_present": {"type": "boolean"},
        "file_statistics": object_schema(
            "host_count",
            "file_count",
            "original_size",
            "packed_size",
            properties={
                "host_count": {"type": "integer", "minimum": 0},
                "file_count": {"type": "integer", "minimum": 0},
                "original_size": {"type": "integer", "minimum": 0},
                "packed_size": {"type": "integer", "minimum": 0},
            },
        ),
        "failure_reason": nullable_schema("string"),
        "failure_category": nullable_schema("string"),
        "pipeline": probe_schema(),
        "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
        "evidence_scope": object_schema(
            "database",
            "pipeline",
            "artifact",
            "mcp_required",
            properties={
                "database": {"type": "string"},
                "pipeline": {"type": "string"},
                "artifact": {"type": "string"},
                "mcp_required": {"type": "boolean"},
            },
        ),
        "mcp_correlation": object_schema(
            "task_id",
            "pipeline_id",
            "job_task_id",
            "link_type",
            "created_at",
            "expiration_date",
            properties={
                "task_id": {"type": "integer", "minimum": 1},
                "pipeline_id": nullable_schema("string"),
                "job_task_id": nullable_schema("integer"),
                "link_type": nullable_schema("string"),
                "created_at": nullable_schema("string"),
                "expiration_date": nullable_schema("string"),
            },
        ),
    },
)
LOG_EXTRACT_ARTIFACT_RESPONSE_SCHEMA = object_schema(
    "task_id",
    "link_type",
    "raw_status",
    "artifact",
    "consistency_warnings",
    properties={
        "task_id": {"type": "integer", "minimum": 1},
        "link_type": nullable_schema("string"),
        "raw_status": nullable_schema("string"),
        "artifact": probe_schema(),
        "consistency_warnings": {"type": "array", "items": diagnostic_schema()},
    },
)


FUNCTIONS = {
    "bklog.log_extract.list": {
        "func_name": "bklog.log_extract.list",
        "description": "Discover log extract tasks through bounded read-only filters.",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "minimum": 1},
                "bk_biz_id": {"type": "integer"},
                "created_by": {"type": "string", "maxLength": 32},
                "source_app_code": {"type": "string", "maxLength": 32},
                "download_status": {"type": "string", "maxLength": 64},
                "target_node_type": {"type": "string", "maxLength": 64},
                "link_id": {"type": "integer", "minimum": 1},
                "link_type": {"type": "string", "enum": ["common", "qcloud_cos", "bk_repo"]},
                "created_from": {"type": "string", "maxLength": 64},
                "created_to": {"type": "string", "maxLength": 64},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE},
                "ordering": {"type": "string", "maxLength": 32},
            },
            "additionalProperties": False,
        },
        "response_schema": LOG_EXTRACT_LIST_RESPONSE_SCHEMA,
        "examples": [{"params": {"bk_biz_id": 2, "download_status": "failed", "page": 1}}],
    },
    "bklog.log_extract.detail": {
        "func_name": "bklog.log_extract.detail",
        "description": "Inspect persisted extract task, Pipeline and bounded target evidence without polling writes.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer", "minimum": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "response_schema": LOG_EXTRACT_DETAIL_RESPONSE_SCHEMA,
        "examples": [{"params": {"task_id": 10001}}],
    },
    "bklog.log_extract.artifact_probe": {
        "func_name": "bklog.log_extract.artifact_probe",
        "description": "Check local, COS or BKRepo artifact existence without generating URLs or reading content.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer", "minimum": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "response_schema": LOG_EXTRACT_ARTIFACT_RESPONSE_SCHEMA,
        "examples": [{"params": {"task_id": 10001}}],
    },
}

HANDLERS = {
    "bklog.log_extract.list": list_log_extract_tasks,
    "bklog.log_extract.detail": get_log_extract_detail,
    "bklog.log_extract.artifact_probe": probe_log_extract_artifact,
}
