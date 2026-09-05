import hashlib
import json
import re
from pathlib import Path

from django.conf import settings

from bkmonitor.nodeman_integration.mode import get_nodeman_integration_mode


REQUIRED_WORK_PACKAGES = frozenset({"M1", "M2", "M3", "M4", "M5", "M6", "M7"})
IMPLEMENTED_WORK_PACKAGES = frozenset({"M1", "M2", "M3", "M4"})
DELIVERY_SCOPE_CAPABILITIES = {
    "prepublished_release": {f"E{index}" for index in range(1, 9)},
    "self_publish": {f"E{index}" for index in range(1, 9)} | {f"K{index}" for index in range(1, 6)},
    "full_plugin_management": {f"E{index}" for index in range(1, 9)} | {f"K{index}" for index in range(1, 9)},
}
PROCESS_ROLES = frozenset({"web", "worker", "beat"})
RUNTIME_ATTESTATION_ISSUER = "bk-monitor-release-gate/v1"
EXPECTED_V3_TASK_NAMES = frozenset(
    {
        "monitor_web.nodeman_integration.v3.tasks.poll_operation",
        "monitor_web.nodeman_integration.v3.tasks.poll_pending_operations",
        "monitor_web.nodeman_integration.v3.tasks.reconcile_binding",
    }
)
EXPECTED_V3_BEAT_NAMES = frozenset(
    {
        "nodeman_v3_poll_pending_operations",
    }
)


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _schedule_contract(schedule) -> dict:
    return {
        "type": schedule.__class__.__name__,
        "minute": schedule._orig_minute,
        "hour": schedule._orig_hour,
        "day_of_week": schedule._orig_day_of_week,
        "day_of_month": schedule._orig_day_of_month,
        "month_of_year": schedule._orig_month_of_year,
    }


def _string_set(value) -> set[str] | None:
    if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
        return None
    return set(value)


def build_process_contract(*, settings_obj=settings, mode: str | None = None) -> dict:
    from config.celery.config import Config as CeleryConfig

    mode = mode or get_nodeman_integration_mode()
    route_items = {
        task_name: dict(route)
        for task_name, route in sorted(getattr(CeleryConfig, "task_routes", {}).items())
        if task_name.startswith("monitor_web.nodeman_integration.v3.")
    }
    beat_items = {
        name: {
            "task": item["task"],
            "schedule": _schedule_contract(item["schedule"]),
            "enabled": item.get("enabled"),
            "options": dict(item.get("options", {})),
        }
        for name, item in sorted(CeleryConfig.beat_schedule.items())
        if item["task"].startswith("monitor_web.nodeman_integration.v3.")
    }
    imports = sorted(
        module
        for module in getattr(CeleryConfig, "imports", ())
        if module.startswith("monitor_web.nodeman_integration.v3.")
    )
    role = settings_obj.NODEMAN_INTEGRATION_PROCESS_ROLE
    integration_config_digest = _digest(
        {
            "nodeman_api_base_url": settings_obj.BKNODEMAN_API_BASE_URL,
            "delivery_scope": settings_obj.NODEMAN_V3_DELIVERY_SCOPE,
            "confirmed_capabilities": sorted(
                capability.strip().upper()
                for capability in settings_obj.NODEMAN_V3_CONFIRMED_CAPABILITIES
                if capability.strip()
            ),
            "capability_evidence_digest": settings_obj.NODEMAN_V3_CAPABILITY_EVIDENCE_DIGEST.lower(),
        }
    )
    role_checks = {}
    runtime_requirements = []
    if mode == "v3_fresh" and role == "web":
        from bkmonitor.nodeman_integration.v3.client import NodeManV3HTTPClient

        role_checks["v3_client_importable"] = NodeManV3HTTPClient.API_VERSION == "v3"
        runtime_requirements.append("v2_outbound_unreachable_audit")
    elif mode == "v3_fresh" and role == "worker":
        import importlib

        from celery import current_app

        for module in imports:
            importlib.import_module(module)
        registered = sorted(task_name for task_name in current_app.tasks if task_name in route_items)
        role_checks["registered_v3_task_names"] = registered
        role_checks["all_declared_tasks_registered"] = registered == sorted(route_items)
        runtime_requirements.append("active_worker_celery_queue")
    elif mode == "v3_fresh" and role == "beat":
        role_checks["declared_v3_beat_names"] = sorted(beat_items)
        role_checks["all_beat_entries_use_celery_queue"] = all(
            item["options"].get("queue") == "celery" for item in beat_items.values()
        )
        runtime_requirements.append("unique_active_beat_owner")
    contract = {
        "process_id": settings_obj.NODEMAN_INTEGRATION_PROCESS_ID,
        "role": role,
        "mode": mode,
        "deployment_id": settings_obj.NODEMAN_INTEGRATION_DEPLOYMENT_ID,
        "build_version": settings_obj.VERSION,
        "integration_config_digest": integration_config_digest,
        "contract_scope": "declared_config_plus_local_role_checks",
        "v3_task_names": sorted(route_items),
        "v3_beat_names": sorted(beat_items),
        "v3_task_registry_digest": _digest({"imports": imports, "routes": route_items}),
        "beat_schedule_digest": _digest(beat_items),
        "role_checks": role_checks,
        "runtime_attestation_requirements": runtime_requirements,
    }
    contract["process_contract_digest"] = _digest(contract)
    return contract


def _validate_process_contract(replica: dict, *, deployment_id: str, build_version: str) -> list[str]:
    reasons = []
    contract = replica.get("process_contract")
    if not isinstance(contract, dict):
        return ["process_contract_missing"]

    claimed_digest = contract.get("process_contract_digest", "")
    digest_payload = dict(contract)
    digest_payload.pop("process_contract_digest", None)
    if (
        not isinstance(claimed_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", claimed_digest)
        or claimed_digest != _digest(digest_payload)
    ):
        reasons.append("process_contract_digest_mismatch")
    if not isinstance(replica.get("process_id"), str) or not replica.get("process_id"):
        reasons.append("process_id_invalid")
    if replica.get("role") not in PROCESS_ROLES:
        reasons.append("process_role_invalid")
    if contract.get("process_id") != replica.get("process_id"):
        reasons.append("process_id_mismatch")
    if contract.get("role") != replica.get("role"):
        reasons.append("process_role_mismatch")
    if contract.get("mode") != "v3_fresh":
        reasons.append("process_mode_mismatch")
    if contract.get("deployment_id") != deployment_id:
        reasons.append("process_deployment_id_mismatch")
    if contract.get("build_version") != build_version:
        reasons.append("process_build_version_mismatch")
    if _string_set(contract.get("v3_task_names")) != EXPECTED_V3_TASK_NAMES:
        reasons.append("v3_task_set_mismatch")
    if _string_set(contract.get("v3_beat_names")) != EXPECTED_V3_BEAT_NAMES:
        reasons.append("v3_beat_set_mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("v3_task_registry_digest", ""))):
        reasons.append("task_registry_digest_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("beat_schedule_digest", ""))):
        reasons.append("beat_schedule_digest_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("integration_config_digest", ""))):
        reasons.append("integration_config_digest_invalid")

    role = replica.get("role")
    role_checks = contract.get("role_checks")
    if not isinstance(role_checks, dict):
        reasons.append("role_checks_missing")
    elif role == "web" and role_checks.get("v3_client_importable") is not True:
        reasons.append("web_v3_client_check_failed")
    elif role == "worker":
        if role_checks.get("all_declared_tasks_registered") is not True:
            reasons.append("worker_task_registry_check_failed")
        if _string_set(role_checks.get("registered_v3_task_names")) != EXPECTED_V3_TASK_NAMES:
            reasons.append("worker_registered_task_set_mismatch")
        active_queues = _string_set(replica.get("active_queues"))
        if active_queues is None or "celery" not in active_queues:
            reasons.append("worker_queue_missing")
    elif role == "beat" and role_checks.get("all_beat_entries_use_celery_queue") is not True:
        reasons.append("beat_queue_check_failed")
    return reasons


def _validate_runtime_attestation(settings_obj) -> tuple[list[dict], str]:
    path_value = settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_PATH
    if not path_value:
        return [{"code": "runtime_attestation_path_missing"}], ""

    try:
        artifact = json.loads(Path(path_value).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [{"code": "runtime_attestation_unreadable"}], ""
    if not isinstance(artifact, dict):
        return [{"code": "runtime_attestation_invalid", "reasons": ["artifact_schema_invalid"]}], ""

    observed_digest = _digest(artifact)
    blockers = []
    if observed_digest != settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST.lower():
        blockers.append({"code": "runtime_attestation_digest_mismatch", "observed": observed_digest})

    reasons = []
    if artifact.get("schema_version") != 1:
        reasons.append("schema_version_invalid")
    if artifact.get("issuer") != RUNTIME_ATTESTATION_ISSUER:
        reasons.append("issuer_invalid")
    if artifact.get("deployment_id") != settings_obj.NODEMAN_INTEGRATION_DEPLOYMENT_ID:
        reasons.append("deployment_id_mismatch")
    if artifact.get("build_version") != settings_obj.VERSION:
        reasons.append("build_version_mismatch")

    replicas = artifact.get("replicas")
    if not isinstance(replicas, list) or not all(isinstance(replica, dict) for replica in replicas):
        reasons.append("replicas_schema_invalid")
        replicas = []
    observed_ids = [replica.get("process_id") for replica in replicas]
    expected_ids = set(settings_obj.NODEMAN_V3_EXPECTED_PROCESS_IDS)
    if not expected_ids:
        reasons.append("expected_replica_set_missing")
    observed_id_set = _string_set(observed_ids)
    if observed_id_set is None or len(observed_ids) != len(observed_id_set) or observed_id_set != expected_ids:
        reasons.append("replica_set_mismatch")
    roles = {replica.get("role") for replica in replicas}
    if not PROCESS_ROLES.issubset(roles):
        reasons.append("required_process_roles_missing")

    task_digests = set()
    beat_digests = set()
    integration_config_digests = set()
    for replica in replicas:
        reasons.extend(
            _validate_process_contract(
                replica,
                deployment_id=settings_obj.NODEMAN_INTEGRATION_DEPLOYMENT_ID,
                build_version=settings_obj.VERSION,
            )
        )
        contract = replica.get("process_contract")
        if isinstance(contract, dict):
            task_digests.add(contract.get("v3_task_registry_digest"))
            beat_digests.add(contract.get("beat_schedule_digest"))
            integration_config_digests.add(contract.get("integration_config_digest"))
    if len(task_digests) != 1:
        reasons.append("task_registry_digest_mismatch")
    if len(beat_digests) != 1:
        reasons.append("beat_schedule_digest_mismatch")
    if len(integration_config_digests) != 1:
        reasons.append("integration_config_digest_mismatch")

    beat_owners = [replica for replica in replicas if replica.get("beat_owner") is True]
    if len(beat_owners) != 1 or beat_owners[0].get("role") != "beat":
        reasons.append("unique_beat_owner_missing")

    outbound_audit = artifact.get("v2_outbound_audit")
    if not isinstance(outbound_audit, dict):
        reasons.append("v2_outbound_audit_missing")
    else:
        if outbound_audit.get("call_count") != 0:
            reasons.append("v2_outbound_calls_detected")
        if _string_set(outbound_audit.get("covered_process_ids")) != expected_ids:
            reasons.append("v2_outbound_audit_coverage_mismatch")

    current_process_id = settings_obj.NODEMAN_INTEGRATION_PROCESS_ID
    current_replicas = [replica for replica in replicas if replica.get("process_id") == current_process_id]
    if len(current_replicas) != 1:
        reasons.append("current_process_missing")
    else:
        current_contract = build_process_contract(settings_obj=settings_obj, mode="v3_fresh")
        if current_replicas[0].get("process_contract") != current_contract:
            reasons.append("current_process_contract_mismatch")

    if reasons:
        blockers.append({"code": "runtime_attestation_invalid", "reasons": sorted(set(reasons))})
    return blockers, observed_digest


def build_readiness_report(
    *,
    settings_obj=settings,
    mode: str | None = None,
    implemented_work_packages=IMPLEMENTED_WORK_PACKAGES,
) -> dict:
    mode = mode or get_nodeman_integration_mode()
    scope = settings_obj.NODEMAN_V3_DELIVERY_SCOPE
    confirmed = {
        capability.strip().upper()
        for capability in settings_obj.NODEMAN_V3_CONFIRMED_CAPABILITIES
        if capability.strip()
    }
    blockers = []
    if mode != "v3_fresh":
        blockers.append({"code": "mode_not_v3_fresh", "actual": mode})
    if not settings_obj.NODEMAN_INTEGRATION_DEPLOYMENT_ID:
        blockers.append({"code": "deployment_id_missing"})
    if settings_obj.NODEMAN_INTEGRATION_PROCESS_ROLE not in PROCESS_ROLES:
        blockers.append(
            {
                "code": "process_role_invalid",
                "actual": settings_obj.NODEMAN_INTEGRATION_PROCESS_ROLE,
                "allowed": sorted(PROCESS_ROLES),
            }
        )
    if not settings_obj.VERSION or settings_obj.VERSION == "Unknown version":
        blockers.append({"code": "build_version_missing"})
    if not settings_obj.BKNODEMAN_API_BASE_URL:
        blockers.append({"code": "nodeman_base_url_missing"})

    missing_work_packages = sorted(REQUIRED_WORK_PACKAGES - set(implemented_work_packages))
    if missing_work_packages:
        blockers.append({"code": "monitor_work_packages_missing", "missing": missing_work_packages})

    required_capabilities = DELIVERY_SCOPE_CAPABILITIES.get(scope)
    if required_capabilities is None:
        blockers.append(
            {
                "code": "delivery_scope_invalid",
                "actual": scope,
                "allowed": sorted(DELIVERY_SCOPE_CAPABILITIES),
            }
        )
        required_capabilities = set()
    missing_capabilities = sorted(required_capabilities - confirmed)
    if missing_capabilities:
        blockers.append({"code": "external_capabilities_missing", "missing": missing_capabilities})
    evidence_digest = settings_obj.NODEMAN_V3_CAPABILITY_EVIDENCE_DIGEST.lower()
    if required_capabilities and not re.fullmatch(r"[0-9a-f]{64}", evidence_digest):
        blockers.append({"code": "external_capability_evidence_digest_invalid"})
    runtime_attestation_digest = settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST.lower()
    runtime_attestation_observed_digest = ""
    if mode == "v3_fresh" and not re.fullmatch(r"[0-9a-f]{64}", runtime_attestation_digest):
        blockers.append({"code": "runtime_attestation_digest_invalid"})
    if mode == "v3_fresh":
        runtime_blockers, runtime_attestation_observed_digest = _validate_runtime_attestation(settings_obj)
        blockers.extend(runtime_blockers)

    return {
        "ready": not blockers,
        "mode": mode,
        "delivery_scope": scope,
        "implemented_work_packages": sorted(implemented_work_packages),
        "confirmed_external_capabilities": sorted(confirmed),
        "external_capability_evidence_digest": evidence_digest,
        "runtime_attestation_digest": runtime_attestation_digest,
        "runtime_attestation_observed_digest": runtime_attestation_observed_digest,
        "blockers": blockers,
    }
