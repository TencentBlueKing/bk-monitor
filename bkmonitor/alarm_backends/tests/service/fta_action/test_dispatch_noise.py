from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from alarm_backends.core.alert import Alert
from alarm_backends.service.alert.manager.checker.action import ActionHandleChecker
from alarm_backends.service.alert.manager.checker.shield import ShieldStatusChecker
from alarm_backends.service.composite import processor as composite
from alarm_backends.service.fta_action import ActionAlreadyFinishedError, BaseActionProcessor
from alarm_backends.service.fta_action.collect import processor as collect
from alarm_backends.service.fta_action.tasks import create_action
from bkmonitor.documents import AlertDocument
from constants.action import ActionNoticeType, ActionSignal, ActionStatus, NotifyStep
from constants.alert import EventStatus


def noise_alert():
    return Alert(
        {
            "id": "test-alert",
            "severity": 2,
            "event": {"tags": []},
            "extra_info": {"matched_rule_info": {"dispatch_result": {"noise": True}}},
        }
    )


@pytest.mark.parametrize(
    "signal", [ActionSignal.ABNORMAL, ActionSignal.NO_DATA, ActionSignal.RECOVERED, ActionSignal.CLOSED]
)
def test_noise_emits_only_lifecycle_queue_even_without_notice_config(signal):
    alert = noise_alert()
    with (
        patch.object(Alert, "mget", return_value=[alert]),
        patch.object(create_action, "Strategy", return_value=SimpleNamespace(config={})),
    ):
        processor = create_action.CreateActionProcessor(1, signal, [alert.id])
    processor.get_alert_shield_result = Mock(return_value=(False, []))
    processor.create_message_queue_action = Mock(side_effect=lambda actions: actions.append(7))
    processor.get_action_relations = Mock()
    processor.alert_assign_handle = Mock()
    processor._process_issue_aggregation = Mock()
    assert processor.do_create_actions() == [7]
    processor.create_message_queue_action.assert_called_once()
    processor.get_action_relations.assert_not_called()
    processor.alert_assign_handle.assert_not_called()
    processor._process_issue_aggregation.assert_not_called()


@pytest.mark.parametrize(
    "kwargs",
    [{"execute_times": 1}, {"notice_type": ActionNoticeType.UPGRADE}, {"is_unshielded": True}, {"relation_id": 9}],
)
def test_previously_queued_followup_is_dropped_before_lifecycle_push(kwargs):
    alert = noise_alert()
    with (
        patch.object(Alert, "mget", return_value=[alert]),
        patch.object(create_action, "Strategy", return_value=SimpleNamespace(config={})),
    ):
        processor = create_action.CreateActionProcessor(1, ActionSignal.ABNORMAL, [alert.id], **kwargs)
    processor.create_message_queue_action = Mock()
    assert processor.do_create_actions() == []
    processor.create_message_queue_action.assert_not_called()


def test_assigned_tag_alone_does_not_classify_historical_alert():
    data = {"assign_tags": [{"key": "is_noise", "value": "true"}]}
    assert not Alert(data).is_dispatch_noise
    assert not AlertDocument(**data).is_dispatch_noise


@pytest.mark.parametrize(
    ("status", "signal"), [(EventStatus.RECOVERED, ActionSignal.RECOVERED), (EventStatus.CLOSED, ActionSignal.CLOSED)]
)
def test_third_party_noise_preserves_terminal_signals(status, signal):
    processor = composite.CompositeProcessor.__new__(composite.CompositeProcessor)
    processor.alert = noise_alert()
    processor.alert_status = status
    processor.actions = []
    processor.push_actions = Mock()
    processor.clear_composite_detect_cache = Mock()
    with (
        patch.object(composite, "service_lock"),
        patch.object(composite, "ALERT_DETECT_RESULT") as detect,
        patch.object(composite, "ALERT_FIRST_HANDLE_RECORD"),
    ):
        detect.client.get.return_value = "2"
        assert processor.process_single_strategy()["signal"] == signal
    processor.push_actions.assert_called_once()
    processor.clear_composite_detect_cache.assert_called_once()


def test_noise_does_not_schedule_periodic_or_unshield_notice():
    alert = noise_alert()
    alert.set("is_handled", True)
    action_checker = ActionHandleChecker([alert])
    shield_checker = ShieldStatusChecker([alert])
    with patch.object(alert, "get_latest_interval_record") as history:
        action_checker.check(alert)
        shield_checker.add_unshield_action(alert, {"id": 9, "config_id": 7})
    history.assert_not_called()
    assert not shield_checker.unshielded_actions


@pytest.mark.parametrize("signal", [ActionSignal.ABNORMAL, ActionSignal.MANUAL, ActionSignal.DEMO])
def test_pending_noise_action_is_skipped_and_running_callbacks_keep_their_state(signal):
    processor = BaseActionProcessor.__new__(BaseActionProcessor)
    processor.action = SimpleNamespace(pk=5, signal=signal, status=ActionStatus.CONVERGED)
    processor.context = {"alert": AlertDocument(**noise_alert().data)}
    processor.action_config = {"plugin_type": "job"}
    processor.notify_config = {"signal": [ActionSignal.EXECUTE_SUCCESS]}
    with patch("alarm_backends.service.fta_action.ActionInstance.objects.filter") as query:
        with pytest.raises(ActionAlreadyFinishedError):
            processor.skip_pending_dispatch_noise()
        query.assert_called_once_with(pk=5, status=ActionStatus.CONVERGED)
        assert query.return_value.update.call_args.kwargs["status"] == ActionStatus.SKIPPED
        query.reset_mock()
        processor.action.status = ActionStatus.RUNNING
        processor.skip_pending_dispatch_noise()
        query.assert_not_called()
        assert processor.no_need_notify(NotifyStep.SUCCESS)


def test_queued_manual_action_checks_secondary_alert_in_group():
    processor = BaseActionProcessor.__new__(BaseActionProcessor)
    processor.action = SimpleNamespace(signal=ActionSignal.MANUAL, alerts=["normal", "test-alert"])
    processor.context = {"alert": AlertDocument(id="normal")}
    with patch.object(AlertDocument, "mget", return_value=[AlertDocument(**noise_alert().data)]):
        assert processor.has_dispatch_noise


def test_demo_checks_real_alert_before_assignment_and_keeps_standalone_example():
    processor = BaseActionProcessor.__new__(BaseActionProcessor)
    processor.action = SimpleNamespace(signal=ActionSignal.DEMO, alerts=["test-alert"], status=ActionStatus.RECEIVED)
    with (
        patch.object(AlertDocument, "mget", return_value=[AlertDocument(**noise_alert().data)]) as mget,
        patch.object(processor, "_fix_demo_action_fields") as assign,
    ):
        assert processor.get_context()["alert"].is_dispatch_noise
        assign.assert_not_called()
        processor.action.alerts = []
        assert not processor.get_context()["alert"].is_dispatch_noise
        mget.assert_called_once()


def test_queued_collect_keeps_only_ordinary_alerts_and_actions():
    noise = AlertDocument(**noise_alert().data)
    ordinary = AlertDocument(id="ordinary")
    processor = collect.ActionProcessor.__new__(collect.ActionProcessor)
    processor.action = Mock()
    processor.alerts = []
    related = MagicMock()
    noise_action = SimpleNamespace(pk=1, alerts=[noise.id])
    ordinary_action = SimpleNamespace(pk=2, alerts=[ordinary.id])
    related.__iter__.return_value = iter([noise_action, ordinary_action])
    related.exclude.return_value = [ordinary_action]
    processor.related_actions = related
    with patch.object(collect, "ActionContext") as context:
        context.return_value.alerts = [noise, ordinary]
        processor.get_context()
        related.exclude.assert_called_once_with(pk__in=[1])
        context.assert_called_with(
            processor.action, related_actions=[ordinary_action], alerts=[ordinary], use_alert_snap=True
        )
