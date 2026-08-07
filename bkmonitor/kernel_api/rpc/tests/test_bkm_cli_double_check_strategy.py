import json
from unittest import mock

import pytest

from bkmonitor.models.config import GlobalConfig
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry


pytestmark = pytest.mark.django_db

CONFIG_KEY = "DOUBLE_CHECK_SUM_STRATEGY_IDS"


def test_double_check_strategy_ops_are_registered():
    query_op = BkmCliOpRegistry.resolve("query-double-check-strategies")
    manage_op = BkmCliOpRegistry.resolve("manage-double-check-strategy")

    assert query_op.func_name == "bkm_cli.query_double_check_strategies"
    assert query_op.risk_level == "readonly"
    assert query_op.requires_confirmation is False
    assert manage_op.func_name == "bkm_cli.manage_double_check_strategy"
    assert manage_op.risk_level == "mutation"
    assert manage_op.requires_confirmation is True


@pytest.mark.parametrize(
    "params",
    [
        {"operation": "enable", "strategy_id": 2, "operator": "alice"},
        {"operation": "enable", "strategy_id": 2, "operator": "alice", "confirmed": False},
        {"operation": "enable", "strategy_id": 2, "operator": "alice", "confirmed": True, "dry_run": False},
        {"operation": "enable", "strategy_id": 2, "confirmed": True},
    ],
)
def test_management_requires_confirmation_operator_and_rejects_dry_run(params):
    from kernel_api.rpc.functions.bkm_cli.double_check_strategy import manage_double_check_strategy

    with pytest.raises(CustomException):
        manage_double_check_strategy(params)


def test_enable_updates_global_config_and_returns_database_readback(mocker):
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    config, _ = GlobalConfig.objects.update_or_create(key=CONFIG_KEY, defaults={"value": [1], "data_type": "List"})
    mocker.patch.object(double_check_strategy, "_validate_strategy_for_enable")
    clear_cache = mocker.patch.object(double_check_strategy, "_clear_dynamic_setting_cache")

    result = double_check_strategy.manage_double_check_strategy(
        {"operation": "enable", "strategy_id": 2, "confirmed": True, "operator": "alice"}
    )

    config.refresh_from_db()
    assert config.value == [1, 2]
    assert result == {
        "operation": "enable",
        "strategy_id": 2,
        "changed": True,
        "configured_strategy_ids": [1, 2],
        "requested_operator": "alice",
        "db_readback": {
            "present": True,
            "key": CONFIG_KEY,
            "value": [1, 2],
            "update_at": config.update_at,
        },
        "cache_propagation_max_seconds": 180,
    }
    clear_cache.assert_called_once_with(CONFIG_KEY)


def test_disable_can_remove_a_stale_strategy_id(mocker):
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    config, _ = GlobalConfig.objects.update_or_create(key=CONFIG_KEY, defaults={"value": [1, 2], "data_type": "List"})
    clear_cache = mocker.patch.object(double_check_strategy, "_clear_dynamic_setting_cache")

    result = double_check_strategy.manage_double_check_strategy(
        {"operation": "disable", "strategy_id": 2, "confirmed": True, "operator": "alice"}
    )

    config.refresh_from_db()
    assert config.value == [1]
    assert result["changed"] is True
    assert result["configured_strategy_ids"] == [1]
    clear_cache.assert_called_once_with(CONFIG_KEY)


def test_idempotent_disable_without_db_row_does_not_create_an_override(mocker):
    from django.conf import settings

    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    GlobalConfig.objects.filter(key=CONFIG_KEY).delete()
    clear_cache = mocker.patch.object(double_check_strategy, "_clear_dynamic_setting_cache")

    with mock.patch.object(settings, CONFIG_KEY, []):
        result = double_check_strategy.manage_double_check_strategy(
            {"operation": "disable", "strategy_id": 2, "confirmed": True, "operator": "alice"}
        )

    assert GlobalConfig.objects.filter(key=CONFIG_KEY).exists() is False
    assert result["changed"] is False
    assert result["db_readback"] == {"present": False}
    clear_cache.assert_not_called()


def test_impact_reports_group_level_access_and_explicit_detect_scope(mocker):
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[2])
    mocker.patch.object(double_check_strategy, "_strategy_summary", return_value={"strategy_id": 2})
    mocker.patch.object(
        double_check_strategy,
        "_strategy_groups",
        return_value=[
            {
                "strategy_group_key": "group-a",
                "member_strategy_ids": [1, 2],
                "runtime_group_found": True,
                "target_strategy_member_found": True,
            }
        ],
    )

    result = double_check_strategy.query_double_check_strategies(
        {"operation": "impact", "strategy_id": 2, "change": "disable"}
    )

    assert result["detect"] == {"before": True, "after": False}
    assert result["groups"] == [
        {
            "strategy_group_key": "group-a",
            "member_strategy_ids": [1, 2],
            "runtime_group_found": True,
            "target_strategy_member_found": True,
            "configured_member_strategy_ids_before": [2],
            "configured_member_strategy_ids_after": [],
            "access_protected_before": True,
            "access_protected_after": False,
        }
    ]
    assert result["access_impact_complete"] is True


@pytest.mark.parametrize(
    "runtime_groups",
    [
        {},
        {"group-a": json.dumps({"1": [10], "bk_biz_id": 7})},
    ],
)
def test_enable_active_eligible_strategy_without_runtime_membership_is_incomplete(mocker, runtime_groups):
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[])
    mocker.patch.object(
        double_check_strategy,
        "_validate_strategy_for_enable",
        return_value={"strategy_id": 2, "exists": True, "is_enabled": True, "is_invalid": False},
    )
    get_all_groups = mocker.patch.object(StrategyCacheManager, "get_all_groups", return_value=runtime_groups)

    result = double_check_strategy.query_double_check_strategies(
        {"operation": "impact", "strategy_id": 2, "change": "enable"}
    )

    assert result["groups"] == []
    assert result["access_impact_complete"] is False
    get_all_groups.assert_called_once_with()


def test_disable_active_access_eligible_strategy_without_runtime_membership_is_incomplete(mocker):
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[2])
    mocker.patch.object(
        double_check_strategy,
        "_strategy_summary",
        return_value={"strategy_id": 2, "exists": True, "is_enabled": True, "is_invalid": False},
    )
    strategy_config = mocker.patch.object(
        double_check_strategy,
        "_strategy_config",
        return_value=(
            mock.sentinel.strategy,
            {"items": [{"query_configs": [{"data_source_label": "bk_monitor", "data_type_label": "time_series"}]}]},
        ),
    )
    get_all_groups = mocker.patch.object(StrategyCacheManager, "get_all_groups", return_value={})

    result = double_check_strategy.query_double_check_strategies(
        {"operation": "impact", "strategy_id": 2, "change": "disable"}
    )

    assert result["groups"] == []
    assert result["access_impact_complete"] is False
    get_all_groups.assert_called_once_with()
    strategy_config.assert_called_once_with(2)


def test_disable_stale_strategy_uses_one_runtime_group_snapshot(mocker):
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[2])
    mocker.patch.object(
        double_check_strategy,
        "_strategy_summary",
        return_value={"strategy_id": 2, "exists": False},
    )
    strategy_config = mocker.patch.object(double_check_strategy, "_strategy_config", return_value=(None, {}))
    get_all_groups = mocker.patch.object(
        StrategyCacheManager,
        "get_all_groups",
        return_value={
            "group-b": json.dumps({"3": [30], "bk_biz_id": 7}),
            "group-a": json.dumps({"2": [20], "1": [10], "bk_biz_id": 7, "interval_list": [60]}),
        },
    )

    result = double_check_strategy.query_double_check_strategies(
        {"operation": "impact", "strategy_id": 2, "change": "disable"}
    )

    assert result["groups"] == [
        {
            "strategy_group_key": "group-a",
            "runtime_group_found": True,
            "bk_biz_id": 7,
            "member_strategy_ids": [1, 2],
            "target_strategy_member_found": True,
            "configured_member_strategy_ids_before": [2],
            "configured_member_strategy_ids_after": [],
            "access_protected_before": True,
            "access_protected_after": False,
        }
    ]
    assert result["access_impact_complete"] is True
    get_all_groups.assert_called_once_with()
    strategy_config.assert_not_called()


def test_disable_stale_strategy_is_actionable_after_complete_empty_runtime_snapshot(mocker):
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[2])
    mocker.patch.object(
        double_check_strategy,
        "_strategy_summary",
        return_value={"strategy_id": 2, "exists": False},
    )
    strategy_config = mocker.patch.object(double_check_strategy, "_strategy_config", return_value=(None, {}))
    get_all_groups = mocker.patch.object(StrategyCacheManager, "get_all_groups", return_value={})

    result = double_check_strategy.query_double_check_strategies(
        {"operation": "impact", "strategy_id": 2, "change": "disable"}
    )

    assert result["groups"] == []
    assert result["access_impact_complete"] is True
    get_all_groups.assert_called_once_with()
    strategy_config.assert_not_called()


def test_impact_stops_when_runtime_group_snapshot_is_malformed(mocker):
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from kernel_api.rpc.functions.bkm_cli import double_check_strategy

    mocker.patch.object(double_check_strategy, "_configured_strategy_ids", return_value=[2])
    mocker.patch.object(
        double_check_strategy,
        "_strategy_summary",
        return_value={"strategy_id": 2, "exists": False},
    )
    get_all_groups = mocker.patch.object(
        StrategyCacheManager,
        "get_all_groups",
        return_value={"group-a": "not-json"},
    )

    with pytest.raises(CustomException, match="共享查询组缓存结构异常: group-a"):
        double_check_strategy.query_double_check_strategies(
            {"operation": "impact", "strategy_id": 2, "change": "disable"}
        )

    get_all_groups.assert_called_once_with()
