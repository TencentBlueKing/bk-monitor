"""Resource Call handlers for bounded Kubernetes collector inspection."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings

from apps.api import TransferApi
from apps.exceptions import BaseException as BklogBaseException
from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.inspection_protocol import (
    INSPECTION_PROBE_SCHEMA,
    INSPECTION_PROBE_SUMMARY_SCHEMA,
    RUNTIME_LOG_OPTIONS_SCHEMA,
    TASK_STATUS_SCHEMA,
)
from apps.log_admin_resource.handlers.inspection import sanitize_json, scope_biz_queryset
from apps.log_admin_resource.inspection_runtime import normalize_runtime_log_options
from apps.log_admin_resource.inspection_tasks import (
    ACTIVE_STATUSES,
    InspectionConcurrencyExceeded,
    TASK_TYPE_K8S_INSPECTION,
    K8sCollectorCandidateStore,
    ResourceInspectionTaskRecord,
)
from apps.log_admin_resource.k8s_inspection import (
    discover_inspection_targets,
    safe_spec_projection,
    expected_bklog_configs,
    target_identity,
)
from apps.log_admin_resource.k8s_cluster_context import ClusterInspectionContext, load_cluster_context
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient
from apps.log_admin_resource.response_schema import diagnostic_schema, nullable_schema, object_schema
from apps.log_bcs.handlers.bcs_handler import BcsHandler
from apps.log_databus.constants import ContainerCollectorType
from apps.log_databus.models import CollectorConfig, ContainerCollectorConfig
from apps.log_search.models import Space
from apps.utils.local import get_request, get_request_tenant_id


START_FUNC_NAME = "bklog.collector.k8s_inspection.start"
DETAIL_FUNC_NAME = "bklog.collector.k8s_inspection.detail"
CONFIG_LIST_FUNC_NAME = "bklog.collector.k8s_inspection.configs"
TARGET_LIST_FUNC_NAME = "bklog.collector.k8s_inspection.targets"
EVIDENCE_GROUPS = ("control_plane", "sidecar", "collector", "progress")
DEFAULT_TARGET_LIMIT = 50
MAX_TARGET_LIMIT = 100
TARGET_SCAN_PAGE_SIZE = 500
MAX_SCANNED_TARGET_OBJECTS = 5000


logger = logging.getLogger(__name__)


POD_TARGET_SCHEMA = object_schema(
    "type",
    "namespace",
    "pod_name",
    "container_name",
    properties={
        "type": {"type": "string", "const": "pod_container"},
        "namespace": {"type": "string", "minLength": 1, "maxLength": 253},
        "pod_name": {"type": "string", "minLength": 1, "maxLength": 253},
        "container_name": {"type": "string", "minLength": 1, "maxLength": 253},
    },
    additional_properties=False,
)
NODE_TARGET_SCHEMA = object_schema(
    "type",
    "node_name",
    properties={
        "type": {"type": "string", "const": "node"},
        "node_name": {"type": "string", "minLength": 1, "maxLength": 253},
    },
    additional_properties=False,
)
TARGET_SCHEMA = {"oneOf": [POD_TARGET_SCHEMA, NODE_TARGET_SCHEMA]}

POD_TARGET_ITEM_SCHEMA = object_schema(
    "target",
    "pod_uid",
    "node_name",
    "phase",
    "ready",
    "workload_type",
    "workload_name",
    "matched_container_config_ids",
    properties={
        "target": POD_TARGET_SCHEMA,
        "pod_uid": nullable_schema("string"),
        "node_name": nullable_schema("string"),
        "phase": nullable_schema("string"),
        "ready": nullable_schema("boolean"),
        "workload_type": nullable_schema("string"),
        "workload_name": nullable_schema("string"),
        "matched_container_config_ids": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
        },
    },
)
NODE_TARGET_ITEM_SCHEMA = object_schema(
    "target",
    "node_uid",
    "ready",
    "matched_container_config_ids",
    properties={
        "target": NODE_TARGET_SCHEMA,
        "node_uid": nullable_schema("string"),
        "ready": nullable_schema("boolean"),
        "matched_container_config_ids": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
        },
    },
)
TARGET_LIST_RESPONSE_SCHEMA = object_schema(
    "collector_config_id",
    "bk_biz_id",
    "bk_data_id",
    "bcs_cluster_id",
    "namespace",
    "limit",
    "container_config_ids",
    "scanned_pod_count",
    "scanned_node_count",
    "pod_scan_truncated",
    "node_scan_truncated",
    "pod_targets",
    "node_targets",
    "pod_target_count",
    "node_target_count",
    "pod_targets_truncated",
    "node_targets_truncated",
    "partial",
    "warnings",
    properties={
        "collector_config_id": nullable_schema("integer"),
        "bk_biz_id": nullable_schema("integer"),
        "bk_data_id": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
        "bcs_cluster_id": {"type": "string", "minLength": 1},
        "namespace": nullable_schema("string"),
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TARGET_LIMIT},
        "container_config_ids": {"type": "array", "items": {"type": "integer", "minimum": 1}},
        "scanned_pod_count": {"type": "integer", "minimum": 0},
        "scanned_node_count": {"type": "integer", "minimum": 0},
        "pod_scan_truncated": {"type": "boolean"},
        "node_scan_truncated": {"type": "boolean"},
        "pod_targets": {"type": "array", "items": POD_TARGET_ITEM_SCHEMA},
        "node_targets": {"type": "array", "items": NODE_TARGET_ITEM_SCHEMA},
        "pod_target_count": {"type": "integer", "minimum": 0},
        "node_target_count": {"type": "integer", "minimum": 0},
        "pod_targets_truncated": {"type": "boolean"},
        "node_targets_truncated": {"type": "boolean"},
        "partial": {"type": "boolean"},
        "warnings": {"type": "array", "items": diagnostic_schema()},
    },
)

NEXT_CALL_SCHEMA = object_schema(
    "func_name",
    "params",
    properties={
        "func_name": {"type": "string", "const": DETAIL_FUNC_NAME},
        "params": object_schema(
            "task_id", properties={"task_id": {"type": "string", "minLength": 36, "maxLength": 36}}
        ),
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
EVIDENCE_SCHEMA = object_schema(
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
        "target": {"type": "object"},
        "remote_execution": object_schema(
            "executor",
            "mode",
            "mutations_permitted",
            properties={
                "executor": {"type": "string", "const": "K8S_API"},
                "mode": {"type": "string", "const": "server_fixed_read_only_probe"},
                "mutations_permitted": {"type": "boolean", "const": False},
            },
        ),
        "probes": {"type": "object", "additionalProperties": INSPECTION_PROBE_SCHEMA},
        "partial": {"type": "boolean"},
        "error": {"anyOf": [diagnostic_schema(), {"type": "null"}]},
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
        "task_type": {"type": "string", "const": TASK_TYPE_K8S_INSPECTION},
        "task_status": TASK_STATUS_SCHEMA,
        "phase": {"type": "string"},
        "target": {"anyOf": [{"type": "object"}, {"type": "null"}]},
        "created_at": nullable_schema("string"),
        "started_at": nullable_schema("string"),
        "updated_at": nullable_schema("string"),
        "finished_at": nullable_schema("string"),
        "heartbeat_at": nullable_schema("string"),
        "result_expires_at": nullable_schema("string"),
        "probes": {"type": "object", "additionalProperties": INSPECTION_PROBE_SUMMARY_SCHEMA},
        "evidence": {"anyOf": [EVIDENCE_SCHEMA, {"type": "null"}]},
        "partial": {"type": "boolean"},
        "error": {"anyOf": [diagnostic_schema(), {"type": "null"}]},
        "next_call": {"anyOf": [NEXT_CALL_SCHEMA, {"type": "null"}]},
    },
)


def list_k8s_inspection_configs(params: dict[str, Any]) -> dict[str, Any]:
    """Discover actual CRs without requiring a SaaS collector or an index set."""
    _request_identity()
    client = K8sInspectionClient(cluster_id=params["bcs_cluster_id"])
    limit = int(params.get("limit") or DEFAULT_TARGET_LIMIT)
    items, next_token = client.list_bklog_config_page(
        params.get("namespace"), limit=limit, continue_token=params.get("continue_token")
    )
    configs = []
    for item in items[:limit]:
        metadata = item.get("metadata") or {}
        configs.append(
            {
                "namespace": metadata.get("namespace"),
                "name": metadata.get("name"),
                "uid": metadata.get("uid"),
                "resource_version": metadata.get("resourceVersion"),
                "bk_env": (metadata.get("labels") or {}).get("bk_env"),
                "spec": safe_spec_projection(item.get("spec") or {}),
            }
        )
    return {
        "bcs_cluster_id": params["bcs_cluster_id"],
        "configs": configs,
        "continue_token": next_token,
        "truncated": bool(next_token) or len(items) > limit,
    }


def _inspection_context(params: dict[str, Any], tenant_id: str):
    if params.get("collector_config_id") is not None:
        if params.get("bklog_config") is not None:
            raise ValidationError("collector_config_id and bklog_config are mutually exclusive")
        collector = _get_collector(int(params["collector_config_id"]))
        return collector, _resolve_collector_identity(collector, tenant_id, params)
    if not params.get("bcs_cluster_id") or not params.get("bklog_config"):
        raise ValidationError("bcs_cluster_id and bklog_config are required without collector_config_id")
    if params.get("bk_data_id") is not None:
        raise ValidationError("cluster inspection derives DataID from the selected BkLogConfig")
    context = load_cluster_context(params["bcs_cluster_id"], params["bklog_config"])
    return context, {
        "tenant_id": tenant_id,
        "bk_biz_id": None,
        "bk_data_id": context.bk_data_id,
        "bcs_cluster_id": context.bcs_cluster_id,
        "bklog_config": context.binding,
    }


def list_k8s_inspection_targets(params: dict[str, Any]) -> dict[str, Any]:
    _, request_tenant_id = _request_identity()
    collector, identity = _inspection_context(params, request_tenant_id)
    namespace = str(params.get("namespace") or "").strip() or None
    if "namespace" in params and namespace is None:
        raise ValidationError("namespace must not be blank")
    limit = int(params.get("limit") or DEFAULT_TARGET_LIMIT)
    if isinstance(collector, ClusterInspectionContext):
        container_configs = []
        expected = collector.expected
    else:
        container_configs = list(
            ContainerCollectorConfig.objects.filter(collector_config_id=collector.collector_config_id).order_by("id")
        )
        expected = expected_bklog_configs(_collector_with_identity(collector, identity), container_configs)
    collector_types = {item["spec"].get("logConfigType") for item in expected}
    client = K8sInspectionClient(cluster_id=identity["bcs_cluster_id"])
    pods = []
    nodes = []
    pod_scan_truncated = False
    node_scan_truncated = False
    warnings = list(identity.get("warnings") or [])
    if collector_types.intersection({ContainerCollectorType.CONTAINER, ContainerCollectorType.STDOUT}):
        try:
            pods, pod_scan_truncated = _collect_bounded_pages(
                lambda *, limit, continue_token: client.list_pod_page(
                    namespace, limit=limit, continue_token=continue_token
                )
            )
        except Exception:
            logger.exception(
                "Resource Kubernetes Pod target discovery failed: collector_config_id=%s namespace=%s",
                collector.collector_config_id,
                namespace,
            )
            warnings.append(
                {
                    "code": "pod_target_discovery_unavailable",
                    "message": "Kubernetes Pod targets could not be listed for this collector configuration",
                    "retryable": True,
                }
            )
        if pod_scan_truncated:
            warnings.append(
                {
                    "code": "pod_target_scan_truncated",
                    "message": "Kubernetes Pod target discovery reached the fixed 5000-object scan limit",
                    "retryable": False,
                }
            )
    if ContainerCollectorType.NODE in collector_types:
        try:
            nodes, node_scan_truncated = _collect_bounded_pages(client.list_node_page)
        except Exception:
            logger.exception(
                "Resource Kubernetes node target discovery failed: collector_config_id=%s",
                collector.collector_config_id,
            )
            warnings.append(
                {
                    "code": "node_target_discovery_unavailable",
                    "message": "Kubernetes node targets could not be listed for this collector configuration",
                    "retryable": True,
                }
            )
        if node_scan_truncated:
            warnings.append(
                {
                    "code": "node_target_scan_truncated",
                    "message": "Kubernetes node target discovery reached the fixed 5000-object scan limit",
                    "retryable": False,
                }
            )
    discovered = discover_inspection_targets(pods=pods, nodes=nodes, expected=expected, limit=limit)
    return {
        "collector_config_id": collector.collector_config_id,
        "bk_biz_id": identity["bk_biz_id"],
        "bk_data_id": identity["bk_data_id"],
        "bcs_cluster_id": identity["bcs_cluster_id"],
        "namespace": namespace,
        "limit": limit,
        "container_config_ids": [item.id for item in container_configs],
        "scanned_pod_count": len(pods),
        "scanned_node_count": len(nodes),
        "pod_scan_truncated": pod_scan_truncated,
        "node_scan_truncated": node_scan_truncated,
        **discovered,
        "partial": bool(warnings),
        "warnings": warnings,
    }


def _collect_bounded_pages(fetch_page) -> tuple[list[Any], bool]:
    items = []
    continue_token = None
    while len(items) < MAX_SCANNED_TARGET_OBJECTS:
        page_limit = min(TARGET_SCAN_PAGE_SIZE, MAX_SCANNED_TARGET_OBJECTS - len(items))
        page, next_token = fetch_page(limit=page_limit, continue_token=continue_token)
        remaining = MAX_SCANNED_TARGET_OBJECTS - len(items)
        items.extend(page[:remaining])
        if len(page) > remaining:
            return items, True
        if not next_token:
            return items, False
        if next_token == continue_token or not page:
            return items, True
        continue_token = next_token
    return items, bool(continue_token)


def start_k8s_inspection(params: dict[str, Any]) -> dict[str, Any]:
    app_code, request_tenant_id = _request_identity()
    collector, identity = _inspection_context(params, request_tenant_id)
    tenant_id = identity["tenant_id"]
    target = _normalize_target(params.get("target"))
    requested_groups = _normalize_groups(params.get("evidence_groups"))
    groups, skipped_groups = _select_runnable_evidence_groups(requested_groups, identity)
    source = (params.get("source") or "").strip() or None
    include_source_sample = bool(params.get("include_source_sample", False))
    if include_source_sample and not source:
        raise ValidationError("include_source_sample requires an explicit source")
    if any(group != "control_plane" for group in groups) and not target:
        raise ValidationError("target is required for sidecar, collector or progress evidence")

    candidate_id = (params.get("collector_candidate_id") or "").strip() or None
    if candidate_id:
        _validate_candidate_binding(
            candidate_id=candidate_id,
            app_code=app_code,
            tenant_id=tenant_id,
            collector=collector,
            target=target,
            identity=identity,
        )

    public_target = {
        "collector_config_id": collector.collector_config_id,
        "bk_biz_id": identity["bk_biz_id"],
        "bk_data_id": identity["bk_data_id"],
        "bcs_cluster_id": identity["bcs_cluster_id"],
        "identity_overrides": identity.get("overrides") or {},
        "observed_object": target,
    }
    if identity.get("bklog_config"):
        public_target["bklog_config"] = identity["bklog_config"]
    request_options = {
        "target": target,
        "evidence_groups": groups,
        "requested_evidence_groups": requested_groups,
        "skipped_evidence_groups": skipped_groups,
        "collector_candidate_id": candidate_id,
        "source": source,
        "include_source_sample": include_source_sample,
        "runtime_log_options": normalize_runtime_log_options(params.get("runtime_log_options")),
        "identity_warnings": identity.get("warnings") or [],
    }
    try:
        record, reused = ResourceInspectionTaskRecord.create_or_reuse(
            app_code=app_code,
            bk_tenant_id=tenant_id,
            target=public_target,
            request_options=request_options,
            task_type=TASK_TYPE_K8S_INSPECTION,
        )
    except InspectionConcurrencyExceeded as error:
        raise BklogBaseException("inspection task concurrency limit reached") from error
    except Exception as error:
        raise BklogBaseException("inspection task storage is unavailable") from error

    if not reused:
        from apps.log_admin_resource.k8s_tasks import run_k8s_inspection

        celery_task_id = str(uuid.uuid4())
        try:
            stored = ResourceInspectionTaskRecord.set_internal_execution_ids(
                record["task_id"], celery_task_id=celery_task_id
            )
            if not stored:
                raise RuntimeError("inspection task metadata disappeared before dispatch")
            run_k8s_inspection.apply_async(args=[record["task_id"]], task_id=celery_task_id)
        except Exception as error:
            ResourceInspectionTaskRecord.delete_pending(record)
            raise BklogBaseException("inspection task dispatch failed") from error

    current = ResourceInspectionTaskRecord.get(record["task_id"]) or record
    return _start_response(current, reused=reused)


def get_k8s_inspection_detail(params: dict[str, Any]) -> dict[str, Any]:
    task_id = params["task_id"]
    app_code, tenant_id = _request_identity()
    record = ResourceInspectionTaskRecord.get(task_id)
    if (
        not record
        or record.get("task_type") != TASK_TYPE_K8S_INSPECTION
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

    return {
        "task_id": task_id,
        "task_type": TASK_TYPE_K8S_INSPECTION,
        "task_status": task_status,
        "phase": "expired" if task_status == "expired" else record.get("phase") or "unknown",
        "target": sanitize_json(record.get("target") or {}, redact_text=True),
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
        raise BklogPermissionError("Kubernetes inspection requires a trusted Resource Call app identity")
    tenant_id = get_request_tenant_id()
    if not tenant_id:
        raise BklogPermissionError("Kubernetes inspection requires a trusted Resource Call tenant")
    return app_code, tenant_id


def _get_collector(collector_config_id: int) -> CollectorConfig:
    collector = scope_biz_queryset(CollectorConfig.objects).filter(collector_config_id=collector_config_id).first()
    if not collector:
        raise ValidationError("collector_config_not_found")
    return collector


def _validate_collector(collector: CollectorConfig, request_tenant_id: str) -> str:
    """Compatibility wrapper for existing tests and call sites."""

    return _resolve_collector_identity(collector, request_tenant_id, {})["tenant_id"]


def _resolve_collector_identity(
    collector: CollectorConfig, request_tenant_id: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    params = params or {}
    if not collector.is_active:
        raise ValidationError("collector_config_inactive")
    if not collector.is_container_collector:
        raise ValidationError("collector_not_k8s")
    if not collector.bk_biz_id:
        raise ValidationError(
            "collector_context_incomplete",
            data={
                "code": "collector_context_incomplete",
                "missing_fields": ["bk_biz_id"],
                "present_fields": {
                    "bk_data_id": collector.bk_data_id or None,
                    "bcs_cluster_id": collector.bcs_cluster_id or None,
                },
                "allowed_overrides": [],
                "runnable_evidence_groups": [],
            },
        )

    tenant_id = Space.get_tenant_id(bk_biz_id=collector.bk_biz_id, is_need_default=False)
    if not tenant_id:
        if settings.ENABLE_MULTI_TENANT_MODE:
            raise BklogPermissionError("collector tenant is not configured")
        tenant_id = request_tenant_id or settings.BK_APP_TENANT_ID
    if request_tenant_id and tenant_id != request_tenant_id:
        raise BklogPermissionError("collector tenant does not match the current Resource Call tenant")

    warnings: list[dict[str, Any]] = []
    overrides: dict[str, Any] = {}
    bcs_cluster_id = str(collector.bcs_cluster_id or "").strip() or None
    bk_data_id = int(collector.bk_data_id) if collector.bk_data_id else None

    override_cluster = str(params.get("bcs_cluster_id") or "").strip() or None
    if override_cluster:
        if bcs_cluster_id and override_cluster != bcs_cluster_id:
            raise ValidationError("cluster_mismatch")
        if not bcs_cluster_id:
            _assert_cluster_visible(collector.bk_biz_id, override_cluster)
            bcs_cluster_id = override_cluster
            overrides["bcs_cluster_id"] = override_cluster
            warnings.append(
                {
                    "code": "bcs_cluster_id_overridden",
                    "message": "collector.bcs_cluster_id was empty; using caller-supplied cluster identity",
                    "retryable": False,
                }
            )
    elif not bcs_cluster_id:
        raise ValidationError(
            "collector_context_incomplete",
            data={
                "code": "collector_context_incomplete",
                "missing_fields": ["bcs_cluster_id"],
                "present_fields": {
                    "bk_biz_id": collector.bk_biz_id,
                    "bk_data_id": bk_data_id,
                },
                "allowed_overrides": ["bcs_cluster_id"],
                "runnable_evidence_groups": [],
                "next_call": {
                    "func_name": START_FUNC_NAME,
                    "params": {
                        "collector_config_id": collector.collector_config_id,
                        "bcs_cluster_id": "<cluster_id_visible_to_business>",
                        "evidence_groups": ["control_plane"],
                    },
                },
            },
        )

    override_data_id = params.get("bk_data_id")
    if override_data_id not in (None, ""):
        try:
            override_data_id = int(override_data_id)
        except (TypeError, ValueError) as error:
            raise ValidationError("bk_data_id must be a positive integer") from error
        if override_data_id <= 0:
            raise ValidationError("bk_data_id must be a positive integer")
        if bk_data_id and override_data_id != bk_data_id:
            raise ValidationError("data_id_mismatch")
        if not bk_data_id:
            _assert_data_id_belongs_to_biz(collector.bk_biz_id, override_data_id)
            bk_data_id = override_data_id
            overrides["bk_data_id"] = override_data_id
            warnings.append(
                {
                    "code": "bk_data_id_overridden",
                    "message": "collector.bk_data_id was empty; using caller-supplied DataID identity",
                    "retryable": False,
                }
            )

    return {
        "tenant_id": tenant_id,
        "bk_biz_id": collector.bk_biz_id,
        "bk_data_id": bk_data_id,
        "bcs_cluster_id": bcs_cluster_id,
        "overrides": overrides,
        "warnings": warnings,
    }


def _select_runnable_evidence_groups(
    requested_groups: list[str], identity: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    skipped = []
    runnable = []
    for group in requested_groups:
        if group == "control_plane":
            runnable.append(group)
            continue
        if not identity.get("bk_data_id"):
            skipped.append(
                {
                    "group": group,
                    "code": "data_id_missing",
                    "message": "sidecar/collector/progress evidence requires a positive bk_data_id",
                }
            )
            continue
        runnable.append(group)
    if not runnable:
        raise ValidationError(
            "collector_context_incomplete",
            data={
                "code": "collector_context_incomplete",
                "missing_fields": ["bk_data_id"],
                "present_fields": {
                    "bk_biz_id": identity.get("bk_biz_id"),
                    "bcs_cluster_id": identity.get("bcs_cluster_id"),
                },
                "allowed_overrides": ["bk_data_id"],
                "runnable_evidence_groups": ["control_plane"],
                "skipped_evidence_groups": skipped,
                "next_call": {
                    "func_name": START_FUNC_NAME,
                    "params": {
                        "collector_config_id": "<collector_config_id>",
                        "evidence_groups": ["control_plane"],
                    },
                },
            },
        )
    return runnable, skipped


def _collector_with_identity(collector: CollectorConfig, identity: dict[str, Any]) -> CollectorConfig:
    """Return a collector object whose runtime identity reflects resolved overrides."""

    if identity.get("bk_data_id") and not collector.bk_data_id:
        collector.bk_data_id = identity["bk_data_id"]
    if identity.get("bcs_cluster_id") and not collector.bcs_cluster_id:
        collector.bcs_cluster_id = identity["bcs_cluster_id"]
    return collector


def _assert_cluster_visible(bk_biz_id: int, cluster_id: str) -> None:
    try:
        clusters = BcsHandler.list_bcs_cluster(bk_biz_id=bk_biz_id)
    except Exception as error:  # pylint: disable=broad-except
        raise ValidationError("cluster_visibility_unavailable") from error
    if not any(str(item.get("cluster_id") or "") == cluster_id for item in clusters):
        raise ValidationError("cluster_not_visible_from_business")


def _assert_data_id_belongs_to_biz(bk_biz_id: int, bk_data_id: int) -> None:
    try:
        data = TransferApi.get_data_id({"bk_data_id": bk_data_id})
    except Exception as error:  # pylint: disable=broad-except
        raise ValidationError("data_id_visibility_unavailable") from error
    data_biz_id = None
    if isinstance(data, dict):
        data_biz_id = data.get("bk_biz_id") or (data.get("data") or {}).get("bk_biz_id")
    try:
        data_biz_id = int(data_biz_id)
    except (TypeError, ValueError):
        data_biz_id = None
    if data_biz_id != int(bk_biz_id):
        raise ValidationError("data_id_not_in_collector_business")


def _validate_candidate_binding(
    *,
    candidate_id: str,
    app_code: str,
    tenant_id: str,
    collector: CollectorConfig,
    target: dict[str, Any] | None,
    identity: dict[str, Any] | None = None,
) -> None:
    binding = K8sCollectorCandidateStore.get(candidate_id)
    identity = identity or {
        "bk_biz_id": collector.bk_biz_id,
        "bk_data_id": collector.bk_data_id,
        "bcs_cluster_id": collector.bcs_cluster_id,
    }
    expected = {
        "app_code": app_code,
        "bk_tenant_id": tenant_id,
        "collector_config_id": collector.collector_config_id,
        "cluster_id": identity["bcs_cluster_id"],
        "target_identity": target_identity(target),
    }
    expected["bklog_config"] = identity.get("bklog_config")
    if not binding or any(binding.get(key) != value for key, value in expected.items()):
        raise ValidationError("collector_candidate_expired_or_unknown")


def _normalize_target(target: dict[str, Any] | None) -> dict[str, Any] | None:
    if not target:
        return None
    if target.get("type") == "node":
        node_name = str(target.get("node_name") or "").strip()
        if not node_name:
            raise ValidationError("node_name is required")
        return {"type": "node", "node_name": node_name}
    if target.get("type") != "pod_container":
        raise ValidationError("unsupported Kubernetes inspection target type")
    result = {
        "type": "pod_container",
        "namespace": str(target.get("namespace") or "").strip(),
        "pod_name": str(target.get("pod_name") or "").strip(),
        "container_name": str(target.get("container_name") or "").strip(),
    }
    if not all(result[key] for key in ("namespace", "pod_name", "container_name")):
        raise ValidationError("namespace, pod_name and container_name are required")
    return result


def _normalize_groups(value: list[str] | None) -> list[str]:
    groups = list(value or ["control_plane"])
    if "all" in groups:
        return list(EVIDENCE_GROUPS)
    unknown = set(groups) - set(EVIDENCE_GROUPS)
    if unknown:
        raise ValidationError(f"unsupported evidence groups: {sorted(unknown)}")
    return sorted(set(groups), key=EVIDENCE_GROUPS.index)


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
        "task_type": TASK_TYPE_K8S_INSPECTION,
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


CONFIG_REFERENCE_SCHEMA = object_schema(
    "namespace",
    "name",
    properties={
        "namespace": {"type": "string", "minLength": 1, "maxLength": 63},
        "name": {"type": "string", "minLength": 1, "maxLength": 253},
    },
    additional_properties=False,
)
INSPECTION_IDENTITY_ALTERNATIVES = [
    {"required": ["collector_config_id"], "not": {"required": ["bklog_config"]}},
    {
        "required": ["bcs_cluster_id", "bklog_config"],
        "not": {"anyOf": [{"required": ["collector_config_id"]}, {"required": ["bk_data_id"]}]},
    },
]
CLUSTER_CONTEXT_NOTES = (
    " Alternatively pass bcs_cluster_id and bklog_config {namespace, name} without collector_config_id. "
    "This mode uses the actual CR DataID and bk_env, with no business ownership lookup. "
    "Execute in the source cluster environment; no cross-environment credential proxy is performed."
)


FUNCTIONS = {
    CONFIG_LIST_FUNC_NAME: {
        "func_name": CONFIG_LIST_FUNC_NAME,
        "description": "Discover actual BkLogConfig resources by cluster ID, without a collector or index set.",
        "notes": "Uses source-environment cluster credentials. Follow continue_token to inspect additional CRs.",
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": object_schema(
            "bcs_cluster_id",
            properties={
                "bcs_cluster_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "namespace": {"type": "string", "minLength": 1, "maxLength": 63},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TARGET_LIMIT},
                "continue_token": {"type": "string", "minLength": 1, "maxLength": 16384},
            },
            additional_properties=False,
        ),
        "response_schema": object_schema(
            "bcs_cluster_id",
            "configs",
            "continue_token",
            "truncated",
            properties={
                "bcs_cluster_id": {"type": "string"},
                "configs": {"type": "array", "items": {"type": "object"}},
                "continue_token": nullable_schema("string"),
                "truncated": {"type": "boolean"},
            },
        ),
        "examples": [{"params": {"bcs_cluster_id": "BCS-K8S-1", "limit": 50}}],
    },
    TARGET_LIST_FUNC_NAME: {
        "func_name": TARGET_LIST_FUNC_NAME,
        "description": "Discover bounded Pod/container and node targets matched by one active Kubernetes collector.",
        "notes": (
            "The optional namespace filters Pod/container targets only; node targets remain cluster-scoped. "
            "When collector.bcs_cluster_id / bk_data_id are empty, callers may supply the same fields "
            "as opt-in identity overrides after tenant-scoped visibility checks."
        )
        + CLUSTER_CONTEXT_NOTES,
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "collector_config_id": {"type": "integer", "minimum": 1},
                "bcs_cluster_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "bk_data_id": {"type": "integer", "minimum": 1},
                "bklog_config": CONFIG_REFERENCE_SCHEMA,
                "namespace": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 63,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TARGET_LIMIT},
            },
            "oneOf": INSPECTION_IDENTITY_ALTERNATIVES,
            "additionalProperties": False,
        },
        "response_schema": TARGET_LIST_RESPONSE_SCHEMA,
        "examples": [
            {"params": {"bcs_cluster_id": "BCS-K8S-1", "bklog_config": {"namespace": "production", "name": "demo"}}},
            {"params": {"collector_config_id": 123, "limit": 50}},
            {"params": {"collector_config_id": 123, "namespace": "production", "limit": 50}},
        ],
    },
    START_FUNC_NAME: {
        "func_name": START_FUNC_NAME,
        "description": "Start a bounded asynchronous inspection of one Kubernetes log collector runtime.",
        "notes": (
            "Missing collector identity returns structured collector_context_incomplete data. "
            "Empty bcs_cluster_id / bk_data_id may be overridden explicitly; deep evidence groups "
            "without DataID are skipped instead of failing the whole task."
        )
        + CLUSTER_CONTEXT_NOTES,
        "safety_level": "inspect",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "collector_config_id": {"type": "integer", "minimum": 1},
                "bcs_cluster_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "bk_data_id": {"type": "integer", "minimum": 1},
                "bklog_config": CONFIG_REFERENCE_SCHEMA,
                "target": TARGET_SCHEMA,
                "collector_candidate_id": {"type": "string", "minLength": 36, "maxLength": 36},
                "evidence_groups": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "uniqueItems": True,
                    "items": {"type": "string", "enum": ["all", *EVIDENCE_GROUPS]},
                },
                "source": {"type": "string", "minLength": 1, "maxLength": 4096},
                "include_source_sample": {"type": "boolean"},
                "runtime_log_options": RUNTIME_LOG_OPTIONS_SCHEMA,
            },
            "oneOf": INSPECTION_IDENTITY_ALTERNATIVES,
            "additionalProperties": False,
        },
        "response_schema": START_RESPONSE_SCHEMA,
        "examples": [
            {
                "params": {
                    "bcs_cluster_id": "BCS-K8S-1",
                    "bklog_config": {"namespace": "production", "name": "demo"},
                    "evidence_groups": ["control_plane"],
                }
            },
            {
                "params": {
                    "collector_config_id": 123,
                    "target": {
                        "type": "pod_container",
                        "namespace": "production",
                        "pod_name": "demo-7d8f9",
                        "container_name": "demo",
                    },
                    "evidence_groups": ["all"],
                }
            },
            {
                "params": {
                    "collector_config_id": 123,
                    "bcs_cluster_id": "BCS-K8S-1",
                    "evidence_groups": ["control_plane"],
                }
            },
        ],
    },
    DETAIL_FUNC_NAME: {
        "func_name": DETAIL_FUNC_NAME,
        "description": "Read progress or bounded evidence for a Resource-owned Kubernetes inspection task.",
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

HANDLERS = {
    CONFIG_LIST_FUNC_NAME: list_k8s_inspection_configs,
    TARGET_LIST_FUNC_NAME: list_k8s_inspection_targets,
    START_FUNC_NAME: start_k8s_inspection,
    DETAIL_FUNC_NAME: get_k8s_inspection_detail,
}
