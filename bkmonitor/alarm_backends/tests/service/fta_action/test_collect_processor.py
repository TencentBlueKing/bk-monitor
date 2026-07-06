import logging
from types import SimpleNamespace

from alarm_backends.service.fta_action.collect.processor import ActionProcessor
from constants.action import ActionSignal, ActionStatus, ConvergeType, FailureType


class _FakeAction(SimpleNamespace):
    def save(self, update_fields=None):
        self.saved_update_fields = update_fields


class _FakeRelatedActions(list):
    def update(self, **kwargs):
        self.updated_kwargs = kwargs


class _FailedSender:
    title = "collect title"
    content = "collect content"

    def __init__(self, *args, **kwargs):
        pass

    def send(self, notice_way, receiver):
        return {receiver[0]: {"result": False, "message": ["missing webhook"]}}


def test_send_collect_notice_logs_regular_failure(settings, monkeypatch, caplog):
    settings.MD_SUPPORTED_NOTICE_WAYS = ["wecom_robot"]
    monkeypatch.setattr("alarm_backends.service.fta_action.collect.processor.i18n.set_biz", lambda *args: None)

    processor = object.__new__(ActionProcessor)
    processor.action = _FakeAction(id=1, bk_biz_id=2, status=None, failure_type=None, outputs={})
    processor.bk_tenant_id = "system"
    processor.converge_instance = SimpleNamespace(id=3)
    processor.related_actions = _FakeRelatedActions([SimpleNamespace(id=11, parent_action_id=101, alerts=[1001])])
    processor.context = {"notice_channel": "test"}
    processor.NOTICE_SENDER = {"test": _FailedSender}
    processor.check_circuit_breaking_for_notice = lambda: False

    with caplog.at_level(logging.ERROR, logger="fta_action.run"):
        processor.send_collect_notice(
            ["chat-id"],
            {"notice_way": "wecom_robot", "signal": ActionSignal.ABNORMAL},
            ConvergeType.ACTION,
        )

    assert processor.action.status == ActionStatus.FAILURE
    assert processor.action.failure_type == FailureType.EXECUTE_ERROR
    assert "in send_collect_notice" in caplog.text
    assert "collect notice failed" in caplog.text
    assert "missing webhook" in caplog.text
