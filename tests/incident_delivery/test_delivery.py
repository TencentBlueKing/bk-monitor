import copy
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.db import close_old_connections, connection
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
