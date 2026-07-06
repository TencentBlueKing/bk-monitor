import pytest
from django.test import override_settings

from bkmonitor.models import ItemModel, QueryConfigModel, StrategyModel
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_migrate import strategy_migration
from monitor_web.management.commands import data_migrate as data_migrate_command
from monitor_web.strategies.default_settings.datalink.v1 import (
    DEFAULT_DATALINK_COLLECTING_FLAG,
    GATHER_UP_DATA_LABEL,
)

LEGACY_RESULT_TABLE_ID = strategy_migration.GATHER_UP_LEGACY_RESULT_TABLE_ID
LEGACY_METRIC_ID = f"bk_monitor.{LEGACY_RESULT_TABLE_ID}.bkm_gather_up"


def _create_legacy_gather_up_strategy(
    *,
    bk_biz_id: int = 2,
    name: str = "集成内置-数据采集系统运行异常告警",
    source: str = DEFAULT_DATALINK_COLLECTING_FLAG,
    result_table_id: str = LEGACY_RESULT_TABLE_ID,
) -> tuple[StrategyModel, ItemModel, QueryConfigModel]:
    strategy = StrategyModel.objects.create(
        name=name,
        bk_biz_id=bk_biz_id,
        source=source,
        scenario="host_process",
        type=StrategyModel.StrategyType.Monitor,
        is_enabled=True,
        is_invalid=False,
        invalid_type="",
        create_user="admin",
        update_user="admin",
    )
    item = ItemModel.objects.create(
        strategy_id=strategy.pk,
        name=name,
        expression="a",
        functions=[],
        origin_sql="",
        no_data_config={"is_enabled": False, "continuous": 5},
        target=[[]],
        metric_type=DataTypeLabel.TIME_SERIES,
    )
    query_config = QueryConfigModel.objects.create(
        strategy_id=strategy.pk,
        item_id=item.pk,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id=LEGACY_METRIC_ID,
        config={
            "result_table_id": result_table_id,
            "metric_field": "bkm_gather_up",
            "agg_method": "COUNT",
            "agg_interval": 60,
            "agg_dimension": ["bk_collect_config_id"],
            "agg_condition": [],
        },
    )
    return strategy, item, query_config


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_gather_up_strategy_config_dry_run_does_not_update():
    _, _, query_config = _create_legacy_gather_up_strategy()

    result = strategy_migration.migrate_gather_up_strategy_config(bk_biz_id=2, dry_run=True)

    assert result["changed_count"] == 1
    assert result["applied_count"] == 0
    assert result["changes"][0]["new_data_label"] == GATHER_UP_DATA_LABEL
    assert result["changes"][0]["new_result_table_id"] == ""

    query_config.refresh_from_db()
    assert query_config.metric_id == LEGACY_METRIC_ID
    assert query_config.config["result_table_id"] == LEGACY_RESULT_TABLE_ID
    assert "data_label" not in query_config.config


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_gather_up_strategy_config_switches_to_data_label():
    _, _, query_config = _create_legacy_gather_up_strategy()

    result = strategy_migration.migrate_gather_up_strategy_config(bk_biz_id=[2], dry_run=False)

    assert result["changed_count"] == 1
    assert result["applied_count"] == 1
    assert result["stale_count"] == 0

    query_config.refresh_from_db()
    assert query_config.config["result_table_id"] == ""
    assert query_config.config["data_label"] == GATHER_UP_DATA_LABEL
    # 其余查询字段保持不变
    assert query_config.config["agg_dimension"] == ["bk_collect_config_id"]
    assert query_config.metric_id == "bk_monitor..bkm_gather_up"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_gather_up_strategy_config_ignores_non_datalink_strategy():
    """仅处理内置采集告警策略，用户自建策略即使引用同一结果表也不迁移。"""
    _, _, query_config = _create_legacy_gather_up_strategy(source="bk_monitorv3")

    result = strategy_migration.migrate_gather_up_strategy_config(dry_run=False)

    assert result["changed_count"] == 0
    query_config.refresh_from_db()
    assert query_config.config["result_table_id"] == LEGACY_RESULT_TABLE_ID


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db
def test_migrate_gather_up_strategy_config_skips_when_single_tenant():
    _, _, query_config = _create_legacy_gather_up_strategy()

    result = strategy_migration.migrate_gather_up_strategy_config(bk_biz_id=2, dry_run=False)

    assert result["changed_count"] == 0
    assert "skipped" in result["message"]
    query_config.refresh_from_db()
    assert query_config.config["result_table_id"] == LEGACY_RESULT_TABLE_ID


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_builtin_strategy_config_aggregates_all_migrations():
    _create_legacy_gather_up_strategy(bk_biz_id=2)

    result = strategy_migration.migrate_builtin_strategy_config(bk_biz_id=2, dry_run=True)

    assert set(result["results"]) == {"system_event", "gather_up"}
    assert result["results"]["gather_up"]["changed_count"] == 1
    # 顶层计数为各迁移之和
    assert result["changed_count"] == (
        result["results"]["system_event"]["changed_count"] + result["results"]["gather_up"]["changed_count"]
    )


def test_migrate_gather_up_strategies_command_passes_optional_biz_ids(monkeypatch):
    received = {}

    def fake_migrate_gather_up_strategy_config(**kwargs):
        received.update(kwargs)
        return {"changed_count": 0, "applied_count": 0, "stale_count": 0, "changes": []}

    monkeypatch.setattr(
        data_migrate_command,
        "migrate_gather_up_strategy_config",
        fake_migrate_gather_up_strategy_config,
    )

    data_migrate_command.Command()._handle_migrate_gather_up_strategies({"bk_biz_ids": [2, 3], "dry_run": True})

    assert received == {"bk_biz_id": [2, 3], "dry_run": True}


def test_migrate_builtin_strategies_command_passes_optional_biz_ids(monkeypatch):
    received = {}

    def fake_migrate_builtin_strategy_config(**kwargs):
        received.update(kwargs)
        return {"changed_count": 0, "applied_count": 0, "stale_count": 0, "results": {}}

    monkeypatch.setattr(
        data_migrate_command,
        "migrate_builtin_strategy_config",
        fake_migrate_builtin_strategy_config,
    )

    data_migrate_command.Command()._handle_migrate_builtin_strategies({"bk_biz_ids": [2], "dry_run": False})

    assert received == {"bk_biz_id": [2], "dry_run": False}
