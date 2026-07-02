import pytest
from django.test import override_settings

from bkmonitor.models import AlgorithmModel, DetectModel, ItemModel, QueryConfigModel, StrategyModel
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_migrate import system_event_strategy
from monitor_web.management.commands import data_migrate as data_migrate_command


@pytest.fixture(autouse=True)
def _mock_bk_tenant_id(monkeypatch):
    """迁移逻辑按业务推导租户 ID，测试固定为 ``tenant`` 以对齐结果表命名。"""
    monkeypatch.setattr(
        system_event_strategy,
        "bk_biz_id_to_bk_tenant_id",
        lambda bk_biz_id: "tenant",
    )


def _create_legacy_system_event_strategy(
    *,
    bk_biz_id: int = 2,
    name: str = "OOM异常告警",
    old_metric_id: str = "bk_monitor.oom-gse",
    old_metric_field: str = "oom-gse",
    data_type_label: str = DataTypeLabel.EVENT,
    result_table_id: str = "system.event",
) -> tuple[StrategyModel, ItemModel, QueryConfigModel, AlgorithmModel, DetectModel]:
    strategy = StrategyModel.objects.create(
        name=name,
        bk_biz_id=bk_biz_id,
        source="bk_monitorv3",
        scenario="os",
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
        expression="",
        functions=[],
        origin_sql="",
        no_data_config={"is_enabled": False, "continuous": 5},
        target=[],
        metric_type=data_type_label,
    )
    query_config = QueryConfigModel.objects.create(
        strategy_id=strategy.pk,
        item_id=item.pk,
        alias="A",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=data_type_label,
        metric_id=old_metric_id,
        config={
            "result_table_id": result_table_id,
            "metric_field": old_metric_field,
            "agg_condition": [],
        },
    )
    algorithm = AlgorithmModel.objects.create(
        strategy_id=strategy.pk,
        item_id=item.pk,
        level=2,
        type="",
        config=[],
        unit_prefix="",
    )
    detect = DetectModel.objects.create(
        strategy_id=strategy.pk,
        level=2,
        expression="",
        connector="and",
        trigger_config={"count": 1, "check_window": 5},
        recovery_config={"check_window": 5, "status_setter": "recovery"},
    )
    return strategy, item, query_config, algorithm, detect


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_system_event_strategy_config_dry_run_does_not_update():
    _, item, query_config, algorithm, detect = _create_legacy_system_event_strategy()

    result = system_event_strategy.migrate_system_event_strategy_config(bk_biz_id=2, dry_run=True)

    assert result["changed_count"] == 1
    assert result["applied_count"] == 0
    assert result["changes"][0]["new_metric_id"] == "custom.event.base_tenant_2_event.OOM"

    query_config.refresh_from_db()
    item.refresh_from_db()
    algorithm.refresh_from_db()
    detect.refresh_from_db()
    assert query_config.metric_id == "bk_monitor.oom-gse"
    assert query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
    assert item.metric_type == DataTypeLabel.EVENT
    assert algorithm.type == ""
    assert detect.recovery_config["status_setter"] == "recovery"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_system_event_strategy_config_updates_legacy_event_strategy():
    _, item, query_config, algorithm, detect = _create_legacy_system_event_strategy()

    result = system_event_strategy.migrate_system_event_strategy_config(bk_biz_id=[2], dry_run=False)

    assert result["changed_count"] == 1
    assert result["applied_count"] == 1
    assert result["skipped_count"] == 0

    query_config.refresh_from_db()
    item.refresh_from_db()
    algorithm.refresh_from_db()
    detect.refresh_from_db()

    assert query_config.data_source_label == DataSourceLabel.CUSTOM
    assert query_config.data_type_label == DataTypeLabel.EVENT
    assert query_config.metric_id == "custom.event.base_tenant_2_event.OOM"
    assert query_config.config == {
        "result_table_id": "base_tenant_2_event",
        "agg_method": "COUNT",
        "agg_interval": 60,
        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
        "agg_condition": [],
        "custom_event_name": "OOM",
    }
    assert item.metric_type == DataTypeLabel.EVENT
    assert algorithm.type == "Threshold"
    assert algorithm.config == [[{"threshold": 1, "method": "gte"}]]
    assert detect.trigger_config == {"count": 1, "check_window": 5}
    assert detect.recovery_config == {"check_window": 5, "status_setter": "close"}


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_system_event_strategy_config_scans_all_biz_when_omitted():
    _create_legacy_system_event_strategy(bk_biz_id=2)
    _create_legacy_system_event_strategy(
        bk_biz_id=3,
        name="磁盘只读",
        old_metric_id="bk_monitor.disk-readonly-gse",
        old_metric_field="disk-readonly-gse",
    )

    result = system_event_strategy.migrate_system_event_strategy_config(dry_run=True)

    assert result["bk_biz_ids"] is None
    assert result["changed_count"] == 2
    assert {change["bk_biz_id"] for change in result["changes"]} == {2, 3}


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_system_event_strategy_config_derives_table_without_metric_cache():
    """无需 MetricListCache 也能直接按业务推导目标结果表。"""
    _, _, query_config, _, _ = _create_legacy_system_event_strategy()

    result = system_event_strategy.migrate_system_event_strategy_config(bk_biz_id=2, dry_run=False)

    assert result["changed_count"] == 1
    assert result["applied_count"] == 1
    assert result["skipped_count"] == 0

    query_config.refresh_from_db()
    assert query_config.metric_id == "custom.event.base_tenant_2_event.OOM"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.django_db
def test_migrate_system_event_strategy_config_skips_non_positive_biz():
    """负数/零业务没有内置分业务 custom event 表，直接跳过。"""
    _create_legacy_system_event_strategy(bk_biz_id=-1)

    result = system_event_strategy.migrate_system_event_strategy_config(bk_biz_id=-1, dry_run=False)

    assert result["changed_count"] == 0
    assert result["applied_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["reason"] == "non-positive bk_biz_id has no built-in custom event table"


def test_migrate_system_event_strategies_command_passes_optional_biz_ids(monkeypatch):
    received = {}

    def fake_migrate_system_event_strategy_config(**kwargs):
        received.update(kwargs)
        return {
            "changed_count": 0,
            "applied_count": 0,
            "stale_count": 0,
            "skipped_count": 0,
            "changes": [],
            "skipped": [],
        }

    monkeypatch.setattr(
        data_migrate_command,
        "migrate_system_event_strategy_config",
        fake_migrate_system_event_strategy_config,
    )

    data_migrate_command.Command()._handle_migrate_system_event_strategies({"bk_biz_ids": [2, 3], "dry_run": True})

    assert received == {"bk_biz_id": [2, 3], "dry_run": True}
