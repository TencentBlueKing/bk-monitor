import copy
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

SOURCE = Path(__file__).resolve().parents[2] / "bkmonitor"
spec = importlib.util.spec_from_file_location(
    "receipt_delivery", SOURCE / "alarm_backends/service/access/incident/delivery.py"
)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
Receipt = apps.get_model("bkmonitor", "IncidentDeliveryReceipt")
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def payload():
    return {
        "notice_source": "bkfara",
        "event_id": "event-1",
        "bk_tenant_id": "tenant-a",
        "scope_id": "bkcc_2",
        "sync_type": "create",
        "incident_id": 1,
        "incident_info": {"scope_id": "bkcc_2", "send_notice": True},
    }


def consume(payload, handler):
    return delivery.consume_once(payload, handler, receipt_model=Receipt)


def diagnosis_payload(payload, status="running"):
    event, operation, task_status = {
        "todo": ("diagnosis.initialized", "diagnosis_pending", None),
        "running": ("diagnosis.requested", "diagnosis_started", "ready"),
        "finished": ("diagnosis.succeeded", "diagnosis_succeeded", "finished"),
        "failed": ("diagnosis.failed", "diagnosis_failed", "failed"),
    }[status]
    payload.update(
        schema_version="1.0",
        sync_type="diagnosis",
        destination="bkfara_internal",
        notification_kind="diagnosis",
        aggregate_revision=1,
        event_id="a" * 64,
        policy_revision="b" * 64,
        event_types=[event],
        operation=operation,
        changes={},
    )
    payload["incident_info"].update(
        create_time=1700000000,
        diagnosis_status=status,
        analysis={"task_id": 17, "task_status": task_status, "execution_backend": "runtime"} if task_status else {},
    )
    return payload


def test_receipt_rejects_outer_transaction_before_any_effect(payload):
    handler = Mock()
    with transaction.atomic(), pytest.raises(RuntimeError, match="independent commit"):
        consume(payload, handler)
    handler.assert_not_called()
    assert not Receipt.objects.exists()


def test_receipt_rejects_manual_transaction_before_any_effect(payload):
    handler = Mock()
    connection.set_autocommit(False)
    try:
        with pytest.raises(RuntimeError, match="independent commit"):
            consume(payload, handler)
    finally:
        connection.rollback()
        connection.set_autocommit(True)
    handler.assert_not_called()
    assert not Receipt.objects.exists()


def test_receipt_reads_stay_on_write_database(payload, monkeypatch):
    # A replica must not decide whether an external effect can run again.
    monkeypatch.setattr(delivery.router, "db_for_read", lambda *a, **kw: "unavailable_replica")
    handler = Mock()
    consume(payload, handler)
    consume(payload, handler)
    assert handler.call_count == 1


def test_success_and_ack_loss_redelivery_are_noops(payload):
    handler = Mock(side_effect=lambda message: message["incident_info"].pop("send_notice"))
    consume(payload, handler)
    consume(payload, handler)
    assert handler.call_count == 1
    assert payload["incident_info"]["send_notice"]
    assert Receipt.objects.get().status == "succeeded"


def test_changed_payload_reusing_id_is_rejected(payload):
    handler = Mock()
    consume(payload, handler)
    payload["incident_id"] = 2
    with pytest.raises(delivery.DeliveryConflict):
        consume(payload, handler)
    assert handler.call_count == 1


@pytest.mark.parametrize("field,value", [("bk_tenant_id", "tenant-b"), ("event_id", "EVENT-1"), ("scope_id", "bkcc_3")])
def test_receipts_do_not_alias_tenants_scopes_or_opaque_ids(payload, field, value):
    handler = Mock()
    consume(payload, handler)
    payload[field] = value
    payload["incident_info"]["scope_id"] = payload["scope_id"]
    consume(payload, handler)
    assert handler.call_count == 2
    assert Receipt.objects.count() == 2


def test_ambiguous_failure_is_never_acknowledged_or_blindly_replayed(payload):
    handler = Mock(side_effect=TimeoutError("remote write outcome unknown"))
    with pytest.raises(delivery.DeliveryUncertain):
        consume(payload, handler)
    with pytest.raises(delivery.DeliveryUncertain):
        consume(payload, handler)
    assert handler.call_count == 1
    assert Receipt.objects.get().status == "uncertain"
    assert Receipt.objects.get().error_type == "TimeoutError"
    assert Receipt.objects.get().payload == payload


def test_crash_after_effect_before_receipt_commit_is_quarantined(payload, monkeypatch):
    original_update = type(Receipt.objects.all()).update

    def fail_completion(queryset, **values):
        if values.get("status") == "succeeded":
            raise ConnectionError("commit acknowledgement lost")
        return original_update(queryset, **values)

    handler = Mock()
    with monkeypatch.context() as patch:
        patch.setattr(type(Receipt.objects.all()), "update", fail_completion)
        with pytest.raises(ConnectionError):
            consume(payload, handler)
    with pytest.raises(delivery.DeliveryBusy):
        consume(payload, handler)
    Receipt.objects.update(started_at=timezone.now() - timedelta(hours=1))
    with pytest.raises(delivery.DeliveryUncertain):
        consume(payload, handler)
    assert handler.call_count == 1
    assert Receipt.objects.get().status == "uncertain"


def test_late_completion_cannot_overwrite_quarantined_outcome(payload):
    def handler(message):
        Receipt.objects.update(started_at=timezone.now() - timedelta(hours=1))
        with pytest.raises(delivery.DeliveryUncertain):
            consume(message, Mock())

    with pytest.raises(delivery.DeliveryUncertain):
        consume(payload, handler)
    assert Receipt.objects.get().status == "uncertain"


@pytest.mark.parametrize(
    "field,value", [("event_id", ""), ("bk_tenant_id", None), ("scope_id", "wrong"), ("sync_type", "other")]
)
def test_invalid_envelope_fails_before_any_effect(payload, field, value):
    payload[field] = value
    handler = Mock()
    with pytest.raises(delivery.DeliveryConflict):
        consume(payload, handler)
    handler.assert_not_called()
    assert not Receipt.objects.exists()


def test_legacy_messages_keep_the_existing_path(payload):
    payload.pop("event_id")
    handler = Mock()
    consume(payload, handler)
    consume(payload, handler)
    assert handler.call_count == 2
    assert not Receipt.objects.exists()


def test_concurrent_redelivery_executes_only_one_handler(payload):
    if connection.vendor != "mysql":
        pytest.skip("row contention requires MySQL")
    started, release = Event(), Event()
    effects = []

    def handler(message):
        effects.append(message["event_id"])
        started.set()
        assert release.wait(10)

    def worker():
        close_old_connections()
        try:
            consume(copy.deepcopy(payload), handler)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(worker)
        try:
            assert started.wait(10)
            with pytest.raises(delivery.DeliveryBusy):
                consume(payload, handler)
        finally:
            release.set()
        pending.result(timeout=10)
    consume(payload, handler)
    assert effects == ["event-1"]


@pytest.mark.parametrize("reference", ["task:17:attempt:1", "task:17:attempt:2:action:incident.lifecycle"])
def test_compact_task_audit_references_do_not_change_message_identity(payload, reference):
    # Producer no longer has result/action tables. Their opaque references remain
    # audit data; only the envelope event ID controls consumer deduplication.
    payload["incident_info"]["analysis_action"] = {"effect_id": reference, "task_id": 17}
    handler = Mock()
    consume(payload, handler)
    consume(copy.deepcopy(payload), handler)
    assert handler.call_count == 1

    assert Receipt.objects.get().payload["incident_info"]["analysis_action"]["effect_id"] == reference
    changed = copy.deepcopy(payload)
    changed["incident_info"]["analysis_action"]["effect_id"] = "different"
    with pytest.raises(delivery.DeliveryConflict):
        consume(changed, handler)
    assert handler.call_count == 1


def test_receiver_misrouting_fails_before_side_effects(payload):
    payload["destination"] = "jingyan"
    handler = Mock()
    with pytest.raises(delivery.DeliveryConflict, match="wrong receiver"):
        consume(payload, handler)
    handler.assert_not_called()
    assert not Receipt.objects.exists()


@pytest.mark.parametrize("status", ["todo", "running", "finished", "failed"])
def test_diagnosis_status_contract_and_duplicate_delivery(payload, status):
    diagnosis_payload(payload, status)
    handler = Mock()
    consume(payload, handler)
    consume(copy.deepcopy(payload), handler)
    assert handler.call_count == 1


@pytest.mark.parametrize(
    "change",
    [
        {"event_id": ""},
        {"aggregate_revision": True},
        {"aggregate_revision": 0},
        {"notice_source": "other"},
    ],
)
def test_invalid_diagnosis_envelope_has_no_effect(payload, change):
    diagnosis_payload(payload)
    payload.update(change)
    handler = Mock()
    with pytest.raises(delivery.DeliveryConflict):
        consume(payload, handler)
    handler.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "2.0"},
        {"schema_version": None},
        {"notification_kind": "lifecycle"},
        {"operation": "fault_occurred"},
        {"event_types": ["incident.created"]},
        {"event_types": []},
        {"event_types": [["diagnosis.requested"]]},
        {"sync_type": "create"},
        {"destination": []},
        {"incident_id": True},
        {"incident_info": []},
        {"policy_revision": "invalid"},
        {"changes": []},
    ],
)
def test_malformed_versioned_protocol_never_reaches_handler(payload, change):
    diagnosis_payload(payload)
    payload.update(change)
    handler = Mock()
    with pytest.raises(delivery.DeliveryConflict):
        consume(payload, handler)
    handler.assert_not_called()
    assert not Receipt.objects.exists()


@pytest.mark.parametrize(
    "change",
    [
        {"diagnosis_status": "finished"},
        {"analysis": {"task_id": 1, "task_status": "finished", "execution_backend": "runtime"}},
        {"analysis": {"task_id": 1, "task_status": "ready", "execution_backend": []}},
        {"create_time": True},
        {"scope_id": "wrong"},
    ],
)
def test_diagnosis_snapshot_must_agree_with_its_event(payload, change):
    diagnosis_payload(payload)
    payload["incident_info"].update(change)
    with pytest.raises(delivery.DeliveryConflict):
        consume(payload, Mock())
    assert not Receipt.objects.exists()


def test_missing_document_can_retry_after_default_creation_without_duplicate_effect(payload):
    diagnosis_payload(payload)
    handler = Mock(side_effect=[delivery.DeliveryBusy("not synchronized"), None])
    with pytest.raises(delivery.DeliveryBusy):
        consume(payload, handler)
    assert Receipt.objects.get().status == "retry"
    consume(payload, handler)
    consume(payload, handler)
    assert handler.call_count == 2
    assert Receipt.objects.get().status == "succeeded"


def test_diagnosis_retry_claim_is_exclusive(payload):
    diagnosis_payload(payload)
    with pytest.raises(delivery.DeliveryBusy):
        consume(payload, Mock(side_effect=delivery.DeliveryBusy("not synchronized")))
    entered, release = Event(), Event()

    def process():
        close_old_connections()
        try:

            def handler(message):
                entered.set()
                assert release.wait(timeout=10)

            consume(payload, handler)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(process)
        try:
            assert entered.wait(timeout=10)
            with pytest.raises(delivery.DeliveryBusy):
                consume(payload, Mock())
        finally:
            release.set()
        worker.result(timeout=10)
    assert Receipt.objects.get().status == "succeeded"


def test_other_producer_legacy_schema_remains_unchanged(payload):
    payload.update(notice_source="other", schema_version="custom")
    handler = Mock()
    consume(payload, handler)
    handler.assert_called_once_with(payload)
    assert not Receipt.objects.exists()


def test_nonfinite_json_is_rejected_before_receipt_or_effect(payload):
    payload["unexpected_float"] = float("nan")
    with pytest.raises(delivery.DeliveryConflict, match="finite JSON"):
        consume(payload, Mock())
    assert not Receipt.objects.exists()
