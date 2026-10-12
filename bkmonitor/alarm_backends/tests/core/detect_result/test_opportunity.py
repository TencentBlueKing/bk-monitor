from unittest.mock import call

from alarm_backends.core.cache import key
from alarm_backends.core.detect_result import CheckResult
from alarm_backends.core.detect_result import opportunity


def test_opportunity_minute_is_stable_and_in_cycle_middle():
    minute = opportunity.opportunity_minute("group-a")

    assert minute == opportunity.opportunity_minute("group-a")
    assert 30 <= minute < 90


def test_claim_only_writes_marker_in_group_candidate_minute(mocker):
    group_key = "group-a"
    cycle_id = 7
    candidate_timestamp = (
        cycle_id * opportunity.OPPORTUNITY_PERIOD_SECONDS + opportunity.opportunity_minute(group_key) * 60
    )
    marker = mocker.patch.object(key, "CHECK_RESULT_OPPORTUNITY_TRIM_MARKER_KEY")
    marker.get_key.return_value = "marker-key"
    marker.client.set.return_value = True

    assert opportunity.claim_opportunity_trim(group_key, candidate_timestamp - 60) is False
    marker.client.set.assert_not_called()

    assert opportunity.claim_opportunity_trim(group_key, candidate_timestamp) is True
    marker.get_key.assert_called_once_with(strategy_group_key=group_key, cycle_id=cycle_id)
    marker.client.set.assert_called_once_with(
        "marker-key",
        1,
        ex=opportunity.OPPORTUNITY_MARKER_TTL_SECONDS,
        nx=True,
    )


def test_trim_strategy_group_uses_bounded_hscan_and_zrem_only(mocker):
    strategy = {
        "id": 1,
        "detects": [],
        "items": [{"id": 11, "no_data_config": {"is_enabled": False}}],
    }
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_group_detail",
        return_value={"1": [11]},
    )
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_by_ids",
        return_value=[strategy],
    )
    mocker.patch.object(opportunity, "detect_result_point_required", return_value=30)
    last_checkpoint_key = mocker.patch.object(key, "LAST_CHECKPOINTS_CACHE_KEY")
    last_checkpoint_key.get_key.return_value = "checkpoint-key"
    last_checkpoint_key.client.hscan.side_effect = [
        (5, {"checkpoint.dimension-a.1": 100}),
        (0, {"checkpoint.dimension-b.1": 200}),
    ]
    check_result_key = mocker.patch.object(key, "CHECK_RESULT_CACHE_KEY")
    check_result_key.get_key.side_effect = ["result-a", "result-b"]
    trim = mocker.patch.object(CheckResult, "trim_check_result_caches", side_effect=[[2], [3]])

    result = opportunity.trim_strategy_group("group-a")

    assert result == {
        "strategy_count": 1,
        "item_count": 1,
        "scanned_fields": 2,
        "zrem_commands": 2,
        "removed_members": 5,
    }
    assert last_checkpoint_key.client.hscan.call_args_list == [
        call(
            "checkpoint-key",
            cursor=0,
            count=opportunity.settings.CHECK_RESULT_CLEAN_HSCAN_COUNT,
        ),
        call(
            "checkpoint-key",
            cursor=5,
            count=opportunity.settings.CHECK_RESULT_CLEAN_HSCAN_COUNT,
        ),
    ]
    assert trim.call_args_list == [
        call(["result-a"], 30),
        call(["result-b"], 30),
    ]
    last_checkpoint_key.client.hkeys.assert_not_called()
    check_result_key.client.zcard.assert_not_called()
    last_checkpoint_key.client.hdel.assert_not_called()


def test_trim_strategy_group_skips_unsafe_no_data_item(mocker):
    strategy = {
        "id": 1,
        "detects": [],
        "items": [{"id": 11, "no_data_config": {"is_enabled": True, "continuous": 40}}],
    }
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_group_detail",
        return_value={"1": [11]},
    )
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_by_ids",
        return_value=[strategy],
    )
    mocker.patch.object(opportunity, "detect_result_point_required", return_value=30)
    last_checkpoint_key = mocker.patch.object(key, "LAST_CHECKPOINTS_CACHE_KEY")

    result = opportunity.trim_strategy_group("group-a")

    assert result["item_count"] == 0
    last_checkpoint_key.client.hscan.assert_not_called()


def test_trim_strategy_group_skips_invalid_no_data_config(mocker):
    strategy = {
        "id": 1,
        "detects": [],
        "items": [{"id": 11, "no_data_config": []}],
    }
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_group_detail",
        return_value={"1": [11]},
    )
    mocker.patch.object(
        opportunity.StrategyCacheManager,
        "get_strategy_by_ids",
        return_value=[strategy],
    )
    mocker.patch.object(opportunity, "detect_result_point_required", return_value=30)
    last_checkpoint_key = mocker.patch.object(key, "LAST_CHECKPOINTS_CACHE_KEY")

    result = opportunity.trim_strategy_group("group-a")

    assert result["item_count"] == 0
    last_checkpoint_key.client.hscan.assert_not_called()
