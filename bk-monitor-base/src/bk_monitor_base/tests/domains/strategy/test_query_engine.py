"""StrategyQueryEngine 单测（表驱动/最小覆盖）。

重点验证：
- 条件归一化：key mapping + values 形式（仅 FilterSpec）
- 逐条件交集语义
- action 无处理套餐（action_id=0）语义
- data_source 组合字符串 `<label>|<type>` 解析
- heavy/未知 key 忽略
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from bk_monitor_base.domains.strategy.constants import DataSourceLabel, DataTypeLabel
from bk_monitor_base.domains.strategy.models import (
    ActionConfig,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyLabel,
    StrategyModel,
)
from bk_monitor_base.domains.strategy.query_engine import StrategyQueryEngine


@pytest.mark.django_db(databases=["default"])
def test_query_engine_normalize_and_split_name_or() -> None:
    """`strategy_name` -> `name`，values 多值默认 OR 语义。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="hello_foo", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="hello_bar", scenario="os", type="monitor")
    StrategyModel.objects.create(bk_biz_id=2, name="hello_baz", scenario="os", type="monitor")

    qs = StrategyQueryEngine.filter_strategies(
        2,
        conditions=[{"key": "strategy_name", "values": ["foo", "bar"], "operator": "icontains"}],
    )
    ids = set(qs.values_list("id", flat=True))
    assert ids == {s1.id, s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_intersection_label_and_data_source() -> None:
    """label 与 data_source 应逐条件求交集。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="s1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="s2", scenario="os", type="monitor")

    # 仅 s1 有 label
    StrategyLabel.objects.create(label_name="/a/", bk_biz_id=2, strategy_id=s1.id)

    # QueryConfig：仅 s1 是 bk_monitor_time_series
    QueryConfigModel.objects.create(
        strategy_id=s1.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.cpu_usage",
        config={"result_table_id": "2_system.cpu", "metric_field": "cpu_usage"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s2.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="custom.metric",
        config={"result_table_id": "custom.table", "metric_field": "x"},
    )

    qs = StrategyQueryEngine.filter_strategies(
        2,
        conditions=[
            {"key": "label", "values": ["/a/"], "operator": "eq"},
            {
                "key": "data_source",
                "values": [f"{DataSourceLabel.BK_MONITOR_COLLECTOR}|{DataTypeLabel.TIME_SERIES}"],
                "operator": "eq",
            },
        ],
    )
    assert list(qs.values_list("id", flat=True)) == [s1.id]


@pytest.mark.django_db(databases=["default"])
def test_query_engine_action_without_actions() -> None:
    """action_id=0 表示筛选未配置处理套餐的策略。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="with_action", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="without_action", scenario="os", type="monitor")

    action = ActionConfig.objects.create(
        name="a1",
        desc="",
        bk_biz_id="2",
        plugin_id="2",
        execute_config="{}",
        create_user="pytest",
        update_user="pytest",
    )
    StrategyActionConfigRelation.objects.create(
        strategy_id=s1.id,
        config_id=action.id,
        relate_type=StrategyActionConfigRelation.RelateType.ACTION,
        signal=[],
        user_groups=[],
        user_type="main",
        options={},
        create_user="pytest",
        update_user="pytest",
    )

    qs = StrategyQueryEngine.filter_strategies(2, conditions=[{"key": "action_id", "values": [0], "operator": "eq"}])
    ids = set(qs.values_list("id", flat=True))
    assert ids == {s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_plugin_id_is_ignored() -> None:
    """plugin_id 已不再由 base 引擎支持，作为未知 key 应被忽略。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="p1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="p2", scenario="os", type="monitor")

    QueryConfigModel.objects.create(
        strategy_id=s1.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.x",
        config={"result_table_id": "plugin_x.cpu", "metric_field": "cpu_usage"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s2.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.y",
        config={"result_table_id": "other.cpu", "metric_field": "cpu_usage"},
    )

    qs = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "plugin_id", "values": ["plugin_x"], "operator": "eq"}]
    )
    assert set(qs.values_list("id", flat=True)) == {s1.id, s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_result_table_id_startswith() -> None:
    """result_table_id__startswith 支持对结果表做前缀匹配。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="rt1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="rt2", scenario="os", type="monitor")
    StrategyModel.objects.create(bk_biz_id=2, name="rt3", scenario="os", type="monitor")

    QueryConfigModel.objects.create(
        strategy_id=s1.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.x",
        config={"result_table_id": "2_system.cpu", "metric_field": "cpu_usage"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s2.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.y",
        config={"result_table_id": "2_system.mem", "metric_field": "mem_usage"},
    )

    qs = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "result_table_id", "values": ["2_system."], "operator": "startswith"}]
    )
    assert set(qs.values_list("id", flat=True)) == {s1.id, s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_result_table_id_icontains() -> None:
    """result_table_id__icontains 支持对结果表做关键字匹配。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="rtc1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="rtc2", scenario="os", type="monitor")
    s3 = StrategyModel.objects.create(bk_biz_id=2, name="rtc3", scenario="os", type="monitor")

    QueryConfigModel.objects.create(
        strategy_id=s1.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.x",
        config={"result_table_id": "2_system.cpu", "metric_field": "cpu_usage"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s2.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.y",
        config={"result_table_id": "2_bkmonitor.cpu_detail", "metric_field": "cpu_detail"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s3.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.z",
        config={"result_table_id": "2_system.mem", "metric_field": "mem_usage"},
    )

    qs = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "result_table_id", "values": ["cpu"], "operator": "icontains"}]
    )
    assert set(qs.values_list("id", flat=True)) == {s1.id, s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_metric_field_icontains() -> None:
    """metric_field__icontains 支持对 metric_field 做关键字匹配。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="mf1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="mf2", scenario="os", type="monitor")
    s3 = StrategyModel.objects.create(bk_biz_id=2, name="mf3", scenario="os", type="monitor")

    QueryConfigModel.objects.create(
        strategy_id=s1.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.x",
        config={"result_table_id": "2_system.cpu", "metric_field": "cpu_usage"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s2.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.y",
        config={"result_table_id": "2_system.cpu", "metric_field": "cpu_load"},
    )
    QueryConfigModel.objects.create(
        strategy_id=s3.id,
        item_id=1,
        alias="a",
        data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="bk_monitor.z",
        config={"result_table_id": "2_system.mem", "metric_field": "mem_usage"},
    )

    qs = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "metric_field", "values": ["cpu"], "operator": "icontains"}]
    )
    assert set(qs.values_list("id", flat=True)) == {s1.id, s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_id_neq_excludes() -> None:
    """id operator=neq：多值等价 NOT IN（AND），应排除指定策略。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="x1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="x2", scenario="os", type="monitor")

    qs = StrategyQueryEngine.filter_strategies(2, conditions=[{"key": "id", "values": [s1.id], "operator": "neq"}])
    assert set(qs.values_list("id", flat=True)) == {s2.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_app_eq_filter() -> None:
    """app 支持精确匹配过滤。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="app1", scenario="os", type="monitor", app="fta")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="app2", scenario="os", type="monitor", app="bk_monitor")
    s3 = StrategyModel.objects.create(bk_biz_id=2, name="app3", scenario="os", type="monitor", app="")

    qs = StrategyQueryEngine.filter_strategies(2, conditions=[{"key": "app", "values": ["fta"], "operator": "eq"}])
    assert set(qs.values_list("id", flat=True)) == {s1.id}

    qs_neq = StrategyQueryEngine.filter_strategies(2, conditions=[{"key": "app", "values": ["fta"], "operator": "neq"}])
    assert set(qs_neq.values_list("id", flat=True)) == {s2.id, s3.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_updated_after_create_bool_filter() -> None:
    """updated_after_create 支持过滤创建后有过修改的策略（固定阈值 1 秒）。"""
    modified = StrategyModel.objects.create(bk_biz_id=2, name="m1", scenario="os", type="monitor")
    unmodified = StrategyModel.objects.create(bk_biz_id=2, name="m2", scenario="os", type="monitor")

    # 通过 update() 绕过 auto_now/auto_now_add，构造稳定的时间差
    base_time = timezone.now() - datetime.timedelta(days=1)
    StrategyModel.objects.filter(id=modified.id).update(
        create_time=base_time,
        update_time=base_time + datetime.timedelta(seconds=2),
    )
    StrategyModel.objects.filter(id=unmodified.id).update(
        create_time=base_time,
        update_time=base_time + datetime.timedelta(milliseconds=500),
    )

    qs_true = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "updated_after_create", "values": [True], "operator": "eq"}]
    )
    assert set(qs_true.values_list("id", flat=True)) == {modified.id}

    qs_false = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "updated_after_create", "values": [False], "operator": "eq"}]
    )
    assert set(qs_false.values_list("id", flat=True)) == {unmodified.id}

    qs_neq_true = StrategyQueryEngine.filter_strategies(
        2, conditions=[{"key": "updated_after_create", "values": [True], "operator": "neq"}]
    )
    assert set(qs_neq_true.values_list("id", flat=True)) == {unmodified.id}


@pytest.mark.django_db(databases=["default"])
def test_query_engine_ignore_unknown_and_heavy_keys() -> None:
    """未知 key / heavy key 应忽略，不影响结果。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="k1", scenario="os", type="monitor")
    StrategyModel.objects.create(bk_biz_id=2, name="k2", scenario="os", type="monitor")

    qs = StrategyQueryEngine.filter_strategies(
        2,
        conditions=[
            {"key": "unknown_key", "values": ["x"]},
            {"key": "ip", "values": ["127.0.0.1"]},
            {"key": "bk_cloud_id", "values": [0]},
            {"key": "id", "values": [s1.id], "operator": "eq"},
        ],
    )
    assert list(qs.values_list("id", flat=True)) == [s1.id]


@pytest.mark.django_db(databases=["default"])
def test_query_engine_legacy_key_suffix_is_ignored() -> None:
    """旧的 `<key>__<suffix>` 形式不再解析，应被忽略。"""
    s1 = StrategyModel.objects.create(bk_biz_id=2, name="legacy1", scenario="os", type="monitor")
    s2 = StrategyModel.objects.create(bk_biz_id=2, name="legacy2", scenario="os", type="monitor")

    qs = StrategyQueryEngine.filter_strategies(
        2,
        conditions=[
            # 过去会被当作 icontains；现在应视为未知 key
            {"key": "name__and", "values": ["legacy1"], "operator": "eq"},
        ],
    )
    assert set(qs.values_list("id", flat=True)) == {s1.id, s2.id}
