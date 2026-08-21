import hashlib
import json
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from bkmonitor.nodeman_integration.readiness import (
    DELIVERY_SCOPE_CAPABILITIES,
    IMPLEMENTED_WORK_PACKAGES,
    REQUIRED_WORK_PACKAGES,
    build_process_contract,
    build_readiness_report,
)


def _settings(**overrides):
    values = {
        "ROLE": "web",
        "VERSION": "1.2.3",
        "BKNODEMAN_API_BASE_URL": "https://nodeman.invalid",
        "NODEMAN_INTEGRATION_DEPLOYMENT_ID": "deployment-a",
        "NODEMAN_INTEGRATION_PROCESS_ID": "web-0",
        "NODEMAN_INTEGRATION_PROCESS_ROLE": "web",
        "NODEMAN_V3_DELIVERY_SCOPE": "prepublished_release",
        "NODEMAN_V3_CONFIRMED_CAPABILITIES": tuple(sorted(DELIVERY_SCOPE_CAPABILITIES["prepublished_release"])),
        "NODEMAN_V3_CAPABILITY_EVIDENCE_DIGEST": "a" * 64,
        "NODEMAN_V3_EXPECTED_PROCESS_IDS": ("beat-0", "web-0", "worker-0"),
        "NODEMAN_V3_RUNTIME_ATTESTATION_PATH": "",
        "NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _restore_v2_celery_config():
    yield
    from tests.nodeman_v3.test_celery_role_contract import _reload_config

    _reload_config("v2")


def _digest(value):
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _with_contract_digest(contract):
    contract = dict(contract)
    contract.pop("process_contract_digest", None)
    contract["process_contract_digest"] = _digest(contract)
    return contract


def _write_valid_runtime_attestation(tmp_path, settings_obj):
    from tests.nodeman_v3.test_celery_role_contract import _reload_config

    _reload_config("v3_fresh")
    current_contract = build_process_contract(settings_obj=settings_obj, mode="v3_fresh")
    worker_contract = _with_contract_digest(
        {
            **current_contract,
            "process_id": "worker-0",
            "role": "worker",
            "role_checks": {
                "registered_v3_task_names": current_contract["v3_task_names"],
                "all_declared_tasks_registered": True,
            },
            "runtime_attestation_requirements": ["active_worker_celery_queue"],
        }
    )
    beat_contract = _with_contract_digest(
        {
            **current_contract,
            "process_id": "beat-0",
            "role": "beat",
            "role_checks": {
                "declared_v3_beat_names": current_contract["v3_beat_names"],
                "all_beat_entries_use_celery_queue": True,
            },
            "runtime_attestation_requirements": ["unique_active_beat_owner"],
        }
    )
    artifact = {
        "schema_version": 1,
        "issuer": "bk-monitor-release-gate/v1",
        "deployment_id": settings_obj.NODEMAN_INTEGRATION_DEPLOYMENT_ID,
        "build_version": settings_obj.VERSION,
        "replicas": [
            {
                "process_id": "web-0",
                "role": "web",
                "process_contract": current_contract,
                "active_queues": [],
                "beat_owner": False,
            },
            {
                "process_id": "worker-0",
                "role": "worker",
                "process_contract": worker_contract,
                "active_queues": ["celery"],
                "beat_owner": False,
            },
            {
                "process_id": "beat-0",
                "role": "beat",
                "process_contract": beat_contract,
                "active_queues": [],
                "beat_owner": True,
            },
        ],
        "v2_outbound_audit": {
            "call_count": 0,
            "covered_process_ids": ["beat-0", "web-0", "worker-0"],
        },
    }
    path = tmp_path / "nodeman-v3-runtime-attestation.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_PATH = str(path)
    settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST = _digest(artifact)
    return artifact


def test_current_monitor_implementation_fails_closed_until_m5_to_m7_are_complete():
    report = build_readiness_report(settings_obj=_settings(), mode="v3_fresh")

    assert report["ready"] is False
    missing = next(blocker for blocker in report["blockers"] if blocker["code"] == "monitor_work_packages_missing")
    assert missing["missing"] == sorted(REQUIRED_WORK_PACKAGES - IMPLEMENTED_WORK_PACKAGES)
    assert missing["missing"] == ["M5", "M6", "M7"]


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ("prepublished_release", {f"E{index}" for index in range(1, 9)}),
        (
            "self_publish",
            {f"E{index}" for index in range(1, 9)} | {f"K{index}" for index in range(1, 6)},
        ),
        (
            "full_plugin_management",
            {f"E{index}" for index in range(1, 9)} | {f"K{index}" for index in range(1, 9)},
        ),
    ],
)
def test_delivery_scope_requires_the_exact_external_capability_set(scope, expected):
    assert DELIVERY_SCOPE_CAPABILITIES[scope] == expected


def test_readiness_reports_configuration_and_external_capability_blockers():
    report = build_readiness_report(
        settings_obj=_settings(
            BKNODEMAN_API_BASE_URL="",
            NODEMAN_INTEGRATION_DEPLOYMENT_ID="",
            NODEMAN_V3_CONFIRMED_CAPABILITIES=("E1",),
        ),
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    blockers = {blocker["code"]: blocker for blocker in report["blockers"]}
    assert set(blockers) == {
        "deployment_id_missing",
        "nodeman_base_url_missing",
        "external_capabilities_missing",
        "runtime_attestation_digest_invalid",
        "runtime_attestation_path_missing",
    }
    assert blockers["external_capabilities_missing"]["missing"] == [f"E{index}" for index in range(2, 9)]


def test_readiness_can_pass_only_when_monitor_external_and_runtime_contracts_are_complete(tmp_path):
    settings_obj = _settings()
    _write_valid_runtime_attestation(tmp_path, settings_obj)
    report = build_readiness_report(
        settings_obj=settings_obj,
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    assert report["ready"] is True
    assert report["blockers"] == []


def test_readiness_rejects_untraceable_capability_flags_and_unknown_process_identity():
    report = build_readiness_report(
        settings_obj=_settings(
            VERSION="Unknown version",
            NODEMAN_INTEGRATION_PROCESS_ROLE="api",
            NODEMAN_V3_CAPABILITY_EVIDENCE_DIGEST="not-a-digest",
            NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST="not-a-digest",
        ),
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    assert {blocker["code"] for blocker in report["blockers"]} == {
        "process_role_invalid",
        "build_version_missing",
        "external_capability_evidence_digest_invalid",
        "runtime_attestation_digest_invalid",
        "runtime_attestation_path_missing",
    }


def test_runtime_attestation_rejects_an_arbitrary_digest_without_a_trusted_artifact():
    report = build_readiness_report(
        settings_obj=_settings(NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST="b" * 64),
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    assert {blocker["code"] for blocker in report["blockers"]} == {"runtime_attestation_path_missing"}


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda artifact: artifact.update(deployment_id="deployment-b"), "deployment_id_mismatch"),
        (lambda artifact: artifact.update(build_version="9.9.9"), "build_version_mismatch"),
        (
            lambda artifact: artifact["replicas"][1].update(active_queues=[]),
            "worker_queue_missing",
        ),
        (
            lambda artifact: artifact["replicas"][2].update(beat_owner=False),
            "unique_beat_owner_missing",
        ),
        (
            lambda artifact: artifact["v2_outbound_audit"].update(call_count=1),
            "v2_outbound_calls_detected",
        ),
        (
            lambda artifact: artifact["v2_outbound_audit"].update(covered_process_ids=["web-0"]),
            "v2_outbound_audit_coverage_mismatch",
        ),
        (
            lambda artifact: artifact["replicas"][0].update(beat_owner=True),
            "unique_beat_owner_missing",
        ),
        (
            lambda artifact: artifact["replicas"].pop(),
            "replica_set_mismatch",
        ),
    ],
)
def test_runtime_attestation_binds_release_topology_and_observed_runtime(tmp_path, mutate, reason):
    settings_obj = _settings()
    artifact = _write_valid_runtime_attestation(tmp_path, settings_obj)
    mutate(artifact)
    path = tmp_path / "nodeman-v3-runtime-attestation.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST = _digest(artifact)

    report = build_readiness_report(
        settings_obj=settings_obj,
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    blocker = next(item for item in report["blockers"] if item["code"] == "runtime_attestation_invalid")
    assert reason in blocker["reasons"]


def test_runtime_attestation_digest_and_current_process_contract_must_match(tmp_path):
    settings_obj = _settings()
    artifact = _write_valid_runtime_attestation(tmp_path, settings_obj)
    artifact["replicas"][0]["process_contract"]["process_contract_digest"] = "e" * 64
    path = tmp_path / "nodeman-v3-runtime-attestation.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    report = build_readiness_report(
        settings_obj=settings_obj,
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    blockers = {item["code"]: item for item in report["blockers"]}
    assert "runtime_attestation_digest_mismatch" in blockers
    assert "current_process_contract_mismatch" in blockers["runtime_attestation_invalid"]["reasons"]


def test_runtime_attestation_requires_one_integration_config_across_all_replicas(tmp_path):
    settings_obj = _settings()
    artifact = _write_valid_runtime_attestation(tmp_path, settings_obj)
    worker_contract = artifact["replicas"][1]["process_contract"]
    artifact["replicas"][1]["process_contract"] = _with_contract_digest(
        {**worker_contract, "integration_config_digest": "e" * 64}
    )
    path = tmp_path / "nodeman-v3-runtime-attestation.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST = _digest(artifact)

    report = build_readiness_report(
        settings_obj=settings_obj,
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    blocker = next(item for item in report["blockers"] if item["code"] == "runtime_attestation_invalid")
    assert "integration_config_digest_mismatch" in blocker["reasons"]


def test_process_contract_binds_non_secret_integration_configuration():
    first = build_process_contract(settings_obj=_settings(), mode="v2")
    second = build_process_contract(
        settings_obj=_settings(BKNODEMAN_API_BASE_URL="https://other-nodeman.invalid"),
        mode="v2",
    )

    assert first["integration_config_digest"] != second["integration_config_digest"]


def test_malformed_runtime_attestation_fails_closed_without_raising(tmp_path):
    settings_obj = _settings()
    artifact = _write_valid_runtime_attestation(tmp_path, settings_obj)
    artifact["replicas"][0]["process_contract"]["process_contract_digest"] = None
    artifact["replicas"][1]["active_queues"] = None
    artifact["v2_outbound_audit"]["covered_process_ids"] = None
    path = tmp_path / "nodeman-v3-runtime-attestation.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    settings_obj.NODEMAN_V3_RUNTIME_ATTESTATION_DIGEST = _digest(artifact)

    report = build_readiness_report(
        settings_obj=settings_obj,
        mode="v3_fresh",
        implemented_work_packages=REQUIRED_WORK_PACKAGES,
    )

    blocker = next(item for item in report["blockers"] if item["code"] == "runtime_attestation_invalid")
    assert {
        "process_contract_digest_mismatch",
        "worker_queue_missing",
        "v2_outbound_audit_coverage_mismatch",
    }.issubset(blocker["reasons"])


def test_v2_mode_is_not_reported_as_v3_ready():
    report = build_readiness_report(settings_obj=_settings(), mode="v2")

    assert report["ready"] is False
    assert report["blockers"][0]["code"] == "mode_not_v3_fresh"


def test_process_contract_has_stable_digests_and_no_v3_entries_in_v2():
    first = build_process_contract(settings_obj=_settings(), mode="v2")
    second = build_process_contract(settings_obj=_settings(), mode="v2")

    assert first == second
    assert first["mode"] == "v2"
    assert first["v3_task_names"] == []
    assert first["v3_beat_names"] == []
    assert len(first["v3_task_registry_digest"]) == 64
    assert len(first["beat_schedule_digest"]) == 64
    assert len(first["process_contract_digest"]) == 64


def test_v3_process_contract_contains_all_declared_tasks_and_beat_entries():
    from tests.nodeman_v3.test_celery_role_contract import _reload_config

    try:
        _reload_config("v3_fresh")
        contract = build_process_contract(
            settings_obj=_settings(
                ROLE="worker",
                NODEMAN_INTEGRATION_PROCESS_ID="worker-0",
                NODEMAN_INTEGRATION_PROCESS_ROLE="worker",
            ),
            mode="v3_fresh",
        )
    finally:
        _reload_config("v2")

    assert contract["v3_task_names"] == [
        "monitor_web.nodeman_integration.v3.tasks.poll_operation",
        "monitor_web.nodeman_integration.v3.tasks.poll_pending_operations",
        "monitor_web.nodeman_integration.v3.tasks.reconcile_active_bindings",
        "monitor_web.nodeman_integration.v3.tasks.reconcile_binding",
    ]
    assert contract["v3_beat_names"] == [
        "nodeman_v3_poll_pending_operations",
        "nodeman_v3_reconcile_active_bindings",
    ]
    assert contract["role_checks"]["all_declared_tasks_registered"] is True
    assert contract["runtime_attestation_requirements"] == ["active_worker_celery_queue"]


def test_dump_process_contract_command_outputs_machine_readable_json(monkeypatch):
    expected = {"role": "worker", "mode": "v3_fresh"}
    monkeypatch.setattr(
        "monitor_web.management.commands.dump_nodeman_v3_process_contract.build_process_contract",
        lambda: expected,
    )
    output = StringIO()

    call_command("dump_nodeman_v3_process_contract", stdout=output)

    assert json.loads(output.getvalue()) == expected


def test_readiness_command_fails_with_blocker_codes(monkeypatch):
    report = {"ready": False, "blockers": [{"code": "monitor_work_packages_missing"}]}
    monkeypatch.setattr(
        "monitor_web.management.commands.check_nodeman_v3_readiness.build_readiness_report",
        lambda: report,
    )
    output = StringIO()

    with pytest.raises(CommandError, match="monitor_work_packages_missing"):
        call_command("check_nodeman_v3_readiness", stdout=output)

    assert json.loads(output.getvalue()) == report
