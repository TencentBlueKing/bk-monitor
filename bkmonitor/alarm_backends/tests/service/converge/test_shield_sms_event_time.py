"""Shield SMS dates describe the occurrence selected by the existing notice checks."""

import os
import time
from datetime import datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import Mock

import arrow
import pytest
from django.utils import timezone, translation

from alarm_backends.service.converge.shield import shield_obj, window
from alarm_backends.service.converge.shield.shield_obj import ShieldObj
from alarm_backends.service.converge.shield.display_manager import DisplayManager
from bkmonitor.utils import send, shield as shield_utils
from bkmonitor.utils.range.period import TimeMatchByDay, TimeMatchByMonth, TimeMatchBySingle, TimeMatchByWeek
from bkmonitor.utils.sms import sms_utf16_length


@pytest.fixture(autouse=True)
def utc_environment(monkeypatch, settings):
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    settings.TIME_ZONE = "UTC"
    settings.DEFAULT_LOCALE = "zh-hans"
    monkeypatch.setattr(window.BusinessManager, "get", lambda *args: SimpleNamespace(time_zone="Asia/Shanghai"))
    try:
        with timezone.override("UTC"), translation.override("zh-hans"):
            yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


def make_shield(matcher_class=TimeMatchByDay, start="10:00:00", end="11:00:00", **cycle):
    config = {
        "id": 1,
        "bk_biz_id": 2,
        "begin_time": datetime(2026, 9, 1, tzinfo=datetime_timezone.utc),
        "end_time": datetime(2026, 10, 1, tzinfo=datetime_timezone.utc),
        "cycle_config": {"begin_time": start, "end_time": end, **cycle},
        "notice_config": {"notice_time": 5},
        "description": "description",
    }
    shield = object.__new__(ShieldObj)
    shield.config = config
    shield.notice_lock_key = "lock"
    shield.time_check = matcher_class(
        config["cycle_config"], arrow.get(config["begin_time"]), arrow.get(config["end_time"])
    )
    shield.display_manager = SimpleNamespace(
        get_category_name=lambda config: "category",
        get_cycle_duration=lambda config: "1小时/天",
        get_shield_content=lambda config: "content",
    )
    return shield


def lock_storage(monkeypatch, value=None):
    client = Mock()
    client.get.return_value = value
    lock = SimpleNamespace(client=client, ttl=60, expire=Mock())
    monkeypatch.setattr(shield_obj, "NOTICE_SHIELD_KEY_LOCK", lock)
    return lock


def test_start_notice_uses_original_future_probe_and_business_timezone(monkeypatch):
    shield = make_shield()
    lock = lock_storage(monkeypatch)
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T09:56:00+00:00")
    assert shield.can_send_start_notice() is True
    context = shield.get_notice_context("start", include_standard_sms=True)
    assert shield._sms_start_notice_probe == arrow.get("2026-09-09T10:01:00+00:00")
    assert context["sms_event_time_formatted"] == "2026年9月9日 18:00分"
    assert context["cycle_duration"] == "1小时/天"
    assert "bk_biz_id" not in context
    lock.client.get.assert_called_once_with("lock")
    lock.expire.assert_not_called()


def test_end_notice_uses_last_matching_minute(monkeypatch):
    shield = make_shield()
    lock_storage(monkeypatch, value="lock")
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T10:55:00+00:00")
    assert shield.can_send_end_notice() is True
    assert shield._sms_end_notice_probe == arrow.get("2026-09-09T11:00:00+00:00")
    assert (
        shield.get_notice_context("end", include_standard_sms=True)["sms_event_time_formatted"]
        == "2026年9月9日 19:00分"
    )


def test_missing_matching_end_probe_displays_unknown_and_keeps_send_decision(monkeypatch):
    shield = make_shield()
    lock_storage(monkeypatch, value="lock")
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T12:00:00+00:00")
    assert shield.can_send_end_notice() is True
    assert shield.get_notice_context("end", include_standard_sms=True)["sms_event_time_formatted"] == "时间未知"


def test_overnight_notice_uses_the_current_occurrence_full_date(monkeypatch):
    shield = make_shield(start="23:00:00", end="01:00:00")
    lock_storage(monkeypatch, value="lock")
    shield.get_now_datetime = lambda: arrow.get("2026-09-10T00:55:00+00:00")
    assert shield.can_send_end_notice() is True
    assert (
        shield.get_notice_context("end", include_standard_sms=True)["sms_event_time_formatted"]
        == "2026年9月10日 09:00分"
    )


@pytest.mark.parametrize("notice_type", ["start", "end"])
def test_single_notice_uses_configured_boundary(monkeypatch, notice_type):
    shield = make_shield(TimeMatchBySingle)
    lock_storage(monkeypatch, value="lock" if notice_type == "end" else None)
    at = "2026-09-30T23:55:00+00:00" if notice_type == "end" else "2026-08-31T23:56:00+00:00"
    shield.get_now_datetime = lambda: arrow.get(at)
    assert getattr(shield, f"can_send_{notice_type}_notice")() is True
    expected = "2026年10月1日 08:00分" if notice_type == "end" else "2026年9月1日 08:00分"
    assert shield.get_notice_context(notice_type, include_standard_sms=True)["sms_event_time_formatted"] == expected


@pytest.mark.parametrize(
    "matcher_class,cycle", [(TimeMatchByWeek, {"week_list": [3]}), (TimeMatchByMonth, {"day_list": [9]})]
)
def test_mixed_system_and_django_offsets_make_week_month_unknown(monkeypatch, matcher_class, cycle):
    shield = make_shield(matcher_class, start="18:00:00", end="19:00:00", **cycle)
    lock_storage(monkeypatch)
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T09:56:00+00:00")
    with timezone.override("Asia/Shanghai"):
        assert shield.can_send_start_notice() is True
        assert shield.get_notice_context("start", include_standard_sms=True)["sms_event_time_formatted"] == "时间未知"


@pytest.mark.parametrize(
    "matcher_class,cycle", [(TimeMatchByWeek, {"week_list": [3]}), (TimeMatchByMonth, {"day_list": [9]})]
)
def test_same_offsets_allow_week_month_window(monkeypatch, matcher_class, cycle):
    shield = make_shield(matcher_class, **cycle)
    lock_storage(monkeypatch)
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T09:56:00+00:00")
    assert shield.can_send_start_notice() is True
    assert (
        shield.get_notice_context("start", include_standard_sms=True)["sms_event_time_formatted"]
        == "2026年9月9日 18:00分"
    )


def test_close_matcher_keeps_its_existing_calendar_when_system_offset_differs(monkeypatch):
    shield = make_shield(TimeMatchByWeek, start="18:00:00", end="19:00:00", week_list=[3])
    shield.config["end_policy"] = "close"
    lock_storage(monkeypatch)
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T09:56:00+00:00")
    with timezone.override("Asia/Shanghai"):
        shield.time_check = window.close_time_matcher(
            {"type": 3, **shield.config["cycle_config"]}, shield.config["begin_time"], shield.config["end_time"]
        )
        assert shield.can_send_start_notice() is True
        assert (
            shield.get_notice_context("start", include_standard_sms=True)["sms_event_time_formatted"]
            == "2026年9月9日 18:00分"
        )


def test_context_formatting_does_not_activate_business_locale_or_timezone(monkeypatch):
    from alarm_backends.core.i18n import i18n

    shield = make_shield()
    shield._sms_start_notice_probe = arrow.get("2026-09-09T10:01:00+00:00")
    set_biz = Mock()
    monkeypatch.setattr(i18n, "set_biz", set_biz)
    language = translation.get_language()
    timezone_name = timezone.get_current_timezone_name()
    context = shield.get_notice_context("start", include_standard_sms=True)
    assert context["sms_event_time_formatted"] == "2026年9月9日 18:00分"
    assert translation.get_language() == language
    assert timezone.get_current_timezone_name() == timezone_name
    set_biz.assert_not_called()


def test_existing_lock_and_send_order_stays_unchanged(monkeypatch):
    shield = make_shield()
    lock = lock_storage(monkeypatch)
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T09:56:00+00:00")
    sent = []

    def send(notice_type):
        sent.append(
            (notice_type, shield.get_notice_context(notice_type, include_standard_sms=True)["sms_event_time_formatted"])
        )
        return {"sms": True}

    shield.send_notice = send
    assert shield.check_and_send_notice() == ({"sms": True}, None)
    assert sent == [("start", "2026年9月9日 18:00分")]
    lock.client.set.assert_called_once_with("lock", "__lock__", 60)
    lock.client.delete.assert_not_called()

    lock.client.get.return_value = "lock"
    shield.get_now_datetime = lambda: arrow.get("2026-09-09T10:55:00+00:00")
    assert shield.check_and_send_notice() == (None, {"sms": True})
    assert sent[-1] == ("end", "2026年9月9日 19:00分")
    lock.expire.assert_called_once_with(shield_id=1)
    lock.client.delete.assert_called_once_with("lock")


@pytest.mark.parametrize("mode", ["legacy", "standard"])
def test_invalid_business_timezone_only_affects_standard_sms_time(monkeypatch, mode):
    shield = make_shield()
    shield.config["notice_config"]["notice_way"] = ["mail", "sms"]
    shield.parse_notice_receivers = lambda: ["alice"]
    mode_read = Mock(return_value=mode)
    monkeypatch.setattr(shield_obj, "get_sms_template_mode", mode_read)
    get_business_timezone = Mock(return_value="Invalid/Zone")
    monkeypatch.setattr(shield_obj, "business_timezone", get_business_timezone)
    sender = Mock()
    sender.return_value.send.return_value = {"alice": {"result": True}}
    monkeypatch.setattr(shield_obj, "Sender", sender)

    result = shield.send_notice("start")

    assert list(result) == ["mail", "sms"]
    mode_read.assert_called_once_with()
    context = sender.call_args.kwargs["context"]
    if mode == "standard":
        assert context["sms_event_time_formatted"] == "时间未知"
        get_business_timezone.assert_called_once()
    else:
        assert "sms_event_time_formatted" not in context
        get_business_timezone.assert_not_called()


def test_standard_shield_time_is_frozen_before_sender_changes_timezone(monkeypatch):
    shield = make_shield()
    shield.config["notice_config"]["notice_way"] = ["mail", "sms"]
    shield.parse_notice_receivers = lambda: ["alice"]
    shield._sms_start_notice_probe = arrow.get("2026-09-09T10:01:00+00:00")
    monkeypatch.setattr(shield_obj, "get_sms_template_mode", lambda: "standard")
    contexts = []

    def sender(**kwargs):
        contexts.append(kwargs)
        timezone.activate("America/Los_Angeles")
        return SimpleNamespace(content="rendered", send=lambda *args: {})

    monkeypatch.setattr(shield_obj, "Sender", sender)
    shield.send_notice("start")

    assert contexts[-1]["context"]["sms_event_time_formatted"] == "2026年9月9日 18:00分"
    assert all(context["sms_template_mode"] == "standard" for context in contexts)


@pytest.mark.parametrize("notice_type", ["start", "end"])
@pytest.mark.parametrize("cycle", ["single", "daily", "weekly", "monthly", "two_hours", "ten_years"])
def test_english_shield_sends_real_translated_duration(monkeypatch, settings, cycle, notice_type):
    settings.DEFAULT_LOCALE = "en"
    settings.SMS_NOTICE_TEMPLATE_MODE = "standard"
    settings.SMS_CONTENT_LENGTH = 50
    assert send.i18n is not None
    # These settings are captured when an English-default process initializes I18N.
    monkeypatch.setattr(send.i18n, "default_locale", settings.DEFAULT_LOCALE)
    monkeypatch.setattr(send.i18n, "default_timezone", "UTC")
    with translation.override("en"):
        # Shield duration labels are non-lazy module constants, translated at import.
        for field, message in {
            "CYCLE_ONCE": "次",
            "CYCLE_DAILY": "天",
            "CYCLE_WEEKLY": "周",
            "CYCLE_MONTHLY": "月",
            "LESS_THAN_AN_HOUR_TEMPLATE": "<1小时/{}",
            "HOURS_TEMPLATE": "{}小时/{}",
        }.items():
            monkeypatch.setattr(shield_utils, field, translation.gettext(message))

        cycle_type = {"daily": 2, "weekly": 3, "monthly": 4}.get(cycle, 1)
        matcher_class = {2: TimeMatchByDay, 3: TimeMatchByWeek, 4: TimeMatchByMonth}.get(cycle_type, TimeMatchBySingle)
        shield = make_shield(matcher_class, end="10:30:00", type=cycle_type, week_list=[3], day_list=[9])
        start = datetime(2026, 9, 9, 10, tzinfo=datetime_timezone.utc)
        finish = start + {"two_hours": timedelta(hours=2), "ten_years": timedelta(days=3650)}.get(
            cycle, timedelta(minutes=30)
        )
        if cycle_type == 1:
            shield.config.update(begin_time=start, end_time=finish)
            shield.time_check = TimeMatchBySingle(shield.config["cycle_config"], arrow.get(start), arrow.get(finish))
        shield.config["notice_config"]["notice_way"] = ["sms"]
        shield.display_manager = DisplayManager()
        monkeypatch.setattr(shield.display_manager, "get_category_name", lambda config: "Alert")
        monkeypatch.setattr(shield.display_manager, "get_shield_content", lambda config: "legacy description")
        shield.parse_notice_receivers = lambda: ["alice"]
        duration = shield.display_manager.get_cycle_duration(shield.config)
        if cycle not in ("two_hours", "ten_years"):
            assert duration.startswith("<1 hour / ")
        boundary = start if notice_type == "start" else finish
        shield.get_now_datetime = lambda: arrow.get(boundary - timedelta(minutes=4 if notice_type == "start" else 5))
        lock_storage(monkeypatch, value="lock" if notice_type == "end" else None)
        assert getattr(shield, f"can_send_{notice_type}_notice")() is True
        monkeypatch.setattr(shield_obj, "bk_biz_id_to_bk_tenant_id", lambda value: "tenant-fixture")
        monkeypatch.setattr(send.GlobalConfig, "get", lambda *args: "BlueKing")
        gateway = Mock(return_value={"username_check": {"invalid": []}, "message": "ok"})
        monkeypatch.setattr(send.api.cmsi, "send_sms", gateway)

        result = shield.send_notice(notice_type)

    assert result["sms"]["alice"]["result"] is True
    body = gateway.call_args.kwargs["content"]
    assert sms_utf16_length(body) <= 70
    assert duration in body
    assert ("Start" if notice_type == "start" else "End") in body
    assert body.endswith("See WeCom/BK.")
    assert send.i18n.get_locale() == "en"
