from bkmonitor.utils.alert_drilling import build_log_search_condition, get_log_clustering_info


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
