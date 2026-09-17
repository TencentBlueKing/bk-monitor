"""Close ownership and expiry use business time, including calendar boundaries."""

import os
import time
from types import SimpleNamespace
from unittest.mock import Mock

import arrow
import pytest
from django.utils import timezone

from alarm_backends.service.alert.manager.shield_tasks import shield_is_active
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield import window
from alarm_backends.service.converge.shield.close import CloseShieldMatcher
from alarm_backends.service.converge.shield.window import business_timezone


@pytest.fixture(autouse=True)
def worker_timezone(monkeypatch):
    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    monkeypatch.setattr("django.conf.settings.TIME_ZONE", "Asia/Shanghai")
    with timezone.override("Asia/Shanghai"):
        yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def configuration(cycle):
    return {
        "id": 1,
        "bk_biz_id": 2,
        "end_policy": "close",
        "cycle_config": cycle,
        "begin_time": arrow.get("2026-08-01T00:00:00Z").datetime,
        "end_time": arrow.get("2026-10-01T00:00:00Z").datetime,
        "is_enabled": True,
        "is_deleted": False,
    }


def assert_match(config, at, expected):
    before = timezone.get_current_timezone_name()
    obj = object.__new__(AlertShieldObj)
    obj.config = config
    obj.dimension_check = Mock()
    obj.dimension_check.is_match.return_value = True
    obj.get_dimension = Mock(return_value={})
    obj._parse_cycle_config()
    alert = SimpleNamespace(begin_time=at.timestamp)
    assert obj.is_match(alert, at) is expected
    assert shield_is_active(SimpleNamespace(**config), at) is expected
    assert timezone.get_current_timezone_name() == before


@pytest.mark.parametrize("at,expected", [("2026-09-09T02:30:00Z", False), ("2026-09-09T10:30:00Z", True)])
def test_utc_business_does_not_inherit_shanghai_worker(monkeypatch, at, expected):
    monkeypatch.setattr(
        window.BusinessManager,
        "get",
        lambda *args: SimpleNamespace(time_zone="UTC"),
    )
    config = configuration({"type": 2, "begin_time": "10:00:00", "end_time": "11:00:00"})
    assert_match(config, arrow.get(at), expected)


@pytest.mark.parametrize(
    "cycle,at",
    [
        ({"type": 3, "week_list": [3]}, "2026-09-08T16:30:00Z"),
        ({"type": 4, "day_list": [1]}, "2026-08-31T16:30:00Z"),
        ({"type": 2, "week_list": [3]}, "2026-09-08T16:30:00Z"),
    ],
)
def test_business_calendar_differs_from_os_calendar(monkeypatch, cycle, at):
    monkeypatch.setattr(
        window.BusinessManager,
        "get",
        lambda *args: SimpleNamespace(time_zone="Asia/Shanghai"),
    )
    config = configuration({"begin_time": "00:00:00", "end_time": "01:00:00", **cycle})
    assert_match(config, arrow.get(at), True)


def test_missing_business_uses_configured_default(monkeypatch):
    monkeypatch.setattr(window.BusinessManager, "get", lambda *args: None)
    assert business_timezone(2) == "Asia/Shanghai"


def test_exception_restores_previous_timezone(monkeypatch):
    monkeypatch.setattr(window.BusinessManager, "get", lambda *args: SimpleNamespace(time_zone="UTC"))
    config = configuration({"type": "invalid"})
    obj = object.__new__(AlertShieldObj)
    obj.config = config
    with pytest.raises(ValueError):
        obj._parse_cycle_config()
    assert timezone.get_current_timezone_name() == "Asia/Shanghai"
    with pytest.raises(ValueError):
        shield_is_active(SimpleNamespace(**config), arrow.now())
    assert timezone.get_current_timezone_name() == "Asia/Shanghai"


def test_takeover_mixed_businesses_restores_context(monkeypatch):
    monkeypatch.setattr(
        window.BusinessManager,
        "get",
        lambda biz_id: SimpleNamespace(time_zone="UTC" if biz_id == 1 else "Asia/Shanghai"),
    )
    matcher = CloseShieldMatcher()
    matcher.now = arrow.get("2026-09-09T02:30:00Z")
    for biz_id in (1, 2):
        config = configuration({"type": 2, "begin_time": "10:00:00", "end_time": "11:00:00"})
        config["bk_biz_id"] = biz_id
        shield = object.__new__(AlertShieldObj)
        shield.config = config
        shield.id = biz_id
        shield.dimension_check = Mock()
        shield.dimension_check.is_match.return_value = True
        shield.get_dimension = Mock(return_value={})
        shield._parse_cycle_config()
        matcher.by_business[biz_id] = [shield]
        alert = SimpleNamespace(
            id=str(biz_id),
            strategy_id=None,
            bk_biz_id=biz_id,
            shield_end_close=False,
            is_abnormal=lambda: True,
            to_document=lambda: SimpleNamespace(begin_time=matcher.now.timestamp),
            set=Mock(),
            update_extra_info=Mock(),
            clear_next_status=Mock(),
        )
        with timezone.override("America/New_York"):
            matcher.take_over(alert)
            assert timezone.get_current_timezone_name() == "America/New_York"
        if biz_id == 1:
            alert.set.assert_not_called()
        else:
            alert.set.assert_any_call("shield_end_close", True)
            alert.update_extra_info.assert_called_once()


def test_shield_reuses_resolved_business_timezone(monkeypatch):
    get_business = Mock(return_value=SimpleNamespace(time_zone="UTC"))
    monkeypatch.setattr(window.BusinessManager, "get", get_business)
    obj = object.__new__(AlertShieldObj)
    obj.config = configuration({"type": 2, "begin_time": "10:00:00", "end_time": "11:00:00"})
    obj._parse_cycle_config()
    obj.dimension_check = Mock()
    obj.dimension_check.is_match.return_value = True
    obj.get_dimension = Mock(return_value={})
    at = arrow.get("2026-09-09T10:30:00Z")
    for _ in range(3):
        assert obj.is_match(SimpleNamespace(begin_time=at.timestamp), at)
    get_business.assert_called_once_with(2)
