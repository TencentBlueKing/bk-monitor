import copy
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from rest_framework.exceptions import ValidationError

from apm_web.models import StrategyInstance
from apm_web.strategy import dispatch
from apm_web.strategy.dispatch import StrategyTemplateUpdater
from apm_web.strategy.dispatch import dispatcher as dispatcher_module
from bkmonitor.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
)
from bkmonitor.strategy.new_strategy import Strategy
from core.errors.strategy import CreateStrategyError

pytestmark = pytest.mark.django_db(databases="__all__")

BK_BIZ_ID = 2


def build_candidate_params() -> dict[str, Any]:
    return {
        "bk_biz_id": BK_BIZ_ID,
        "service_name": "service-a",
        "name": "updated strategy",
        "scenario": "application_check",
        "source": "candidate-source",
        "type": "monitor",
        "is_enabled": True,
        "priority": None,
        "labels": [
            "APM-APP(app-a)",
            "APM-SERVICE(service-a)",
            "APM-SYSTEM(RPC)",
            "APM-CATEGORY(DEFAULT)",
            "APM-TEMPLATE(10)",
            "candidate-custom-label",
        ],
        "items": [
            {
                "name": "updated item",
                "expression": "a",
                "functions": [],
                "origin_sql": "candidate origin sql",
                "target": [[]],
                "no_data_config": {"is_enabled": False, "continuous": 10, "agg_dimension": []},
                "metric_type": "time_series",
                "query_configs": [
                    {
                        "data_source_label": "custom",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "result_table_id": "2_apm_metric.__default__",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": ["service_name"],
                        "agg_condition": [],
                        "metric_field": "duration",
                        "unit": "ms",
                        "functions": [],
                    }
                ],
                "algorithms": [
                    {
                        "type": "Threshold",
                        "level": 2,
                        "unit_prefix": "ms",
                        "config": [[{"method": "gte", "threshold": 1000}]],
                    }
                ],
            }
        ],
        "detects": [
            {
                "level": 2,
                "expression": "",
                "connector": "and",
                "trigger_config": {"count": 2, "check_window": 3},
                "recovery_config": {"check_window": 2, "status_setter": "recovery"},
            }
        ],
        "notice": {
            "user_groups": [201],
            "signal": ["abnormal", "no_data"],
            "options": {"converge_config": {"need_biz_converge": True}},
            "config": {
                "need_poll": True,
                "notify_interval": 7200,
                "interval_notify_mode": "standard",
                "template": [],
            },
        },
        "actions": [],
    }


@pytest.fixture
def existing_strategy() -> dict[str, Any]:
    strategy = StrategyModel.objects.create(
        bk_biz_id=BK_BIZ_ID,
        name="original strategy",
        scenario="apm",
        source="preserved-source",
        type="monitor",
        is_enabled=False,
        is_invalid=True,
        invalid_type=StrategyModel.InvalidType.INVALID_METRIC,
        priority=99,
        priority_group_key="PGK:preserved",
        app="preserved-app",
        path="preserved-path",
        hash="preserved-hash",
        snippet="preserved-snippet",
    )
    item = ItemModel.objects.create(
        strategy_id=strategy.id,
        name="original item",
        expression="old_a",
        functions=[{"id": "abs", "params": []}],
        origin_sql="preserved origin sql",
        no_data_config={"is_enabled": True, "continuous": 5, "agg_dimension": ["service_name"]},
        target=[[{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 1}]}]],
        meta={"preserved": True},
        metric_type="old_metric_type",
        time_delay=30,
    )
    query_config = QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=item.id,
        alias="old_a",
        data_source_label="custom",
        data_type_label="time_series",
        metric_id="custom.2_old.metric",
        config={
            "result_table_id": "2_old",
            "agg_method": "MAX",
            "agg_interval": 120,
            "agg_dimension": ["old_dimension"],
            "agg_condition": [],
            "metric_field": "metric",
            "unit": "count",
            "functions": [],
        },
    )
    algorithm = AlgorithmModel.objects.create(
        strategy_id=strategy.id,
        item_id=item.id,
        type="Threshold",
        level=3,
        unit_prefix="",
        config=[[{"method": "gt", "threshold": 1}]],
    )
    detect = DetectModel.objects.create(
        strategy_id=strategy.id,
        level=3,
        expression="",
        connector="or",
        trigger_config={"count": 1, "check_window": 1},
        recovery_config={"check_window": 1, "status_setter": "recovery"},
    )
    notice_config = ActionConfig.objects.create(
        name="preserved notice",
        desc="preserved notice config",
        bk_biz_id=str(BK_BIZ_ID),
        plugin_id=ActionConfig.NOTICE_PLUGIN_ID,
        execute_config={
            "template_detail": {
                "need_poll": False,
                "notify_interval": 600,
                "interval_notify_mode": "fixed",
                "template": [{"signal": "abnormal", "message_tmpl": "preserved message"}],
            }
        },
    )
    notice_relation = StrategyActionConfigRelation.objects.create(
        strategy_id=strategy.id,
        config_id=notice_config.id,
        relate_type=StrategyActionConfigRelation.RelateType.NOTICE,
        signal=["abnormal", "recovered"],
        user_groups=[101],
        user_type="main",
        options={
            "start_time": "08:00:00",
            "end_time": "20:00:00",
            "upgrade_config": {"is_enabled": True, "upgrade_interval": 60, "user_groups": [202]},
            "noise_reduce_config": {"is_enabled": True, "dimensions": ["service_name"], "count": 10},
        },
    )
    action_config = ActionConfig.objects.create(
        name="preserved action",
        desc="preserved action config",
        bk_biz_id=str(BK_BIZ_ID),
        plugin_id="webhook",
        execute_config={"template_detail": {"url": "https://example.test"}},
    )
    action_relation = StrategyActionConfigRelation.objects.create(
        strategy_id=strategy.id,
        config_id=action_config.id,
        relate_type=StrategyActionConfigRelation.RelateType.ACTION,
        signal=["abnormal", "recovered"],
        user_groups=[101, 102],
        user_type="main",
        options={"converge_config": {"is_enabled": False}, "preserved": True},
    )
    StrategyLabel.objects.bulk_create(
        [
            StrategyLabel(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/APM-APP(old-app)/"),
            StrategyLabel(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/APM-TEMPLATE(9)/"),
            StrategyLabel(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/custom-label/"),
        ]
    )
    return {
        "strategy": strategy,
        "item": item,
        "query_config": query_config,
        "algorithm": algorithm,
        "detect": detect,
        "notice_config": notice_config,
        "notice_relation": notice_relation,
        "action_config": action_config,
        "action_relation": action_relation,
    }


def test_update_only_changes_template_managed_fields(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    item: ItemModel = existing_strategy["item"]
    notice_relation: StrategyActionConfigRelation = existing_strategy["notice_relation"]
    action_relation: StrategyActionConfigRelation = existing_strategy["action_relation"]
    action_config: ActionConfig = existing_strategy["action_config"]
    original_action_relation: dict[str, Any] = copy.deepcopy(
        StrategyActionConfigRelation.objects.filter(id=action_relation.id).values().get()
    )
    original_action_config: dict[str, Any] = copy.deepcopy(
        ActionConfig.objects.filter(id=action_config.id).values().get()
    )
    original_notice_relation: dict[str, Any] = copy.deepcopy(
        StrategyActionConfigRelation.objects.filter(id=notice_relation.id).values().get()
    )
    original_notice_config: dict[str, Any] = copy.deepcopy(
        ActionConfig.objects.filter(id=existing_strategy["notice_config"].id).values().get()
    )

    assert StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params()) == strategy.id

    strategy.refresh_from_db()
    assert (strategy.name, strategy.scenario) == ("updated strategy", "application_check")
    assert strategy.source == "preserved-source"
    assert strategy.is_enabled is False
    assert strategy.is_invalid is True
    assert strategy.invalid_type == StrategyModel.InvalidType.INVALID_METRIC
    assert strategy.priority == 99
    assert strategy.priority_group_key == "PGK:preserved"
    assert strategy.app == "preserved-app"
    assert strategy.path == "preserved-path"
    assert (strategy.hash, strategy.snippet) == ("", "")

    item.refresh_from_db()
    assert (item.name, item.expression, item.functions, item.metric_type) == (
        "updated item",
        "a",
        [],
        "time_series",
    )
    assert item.origin_sql == "preserved origin sql"
    assert item.no_data_config == {"is_enabled": True, "continuous": 5, "agg_dimension": ["service_name"]}
    assert item.target == [[{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 1}]}]]
    assert item.meta == {"preserved": True}
    assert item.time_delay == 30

    assert StrategyActionConfigRelation.objects.filter(id=action_relation.id).values().get() == original_action_relation
    assert ActionConfig.objects.filter(id=action_config.id).values().get() == original_action_config
    updated_notice_relation: dict[str, Any] = (
        StrategyActionConfigRelation.objects.filter(id=notice_relation.id).values().get()
    )
    assert updated_notice_relation.pop("user_groups") == [201]
    original_notice_relation.pop("user_groups")
    assert updated_notice_relation == original_notice_relation
    assert (
        ActionConfig.objects.filter(id=existing_strategy["notice_config"].id).values().get() == original_notice_config
    )

    assert set(StrategyLabel.objects.filter(strategy_id=strategy.id).values_list("label_name", flat=True)) == {
        "/APM-APP(app-a)/",
        "/APM-SERVICE(service-a)/",
        "/APM-SYSTEM(RPC)/",
        "/APM-CATEGORY(DEFAULT)/",
        "/APM-TEMPLATE(10)/",
        "/custom-label/",
    }
    history: StrategyHistoryModel = StrategyHistoryModel.objects.get(strategy_id=strategy.id)
    assert history.status is True
    assert history.content["actions"][0]["config_id"] == action_config.id
    assert history.content["notice"]["config_id"] == existing_strategy["notice_config"].id


def test_repeated_update_is_idempotent(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    params: dict[str, Any] = build_candidate_params()
    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, params)
    strategy.refresh_from_db()
    first_update_time = strategy.update_time
    child_ids: tuple[list[int], list[int], list[int]] = (
        list(QueryConfigModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
        list(AlgorithmModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
        list(DetectModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
    )

    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, params)

    strategy.refresh_from_db()
    assert strategy.update_time == first_update_time
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 1
    assert child_ids == (
        list(QueryConfigModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
        list(AlgorithmModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
        list(DetectModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)),
    )


def test_update_recalculates_automatic_priority_group_key(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    StrategyModel.objects.filter(id=strategy.id).update(priority_group_key="stale-auto-key")

    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    persisted_strategy: Strategy = Strategy.from_models([strategy])[0]
    expected_priority_group_key: str = Strategy.get_priority_group_key(BK_BIZ_ID, persisted_strategy.items)
    assert strategy.priority_group_key == expected_priority_group_key
    assert strategy.priority_group_key != "stale-auto-key"

    first_update_time = strategy.update_time
    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    assert strategy.update_time == first_update_time
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 1


def test_update_removes_extra_template_child_configs(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    item: ItemModel = existing_strategy["item"]
    QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=item.id,
        alias="extra",
        data_source_label="custom",
        data_type_label="time_series",
        metric_id="custom.2_extra.metric",
        config=copy.deepcopy(existing_strategy["query_config"].config),
    )
    AlgorithmModel.objects.create(
        strategy_id=strategy.id,
        item_id=item.id,
        type="Threshold",
        level=1,
        unit_prefix="",
        config=[[{"method": "gt", "threshold": 10}]],
    )
    DetectModel.objects.create(
        strategy_id=strategy.id,
        level=1,
        expression="",
        connector="and",
        trigger_config={"count": 1, "check_window": 1},
        recovery_config={"check_window": 1, "status_setter": "recovery"},
    )

    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    assert list(QueryConfigModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)) == [
        existing_strategy["query_config"].id
    ]
    assert list(AlgorithmModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)) == [
        existing_strategy["algorithm"].id
    ]
    assert list(DetectModel.objects.filter(strategy_id=strategy.id).values_list("id", flat=True)) == [
        existing_strategy["detect"].id
    ]


def test_invalid_item_structure_rolls_back(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    original_name = strategy.name
    ItemModel.objects.create(
        strategy_id=strategy.id,
        name="unexpected item",
        expression="b",
        functions=[],
        origin_sql="",
        no_data_config={},
        target=[[]],
        meta={},
        metric_type="time_series",
    )

    with pytest.raises(ValidationError, match="单监控项"):
        StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    assert strategy.name == original_name
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 0


def test_existing_notice_upgrade_groups_are_validated(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    params: dict[str, Any] = build_candidate_params()
    params["notice"]["user_groups"] = [202]

    with pytest.raises(ValidationError, match="通知升级"):
        StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, params)

    strategy.refresh_from_db()
    assert strategy.name == "original strategy"
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 0


def test_update_rejects_multiple_notice_relations(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    StrategyActionConfigRelation.objects.create(
        strategy_id=strategy.id,
        config_id=existing_strategy["notice_config"].id,
        relate_type=StrategyActionConfigRelation.RelateType.NOTICE,
        signal=["abnormal"],
        user_groups=[301],
        user_type="main",
        options={},
    )

    with pytest.raises(ValidationError, match="唯一通知关系"):
        StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    assert strategy.name == "original strategy"
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 0


def test_update_name_conflict_preserves_strategy_and_records_failed_history(
    existing_strategy: dict[str, Any],
) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    StrategyModel.objects.create(
        bk_biz_id=BK_BIZ_ID,
        name="updated strategy",
        scenario="apm",
        type=StrategyModel.StrategyType.Monitor,
    )

    with pytest.raises(CreateStrategyError, match="不能重复"):
        StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    assert (strategy.name, strategy.scenario, strategy.hash, strategy.snippet) == (
        "original strategy",
        "apm",
        "preserved-hash",
        "preserved-snippet",
    )
    history: StrategyHistoryModel = StrategyHistoryModel.objects.get(strategy_id=strategy.id)
    assert history.status is False
    assert "策略名称(updated strategy)不能重复" in history.message
    assert history.content["name"] == "original strategy"


def test_update_removes_duplicate_managed_labels(existing_strategy: dict[str, Any]) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    retained_label = StrategyLabel.objects.create(
        bk_biz_id=BK_BIZ_ID,
        strategy_id=strategy.id,
        label_name="/APM-APP(app-a)/",
    )
    duplicate_label = StrategyLabel.objects.create(
        bk_biz_id=BK_BIZ_ID,
        strategy_id=strategy.id,
        label_name="/APM-APP(app-a)/",
    )

    StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    assert StrategyLabel.objects.filter(id=retained_label.id).exists()
    assert not StrategyLabel.objects.filter(id=duplicate_label.id).exists()
    assert StrategyLabel.objects.filter(strategy_id=strategy.id, label_name="/APM-APP(app-a)/").count() == 1


def test_persistence_failure_rolls_back_template_fields(
    existing_strategy: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy: StrategyModel = existing_strategy["strategy"]
    item: ItemModel = existing_strategy["item"]
    original_query_config: dict[str, Any] = copy.deepcopy(
        QueryConfigModel.objects.filter(id=existing_strategy["query_config"].id).values().get()
    )

    def raise_persistence_error(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("persistence failed")

    monkeypatch.setattr(StrategyTemplateUpdater, "_save_algorithms", raise_persistence_error)

    with pytest.raises(RuntimeError, match="persistence failed"):
        StrategyTemplateUpdater.update(BK_BIZ_ID, strategy.id, build_candidate_params())

    strategy.refresh_from_db()
    item.refresh_from_db()
    assert (strategy.name, strategy.scenario, strategy.hash, strategy.snippet) == (
        "original strategy",
        "apm",
        "preserved-hash",
        "preserved-snippet",
    )
    assert (item.name, item.expression, item.metric_type) == ("original item", "old_a", "old_metric_type")
    assert (
        QueryConfigModel.objects.filter(id=existing_strategy["query_config"].id).values().get() == original_query_config
    )
    history: StrategyHistoryModel = StrategyHistoryModel.objects.get(strategy_id=strategy.id)
    assert history.status is False
    assert "persistence failed" in history.message
    assert history.content["name"] == "original strategy"
    assert history.content["actions"][0]["config_id"] == existing_strategy["action_config"].id


def test_dispatcher_routes_existing_strategy_to_template_updater(monkeypatch: pytest.MonkeyPatch) -> None:
    template = SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name="app-a", id=10, root_id=0)
    query_template_wrapper = SimpleNamespace(bk_biz_id=BK_BIZ_ID, name="query-template")
    strategy_dispatcher = dispatch.StrategyDispatcher(template, query_template_wrapper)
    service_config = dispatch.DispatchConfig(
        service_name="service-a",
        context={},
        detect={"connector": "and"},
        algorithms=[],
        user_group_ids=[201],
    )
    strategy_instance = StrategyInstance.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name="app-a",
        service_name="service-a",
        strategy_id=100,
        strategy_template_id=template.id,
        root_strategy_template_id=template.root_id,
    )
    captured_params: list[dict[str, Any]] = []

    monkeypatch.setattr(strategy_dispatcher, "_enrich", lambda *args, **kwargs: {"service-a": service_config})
    monkeypatch.setattr(
        dispatcher_module.builder,
        "StrategyBuilder",
        lambda **kwargs: SimpleNamespace(build=lambda: {"bk_biz_id": BK_BIZ_ID, "service_name": "service-a"}),
    )
    monkeypatch.setattr(dispatcher_module.helper, "get_id_strategy_map", lambda *args, **kwargs: {100: {"id": 100}})
    monkeypatch.setattr(
        dispatcher_module,
        "run_threads",
        lambda threads: [thread._target(*thread._args, **thread._kwargs) for thread in threads],
    )

    def fake_update(_bk_biz_id: int, strategy_id: int, params: dict[str, Any]) -> int:
        captured_params.append(copy.deepcopy(params))
        return strategy_id

    monkeypatch.setattr(
        dispatcher_module.StrategyTemplateUpdater,
        "update",
        fake_update,
    )
    save_strategy = mock.Mock()
    monkeypatch.setattr(dispatcher_module.resource.strategies, "save_strategy_v2", save_strategy)

    result = strategy_dispatcher.dispatch(SimpleNamespace(service_names=["service-a"]))

    assert result == {"service-a": 100}
    assert captured_params == [{"bk_biz_id": BK_BIZ_ID, "service_name": "service-a", "id": 100}]
    save_strategy.assert_not_called()
    strategy_instance.refresh_from_db()
    assert strategy_instance.strategy_id == 100


def test_dispatcher_reuses_same_origin_strategy_for_template_update(monkeypatch: pytest.MonkeyPatch) -> None:
    template = SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name="app-a", id=10, root_id=0)
    query_template_wrapper = SimpleNamespace(bk_biz_id=BK_BIZ_ID, name="query-template")
    strategy_dispatcher = dispatch.StrategyDispatcher(template, query_template_wrapper)
    service_config = dispatch.DispatchConfig(
        service_name="service-a",
        context={},
        detect={"connector": "and"},
        algorithms=[],
        user_group_ids=[201],
    )
    old_instance = StrategyInstance.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name="app-a",
        service_name="service-a",
        strategy_id=100,
        strategy_template_id=11,
        root_strategy_template_id=template.id,
    )
    captured_params: list[dict[str, Any]] = []

    monkeypatch.setattr(strategy_dispatcher, "_enrich", lambda *args, **kwargs: {"service-a": service_config})
    monkeypatch.setattr(
        dispatcher_module.builder,
        "StrategyBuilder",
        lambda **kwargs: SimpleNamespace(build=lambda: {"bk_biz_id": BK_BIZ_ID, "service_name": "service-a"}),
    )
    monkeypatch.setattr(dispatcher_module.helper, "get_id_strategy_map", lambda *args, **kwargs: {100: {"id": 100}})
    monkeypatch.setattr(
        dispatcher_module,
        "run_threads",
        lambda threads: [thread._target(*thread._args, **thread._kwargs) for thread in threads],
    )

    def fake_update(_bk_biz_id: int, strategy_id: int, params: dict[str, Any]) -> int:
        captured_params.append(copy.deepcopy(params))
        return strategy_id

    monkeypatch.setattr(dispatcher_module.StrategyTemplateUpdater, "update", fake_update)
    save_strategy = mock.Mock()
    monkeypatch.setattr(dispatcher_module.resource.strategies, "save_strategy_v2", save_strategy)

    result = strategy_dispatcher.dispatch(SimpleNamespace(service_names=["service-a"]))

    assert result == {"service-a": 100}
    assert captured_params == [{"bk_biz_id": BK_BIZ_ID, "service_name": "service-a", "id": 100}]
    save_strategy.assert_not_called()
    assert not StrategyInstance.objects.filter(id=old_instance.id).exists()
    assert StrategyInstance.objects.filter(
        bk_biz_id=BK_BIZ_ID,
        app_name="app-a",
        service_name="service-a",
        strategy_id=100,
        strategy_template_id=template.id,
        root_strategy_template_id=template.root_id,
    ).exists()


def test_dispatcher_keeps_full_save_for_new_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    template = SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name="app-a", id=10, root_id=0)
    query_template_wrapper = SimpleNamespace(bk_biz_id=BK_BIZ_ID, name="query-template")
    strategy_dispatcher = dispatch.StrategyDispatcher(template, query_template_wrapper)
    service_config = dispatch.DispatchConfig(
        service_name="service-a",
        context={},
        detect={"connector": "and"},
        algorithms=[],
        user_group_ids=[201],
    )
    candidate_params: dict[str, Any] = {"bk_biz_id": BK_BIZ_ID, "service_name": "service-a"}

    monkeypatch.setattr(strategy_dispatcher, "_enrich", lambda *args, **kwargs: {"service-a": service_config})
    monkeypatch.setattr(
        dispatcher_module.builder,
        "StrategyBuilder",
        lambda **kwargs: SimpleNamespace(build=lambda: copy.deepcopy(candidate_params)),
    )
    monkeypatch.setattr(dispatcher_module.helper, "get_id_strategy_map", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        dispatcher_module,
        "run_threads",
        lambda threads: [thread._target(*thread._args, **thread._kwargs) for thread in threads],
    )
    update_strategy = mock.Mock()
    monkeypatch.setattr(dispatcher_module.StrategyTemplateUpdater, "update", update_strategy)
    save_strategy = mock.Mock(return_value={"id": 101})
    monkeypatch.setattr(dispatcher_module.resource.strategies, "save_strategy_v2", save_strategy)

    result = strategy_dispatcher.dispatch(SimpleNamespace(service_names=["service-a"]))

    assert result == {"service-a": 101}
    save_strategy.assert_called_once_with(**candidate_params)
    update_strategy.assert_not_called()
    assert StrategyInstance.objects.filter(
        bk_biz_id=BK_BIZ_ID,
        app_name="app-a",
        service_name="service-a",
        strategy_id=101,
        strategy_template_id=template.id,
    ).exists()
