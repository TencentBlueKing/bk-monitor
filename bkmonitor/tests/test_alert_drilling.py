import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bkmonitor.utils.alert_drilling import (
    ClusteringType,
    build_log_search_condition,
    get_log_clustering_filter_dict,
    get_log_clustering_info,
)
from bkmonitor.utils.event_related_info import get_clustering_log


def _clustering_alert(agg_dimension, agg_condition, dimensions):
    query_config = {
        "data_source_label": "bk_log_search",
        "data_type_label": "log",
        "agg_dimension": agg_dimension,
        "agg_condition": agg_condition,
    }
    return SimpleNamespace(
        id="1",
        strategy={"items": [{"query_configs": [query_config]}]},
        origin_alarm={"data": {"dimensions": dimensions}},
        event=SimpleNamespace(bk_biz_id=2),
    )


@pytest.mark.parametrize("clustering_type", [ClusteringType.COUNT, ClusteringType.NEW_CLASS])
def test_get_log_clustering_filter_dict_uses_signature_for_signature_strategy(clustering_type) -> None:
    alert = _clustering_alert(
        ["signature"],
        [{"key": "signature", "method": "exists", "value": [""]}],
        {"signature": "abc"},
    )

    assert get_log_clustering_filter_dict(alert, clustering_type) == {"signature": ["abc"]}


def test_get_log_clustering_filter_dict_keeps_dist_field_for_legacy_strategy() -> None:
    alert = _clustering_alert(
        ["signature", "service"],
        [{"key": "__dist_05", "method": "neq", "value": [""]}],
        {"signature": "abc", "service": "api"},
    )

    assert get_log_clustering_filter_dict(alert, ClusteringType.NEW_CLASS) == {"__dist_09": ["abc"]}


def test_get_clustering_log_uses_signature_dimension_without_pattern_level() -> None:
    alert = _clustering_alert(["signature"], [], {})
    log_data_source = MagicMock(time_field="dtEventTimeStamp")
    record = {"log": "hello", "signature": "abc", "__log_signature": "abc", "__log_cluster_publish_revision": 3}
    uq = MagicMock()
    uq.query_log.return_value = ([record], 1)
    search_pattern = MagicMock(return_value=[{"pattern": "hello #NUMBER#", "owners": [], "remark": []}])

    with (
        patch("bkmonitor.utils.event_related_info.load_data_source") as load_data_source,
        patch("bkmonitor.utils.event_related_info.UnifyQuery", return_value=uq),
        patch(
            "bkmonitor.utils.event_related_info.api",
            new=SimpleNamespace(log_search=SimpleNamespace(search_pattern=search_pattern)),
        ),
    ):
        load_data_source.return_value.init_by_query_config.return_value = log_data_source
        content = get_clustering_log(alert, "1", 0, 60, {"signature": ["abc"]}, ["signature"], {"signature": "abc"})

    agg_condition = load_data_source.return_value.init_by_query_config.call_args.args[0]["agg_condition"]
    assert agg_condition == [{"key": "signature", "method": "eq", "value": ["abc"]}]
    pattern_params = search_pattern.call_args.args[0]
    assert "pattern_level" not in pattern_params
    assert pattern_params["addition"] == [{"field": "signature", "operator": "=", "value": "abc"}]
    record = json.loads(content)
    assert record["pattern"] == "hello #NUMBER#"
    assert not {"signature", "__log_signature", "__log_cluster_publish_revision"} & record.keys()


def test_build_log_search_condition_merge_keyword_with_filters() -> None:
    result = build_log_search_condition(
        query_config={
            "query_string": 'message: "failed"',
            "agg_condition": [
                {"key": "level", "method": "neq", "value": ["debug"], "condition": "and"},
                {"key": "content", "method": "include", "value": ["timeout"], "condition": "and"},
            ],
        },
        dimensions={"service": "api"},
        is_merge2keyword=True,
    )

    assert result["keyword"] == (
        '(message: "failed") AND (service: "api" AND NOT level: "debug" AND content: *timeout*)'
    )
    assert result["addition"] == []


def test_build_log_search_condition_keep_ui_mode_without_effective_keyword() -> None:
    query_config = {
        "agg_condition": [{"key": "level", "method": "eq", "value": ["error"], "condition": "and"}],
    }

    empty_keyword_result = build_log_search_condition(
        query_config={**query_config, "query_string": ""},
        dimensions={},
        is_merge2keyword=True,
    )
    wildcard_keyword_result = build_log_search_condition(
        query_config={**query_config, "query_string": " * "},
        dimensions={},
        is_merge2keyword=True,
    )

    expected_addition = [{"field": "level", "operator": "=", "value": ["error"]}]
    assert empty_keyword_result == {"addition": expected_addition, "keyword": ""}
    assert wildcard_keyword_result == {"addition": expected_addition, "keyword": " * "}


def test_build_log_search_condition_keeps_separate_filters_by_default() -> None:
    result = build_log_search_condition(
        query_config={
            "query_string": 'message: "failed"',
            "agg_condition": [{"key": "level", "method": "eq", "value": ["error"], "condition": "and"}],
        },
        dimensions={},
    )

    assert result == {
        "addition": [{"field": "level", "operator": "=", "value": ["error"]}],
        "keyword": 'message: "failed"',
    }


def test_build_log_search_condition_merge_scalar_values_and_skip_empty_values() -> None:
    result = build_log_search_condition(
        query_config={
            "query_string": 'message: "failed"',
            "agg_condition": [
                {"key": "level", "method": "eq", "value": "error", "condition": "and"},
                {"key": "status_code", "method": "eq", "value": 500, "condition": "and"},
                {"key": "service", "method": "eq", "value": [], "condition": "and"},
            ],
        },
        dimensions={},
        is_merge2keyword=True,
    )

    assert result == {
        "addition": [],
        "keyword": '(message: "failed") AND (level: "error" AND status_code: 500)',
    }


def test_get_log_clustering_info_returns_empty_strings_without_clustering_label() -> None:
    assert get_log_clustering_info({}) == ("", "")
