"""Event snapshots used by standard SMS rendering stay tied to the triggering operation."""

from contextlib import nullcontext
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from django.utils import timezone, translation

from alarm_backends.core.context.alarm import Alarm
from alarm_backends.service import fta_action
from alarm_backends.service.fta_action import BaseActionProcessor
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor
from bkmonitor.aiops.incident.notice import IncidentNoticeHelper
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.documents.incident import IncidentDocument, IncidentOperationDocument
from bkmonitor.models.fta import ActionInstance
from bkmonitor.utils.send import Sender
from constants.action import ActionPluginType, ActionSignal, ActionStatus, NotifyStep
from constants.incident import IncidentOperationType
from fta_web.action.resources import backend_resources


def test_ack_logs_and_reason_share_the_existing_query(monkeypatch):
    logs = [SimpleNamespace(create_time=200, description="latest"), SimpleNamespace(create_time=100, description="old")]
    query = Mock(return_value=logs)
    monkeypatch.setattr(AlertLog, "get_ack_logs", query)
    alarm = Alarm(SimpleNamespace(alert=object(), alerts=[SimpleNamespace(id="a"), SimpleNamespace(id="b")]))

    assert alarm.ack_reason == ["latest", "old"]
    assert alarm.ack_logs[0].create_time == 200
    assert alarm.ack_logs is logs
    query.assert_called_once_with(["a", "b"])


def test_ack_without_alert_keeps_empty_context(monkeypatch):
    query = Mock()
    monkeypatch.setattr(AlertLog, "get_ack_logs", query)
    alarm = Alarm(SimpleNamespace(alert=None, alerts=[]))
    assert alarm.ack_logs == []
    assert alarm.ack_reason is None
    query.assert_not_called()


@pytest.mark.parametrize("signal", [ActionSignal.RECOVERED, ActionSignal.CLOSED])
def test_action_creation_snapshots_both_alert_times(signal):
    processor = object.__new__(CreateActionProcessor)
    processor.__dict__.update(
        signal=signal,
        is_alert_shielded=False,
        shield_detail="",
        is_unshielded=False,
        notice_type="",
        strategy_id=1,
        severity=1,
        generate_uuid="batch",
        dimensions=[],
        dimension_hash="",
        strategy={},
        execute_times=0,
    )
    alert = SimpleNamespace(
        id="alert",
        latest_time=100,
        end_time=200,
        severity=1,
        event=SimpleNamespace(bk_biz_id=2),
        alert_name="test alert",
        extra_info={},
    )
    assignees = SimpleNamespace(get_appointees=lambda **kwargs: ["user"])
    action = processor.do_create_action(
        {"id": 1},
        {"plugin_type": ActionPluginType.WEBHOOK},
        alert,
        action_relation={"options": {}},
        assignee_manager=assignees,
    )
    alert.latest_time = 300
    alert.end_time = 400
    assert action.inputs["alert_latest_time"] == 100
    assert action.inputs["alert_end_time"] == 200


def test_manual_action_uses_latest_valid_alert_event_not_creation_time(monkeypatch):
    alerts = [
        SimpleNamespace(
            id=str(index),
            strategy_id=1,
            severity=1,
            latest_time=latest_time,
            event=SimpleNamespace(bk_biz_id=biz_id),
            assignee=[],
        )
        for index, latest_time, biz_id in [(1, 100, 2), (2, 200, 2), (3, 999, 3)]
    ]
    monkeypatch.setattr(AlertDocument, "mget", Mock(return_value=alerts))
    monkeypatch.setattr(backend_resources.ActionPlugin.objects, "all", Mock(return_value=[]))
    created = []

    def create_action(**kwargs):
        action = ActionInstance(id=10, create_time=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc), **kwargs)
        created.append(action)
        return action

    monkeypatch.setattr(ActionInstance.objects, "create", create_action)
    monkeypatch.setattr(backend_resources, "get_user_display_name", lambda username: username)
    monkeypatch.setattr(backend_resources.PushActionProcessor, "push_actions_to_queue", lambda *args: [10])
    monkeypatch.setattr(AlertDocument, "bulk_create", Mock())
    monkeypatch.setattr(AlertLog, "bulk_create", Mock())

    result = backend_resources.BatchCreateActionResource().perform_request(
        {
            "bk_biz_id": 2,
            "creator": "user",
            "operate_data_list": [
                {"alert_ids": ["1", "2", "3"], "action_configs": [{"config_id": 1, "plugin_id": 1, "name": "action"}]}
            ],
        }
    )

    assert created[0].signal == ActionSignal.MANUAL
    assert created[0].alerts == ["1", "2"]
    assert created[0].inputs["alert_latest_time"] == 200
    assert result["alert_ids"] == ["1", "2"]


@pytest.fixture
def action_notice_environment(monkeypatch, settings):
    from alarm_backends.core.cache.cmdb.business import BusinessManager
    from alarm_backends.service.fta_action import utils

    settings.SMS_CONTENT_LENGTH = 1000
    group = SimpleNamespace(
        id=1,
        mention_list=[],
        mention_type=0,
        channels=[],
        action_notice=[
            {
                "time_range": "00:00--23:59",
                "notify_config": [
                    {"phase": phase, "notice_ways": [{"name": "sms", "receivers": ["user"]}]}
                    for phase in [NotifyStep.BEGIN, NotifyStep.SUCCESS, NotifyStep.FAILURE]
                ],
            }
        ],
    )

    def groups(**kwargs):
        queryset = MagicMock()
        queryset.only.return_value = []
        queryset.values_list.return_value = []
        queryset.__iter__.return_value = iter([group])
        return queryset

    monkeypatch.setattr(utils.UserGroup.objects, "filter", groups)
    monkeypatch.setattr(utils.DutyArrange.objects, "filter", Mock(return_value=Mock(order_by=lambda *args: [])))
    monkeypatch.setattr(utils, "get_business_roles", lambda *args: {})
    monkeypatch.setattr(
        BusinessManager,
        "get",
        lambda *args: SimpleNamespace(language=settings.DEFAULT_LOCALE, time_zone="UTC"),
    )
    sent = []

    class CapturingSender(Sender):
        def send(self, *args, **kwargs):
            sent.append(dict(self.context))
            return {"result": True}

    monkeypatch.setattr(fta_action, "Sender", CapturingSender)
    with timezone.override("UTC"), translation.override(settings.DEFAULT_LOCALE):
        yield sent


def action_processor():
    processor = object.__new__(BaseActionProcessor)
    processor.action = ActionInstance(
        id=1,
        status=ActionStatus.RECEIVED,
        action_plugin={"plugin_type": ActionPluginType.WEBHOOK},
        execute_times=0,
        bk_biz_id="2",
    )
    processor.action_config = {"plugin_type": ActionPluginType.WEBHOOK}
    processor.notify_config = {
        "user_groups": [1],
        "signal": [ActionSignal.EXECUTE, ActionSignal.EXECUTE_SUCCESS, ActionSignal.EXECUTE_FAILED],
    }
    processor.bk_tenant_id = "tenant"
    processor.context = {
        "alert": SimpleNamespace(event=SimpleNamespace(bk_biz_id=2)),
        "bk_biz_id": 2,
        "notice_way": "sms",
        "target": SimpleNamespace(business=SimpleNamespace(bk_biz_id=2, bk_biz_name="business"), host=None),
        "alarm": SimpleNamespace(target_display="", new_dimensions={}),
        "action_instance": SimpleNamespace(name="action", operate_target_string="target"),
    }
    processor.retry_times = 0
    processor.timeout_setting = 0
    return processor


def test_action_start_captures_execution_time_before_existing_status_update(monkeypatch, action_notice_environment):
    processor = action_processor()
    processor.action.strategy = {}
    monkeypatch.setattr(fta_action.transaction, "atomic", lambda **kwargs: nullcontext())
    monkeypatch.setattr(
        ActionInstance.objects, "select_for_update", Mock(return_value=Mock(get=lambda **kwargs: processor.action))
    )
    monkeypatch.setattr(ActionInstance, "save", Mock())
    before = timezone.now()
    processor.set_start_to_execute()
    after = timezone.now()

    assert len(action_notice_environment) == 1
    context = action_notice_environment[0]
    assert before <= context["sms_event_time"] <= after
    assert context["sms_action_status"] == ActionStatus.RUNNING
    assert processor.action.status == ActionStatus.RUNNING
    assert processor.action.execute_times == 1
    assert "sms_event_time" not in processor.context


@pytest.mark.parametrize(
    "status,step", [(ActionStatus.SUCCESS, NotifyStep.SUCCESS), (ActionStatus.FAILURE, NotifyStep.FAILURE)]
)
def test_action_end_notice_uses_saved_end_time(status, step, action_notice_environment):
    processor = action_processor()
    processor.action.status = status
    processor.action.end_time = datetime(2020, 1, 1, tzinfo=datetime_timezone.utc)
    processor.notify(step)
    assert len(action_notice_environment) == 1
    assert action_notice_environment[0]["sms_event_time"] == processor.action.end_time
    assert action_notice_environment[0]["sms_action_status"] == status


def incident_document(has_snapshot=False):
    return IncidentDocument(
        bk_biz_id=2,
        incident_id=1,
        incident_name="incident",
        begin_time=100,
        alert_count=9,
        status="abnormal",
        level="WARN",
        assignees=[],
        snapshot={"content": {"incident_alerts": [{"id": "1", "alert_status": "ABNORMAL"}]}} if has_snapshot else {},
    )


@pytest.fixture
def incident_notice_environment(monkeypatch, settings):
    from alarm_backends.core.cache.cmdb.business import BusinessManager
    from bkmonitor.aiops.incident import notice

    settings.ENABLE_BK_INCIDENT_NOTICE = True
    monkeypatch.setattr(notice.api.metadata, "get_space_detail", lambda **kwargs: {"space_name": "business"})
    monkeypatch.setattr(
        BusinessManager,
        "get",
        lambda *args: SimpleNamespace(language=settings.DEFAULT_LOCALE, time_zone="UTC"),
    )
    sent = []

    def send(sender, **kwargs):
        sent.append(dict(sender.context))
        return {}

    monkeypatch.setattr(Sender, "send", send)
    with timezone.override("UTC"), translation.override(settings.DEFAULT_LOCALE):
        yield sent


@pytest.mark.parametrize(
    "operation", [IncidentOperationType.CREATE, IncidentOperationType.RECOVER, IncidentOperationType.MERGE]
)
@pytest.mark.parametrize("operate_time", [None, 123])
def test_incident_notice_reuses_operation_log_time(monkeypatch, incident_notice_environment, operation, operate_time):
    written = Mock()
    monkeypatch.setattr(IncidentOperationDocument, "bulk_create", written)
    monkeypatch.setattr("bkmonitor.aiops.incident.operation.time.time", lambda: 456)
    IncidentOperationManager.record_operation(
        1,
        operation,
        operate_time=operate_time,
        send_notice=True,
        incident_document=incident_document(),
        notice_config={"module": {"sms": {"is_select": True, "receivers": ["user"]}}},
    )
    expected = 456 if operate_time is None else operate_time
    assert written.call_args.args[0][0].create_time == expected
    assert len(incident_notice_environment) == 1
    assert incident_notice_environment[0]["sms_event_time"] == expected
    assert "operate_time" not in written.call_args.args[0][0].extra_info


@pytest.mark.parametrize(
    "operation", [IncidentOperationType.OBSERVE, IncidentOperationType.REOPEN, IncidentOperationType.UPDATE]
)
def test_incident_notice_trigger_scope_stays_unchanged(monkeypatch, incident_notice_environment, operation):
    monkeypatch.setattr(IncidentOperationDocument, "bulk_create", Mock())
    IncidentOperationManager.record_operation(
        1,
        operation,
        send_notice=True,
        incident_document=incident_document(),
        notice_config={"module": {"sms": {"is_select": True, "receivers": ["user"]}}},
    )
    assert incident_notice_environment == []


@pytest.mark.parametrize("has_snapshot", [False, True])
def test_incident_context_exposes_raw_event_fields_and_preserves_notify_time(monkeypatch, has_snapshot):
    from bkmonitor.aiops.incident import notice

    monkeypatch.setattr(notice.api.metadata, "get_space_detail", lambda **kwargs: {"space_name": "business"})
    context = IncidentNoticeHelper.get_incident_context(
        incident_document(has_snapshot), operation_type=IncidentOperationType.CREATE, operate_time=123
    )
    assert context["sms_event_time"] == 123
    assert context["sms_level"] == "WARN"
    assert context["sms_alert_count"] == (1 if has_snapshot else 9)
    assert isinstance(context["notify_time"], str)
    assert context["notify_time"] != "123"
