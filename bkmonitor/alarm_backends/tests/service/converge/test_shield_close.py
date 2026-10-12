"""Close shields keep ownership separate from ordinary notification shielding."""

import os
import time
from types import SimpleNamespace
from unittest.mock import Mock

import arrow
import pytest
from django.utils import timezone

from alarm_backends.core.alert.alert import Alert
from alarm_backends.service.converge.shield.close import CloseShieldMatcher
from alarm_backends.service.converge.shield.shield_obj import AlertShieldObj
from alarm_backends.service.converge.shield import window
from alarm_backends.service.converge.shield.window import matching_window
from bkmonitor.utils.range.period import TimeMatchByDay, TimeMatchByMonth, TimeMatchBySingle, TimeMatchByWeek


@pytest.fixture(autouse=True)
def utc_timezone(monkeypatch):
    monkeypatch.setattr("django.conf.settings.TIME_ZONE", "UTC")
    monkeypatch.setattr(window.BusinessManager, "get", lambda *args: SimpleNamespace(time_zone="UTC"))
    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        with timezone.override("UTC"):
            yield
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


def matcher(cls=TimeMatchByDay, start="10:00:00", end="11:00:00", **cycle):
    return cls(
        {"begin_time": start, "end_time": end, **cycle},
        arrow.get("2026-09-01T00:00:00+00:00"),
        arrow.get("2026-10-01T00:00:00+00:00"),
    )


@pytest.mark.parametrize(
    "cls,cycle", [(TimeMatchByDay, {}), (TimeMatchByWeek, {"week_list": [3]}), (TimeMatchByMonth, {"day_list": [9]})]
)
def test_periodic_windows_identify_current_occurrence(cls, cycle):
    at = arrow.get("2026-09-09T10:30:00+00:00")
    begin, end = matching_window(matcher(cls, **cycle), at)
    assert begin == arrow.get("2026-09-09T10:00:00+00:00").timestamp
    assert end == arrow.get("2026-09-09T11:00:00+00:00").timestamp
    assert at.replace(days=-1).timestamp < begin


@pytest.mark.parametrize("at", ["2026-09-09T23:30:00+00:00", "2026-09-10T00:30:00+00:00"])
def test_overnight_window(at):
    begin, end = matching_window(matcher(start="23:00:00", end="01:00:00"), arrow.get(at))
    assert begin == arrow.get("2026-09-09T23:00:00+00:00").timestamp
    assert end == arrow.get("2026-09-10T01:00:00+00:00").timestamp


def test_weekly_overnight_respects_existing_day_filter():
    begin, end = matching_window(
        matcher(TimeMatchByWeek, start="23:00:00", end="01:00:00", week_list=[3]),
        arrow.get("2026-09-09T23:30:00+00:00"),
    )
    assert end == arrow.get("2026-09-09T23:59:59+00:00").timestamp
    assert begin == arrow.get("2026-09-09T23:00:00+00:00").timestamp


def test_single_window_and_outside():
    check = matcher(TimeMatchBySingle)
    assert matching_window(check, arrow.get("2026-09-09")) == (
        check.begin_datetime.timestamp,
        check.end_datetime.timestamp,
    )
    assert matching_window(check, arrow.get("2026-11-01")) is None


def test_close_rejects_previous_occurrence_but_default_does_not():
    shield = object.__new__(AlertShieldObj)
    shield.config = {"end_policy": "close"}
    shield.time_check = matcher()
    shield.dimension_check = Mock()
    shield.dimension_check.is_match.return_value = True
    shield.get_dimension = Mock(return_value={})
    alert = SimpleNamespace(begin_time=arrow.get("2026-09-08T10:30:00+00:00").timestamp)
    at = arrow.get("2026-09-09T10:30:00+00:00")
    assert not shield.is_match(alert, at)
    shield.dimension_check.is_match.assert_not_called()
    shield.config["end_policy"] = "notify_once"
    assert shield.is_match(alert, at)


def test_take_over_selects_farthest_end_then_lowest_id(monkeypatch):
    from alarm_backends.service.converge.shield import close

    monkeypatch.setattr(close.arrow, "now", lambda: arrow.get("2026-09-09T10:30:00+00:00"))
    candidates = [
        SimpleNamespace(id=key, time_check=matcher(end=end), is_match=lambda *args: True)
        for key, end in [(3, "11:00:00"), (2, "12:00:00"), (1, "12:00:00")]
    ]
    match = CloseShieldMatcher()
    match.by_business[1] = candidates
    alert = Alert({"status": "ABNORMAL", "event": {"bk_biz_id": 1}})
    monkeypatch.setattr(alert, "to_document", lambda: None)
    match.take_over(alert)
    assert alert.shield_end_close
    assert alert.get_extra_info("shield_end_close_config")["shield_id"] == 1
    match.by_business[1] = []
    match.take_over(alert)
    assert alert.get_extra_info("shield_end_close_config")["shield_id"] == 1
    assert not alert.should_send_signal()


@pytest.mark.parametrize("status", ["RECOVERED", "CLOSED", "ABNORMAL"])
def test_owned_alert_updates_without_ending_or_scheduling(status):
    alert = Alert(
        {
            "status": "ABNORMAL",
            "shield_end_close": True,
            "severity": 2,
            "begin_time": 100,
            "latest_time": 101,
            "event": {},
        }
    )
    event = SimpleNamespace(
        status=status,
        severity=1,
        id="e",
        description="event",
        time=102,
        anomaly_time=100,
        to_dict=lambda: {"severity": 1},
    )
    alert.update(event)
    assert alert.is_abnormal()
    assert not alert.data.get("next_status")
    assert not alert.should_send_signal()


def test_batch_reuses_business_configuration(monkeypatch):
    from alarm_backends.service.converge.shield import close

    fetch = Mock(return_value=[])
    fetch_timezone = Mock(return_value="UTC")
    monkeypatch.setattr(close.ShieldCacheManager, "get_shields_by_biz_id", fetch)
    monkeypatch.setattr(close, "business_timezone", fetch_timezone)
    match = CloseShieldMatcher()
    for _ in range(100):
        match.take_over(Alert({"status": "ABNORMAL", "event": {"bk_biz_id": 1}}))
    fetch.assert_called_once_with(1)
    fetch_timezone.assert_not_called()


def test_batch_reuses_business_timezone(monkeypatch):
    from alarm_backends.service.converge.shield import close

    fetch_timezone = Mock(return_value="UTC")
    monkeypatch.setattr(close, "business_timezone", fetch_timezone)
    shields = CloseShieldMatcher()
    shields.by_business[1] = [SimpleNamespace(is_match=lambda document, now: False)]
    for _ in range(100):
        alert = Alert({"status": "ABNORMAL", "event": {"bk_biz_id": 1}})
        monkeypatch.setattr(alert, "to_document", lambda: None)
        shields.take_over(alert)
    fetch_timezone.assert_called_once_with(1)


def test_public_signal_entry_filters_owned_alert(monkeypatch):
    from alarm_backends.service.alert import processor

    emit = Mock()
    monkeypatch.setattr(processor, "check_action_and_composite", SimpleNamespace(delay=emit))
    owned = SimpleNamespace(is_blocked=False, shield_end_close=True)
    normal = SimpleNamespace(is_blocked=False, shield_end_close=False, key="normal", status="ABNORMAL")
    processor.BaseAlertProcessor.send_signal([owned, normal])
    emit.assert_called_once_with(alert_key="normal", alert_status="ABNORMAL")


def test_queued_composite_rechecks_ownership(monkeypatch):
    from alarm_backends.service.composite import tasks

    monkeypatch.setattr(tasks.Alert, "get", Mock(return_value=SimpleNamespace(shield_end_close=True, id="a")))
    process = Mock()
    monkeypatch.setattr(tasks, "CompositeProcessor", process)
    tasks.check_action_and_composite(SimpleNamespace(alert_id="a", strategy_id=1), "ABNORMAL")
    process.assert_not_called()


def test_match_failure_does_not_abort_other_alerts(monkeypatch):

    bad = Alert({"id": "bad", "status": "ABNORMAL", "event": {"bk_biz_id": 1}})
    good = Alert({"id": "good", "status": "ABNORMAL", "event": {"bk_biz_id": 1}})
    monkeypatch.setattr(bad, "to_document", lambda: "bad")
    monkeypatch.setattr(good, "to_document", lambda: "good")

    def match(document, now):
        if document == "bad":
            raise RuntimeError("strategy cache unavailable")
        return True

    shields = CloseShieldMatcher()
    shields.now = arrow.get("2026-09-09T10:30:00+00:00")
    shields.by_business[1] = [SimpleNamespace(id=1, time_check=matcher(), is_match=match)]
    for alert in [bad, good]:
        shields.take_over(alert)
    assert not bad.shield_end_close
    assert good.shield_end_close


def test_takeover_completes_strategy_snapshot_before_matching(monkeypatch):
    from alarm_backends.service.alert.enricher.strategy import StrategySnapshotEnricher

    alert = Alert({"id": "a", "strategy_id": 1, "status": "ABNORMAL", "event": {"bk_biz_id": 1}})
    snapshot = {"items": [{"query_configs": [{"metric_id": "system.cpu"}]}]}

    def enrich(self, value):
        value.update_extra_info("strategy", snapshot)
        return value

    prepare = Mock(side_effect=enrich)
    monkeypatch.setattr(StrategySnapshotEnricher, "enrich_alert", lambda self, value: prepare(self, value))
    monkeypatch.setattr(alert, "to_document", lambda: alert.get_extra_info("strategy"))
    candidate = SimpleNamespace(id=1, time_check=matcher(), is_match=lambda document, now: document == snapshot)
    shields = CloseShieldMatcher()
    shields.now = arrow.get("2026-09-09T10:30:00+00:00")
    shields.by_business[1] = [candidate]
    shields.take_over(alert)
    assert alert.shield_end_close
    prepare.assert_called_once()


def test_takeover_uses_snapshot_when_strategy_cache_is_missing(monkeypatch):
    from alarm_backends.service.alert.enricher import strategy

    alert = Alert(
        {
            "id": "a",
            "strategy_id": 1,
            "status": "ABNORMAL",
            "event": {"bk_biz_id": 1},
            "extra_info": {"origin_alarm": {"strategy_snapshot_key": "snapshot-key"}},
        }
    )
    snapshot = {"items": [{"query_configs": [{"metric_id": "system.cpu"}]}], "labels": []}
    fetch_snapshot = Mock(return_value=snapshot)
    fetch_cache = Mock(return_value=None)
    monkeypatch.setattr(strategy.Strategy, "get_strategy_snapshot_by_key", fetch_snapshot)
    monkeypatch.setattr(strategy.StrategyCacheManager, "get_strategy_by_id", fetch_cache)
    monkeypatch.setattr(alert, "to_document", lambda: alert.get_extra_info("strategy"))
    shields = CloseShieldMatcher()
    shields.now = arrow.get("2026-09-09T10:30:00+00:00")
    shields.by_business[1] = [
        SimpleNamespace(id=1, time_check=matcher(), is_match=lambda document, now: document == snapshot)
    ]
    shields.take_over(alert)
    assert alert.shield_end_close
    fetch_snapshot.assert_called_once_with("snapshot-key", 1)
    fetch_cache.assert_not_called()
