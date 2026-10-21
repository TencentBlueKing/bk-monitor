"""Exercise the real consumer boundary with external transports mocked."""

import importlib.util
import json
import sys
from enum import Enum
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import test_delivery
from test_delivery import SOURCE, Receipt, delivery

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
