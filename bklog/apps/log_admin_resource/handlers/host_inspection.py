"""Resource Call handlers for bounded Linux host collector inspection."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings

from apps.api import NodeApi
from apps.exceptions import BaseException as BklogBaseException
from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import sanitize_json, scope_biz_queryset
from apps.log_admin_resource.inspection_protocol import (
    INSPECTION_PROBE_SCHEMA,
    INSPECTION_PROBE_SUMMARY_SCHEMA,
    RUNTIME_LOG_OPTIONS_SCHEMA,
    TASK_STATUS_SCHEMA,
)
from apps.log_admin_resource.inspection_tasks import (
    ACTIVE_STATUSES,
    InspectionConcurrencyExceeded,
    ResourceInspectionTaskRecord,
    TASK_TYPE_HOST_INSPECTION,
)
from apps.log_admin_resource.inspection_runtime import normalize_runtime_log_options
from apps.log_admin_resource.response_schema import diagnostic_schema, nullable_schema, object_schema
from apps.log_databus.constants import Environment
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import Space
from apps.utils.local import get_request, get_request_tenant_id


START_FUNC_NAME = "bklog.collector.host_inspection.start"
DETAIL_FUNC_NAME = "bklog.collector.host_inspection.detail"

TARGET_SCHEMA = object_schema(
    "collector_config_id",
    "bk_host_id",
    "bk_biz_id",
    "bk_data_id",
    "subscription_id",
    properties={
        "collector_config_id": {"type": "integer", "minimum": 1},
        "bk_host_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": {"type": "integer", "minimum": 1},
        "bk_data_id": {"type": "integer", "minimum": 1},
        "subscription_id": {"type": "integer", "minimum": 1},
        "source": nullable_schema("string"),
        "include_source_sample": {"type": "boolean"},
    },
)

NEXT_CALL_SCHEMA = object_schema(
    "func_name",
    "params",
    properties={
        "func_name": {"type": "string", "const": DETAIL_FUNC_NAME},
        "params": object_schema(
            "task_id",
            properties={"task_id": {"type": "string", "minLength": 36, "maxLength": 36}},
        ),
    },
)

RESULT_TARGET_SCHEMA = object_schema(
    "collector_config_id",
    "bk_host_id",
    "bk_biz_id",
    "bk_data_id",
    "subscription_id",
    properties={
        "collector_config_id": {"type": "integer", "minimum": 1},
        "bk_host_id": {"type": "integer", "minimum": 1},
        "bk_biz_id": {"type": "integer", "minimum": 1},
        "bk_data_id": {"type": "integer", "minimum": 1},
        "subscription_id": {"type": "integer", "minimum": 1},
    },
)

INSPECTION_EVIDENCE_SCHEMA = object_schema(
    "problem_env",
    "source_env",
    "observed_at",
    "target",
    "remote_execution",
    "probes",
    "partial",
    "error",
    properties={
        "problem_env": {"type": "string"},
        "source_env": {"type": "string"},
        "observed_at": {"type": "string", "format": "date-time"},
        "target": RESULT_TARGET_SCHEMA,
        "remote_execution": object_schema(
            "executor",
            "mode",
            "mutations_permitted",
            properties={
                "executor": {"type": "string", "const": "JOB"},
                "mode": {"type": "string", "const": "server_fixed_read_only_script"},
                "mutations_permitted": {"type": "boolean", "const": False},
            },
        ),
        "probes": {"type": "object", "additionalProperties": INSPECTION_PROBE_SCHEMA},
        "partial": {"type": "boolean"},
        "error": {"anyOf": [diagnostic_schema(), {"type": "null"}]},
    },
)

START_RESPONSE_SCHEMA = object_schema(
    "task_id",
    "task_status",
    "reused",
    "created_at",
    "result_expires_at",
    "next_call",
    properties={
        "task_id": {"type": "string", "minLength": 36, "maxLength": 36},
        "task_status": {
            "type": "string",
            "enum": ["pending", "running", "success", "partial", "failed", "timed_out"],
        },
        "reused": {"type": "boolean"},
        "created_at": {"type": "string", "format": "date-time"},
        "result_expires_at": {"type": "string", "format": "date-time"},
        "next_call": NEXT_CALL_SCHEMA,
    },
)

DETAIL_RESPONSE_SCHEMA = object_schema(
    "task_id",
    "task_type",
    "task_status",
    "phase",
    "target",
    "created_at",
    "started_at",
    "updated_at",
    "finished_at",
    "heartbeat_at",
    "result_expires_at",
    "probes",
    "evidence",
    "partial",
    "error",
    "next_call",
    properties={
        "task_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "task_type": {"type": "string", "const": TASK_TYPE_HOST_INSPECTION},
        "task_status": TASK_STATUS_SCHEMA,
        "phase": {"type": "string"},
        "target": {"anyOf": [TARGET_SCHEMA, {"type": "null"}]},
        "created_at": nullable_schema("string"),
        "started_at": nullable_schema("string"),
        "updated_at": nullable_schema("string"),
        "finished_at": nullable_schema("string"),
        "heartbeat_at": nullable_schema("string"),
        "result_expires_at": nullable_schema("string"),
        "probes": {
            "type": "object",
            "additionalProperties": INSPECTION_PROBE_SUMMARY_SCHEMA,
        },
        "evidence": {"anyOf": [INSPECTION_EVIDENCE_SCHEMA, {"type": "null"}]},
        "partial": {"type": "boolean"},
        "error": {"anyOf": [diagnostic_schema(), {"type": "null"}]},
        "next_call": {"anyOf": [NEXT_CALL_SCHEMA, {"type": "null"}]},
    },
)


def start_host_inspection(params: dict[str, Any]) -> dict[str, Any]:
    collector_config_id = int(params["collector_config_id"])
    bk_host_id = int(params["bk_host_id"])
    app_code, request_tenant_id = _request_identity()
    collector = _get_collector(collector_config_id)
    tenant_id = _validate_collector(collector, request_tenant_id)
    _validate_host_membership(collector, bk_host_id, tenant_id)

    source = (params.get("source") or "").strip() or None
    target = {
        "collector_config_id": collector.collector_config_id,
        "bk_host_id": bk_host_id,
        "bk_biz_id": collector.bk_biz_id,
        "bk_data_id": collector.bk_data_id,
        "subscription_id": collector.subscription_id,
        "source": source,
        "include_source_sample": bool(params.get("include_source_sample", False)),
    }
    runtime_log_options = _runtime_log_options(params.get("runtime_log_options"))
    request_options = {
        "source": source,
        "include_source_sample": target["include_source_sample"],
        "runtime_log_options": runtime_log_options,
    }

    try:
        record, reused = ResourceInspectionTaskRecord.create_or_reuse(
            app_code=app_code,
            bk_tenant_id=tenant_id,
            target=target,
            request_options=request_options,
            task_type=TASK_TYPE_HOST_INSPECTION,
        )
    except InspectionConcurrencyExceeded as error:
        raise BklogBaseException("inspection task concurrency limit reached") from error
    except Exception as error:
        raise BklogBaseException("inspection task storage is unavailable") from error

    if not reused:
        from apps.log_admin_resource.tasks import run_host_inspection

        celery_task_id = str(uuid.uuid4())
        try:
            stored = ResourceInspectionTaskRecord.set_internal_execution_ids(
                record["task_id"], celery_task_id=celery_task_id
            )
            if not stored:
                raise RuntimeError("inspection task metadata disappeared before dispatch")
            run_host_inspection.apply_async(args=[record["task_id"]], task_id=celery_task_id)
        except Exception as error:
            ResourceInspectionTaskRecord.delete_pending(record)
            raise BklogBaseException("inspection task dispatch failed") from error

    current = ResourceInspectionTaskRecord.get(record["task_id"]) or record
    return _start_response(current, reused=reused)


def get_host_inspection_detail(params: dict[str, Any]) -> dict[str, Any]:
    task_id = params["task_id"]
    app_code, tenant_id = _request_identity()
    record = ResourceInspectionTaskRecord.get(task_id)
    if (
        not record
        or record.get("task_type") != TASK_TYPE_HOST_INSPECTION
        or record.get("app_code") != app_code
        or record.get("bk_tenant_id") != tenant_id
    ):
        return _not_found_response(task_id)

    record = ResourceInspectionTaskRecord.normalize_timeout(record)
    task_status = record.get("task_status")
    evidence = None
    error = sanitize_json(record.get("error"), redact_text=True) if record.get("error") else None
    if task_status not in ACTIVE_STATUSES and ResourceInspectionTaskRecord.result_expired(record):
        task_status = "expired"
        error = {"code": "task_expired", "message": "inspection evidence has expired", "retryable": False}
    elif task_status not in ACTIVE_STATUSES:
        evidence = ResourceInspectionTaskRecord.load_result(task_id)

    public_target = {
        key: value
        for key, value in (record.get("target") or {}).items()
        if key
        in {
            "collector_config_id",
            "bk_host_id",
            "bk_biz_id",
            "bk_data_id",
            "subscription_id",
            "source",
            "include_source_sample",
        }
    }
    return {
        "task_id": task_id,
        "task_type": TASK_TYPE_HOST_INSPECTION,
        "task_status": task_status,
        "phase": "expired" if task_status == "expired" else record.get("phase") or "unknown",
        "target": public_target,
        "created_at": record.get("created_at"),
        "started_at": record.get("started_at"),
        "updated_at": record.get("updated_at"),
        "finished_at": record.get("finished_at"),
        "heartbeat_at": record.get("heartbeat_at"),
        "result_expires_at": record.get("result_expires_at"),
        "probes": sanitize_json(record.get("probes") or {}, redact_text=True),
        "evidence": sanitize_json(evidence, redact_text=True) if evidence is not None else None,
        "partial": task_status == "partial" or bool(isinstance(evidence, dict) and evidence.get("partial")),
        "error": error,
        "next_call": _next_call(task_id) if task_status in ACTIVE_STATUSES else None,
    }


def _request_identity() -> tuple[str, str]:
    request = get_request(peaceful=True)
    app_code = getattr(request, "resource_app_code", "") if request else ""
    if not app_code:
        raise BklogPermissionError("host inspection requires a trusted Resource Call app identity")
    tenant_id = get_request_tenant_id()
    if not tenant_id:
        raise BklogPermissionError("host inspection requires a trusted Resource Call tenant")
    return app_code, tenant_id


def _get_collector(collector_config_id: int) -> CollectorConfig:
    collector = scope_biz_queryset(CollectorConfig.objects).filter(collector_config_id=collector_config_id).first()
    if not collector:
        raise ValidationError("collector_config_not_found")
    return collector


def _validate_collector(collector: CollectorConfig, request_tenant_id: str) -> str:
    if not collector.is_active:
        raise ValidationError("collector_config_inactive")
    if collector.environment != Environment.LINUX or collector.is_container_collector:
        raise ValidationError("unsupported_os: only Linux host collectors are supported")
    if not collector.bk_biz_id or not collector.bk_data_id or not collector.subscription_id:
        raise ValidationError("collector_context_incomplete")

    tenant_id = Space.get_tenant_id(bk_biz_id=collector.bk_biz_id, is_need_default=False)
    if not tenant_id:
        if settings.ENABLE_MULTI_TENANT_MODE:
            raise BklogPermissionError("collector tenant is not configured")
        tenant_id = request_tenant_id or settings.BK_APP_TENANT_ID
    if request_tenant_id and tenant_id != request_tenant_id:
        raise BklogPermissionError("collector tenant does not match the current Resource Call tenant")
    return tenant_id


def _validate_host_membership(collector: CollectorConfig, bk_host_id: int, tenant_id: str) -> None:
    rows = NodeApi.query_host_subscriptions(
        params={
            "bk_biz_id": collector.bk_biz_id,
            "bk_host_id": bk_host_id,
            "source_type": "subscription",
        },
        request_cookies=False,
        bk_tenant_id=tenant_id,
    )
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("data") or []
    subscription_ids = {
        int(row["source_id"]) for row in rows or [] if isinstance(row, dict) and str(row.get("source_id", "")).isdigit()
    }
    if collector.subscription_id not in subscription_ids:
        raise ValidationError("host_not_in_collector_subscription")


def _runtime_log_options(value: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_runtime_log_options(value)


def _start_response(record: dict[str, Any], *, reused: bool) -> dict[str, Any]:
    return {
        "task_id": record["task_id"],
        "task_status": record.get("task_status", "pending"),
        "reused": reused,
        "created_at": record["created_at"],
        "result_expires_at": record["result_expires_at"],
        "next_call": _next_call(record["task_id"]),
    }


def _next_call(task_id: str) -> dict[str, Any]:
    return {"func_name": DETAIL_FUNC_NAME, "params": {"task_id": task_id}}


def _not_found_response(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "task_type": TASK_TYPE_HOST_INSPECTION,
        "task_status": "not_found",
        "phase": "not_found",
        "target": None,
        "created_at": None,
        "started_at": None,
        "updated_at": None,
        "finished_at": None,
        "heartbeat_at": None,
        "result_expires_at": None,
        "probes": {},
        "evidence": None,
        "partial": False,
        "error": {"code": "task_not_found", "message": "inspection task was not found", "retryable": False},
        "next_call": None,
    }


FUNCTIONS = {
    START_FUNC_NAME: {
        "func_name": START_FUNC_NAME,
        "description": "Start a bounded asynchronous inspection of one Linux host collector runtime.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "collector_config_id": {"type": "integer", "minimum": 1},
                "bk_host_id": {"type": "integer", "minimum": 1},
                "source": {"type": "string", "minLength": 1, "maxLength": 4096},
                "include_source_sample": {"type": "boolean"},
                "runtime_log_options": RUNTIME_LOG_OPTIONS_SCHEMA,
            },
            "required": ["collector_config_id", "bk_host_id"],
            "additionalProperties": False,
        },
        "response_schema": START_RESPONSE_SCHEMA,
        "examples": [{"params": {"collector_config_id": 123, "bk_host_id": 51985}}],
    },
    DETAIL_FUNC_NAME: {
        "func_name": DETAIL_FUNC_NAME,
        "description": "Read progress or bounded evidence for a Resource-owned host inspection task.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "minLength": 36, "maxLength": 36}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "response_schema": DETAIL_RESPONSE_SCHEMA,
        "examples": [{"params": {"task_id": "94a4c1a8-fb24-49b4-9bfa-b2dc724f07d5"}}],
    },
}

HANDLERS = {START_FUNC_NAME: start_host_inspection, DETAIL_FUNC_NAME: get_host_inspection_detail}
