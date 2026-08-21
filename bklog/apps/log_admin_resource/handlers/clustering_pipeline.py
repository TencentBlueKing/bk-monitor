import time

from django.utils import timezone
from pipeline.engine import states
from pipeline.engine.models import Data, PipelineProcess, ProcessCeleryTask, Status
from pipeline.service import task_service

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import (
    probe_failure,
    probe_skipped,
    reject_identity_params,
    sanitize_json,
)
from apps.log_clustering.models import ClusteringConfig


MAX_PIPELINE_DATA_BYTES = 256 * 1024

PIPELINE_ACTIONS = {
    "retry": {"expected_state": states.FAILED, "method_name": "retry_activity"},
    "skip": {"expected_state": states.FAILED, "method_name": "skip_activity"},
    "force_fail": {"expected_state": states.RUNNING, "method_name": "forced_fail"},
}

PIPELINE_ACTION_STRING_LIMITS = {
    "task_id": 256,
    "node_id": 256,
    "expected_version": 64,
    "reason": 500,
}


def get_clustering_access_pipeline(params):
    params = params or {}
    reject_identity_params(params)
    config_id = params.get("config_id")
    if config_id in (None, ""):
        raise ValidationError("config_id is required")
    try:
        config = ClusteringConfig.objects.get(id=int(config_id))
    except (TypeError, ValueError):
        raise ValidationError("config_id must be an integer")
    except ClusteringConfig.DoesNotExist:
        raise ValidationError(f"config_id does not exist: {config_id}")

    task_records = _serialize_task_records(config.task_records or [])
    task_id = params.get("task_id")
    if task_id in (None, ""):
        task_id = next((record["task_id"] for record in reversed(task_records) if record["task_id"]), None)
    elif not isinstance(task_id, str):
        task_id = str(task_id)

    if not task_id:
        return {
            "config_id": config.id,
            "selected_task_id": None,
            "task_selection": "latest",
            "task_records": task_records,
            "pipeline": probe_skipped("PIPELINE_RECORD_NOT_FOUND", "No access pipeline task has been recorded."),
        }

    started = time.monotonic()
    process = PipelineProcess.objects.filter(root_pipeline_id=task_id, parent_id="").order_by("id").first()
    root_status = Status.objects.filter(id=task_id).first()
    current_status = None
    current_data = None
    celery_task = None
    if process:
        current_status = Status.objects.filter(id=process.current_node_id).first()
        current_data = Data.objects.filter(id=process.current_node_id).first()
        celery_task = ProcessCeleryTask.objects.filter(process_id=process.id).first()

    pipeline_data = {
        "task_id": task_id,
        "root_status": _serialize_status(root_status),
        "process": _serialize_process(process),
        "current_node": {
            "status": _serialize_status(current_status),
            "data": _serialize_data(current_data),
        },
        "celery_task": _serialize_celery_task(celery_task),
        "persistent_task_steps": sanitize_json((config.task_details or {}).get(task_id, [])),
    }
    warnings = []
    if not process and not root_status:
        warnings.append(
            {
                "code": "PIPELINE_ENGINE_ROW_NOT_FOUND",
                "message": "No pipeline engine row was found; persistent task steps are still returned.",
            }
        )
    elif not process:
        warnings.append(
            {
                "code": "PIPELINE_PROCESS_NOT_FOUND",
                "message": "The root status exists but its serial pipeline process row is missing.",
            }
        )
    elif not root_status:
        warnings.append(
            {
                "code": "PIPELINE_ROOT_STATUS_NOT_FOUND",
                "message": "The pipeline process exists but its root status row is missing.",
            }
        )
    if task_id not in {record["task_id"] for record in task_records}:
        warnings.append(
            {
                "code": "PIPELINE_TASK_RECORD_CONFLICT",
                "message": "The selected task is not present in the clustering task history.",
            }
        )
    has_pipeline_evidence = bool(process or root_status or pipeline_data["persistent_task_steps"])
    pipeline_probe = {
        "probe_status": "success" if has_pipeline_evidence else "failed",
        "exists": has_pipeline_evidence,
        "empty": not has_pipeline_evidence,
        "observed_at": timezone.now().isoformat(),
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "data": pipeline_data,
        "error": None,
        "warnings": warnings,
    }
    if not has_pipeline_evidence:
        pipeline_probe["error"] = {
            "code": "PIPELINE_RECORD_NOT_FOUND",
            "message": "No pipeline engine row or persistent task step was found.",
            "upstream_code": None,
            "upstream_message": None,
            "request_id": None,
            "retryable": False,
        }
    return {
        "config_id": config.id,
        "selected_task_id": task_id,
        "task_selection": "explicit" if params.get("task_id") not in (None, "") else "latest",
        "task_records": task_records,
        "pipeline": pipeline_probe,
    }


def retry_clustering_pipeline_node(params):
    return _operate_clustering_pipeline_node(params, "retry")


def skip_clustering_pipeline_node(params):
    return _operate_clustering_pipeline_node(params, "skip")


def force_fail_clustering_pipeline_node(params):
    return _operate_clustering_pipeline_node(params, "force_fail")


def _operate_clustering_pipeline_node(params, action):
    if not isinstance(params, dict):
        raise ValidationError("params must be an object")
    reject_identity_params(params)
    task_id = _require_string(params, "task_id")
    node_id = _require_string(params, "node_id")
    expected_version = _require_string(params, "expected_version")
    reason = _require_string(params, "reason")

    config = _get_clustering_config(params.get("config_id"))
    task_ids = {
        str(record.get("task_id"))
        for record in config.task_records or []
        if isinstance(record, dict) and record.get("task_id")
    }
    if task_id not in task_ids:
        raise ValidationError("task_id does not belong to the clustering configuration")

    try:
        status = Status.objects.get(id=node_id)
    except Status.DoesNotExist:
        raise ValidationError("pipeline node status does not exist")

    try:
        process = PipelineProcess.objects.get(root_pipeline_id=task_id, parent_id="")
    except PipelineProcess.DoesNotExist:
        raise ValidationError("pipeline process does not exist")
    except PipelineProcess.MultipleObjectsReturned:
        raise ValidationError("multiple root pipeline processes exist; operation is blocked")
    if not process.is_alive:
        raise ValidationError("pipeline process is no longer alive")
    if process.is_frozen:
        raise ValidationError("pipeline process is frozen")
    if process.current_node_id != node_id:
        raise ValidationError(
            f"node_id is no longer the current pipeline node: expected {node_id}, actual {process.current_node_id}"
        )
    action_config = PIPELINE_ACTIONS[action]
    expected_state = action_config["expected_state"]
    if status.state != expected_state:
        raise ValidationError(f"pipeline node state changed: expected {expected_state}, actual {status.state}")
    if status.version != expected_version:
        raise ValidationError("pipeline node version changed; refresh the pipeline before operating again")
    if action == "skip" and params.get("acknowledge_external_effects") is not True:
        raise ValidationError("skip requires acknowledge_external_effects=true")

    before = {"status": _serialize_status(status), "process": _serialize_process(process)}
    config_id = config.id
    task_records = _serialize_task_records(config.task_records or [])

    # Pipeline 引擎负责最终的原子状态迁移；这里的版本和当前节点检查用于给管理端返回明确错误。
    action_method = getattr(task_service, action_config["method_name"])
    if action == "force_fail":
        action_result = action_method(node_id, ex_data=f"Admin forced failure: {reason}")
    else:
        action_result = action_method(node_id)
    if not action_result.result:
        raise ValidationError(f"pipeline engine rejected {action}: {action_result.message}")

    try:
        snapshot = get_clustering_access_pipeline({"config_id": config_id, "task_id": task_id})
    except Exception as error:
        snapshot = {
            "config_id": config_id,
            "selected_task_id": task_id,
            "task_selection": "explicit",
            "task_records": task_records,
            "pipeline": probe_failure(error),
        }
    return {
        "action": action,
        "config_id": config_id,
        "task_id": task_id,
        "node_id": node_id,
        "reason": reason,
        "result": True,
        "message": str(action_result.message or ""),
        "before": before,
        "pipeline": snapshot,
    }


def _get_clustering_config(config_id):
    if config_id in (None, ""):
        raise ValidationError("config_id is required")
    if isinstance(config_id, bool) or not isinstance(config_id, int):
        raise ValidationError("config_id must be an integer")
    if config_id < 1:
        raise ValidationError("config_id must be positive")
    try:
        return ClusteringConfig.objects.get(id=config_id)
    except ClusteringConfig.DoesNotExist:
        raise ValidationError(f"config_id does not exist: {config_id}")


def _require_string(params, key):
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key} is required")
    value = value.strip()
    maximum = PIPELINE_ACTION_STRING_LIMITS[key]
    if len(value) > maximum:
        raise ValidationError(f"{key} must not exceed {maximum} characters")
    return value


def _serialize_task_records(records):
    result = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("task_id"):
            result.append(
                {"sequence": index, "task_id": None, "operate": None, "time": None, "raw": sanitize_json(record)}
            )
            continue
        result.append(
            {
                "sequence": index,
                "task_id": str(record["task_id"]),
                "operate": record.get("operate"),
                "time": record.get("time"),
                "raw": sanitize_json(record),
            }
        )
    return result


def _serialize_status(status):
    if not status:
        return None
    return {
        "id": status.id,
        "state": status.state,
        "name": status.name,
        "retry": status.retry,
        "skip": status.skip,
        "error_ignorable": status.error_ignorable,
        "created_time": status.created_time.isoformat() if status.created_time else None,
        "started_time": status.started_time.isoformat() if status.started_time else None,
        "archived_time": status.archived_time.isoformat() if status.archived_time else None,
        "state_refresh_at": status.state_refresh_at.isoformat() if status.state_refresh_at else None,
        "version": status.version,
    }


def _serialize_process(process):
    if not process:
        return None
    return {
        "process_id": process.id,
        "root_pipeline_id": process.root_pipeline_id,
        "current_node_id": process.current_node_id,
        "is_alive": process.is_alive,
        "is_sleep": process.is_sleep,
        "is_frozen": process.is_frozen,
    }


def _serialize_data(data):
    if not data:
        return None
    return {
        "id": data.id,
        "inputs": sanitize_json(data.inputs, max_bytes=MAX_PIPELINE_DATA_BYTES),
        "outputs": sanitize_json(data.outputs, max_bytes=MAX_PIPELINE_DATA_BYTES),
        "ex_data": sanitize_json(data.ex_data, max_bytes=MAX_PIPELINE_DATA_BYTES),
    }


def _serialize_celery_task(task):
    if not task:
        return None
    return {"process_id": task.process_id, "celery_task_id": task.celery_task_id}
