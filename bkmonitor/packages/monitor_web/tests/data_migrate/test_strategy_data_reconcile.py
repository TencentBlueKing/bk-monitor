from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID

MODULE_PATH = Path(__file__).resolve().parents[2] / "data_migrate" / "strategy_data_reconcile.py"
SPEC = spec_from_file_location("strategy_data_reconcile_for_test", MODULE_PATH)
strategy_data_reconcile = module_from_spec(SPEC)
SPEC.loader.exec_module(strategy_data_reconcile)


def _strategy_config(
    strategy_id: int,
    *,
    data_source_label: str = DataSourceLabel.CUSTOM,
    data_type_label: str = DataTypeLabel.TIME_SERIES,
    result_table_id: str = "demo.table",
    metric_id: str = "custom.demo.metric",
) -> dict:
    return {
        "id": strategy_id,
        "name": f"strategy-{strategy_id}",
        "bk_biz_id": 2,
        "scenario": "os",
        "type": "monitor",
        "items": [
            {
                "id": strategy_id * 10,
                "query_configs": [
                    {
                        "data_source_label": data_source_label,
                        "data_type_label": data_type_label,
                        "result_table_id": result_table_id,
                        "metric_id": metric_id,
                    }
                ],
            }
        ],
    }


def test_collect_strategy_data_stats_skips_system_event_and_aggregates(monkeypatch):
    strategy_configs = {
        1: _strategy_config(1),
        2: _strategy_config(
            2,
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.EVENT,
            result_table_id=SYSTEM_EVENT_RT_TABLE_ID,
            metric_id="bk_monitor.oom-gse",
        ),
    }

    monkeypatch.setattr(strategy_data_reconcile, "_get_strategy_configs", lambda bk_biz_id: strategy_configs)
    monkeypatch.setattr(
        strategy_data_reconcile,
        "_collect_one_strategy_stats",
        lambda **kwargs: {
            "strategy_id": kwargs["strategy_id"],
            "strategy_name": "strategy-1",
            "bk_biz_id": 2,
            "scenario": "os",
            "type": "monitor",
            "items": [],
            "raw_data_point_count": 5,
            "data_point_count": 4,
            "dimension_combination_count": 3,
            "error_count": 0,
            "errors": [],
        },
    )

    result = strategy_data_reconcile.collect_strategy_data_stats(
        bk_biz_id=2,
        start_time=100,
        end_time=200,
    )

    assert result["strategy_count"] == 1
    assert result["skipped_strategy_count"] == 1
    assert result["raw_data_point_count"] == 5
    assert result["data_point_count"] == 4
    assert result["dimension_combination_count"] == 3
    assert result["max_workers"] == strategy_data_reconcile.DEFAULT_STRATEGY_WORKERS
    assert result["strategies"][0]["strategy_id"] == 1
    assert result["skipped"][0]["strategy_id"] == 2
    assert result["skipped"][0]["reason"] == "system event strategy uses kafka and is not query-countable"


def test_collect_strategy_data_stats_filters_strategy_ids(monkeypatch):
    strategy_configs = {1: _strategy_config(1), 3: _strategy_config(3)}
    collected_ids = []

    monkeypatch.setattr(strategy_data_reconcile, "_get_strategy_configs", lambda bk_biz_id: strategy_configs)

    def fake_collect_one_strategy_stats(**kwargs):
        collected_ids.append(kwargs["strategy_id"])
        return {
            "strategy_id": kwargs["strategy_id"],
            "strategy_name": f"strategy-{kwargs['strategy_id']}",
            "bk_biz_id": 2,
            "scenario": "os",
            "type": "monitor",
            "items": [],
            "raw_data_point_count": 0,
            "data_point_count": 0,
            "dimension_combination_count": 0,
            "error_count": 0,
            "errors": [],
        }

    monkeypatch.setattr(strategy_data_reconcile, "_collect_one_strategy_stats", fake_collect_one_strategy_stats)

    result = strategy_data_reconcile.collect_strategy_data_stats(
        bk_biz_id=2,
        start_time=100,
        end_time=200,
        strategy_ids=[3],
    )

    assert collected_ids == [3]
    assert result["selected_strategy_ids"] == [3]
    assert [strategy["strategy_id"] for strategy in result["strategies"]] == [3]


def test_collect_strategy_data_stats_uses_max_workers_and_keeps_strategy_order(monkeypatch):
    strategy_configs = {3: _strategy_config(3), 1: _strategy_config(1)}

    monkeypatch.setattr(strategy_data_reconcile, "_get_strategy_configs", lambda bk_biz_id: strategy_configs)
    monkeypatch.setattr(
        strategy_data_reconcile,
        "_collect_one_strategy_stats",
        lambda **kwargs: {
            "strategy_id": kwargs["strategy_id"],
            "strategy_name": f"strategy-{kwargs['strategy_id']}",
            "bk_biz_id": 2,
            "scenario": "os",
            "type": "monitor",
            "items": [],
            "raw_data_point_count": kwargs["strategy_id"],
            "data_point_count": kwargs["strategy_id"],
            "dimension_combination_count": 1,
            "error_count": 0,
            "errors": [],
        },
    )

    result = strategy_data_reconcile.collect_strategy_data_stats(
        bk_biz_id=2,
        start_time=100,
        end_time=200,
        max_workers=2,
    )

    assert result["max_workers"] == 2
    assert [strategy["strategy_id"] for strategy in result["strategies"]] == [1, 3]
    assert result["data_point_count"] == 4


def test_is_system_event_strategy_matches_metric_id_without_result_table():
    strategy_config = _strategy_config(
        1,
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.EVENT,
        result_table_id="",
        metric_id="bk_monitor.oom-gse",
    )

    assert strategy_data_reconcile._is_system_event_strategy(strategy_config) is True


def test_summarize_records_counts_stable_dimension_keys():
    class FakeRecord:
        def __init__(self, dimensions, record_time):
            self.data = {"dimensions": dimensions, "time": record_time}

    result = strategy_data_reconcile._summarize_records(
        records=[
            FakeRecord({"b": 2, "a": 1}, 100),
            FakeRecord({"a": 1, "b": 2}, 160),
            FakeRecord({"a": 3}, 220),
        ],
        include_dimension_keys=True,
    )

    assert result["data_point_count"] == 3
    assert result["dimension_combination_count"] == 2
    assert result["first_data_time"] == 100
    assert result["last_data_time"] == 220
    assert result["dimension_counts"] == {'{"a":1,"b":2}': 2, '{"a":3}': 1}
