"""Celery executor for bounded Resource Call host inspections."""

from __future__ import annotations

import base64
import logging
import time
from types import SimpleNamespace
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.api import JobApi, NodeApi
from apps.constants import ScriptType
from apps.exceptions import ValidationError
from apps.log_admin_resource.collector_probe import (
    FixedProbeError,
    fixed_probe_metadata,
    fixed_probe_script,
    parse_and_validate_probe_output,
)
from apps.log_admin_resource.collector_probe_evidence import build_collector_file_log_probe, build_probe_evidence
from apps.log_admin_resource.handlers.host_inspection import _validate_host_membership
from apps.log_admin_resource.handlers.inspection import sanitize_json, sanitize_sensitive_text
from apps.log_admin_resource.inspection_runtime import (
    _merge_context_intervals as _merge_context_intervals,
    apply_runtime_log_filter as _apply_runtime_log_filter,
    filter_runtime_logs as filter_runtime_logs,
)
from apps.log_admin_resource.inspection_tasks import ResourceInspectionTaskRecord, store_bounded_inspection_result
from apps.log_commons.job import JobHelper
from apps.log_databus.constants import DEFAULT_BK_USERNAME, DEFAULT_EXECUTE_SCRIPT_ACCOUNT, JOB_SUCCESS_STATUS
from apps.utils.task import high_priority_task


logger = logging.getLogger(__name__)
JOB_SCRIPT_TIMEOUT_SECONDS = 45
JOB_POLL_INTERVAL_SECONDS = 2


@high_priority_task(ignore_result=True, soft_time_limit=90, time_limit=100)
def run_host_inspection(task_id: str) -> None:
    record = ResourceInspectionTaskRecord.get(task_id)
    if not record:
        return
    record = ResourceInspectionTaskRecord.normalize_timeout(record)
    if not ResourceInspectionTaskRecord.is_active(record):
        ResourceInspectionTaskRecord.release_active(record)
        return
    if not ResourceInspectionTaskRecord.claim_execution(task_id):
        return

    probes: dict[str, dict[str, Any]] = {}
    try:
        started_at = timezone.now().isoformat()
        record = ResourceInspectionTaskRecord.update(
            task_id,
            task_status="running",
            phase="resolving_nodeman",
            started_at=started_at,
            error=None,
        )
        if not record:
            raise RuntimeError("inspection task metadata disappeared before execution")
        nodeman_probe, setup_path = _inspect_nodeman(record)
        probes["nodeman"] = nodeman_probe
        if not ResourceInspectionTaskRecord.set_probe(task_id, "nodeman", nodeman_probe):
            raise RuntimeError("inspection task metadata disappeared after NodeMan probe")
        if nodeman_probe["status"] == "failed" or not setup_path:
            _finish(task_id, record, probes, task_status="failed", error=_task_error("nodeman_unavailable"))
            return
        if ResourceInspectionTaskRecord.remaining_seconds(record) <= 5:
            _finish(task_id, record, probes, task_status="timed_out", error=_task_error("task_timed_out"))
            return

        if not ResourceInspectionTaskRecord.update(task_id, phase="dispatching_read_only_job"):
            raise RuntimeError("inspection task metadata disappeared before JOB dispatch")
        parsed_probe = _run_remote_inspection(record)
        options = record.get("request_options") or {}
        remote_probes = build_probe_evidence(
            parsed_probe,
            bk_data_id=record["target"]["bk_data_id"],
            source=options.get("source"),
            include_source_sample=bool(options.get("include_source_sample")),
            config_map_main=None,
            sidecar_required=False,
        )
        remote_probes["collector_logs"] = build_collector_file_log_probe(parsed_probe, fallback=False)
        for probe in remote_probes.values():
            probe["probe_metadata"] = parsed_probe.get("metadata")
            _complete_probe(probe)
        _apply_runtime_log_filter(remote_probes, (record.get("request_options") or {}).get("runtime_log_options"))
        for name, probe in remote_probes.items():
            if not isinstance(probe, dict):
                continue
            probes[name] = probe
            if not ResourceInspectionTaskRecord.set_probe(task_id, name, probe):
                raise RuntimeError("inspection task metadata disappeared while saving probe summaries")

        task_status = _aggregate_status(probes)
        error = _task_error("no_usable_evidence") if task_status == "failed" else None
        _finish(task_id, record, probes, task_status=task_status, error=error)
    except SoftTimeLimitExceeded:
        _finish(task_id, record, probes, task_status="timed_out", error=_task_error("task_timed_out"))
    except FixedProbeError as error:
        logger.warning("Resource host fixed probe failed, task_id=%s code=%s", task_id, error.code)
        failed_probe = {
            "status": "failed",
            "code": error.code,
            "summary": sanitize_sensitive_text(str(error)),
            "evidence": None,
            "warnings": [],
        }
        _complete_probe(failed_probe)
        probes["collector_probe"] = failed_probe
        ResourceInspectionTaskRecord.set_probe(task_id, "collector_probe", failed_probe)
        _finish(
            task_id,
            record,
            probes,
            task_status="partial" if _has_usable_probe(probes) else "failed",
            error={
                "code": error.code,
                "message": sanitize_sensitive_text(str(error)),
                "retryable": error.retryable,
            },
        )
    except Exception:
        logger.exception("Resource host inspection failed, task_id=%s", task_id)
        task_status = "partial" if _has_usable_probe(probes) else "failed"
        _finish(task_id, record, probes, task_status=task_status, error=_task_error("inspection_execution_failed"))
    finally:
        ResourceInspectionTaskRecord.release_execution(task_id)
        current = ResourceInspectionTaskRecord.get(task_id) or record
        ResourceInspectionTaskRecord.release_active(current)


def _inspect_nodeman(record: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    started_at = timezone.now().isoformat()
    started = time.monotonic()
    target = record["target"]
    try:
        _validate_host_membership(
            SimpleNamespace(
                bk_biz_id=target["bk_biz_id"],
                subscription_id=target["subscription_id"],
            ),
            target["bk_host_id"],
            record["bk_tenant_id"],
        )
    except ValidationError:
        return _probe(
            "failed",
            "host_not_in_collector_subscription",
            "the host no longer belongs to the collector subscription",
            None,
            started_at,
            started,
        ), None
    try:
        raw = NodeApi.plugin_search(
            params={"conditions": [], "bk_host_id": [target["bk_host_id"]], "page": 1, "pagesize": 20},
            request_cookies=False,
            bk_tenant_id=record["bk_tenant_id"],
            timeout=15,
        )
        rows = raw.get("list", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
        rows = [
            row for row in rows if isinstance(row, dict) and str(row.get("bk_host_id")) == str(target["bk_host_id"])
        ]
        setup_paths = sorted({str(row.get("setup_path") or "").rstrip("/") for row in rows if row.get("setup_path")})
        if len(setup_paths) != 1:
            code = "nodeman_host_not_found" if not setup_paths else "multiple_nodeman_setup_paths"
            return _probe(
                "failed", code, "NodeMan did not return one unambiguous setup_path", None, started_at, started
            ), None

        explicit_os_types = {str(row.get("os_type") or "").lower() for row in rows if row.get("os_type")}
        if explicit_os_types and explicit_os_types != {"linux"}:
            return _probe(
                "failed", "unsupported_os", "only Linux host inspection is supported", None, started_at, started
            ), None

        selected = rows[0]
        plugins = []
        for plugin in selected.get("plugin_status", []) or []:
            if isinstance(plugin, dict) and plugin.get("name") == "bkunifylogbeat":
                plugins.append({key: plugin.get(key) for key in ("name", "status", "version")})
        evidence = {
            "bk_host_id": target["bk_host_id"],
            "bk_biz_id": target["bk_biz_id"],
            "subscription_id": target["subscription_id"],
            "agent": {
                key: selected.get(key)
                for key in ("status", "node_from", "bk_agent_id", "bk_host_name", "os_type", "version")
                if selected.get(key) is not None
            },
            "bkunifylogbeat": plugins,
            "setup_path": setup_paths[0],
        }
        subscription_evidence, subscription_warnings = _nodeman_subscription_evidence(record)
        evidence["subscription"] = subscription_evidence
        status = "success" if plugins and plugins[0].get("status") == "RUNNING" else "warning"
        code = "nodeman_resolved" if status == "success" else "collector_plugin_not_running"
        probe = _probe(
            status, code, "NodeMan host and exact plugin environment were resolved", evidence, started_at, started
        )
        probe["warnings"] = subscription_warnings
        return probe, setup_paths[0]
    except Exception:
        logger.exception("NodeMan evidence failed for Resource host inspection")
        return _probe(
            "failed", "nodeman_query_failed", "NodeMan host evidence is unavailable", None, started_at, started
        ), None


def _nodeman_subscription_evidence(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target = record["target"]
    evidence: dict[str, Any] = {"summary": [], "target_instances": []}
    warnings = []
    try:
        raw_summary = NodeApi.get_subscription_info(
            params={"subscription_id_list": [target["subscription_id"]], "bk_biz_id": target["bk_biz_id"]},
            request_cookies=False,
            bk_tenant_id=record["bk_tenant_id"],
            timeout=10,
        )
        rows = (
            raw_summary
            if isinstance(raw_summary, list)
            else raw_summary.get("list", [])
            if isinstance(raw_summary, dict)
            else []
        )
        evidence["summary"] = [
            {key: row.get(key) for key in ("id", "name", "enable", "category", "plugin_name")}
            for row in rows[:5]
            if isinstance(row, dict)
        ]
    except Exception:
        warnings.append(
            {
                "code": "subscription_summary_unavailable",
                "message": "NodeMan subscription summary is unavailable",
                "retryable": True,
            }
        )
    try:
        raw_instances = NodeApi.get_subscription_task_status(
            params={
                "subscription_id": target["subscription_id"],
                "need_detail": False,
                "need_aggregate_all_tasks": True,
                "need_out_of_scope_snapshots": False,
                "page": 1,
                "pagesize": 100,
                "bk_biz_id": target["bk_biz_id"],
            },
            request_cookies=False,
            bk_tenant_id=record["bk_tenant_id"],
            timeout=10,
        )
        rows = (
            raw_instances.get("list", [])
            if isinstance(raw_instances, dict)
            else raw_instances
            if isinstance(raw_instances, list)
            else []
        )
        target_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            host = (
                ((row.get("instance_info") or {}).get("host") or {})
                if isinstance(row.get("instance_info"), dict)
                else {}
            )
            if str(host.get("bk_host_id")) != str(target["bk_host_id"]):
                continue
            target_rows.append(
                {
                    key: row.get(key)
                    for key in ("status", "task_id", "create_time", "update_time", "last_task_id")
                    if row.get(key) is not None
                }
            )
        evidence["target_instances"] = target_rows[:20]
    except Exception:
        warnings.append(
            {
                "code": "subscription_instance_unavailable",
                "message": "NodeMan target deployment status is unavailable",
                "retryable": True,
            }
        )
    return evidence, warnings


def _run_remote_inspection(record: dict[str, Any]) -> dict[str, Any]:
    target = record["target"]
    script_content = base64.b64encode(_fixed_remote_shell_script()).decode("ascii")
    target_server = JobHelper.adapt_hosts_target_server(
        bk_biz_id=target["bk_biz_id"], hosts=[{"bk_host_id": target["bk_host_id"]}]
    )
    execute_result = JobHelper.execute_script(
        script_content=script_content,
        target_server=target_server,
        bk_biz_id=target["bk_biz_id"],
        bk_username=DEFAULT_BK_USERNAME,
        account=DEFAULT_EXECUTE_SCRIPT_ACCOUNT,
        task_name="BKLog read-only host collector inspection",
        script_language=ScriptType.SHELL.value,
        timeout=JOB_SCRIPT_TIMEOUT_SECONDS,
    )
    job_instance_id = int(execute_result.get("job_instance_id") or 0)
    step_instance_id = int(execute_result.get("step_instance_id") or 0)
    if not job_instance_id:
        raise RuntimeError("JOB did not create an inspection instance")
    stored = ResourceInspectionTaskRecord.set_internal_execution_ids(
        record["task_id"], job_instance_id=job_instance_id, job_step_instance_id=step_instance_id or None
    )
    if not stored:
        raise RuntimeError("inspection task metadata disappeared after JOB dispatch")
    if not ResourceInspectionTaskRecord.update(record["task_id"], phase="waiting_read_only_job"):
        raise RuntimeError("inspection task metadata disappeared while waiting for JOB")

    remaining_seconds = ResourceInspectionTaskRecord.remaining_seconds(record)
    deadline = time.monotonic() + min(70, max(1, remaining_seconds - 5))
    ip_results = []
    while time.monotonic() < deadline:
        status = JobApi.get_job_instance_status(
            params={
                "bk_biz_id": target["bk_biz_id"],
                "bk_username": DEFAULT_BK_USERNAME,
                "job_instance_id": job_instance_id,
                "return_ip_result": True,
            },
            request_cookies=False,
            bk_tenant_id=record["bk_tenant_id"],
            timeout=15,
        )
        if not ResourceInspectionTaskRecord.update(record["task_id"], phase="waiting_read_only_job"):
            raise RuntimeError("inspection task metadata disappeared while polling JOB")
        if status.get("finished"):
            steps = status.get("step_instance_list") or []
            selected = next(
                (item for item in steps if not step_instance_id or item.get("step_instance_id") == step_instance_id),
                steps[0] if steps else {},
            )
            step_instance_id = int(selected.get("step_instance_id") or step_instance_id or 0)
            ip_results = selected.get("step_ip_result_list") or []
            break
        time.sleep(JOB_POLL_INTERVAL_SECONDS)
    else:
        raise RuntimeError("read-only JOB inspection timed out")

    if not step_instance_id:
        raise RuntimeError("JOB inspection step is unavailable")
    if ip_results and not any(
        item.get("status") == JOB_SUCCESS_STATUS for item in ip_results if isinstance(item, dict)
    ):
        raise RuntimeError("read-only JOB inspection did not succeed on the target host")

    if not ResourceInspectionTaskRecord.update(record["task_id"], phase="reading_read_only_job_result"):
        raise RuntimeError("inspection task metadata disappeared before reading JOB evidence")
    logs = JobApi.batch_get_job_instance_ip_log(
        params={
            "bk_biz_id": target["bk_biz_id"],
            "host_id_list": [target["bk_host_id"]],
            "job_instance_id": job_instance_id,
            "step_instance_id": step_instance_id,
        },
        request_cookies=False,
        bk_tenant_id=record["bk_tenant_id"],
        timeout=15,
    )
    contents = [
        item.get("log_content", "")
        for item in (logs.get("script_task_logs") or [])
        if isinstance(item, dict) and item.get("log_content")
    ]
    parsed = _parse_remote_result("\n".join(contents))
    parsed["metadata"] = fixed_probe_metadata(executor="JOB", script_language="SHELL")
    return parsed


def _fixed_remote_shell_script() -> bytes:
    return fixed_probe_script()


def _parse_remote_result(value: str) -> dict[str, Any]:
    return parse_and_validate_probe_output(value)


def _finish(
    task_id: str,
    record: dict[str, Any],
    probes: dict[str, dict[str, Any]],
    *,
    task_status: str,
    error: dict[str, Any] | None,
) -> None:
    current = ResourceInspectionTaskRecord.get(task_id) or record
    if ResourceInspectionTaskRecord.is_deadline_exceeded(current):
        task_status = "timed_out"
        error = _task_error("task_timed_out")
    partial = task_status == "partial" or (task_status == "timed_out" and _has_usable_probe(probes))
    result = {
        "problem_env": getattr(settings, "ENVIRONMENT", ""),
        "source_env": getattr(settings, "ENVIRONMENT", ""),
        "observed_at": timezone.now().isoformat(),
        "target": {
            key: value
            for key, value in (current.get("target") or {}).items()
            if key not in {"source", "include_source_sample"}
        },
        "remote_execution": {
            "executor": "JOB",
            "mode": "server_fixed_read_only_script",
            "mutations_permitted": False,
        },
        "probes": sanitize_json(probes, redact_text=True),
        "partial": partial,
        "error": error,
    }
    response_compacted = store_bounded_inspection_result(
        task_id,
        result,
        compaction_probe={
            "status": "warning",
            "code": "response_compacted",
            "summary": "oversized string and list evidence was compacted to preserve a valid final response",
            "evidence": {"maximum_response_bytes": ResourceInspectionTaskRecord.MAX_RESULT_BYTES},
        },
        compaction_error=_task_error("response_compacted"),
    )
    if response_compacted and task_status == "success":
        task_status = "partial"
        error = _task_error("response_compacted")
    finished_at = timezone.now().isoformat()
    ResourceInspectionTaskRecord.update(
        task_id,
        task_status=task_status,
        phase="completed" if task_status in {"success", "partial"} else task_status,
        finished_at=finished_at,
        error=error,
    )


def _aggregate_status(probes: dict[str, dict[str, Any]]) -> str:
    statuses = [probe.get("status") for probe in probes.values() if isinstance(probe, dict)]
    if not any(status in {"success", "warning"} for status in statuses):
        return "failed"
    if any(status == "failed" for status in statuses):
        return "partial"
    return "success"


def _complete_probe(probe: dict[str, Any]) -> None:
    now = timezone.now().isoformat()
    probe.setdefault("started_at", now)
    probe.setdefault("finished_at", now)
    probe.setdefault("duration_ms", 0)


def _has_usable_probe(probes: dict[str, dict[str, Any]]) -> bool:
    return any(probe.get("status") in {"success", "warning"} for probe in probes.values())


def _probe(status: str, code: str, summary: str, evidence: Any, started_at: str, started: float) -> dict[str, Any]:
    return {
        "status": status,
        "code": code,
        "summary": summary,
        "evidence": sanitize_json(evidence, redact_text=True),
        "warnings": [],
        "started_at": started_at,
        "finished_at": timezone.now().isoformat(),
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }


def _task_error(code: str) -> dict[str, Any]:
    messages = {
        "nodeman_unavailable": "NodeMan could not identify one bounded host plugin environment",
        "task_timed_out": "inspection task exceeded its 90 second deadline",
        "no_usable_evidence": "inspection completed without usable evidence",
        "inspection_execution_failed": "inspection execution failed after preserving completed probes",
        "response_compacted": "oversized evidence was compacted to preserve the final response",
    }
    return {
        "code": code,
        "message": sanitize_sensitive_text(messages[code]),
        "retryable": code != "nodeman_unavailable",
    }
