"""CHECK_RESULT member-count retention rules."""

import pytest

from alarm_backends.core.detect_result_retention import (
    InvalidRetentionConfig,
    calculate_item_retention,
    is_item_rank_trim_eligible,
    rank_trim_stop,
)


def _detect(level, trigger_window=5, recovery_window=5):
    return {
        "level": level,
        "trigger_config": {"check_window": trigger_window},
        "recovery_config": {"check_window": recovery_window},
    }


def _item(*levels, data_type="time_series", no_data_config=None):
    return {
        "algorithms": [{"level": level, "type": "Threshold"} for level in levels],
        "query_configs": [{"data_type_label": data_type}],
        "no_data_config": no_data_config or {"is_enabled": False},
    }


def test_default_retention_is_twelve_without_usable_windows():
    assert calculate_item_retention({"detects": []}, _item()) == 12


def test_retention_only_uses_levels_owned_by_current_item():
    strategy = {"detects": [_detect(1), _detect(2, trigger_window=100, recovery_window=100)]}

    assert calculate_item_retention(strategy, _item(1)) == 12


def test_retention_uses_largest_current_item_level_window():
    strategy = {"detects": [_detect(1), _detect(2, trigger_window=10, recovery_window=3)]}

    assert calculate_item_retention(strategy, _item(1, 2)) == 15


def test_retention_includes_enabled_no_data_window():
    strategy = {"detects": [_detect(1, trigger_window=1, recovery_window=1)]}
    item = _item(1, no_data_config={"is_enabled": True, "continuous": 20})

    assert calculate_item_retention(strategy, item) == 22


def test_aiops_only_strategy_uses_effective_trigger_window():
    strategy = {"detects": [_detect(1, trigger_window="ignored", recovery_window=7)]}

    assert calculate_item_retention(strategy, _item(1), aiops_only=True) == 14


@pytest.mark.parametrize("invalid", [True, False, 0, -1, 1.5, "invalid"])
def test_explicit_invalid_detect_window_is_rejected(invalid):
    strategy = {"detects": [_detect(1, trigger_window=invalid)]}

    with pytest.raises(InvalidRetentionConfig):
        calculate_item_retention(strategy, _item(1))


@pytest.mark.parametrize("invalid", [True, False, 0, -1, 1.5, "invalid"])
def test_explicit_invalid_no_data_window_is_rejected(invalid):
    item = _item(no_data_config={"is_enabled": True, "continuous": invalid})

    with pytest.raises(InvalidRetentionConfig):
        calculate_item_retention({"detects": []}, item)


@pytest.mark.parametrize("invalid", [False, 0, "invalid", []])
def test_explicit_invalid_no_data_config_is_rejected(invalid):
    item = _item()
    item["no_data_config"] = invalid

    with pytest.raises(InvalidRetentionConfig):
        calculate_item_retention({"detects": []}, item)


def test_missing_selected_level_config_falls_back_to_twelve():
    assert calculate_item_retention({"detects": []}, _item(1)) == 12


@pytest.mark.parametrize(
    ("data_types", "expected"),
    [
        (["time_series"], True),
        (["log"], True),
        (["time_series", "log"], True),
        (["event"], False),
        (["time_series", "event"], False),
        ([], False),
    ],
)
def test_rank_trim_eligibility_excludes_event_and_unknown_items(data_types, expected):
    item = {"query_configs": [{"data_type_label": value} for value in data_types]}

    assert is_item_rank_trim_eligible(item) is expected


def test_rank_trim_stop_keeps_exact_retention_count():
    assert rank_trim_stop(12) == -13


@pytest.mark.parametrize("invalid", [True, 0, -1])
def test_rank_trim_stop_rejects_invalid_count(invalid):
    with pytest.raises(InvalidRetentionConfig):
        rank_trim_stop(invalid)
