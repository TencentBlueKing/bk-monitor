from datetime import datetime, timezone as datetime_timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone, translation
from django.db import connection

from bkmonitor.define.global_config import STANDARD_CONFIGS
from bkmonitor.models import ActionInstance
from bkmonitor.utils import dynamic_settings, sms
from bkmonitor.utils.dynamic_settings import DynamicSettings
from bkmonitor.utils.send import NoneTemplateSender, Sender
from bkmonitor.utils.sms_context import standard_sms_values
from constants.action import ACTION_STATUS_DICT, ActionStatus
from constants.alert import EVENT_SEVERITY_DICT


class MemoryCache:
    def __init__(self):
        self.values = {}

    def has_key(self, name):
        return name in self.values

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value, timeout=None):
        self.values[name] = value


def test_sms_mode_database_failure_uses_values_default_without_caching(monkeypatch):
    cache = MemoryCache()
    monkeypatch.setattr(dynamic_settings, "locmem_cache", cache)
    monkeypatch.setattr(dynamic_settings, "redis_cache", None)
    config = Mock()
    config.get.side_effect = RuntimeError("database unavailable")
    wrapped = SimpleNamespace(SMS_NOTICE_TEMPLATE_MODE="standard", SMS_NOTICE_TEMPLATE_MODE_DEFAULT="standard")
    effective = DynamicSettings(wrapped, config)
    monkeypatch.setattr(sms, "settings", effective)

    assert sms.get_sms_template_mode() == "standard"
    assert cache.values == {}
    config.get.side_effect = None
    config.get.return_value = "legacy"
    assert sms.get_sms_template_mode() == "legacy"
    assert cache.values == {"SMS_NOTICE_TEMPLATE_MODE": "legacy"}


def test_sms_mode_registered_with_static_default(settings):
    field = STANDARD_CONFIGS["SMS_NOTICE_TEMPLATE_MODE"]
    assert field.default == settings.SMS_NOTICE_TEMPLATE_MODE_DEFAULT
    assert list(field.choices) == ["legacy", "standard"]


def notification_context(times=(100, 200), end_times=(300, 400)):
    actions = [
        SimpleNamespace(id=index, inputs={"alert_latest_time": latest, "alert_end_time": end})
        for index, (latest, end) in enumerate(zip(times, end_times))
    ]
    alarm = SimpleNamespace(
        name="CPU alert",
        collect_count=len(actions),
        ack_operators=["alice"],
        ack_logs=[SimpleNamespace(create_time=500)],
        parent=SimpleNamespace(related_actions=actions),
    )
    return {
        "notice_way": "sms",
        "bk_biz_id": 0,
        "alarm": alarm,
        "alert": SimpleNamespace(severity=1),
        "action": actions[0],
        "level_name": "[疑似异常]致命",
        "user_content": "https://example.com/legacy-details",
    }


@pytest.mark.parametrize(
    "kind,expected", [("abnormal/converge", 200), ("recovered/converge", 400), ("ack/converge", 500)]
)
def test_standard_context_uses_latest_matching_event(kind, expected):
    with timezone.override("UTC"), translation.override("zh-hans"):
        values = standard_sms_values(kind, notification_context())
        assert values["time"] == sms.format_sms_time(expected)
        assert values["level"] == "致命"


def test_standard_context_does_not_substitute_send_time():
    context = notification_context(times=(None,), end_times=(None,))
    with translation.override("zh-hans"):
        assert standard_sms_values("abnormal/action", context)["time"] == "时间未知"


@pytest.mark.parametrize("limit", [50, 70, 100])
@pytest.mark.parametrize("kind", ["abnormal/action", "ack/converge", "shield", "incident", "fta_action"])
@pytest.mark.parametrize("language", ["zh-hans", "en"])
def test_standard_sender_preserves_full_sms_at_cmsi_boundary(settings, monkeypatch, limit, kind, language):
    settings.SMS_NOTICE_TEMPLATE_MODE = "standard"
    settings.SMS_CONTENT_LENGTH = limit
    settings.DEFAULT_LOCALE = "zh_Hans"
    monkeypatch.setattr("bkmonitor.utils.send.i18n", None)
    monkeypatch.setattr("bkmonitor.utils.send.GlobalConfig.get", lambda *args: "蓝鲸监控")
    send_sms = Mock(return_value={"username_check": {"invalid": []}, "message": "ok"})
    monkeypatch.setattr("bkmonitor.utils.send.api.cmsi.send_sms", send_sms)
    context = notification_context()
    context.update(
        sms_event_time=datetime(2025, 12, 1, 5, 35, tzinfo=datetime_timezone.utc),
        sms_action_status=ActionStatus.SUCCESS,
        action_instance=SimpleNamespace(name="处理套餐" * 30),
        sms_event_time_formatted="2025年12月1日 13:35分",
        notice_type="开始",
        cycle_duration="2小时",
        sms_level="ERROR",
        sms_alert_count=12,
    )
    with translation.override(language), timezone.override("Asia/Shanghai"):
        sender = Sender(
            context=context,
            content_template_path=f"notice/{kind}/sms_content.jinja",
            bk_tenant_id="tenant-fixture",
        )
        result = sender.send("sms", ["alice"])
    body = send_sms.call_args.kwargs["content"]
    assert result["alice"]["result"] is True
    assert sms.sms_utf16_length(body) <= 70
    assert body.endswith("See WeCom/BK." if language == "en" else "请到企业微信/蓝鲸监控平台查看。")
    assert "https://" not in body
    assert "疑似异常" not in body
    assert send_sms.call_args.kwargs["bk_tenant_id"] == "tenant-fixture"


def test_none_template_sender_initializes_shared_fields_without_rerendering():
    sender = NoneTemplateSender(title="title", content="already rendered", bk_tenant_id="tenant-fixture")
    assert sender.content == "already rendered"
    assert sender.bk_tenant_id == "tenant-fixture"
    assert sender.mentioned_users is None
    assert sender._is_wxwork_layouts_enabled is False


def test_standard_render_failure_is_recorded_instead_of_sending_error_text(settings, monkeypatch):
    settings.SMS_NOTICE_TEMPLATE_MODE = "standard"
    monkeypatch.setattr("bkmonitor.utils.send.i18n", None)
    monkeypatch.setattr("bkmonitor.utils.send.GlobalConfig.get", lambda *args: "蓝鲸监控")
    render = Mock(side_effect=ValueError("invalid standard template"))
    monkeypatch.setattr("bkmonitor.utils.send.render_standard_sms", render)
    send_sms = Mock()
    monkeypatch.setattr("bkmonitor.utils.send.api.cmsi.send_sms", send_sms)
    sender = Sender(context=notification_context(), content_template_path="notice/abnormal/action/sms_content.jinja")

    result = sender.send("sms", ["alice"])

    assert result["alice"] == {"message": "invalid standard template", "result": False}
    send_sms.assert_not_called()
    payload = {"content": sender.content, "notice_results": result}
    stored = ActionInstance._meta.get_field("outputs").get_db_prep_value(payload, connection)
    assert json.loads(stored) == payload


@pytest.mark.parametrize("severity", [1, 2])
@pytest.mark.parametrize(
    "kind,status,visible_name_length",
    [
        ("closed/action", ActionStatus.SUCCESS, 8),
        ("recovered/action", ActionStatus.SUCCESS, 10),
        ("fta_action", ActionStatus.PARTIAL_SUCCESS, 9),
        ("fta_action", ActionStatus.PARTIAL_FAILURE, 9),
    ],
)
def test_english_single_notice_preserves_recognizable_name(kind, status, visible_name_length, severity):
    name = "CPU usage too high"
    with translation.override("en"):
        level = str(EVENT_SEVERITY_DICT[severity])
        status_name = str(ACTION_STATUS_DICT[status])
        body = sms.render_standard_sms(
            kind,
            {
                "time": "2026-12-31 23:59",
                "level": level,
                "count": 1,
                "name": name,
                "status": status_name,
            },
        )

    assert name[:visible_name_length] in body
    assert sms.sms_utf16_length(body) <= 70
    assert body.endswith("See WeCom/BK.")
    if kind == "fta_action":
        assert status_name in body
    else:
        assert level in body
        assert "Skip " in body
