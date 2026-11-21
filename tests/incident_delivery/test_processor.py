"""Exercise the real consumer boundary with external transports mocked."""

import importlib.util
import json
import sys
from enum import Enum
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import test_delivery
from test_delivery import SOURCE, Receipt, delivery, diagnosis_payload

payload = test_delivery.payload


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def processor(monkeypatch):
    class Status(Enum):
        ABNORMAL = "abnormal"
        RECOVERING = "recovering"
        RECOVERED = "recovered"
        MERGED = "merged"
        CLOSED = "closed"

        @property
        def order(self):
            return 0

        @classmethod
        def get_enum_value_list(cls):
            return [item.value for item in cls]

    dependencies = {
        "pika.adapters.blocking_connection": {"BlockingChannel": object},
        "pika.spec": {"Basic": SimpleNamespace(Deliver=object)},
        "alarm_backends.core.cache.strategy": {"StrategyCacheManager": Mock()},
        "alarm_backends.core.storage.rabbitmq": {"RabbitMQClient": Mock()},
        "alarm_backends.service.access.base": {"BaseAccessProcess": object},
        "alarm_backends.service.access.incident.delivery": vars(delivery),
        "alarm_backends.service.composite.tasks": {"check_incident_action_and_composite": Mock()},
        "bkmonitor.aiops.incident.models": {"IncidentSnapshot": Mock()},
        "bkmonitor.aiops.incident.operation": {"IncidentOperationManager": Mock()},
        "bkmonitor.documents.alert": {"AlertDocument": Mock()},
        "bkmonitor.documents.base": {
            "BulkActionType": SimpleNamespace(CREATE="create", UPDATE="update", UPSERT="upsert")
        },
        "bkmonitor.documents.incident": {"IncidentDocument": Mock(), "IncidentSnapshotDocument": Mock()},
        "constants.alert": {"EventStatus": Mock()},
        "constants.incident": {
            "IncidentGraphComponentType": Mock(),
            "IncidentStatus": Status,
            "IncidentSyncType": SimpleNamespace(
                CREATE=SimpleNamespace(value="create"), UPDATE=SimpleNamespace(value="update")
            ),
        },
        "core.drf_resource": {"api": Mock()},
        "core.errors.incident": {"IncidentNotFoundError": type("IncidentNotFoundError", (Exception,), {})},
    }
    for name, attributes in dependencies.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location(
        "receipt_processor", SOURCE / "alarm_backends/service/access/incident/processor.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.consume_once = lambda message, handler: delivery.consume_once(message, handler, receipt_model=Receipt)
    instance = object.__new__(module.AccessIncidentProcess)
    instance.client = Mock()
    instance.queue_name = "test"
    return module, instance


def test_callback_acknowledges_success_and_duplicate_without_reexecution(processor, payload):
    _, instance = processor
    instance.create_incident = Mock()
    instance.process()
    callback = instance.client.start_consuming.call_args.kwargs["callback"]
    channel, method = Mock(), SimpleNamespace(delivery_tag=17)
    for _ in range(2):
        callback(channel, method, {}, json.dumps(payload))
    assert instance.create_incident.call_count == 1
    assert channel.basic_ack.call_count == 2
    channel.basic_nack.assert_not_called()


@pytest.mark.parametrize(
    "error,requeue",
    [
        (delivery.DeliveryBusy("busy"), True),
        (delivery.DeliveryConflict("conflict"), False),
        (delivery.DeliveryUncertain("uncertain"), False),
    ],
)
def test_callback_never_acks_rejected_or_busy_messages(processor, payload, error, requeue):
    _, instance = processor
    instance.handle_sync_info = Mock(side_effect=error)
    instance.process()
    callback = instance.client.start_consuming.call_args.kwargs["callback"]
    channel, method = Mock(), SimpleNamespace(delivery_tag=17)
    callback(channel, method, {}, json.dumps(payload))
    channel.basic_ack.assert_not_called()
    channel.basic_nack.assert_called_once_with(17, requeue=requeue)


@pytest.mark.parametrize("operation", ["create", "update"])
def test_processor_does_not_swallow_versioned_message_failures(processor, payload, operation):
    module, instance = processor
    payload["sync_type"] = operation
    # Real create/update preparation fails before any external write.
    module.IncidentDocument.side_effect = RuntimeError("document initialization failed")
    module.IncidentDocument.get.side_effect = RuntimeError("document lookup failed")
    with pytest.raises(delivery.DeliveryUncertain):
        instance.handle_sync_info(payload)
    assert Receipt.objects.get().status == "uncertain"


def test_legacy_processor_still_handles_errors_without_receipt(processor, payload):
    module, instance = processor
    payload.pop("event_id")
    module.IncidentDocument.side_effect = RuntimeError("legacy failure")
    instance.handle_sync_info(payload)
    assert not Receipt.objects.exists()


def test_diagnosis_message_never_runs_full_incident_sync(processor, payload):
    _, instance = processor
    diagnosis_payload(payload)
    instance.update_diagnosis = Mock()
    instance.create_incident = Mock()
    instance.update_incident = Mock()
    instance.handle_sync_info(payload)
    instance.handle_sync_info(payload)
    instance.update_diagnosis.assert_called_once_with(payload)
    instance.create_incident.assert_not_called()
    instance.update_incident.assert_not_called()


def test_legacy_sync_preserves_optional_diagnosis_and_tenant(processor, payload):
    _, instance = processor
    payload["incident_info"].update(diagnosis_status="finished", analysis={"task_id": 7, "execution_backend": "bkflow"})
    values = instance.extract_bkfara_process_info(payload, payload["incident_info"], True)
    document = SimpleNamespace(extra_info={"unrelated": 1})
    instance.mark_incident_source(payload, document, values)
    assert document.extra_info["diagnosis_status"] == "finished"
    assert document.extra_info["analysis"]["execution_backend"] == "bkflow"
    assert document.extra_info["bk_tenant_id"] == payload["bk_tenant_id"]
    assert document.extra_info["unrelated"] == 1


def test_diagnosis_projection_only_sends_guarded_partial_update(processor, payload):
    spec = importlib.util.spec_from_file_location(
        "diagnosis_projection", SOURCE / "alarm_backends/service/access/incident/diagnosis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload.update(aggregate_revision=3)
    payload["incident_info"].update(create_time=1700000000, diagnosis_status="finished", analysis={"task_id": 7})
    documents = Mock()
    documents.search.return_value.filter.return_value.execute.return_value.hits = [
        SimpleNamespace(meta=SimpleNamespace(index="test-index", id="17000000001")),
    ]
    module.update_diagnosis(payload, documents)
    call = documents._index._get_connection.return_value.update.call_args.kwargs
    assert call["index"] == "test-index" and call["retry_on_conflict"] == 3
    assert set(call["body"]) == {"script"}
    script = call["body"]["script"]
    assert script["params"]["snapshot"]["revision"] == 3
    assert script["params"]["bk_tenant_id"] == payload["bk_tenant_id"]
    assert "previous.revision < params.snapshot.revision" in script["source"]
    documents.bulk_create.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("notice_fails", [False, True])
def test_real_handler_external_effects_are_not_repeated(processor, payload, operation, notice_fails):
    module, instance = processor
    document = SimpleNamespace(
        status="abnormal",
        assignees=[],
        handlers=[],
        labels=[],
        extra_info={},
        generate_handlers=Mock(),
        generate_assignees=Mock(),
        snapshot=Mock(),
        end_time=None,
    )
    module.IncidentDocument.return_value = document
    module.IncidentDocument.get.return_value = document
    module.IncidentSnapshotDocument.return_value = SimpleNamespace(
        status="abnormal",
        alerts=[],
        content=SimpleNamespace(to_dict=lambda: {}),
    )
    instance.generate_incident_labels = Mock()
    instance.generate_alert_operations = Mock()
    instance.update_alert_incident_relations = Mock(return_value={})
    payload.update(
        {
            "sync_type": operation,
            "fpp_snapshot_id": "fpp:None",
            "rca_time": 1700000000,
            "scope": {"bk_biz_ids": [2], "alerts": [], "events": []},
            "update_attributes": {"status": {"from": "abnormal", "to": "recovering"}},
        }
    )
    payload["incident_info"].update(
        {
            "status": "abnormal",
            "bk_biz_id": 2,
            "create_time": 1700000000,
            "update_time": 1700000010,
        }
    )
    notification = getattr(module.IncidentOperationManager, f"record_{operation}_incident")
    if notice_fails:
        notification.side_effect = TimeoutError("notice acknowledgement lost")
        for _ in range(2):
            with pytest.raises(delivery.DeliveryUncertain):
                instance.handle_sync_info(payload)
    else:
        instance.handle_sync_info(payload)
        instance.handle_sync_info(payload)
    assert notification.call_count == 1
    assert module.IncidentSnapshotDocument.bulk_create.call_count == 1
    assert Receipt.objects.get().status == ("uncertain" if notice_fails else "succeeded")


@pytest.mark.parametrize("results", [{}, {"mail": {"operator": {"result": False}}}])
def test_real_notice_helper_failure_blocks_receipt_completion(processor, payload, monkeypatch, results):
    _, instance = processor
    constants = sys.modules["constants.incident"]
    for name in (
        "INCIDENT_ATTRIBUTE_ALIAS_MAPPINGS",
        "INCIDENT_ATTRIBUTE_VALUE_ENUMS",
        "IncidentOperationClass",
        "IncidentOperationType",
    ):
        monkeypatch.setattr(constants, name, Mock(), raising=False)
    monkeypatch.setattr(sys.modules["bkmonitor.documents.incident"], "IncidentOperationDocument", Mock(), raising=False)
    request_module = ModuleType("bkmonitor.utils.request")
    request_module.get_request_username = lambda: "test"
    monkeypatch.setitem(sys.modules, request_module.__name__, request_module)
    notice_module = ModuleType("bkmonitor.aiops.incident.notice")
    notice_module.IncidentNoticeHelper = Mock()
    notice_module.IncidentNoticeHelper._get_configured_notice_targets.return_value = [
        {"notice_way": "mail", "receivers": ["operator"]}
    ]
    notice_module.IncidentNoticeHelper.send_incident_notice.return_value = results
    monkeypatch.setitem(sys.modules, notice_module.__name__, notice_module)
    spec = importlib.util.spec_from_file_location("receipt_operation", SOURCE / "bkmonitor/aiops/incident/operation.py")
    operation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operation)

    def send(message):
        operation.IncidentOperationManager._send_incident_notice(
            1, SimpleNamespace(value="create"), incident_document=Mock(), notice_config={"enabled": True}
        )

    instance.create_incident = send
    with pytest.raises(delivery.DeliveryUncertain):
        instance.handle_sync_info(payload)
    assert Receipt.objects.get().status == "uncertain"
    # Context must be reset; the legacy best-effort path remains compatible.
    send(payload)


@pytest.mark.parametrize("body", ["{", "[]", "null", '{"schema_version":"2.0","scope":[]}'])
def test_poison_message_is_rejected_without_crashing_callback(processor, body):
    _, instance = processor
    instance.process()
    callback = instance.client.start_consuming.call_args.kwargs["callback"]
    channel = Mock()
    callback(channel, SimpleNamespace(delivery_tag=17), {}, body)
    channel.basic_ack.assert_not_called()
    channel.basic_nack.assert_called_once_with(17, requeue=False)
    assert not Receipt.objects.exists()


def test_lifecycle_write_cannot_overwrite_newer_diagnosis_even_from_stale_cache(processor, payload):
    module, instance = processor
    document = SimpleNamespace(
        extra_info={
            "diagnosis_status": "running",
            "analysis": {"task_id": 7},
            "diagnosis_notification": {"revision": 2, "event_id": "old"},
            "unrelated": 1,
        }
    )
    # Simulate a new diagnosis delta arriving after this document was loaded.
    stored = {
        "diagnosis_status": "finished",
        "analysis": {"task_id": 7},
        "diagnosis_notification": {"revision": 3, "event_id": "new"},
        "unrelated": 0,
    }

    def write(documents, **kwargs):
        stored.update(documents[0].extra_info)

    module.IncidentDocument.bulk_create.side_effect = write
    instance.persist_incident_update(payload, document)
    assert stored["diagnosis_status"] == "finished"
    assert stored["diagnosis_notification"]["revision"] == 3
    assert stored["unrelated"] == 1
    assert document.extra_info["diagnosis_status"] == "running"


def test_non_bkfara_updates_keep_original_fields(processor, payload):
    module, instance = processor
    payload["notice_source"] = "other"
    document = SimpleNamespace(extra_info={"analysis": {"custom": 1}})
    instance.persist_incident_update(payload, document)
    assert module.IncidentDocument.bulk_create.call_args.args[0] == [document]


def test_missing_projection_is_retryable_before_any_write(processor, payload):
    spec = importlib.util.spec_from_file_location(
        "missing_diagnosis_projection", SOURCE / "alarm_backends/service/access/incident/diagnosis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    diagnosis_payload(payload)
    documents = Mock()
    documents.search.return_value.filter.return_value.execute.return_value.hits = []
    with pytest.raises(delivery.DeliveryBusy):
        module.update_diagnosis(payload, documents)
    documents._index._get_connection.assert_not_called()
