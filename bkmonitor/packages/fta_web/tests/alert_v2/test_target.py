from types import SimpleNamespace

import pytest

from constants.data_source import DataSourceLabel
from fta_web.alert_v2 import target as target_module
from fta_web.alert_v2.target import DefaultTarget


def test_default_target_merges_addition_for_non_clustering_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    query_config = {
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
        "index_set_id": 100,
        "query_string": 'message: "failed"',
        "agg_condition": [],
    }
    alert = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2),
        origin_alarm={
            "data": {
                "dimensions": {"service": "api"},
                "dimension_fields": ["service"],
            }
        },
    )

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: query_config)
    monkeypatch.setattr(target_module, "get_log_clustering_info", lambda _: ("", ""))
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 100, "index_set_name": "application"}],
    )

    result = DefaultTarget(alert).list_related_log_targets()

    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "application",
            "addition": [],
            "keyword": '(message: "failed") AND (service: "api")',
        }
    ]


def test_default_target_clustering_keeps_addition_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    query_config = {
        "query_string": 'message: "failed"',
        "agg_condition": [],
    }
    alert = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2),
        origin_alarm={
            "data": {
                "dimensions": {"service": "api"},
                "dimension_fields": ["service"],
            }
        },
    )

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: query_config)
    monkeypatch.setattr(target_module, "get_log_clustering_info", lambda _: ("count", "100"))
    monkeypatch.setattr(target_module, "get_log_clustering_time_range", lambda *_: None)
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 100, "index_set_name": "clustering"}],
    )

    result = DefaultTarget(alert).list_related_log_targets()

    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "clustering",
            "addition": [{"field": "service", "operator": "=", "value": ["api"]}],
            "keyword": "",
        }
    ]
