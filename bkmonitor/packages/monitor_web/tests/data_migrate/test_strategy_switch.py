from contextlib import nullcontext
from types import SimpleNamespace

from monitor_web.data_migrate import data_rebuilder


class _FakeStrategyQuerySet:
    def __init__(self, rows, events):
        self.rows = rows
        self.events = events

    def values_list(self, field_name, flat=False):
        assert field_name == "id"
        assert flat is True
        return [row["id"] for row in self.rows]

    def update(self, **kwargs):
        self.events.append("strategy_update")
        for row in self.rows:
            row.update(kwargs)
        return len(self.rows)


class _FakeStrategyManager:
    def __init__(self, rows, events):
        self.rows = rows
        self.events = events

    def select_for_update(self):
        return self

    def filter(self, **kwargs):
        matched_rows = self.rows
        for field_name, expected_value in kwargs.items():
            if field_name == "id__in":
                matched_rows = [row for row in matched_rows if row["id"] in expected_value]
            else:
                matched_rows = [row for row in matched_rows if row[field_name] == expected_value]
        return _FakeStrategyQuerySet(matched_rows, self.events)


class _FakeApplicationConfigQuerySet:
    def __init__(self, record):
        self.record = record

    def first(self):
        return self.record


class _FakeApplicationConfigManager:
    def __init__(self, records, events):
        self.records = records
        self.events = events

    def select_for_update(self):
        return self

    def filter(self, **kwargs):
        return _FakeApplicationConfigQuerySet(self.records.get((kwargs["cc_biz_id"], kwargs["key"])))

    def update_or_create(self, *, cc_biz_id, key, defaults):
        self.events.append("config_update")
        record_key = (cc_biz_id, key)
        record = self.records.get(record_key)
        if record is None:
            record = SimpleNamespace(value=defaults["value"])
            self.records[record_key] = record
            return record, True
        record.value = defaults["value"]
        return record, False


def _setup_fake_models(monkeypatch, strategy_rows, config_records, events):
    monkeypatch.setattr(data_rebuilder.transaction, "atomic", nullcontext)
    monkeypatch.setattr(
        data_rebuilder.StrategyModel,
        "objects",
        _FakeStrategyManager(strategy_rows, events),
    )
    monkeypatch.setattr(
        data_rebuilder.ApplicationConfig,
        "objects",
        _FakeApplicationConfigManager(config_records, events),
    )


def test_disable_enabled_strategies_records_ids_before_disabling(monkeypatch):
    events = []
    strategy_rows = [
        {"id": 1, "bk_biz_id": 2, "is_enabled": True, "update_user": "admin"},
        {"id": 2, "bk_biz_id": 2, "is_enabled": True, "update_user": "admin"},
        {"id": 3, "bk_biz_id": 2, "is_enabled": False, "update_user": "admin"},
        {"id": 4, "bk_biz_id": 3, "is_enabled": True, "update_user": "admin"},
    ]
    config_key = (2, data_rebuilder.DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY)
    config_records = {
        config_key: SimpleNamespace(
            value={
                data_rebuilder.STRATEGY_CLOSE_RECORDS_MODEL_LABEL: [3, "1", "invalid"],
                data_rebuilder.UPTIME_CHECK_CLOSE_RECORDS_MODEL_LABEL: [9],
            }
        )
    }
    _setup_fake_models(monkeypatch, strategy_rows, config_records, events)

    result = data_rebuilder.disable_enabled_strategies([2])

    assert events == ["config_update", "strategy_update"]
    assert config_records[config_key].value == {
        data_rebuilder.STRATEGY_CLOSE_RECORDS_MODEL_LABEL: [1, 2, 3],
        data_rebuilder.UPTIME_CHECK_CLOSE_RECORDS_MODEL_LABEL: [9],
    }
    assert [(row["id"], row["is_enabled"], row["update_user"]) for row in strategy_rows] == [
        (1, False, "system"),
        (2, False, "system"),
        (3, False, "admin"),
        (4, True, "admin"),
    ]
    assert result == {
        2: {
            "enabled_count": 2,
            "previously_recorded_count": 2,
            "newly_recorded_count": 1,
            "recorded_count": 3,
            "disabled_count": 2,
            "dry_run": False,
        }
    }


def test_disable_enabled_strategies_dry_run_does_not_write(monkeypatch):
    events = []
    strategy_rows = [{"id": 1, "bk_biz_id": -4759, "is_enabled": True, "update_user": "admin"}]
    config_records = {}
    _setup_fake_models(monkeypatch, strategy_rows, config_records, events)

    result = data_rebuilder.disable_enabled_strategies([-4759], dry_run=True)

    assert events == []
    assert config_records == {}
    assert strategy_rows[0]["is_enabled"] is True
    assert result[-4759] == {
        "enabled_count": 1,
        "previously_recorded_count": 0,
        "newly_recorded_count": 1,
        "recorded_count": 1,
        "disabled_count": 0,
        "dry_run": True,
    }
