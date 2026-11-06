"""Standard strategy mutations must survive the real save and ORM readback path."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.conf import settings
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers import UpgradeConfigSlz
from bkmonitor.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyModel,
    UserGroup,
)
from bkmonitor.strategy.new_strategy import Item, NoticeRelation, Strategy
from core.drf_resource.exceptions import CustomException
from kernel_api.resource.alert import get_strategy_config_version
from kernel_api.rpc.functions.bkm_cli import strategy_management as management
from monitor_web.strategies.resources.v2 import SaveStrategyV2Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def stored_standard_strategy(monkeypatch):
    # External identity and CMDB are isolated; serializers, Resources and persistence are real.
    monkeypatch.setattr(settings, "IS_ACCESS_BK_DATA", False)
    request = SimpleNamespace(user=SimpleNamespace(username="authenticated-user", tenant_id="system"))
    monkeypatch.setattr("bkmonitor.utils.request.get_request", lambda **_kwargs: request)
    monkeypatch.setattr("bkmonitor.strategy.new_strategy.is_ipv6_biz", lambda _biz: False)
    monkeypatch.setattr(management, "authorize_strategy_business", lambda _params: None)
    group = UserGroup.objects.create(name="synthetic recipients", bk_biz_id=2)
    action = ActionConfig.objects.create(name="synthetic action", bk_biz_id=2, plugin_id=2)
    upgrade_config = UpgradeConfigSlz().run_validation({})
    strategy = Strategy(
        bk_biz_id=2,
        name="synthetic standard strategy",
        scenario="os",
        is_enabled=False,
        notice={
            "user_groups": [group.id],
            "config": {"template": []},
            "options": {"upgrade_config": deepcopy(upgrade_config)},
        },
        actions=[
            {
                "config_id": action.id,
                "user_groups": [group.id],
                "options": {"converge_config": {}, "upgrade_config": deepcopy(upgrade_config)},
            }
        ],
        items=[
            {
                "name": "synthetic metric",
                "no_data_config": {"is_enabled": False},
                "expression": "a+b",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": alias,
                        "result_table_id": "system.cpu",
                        "metric_field": f"cpu_{alias}",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": [],
                        "agg_condition": [],
                        "functions": [],
                        "unit": "%",
                    }
                    for alias in "abc"
                ],
                "algorithms": [{"type": "Threshold", "level": 2, "config": [[{"method": "gt", "threshold": 5}]]}],
            }
        ],
        detects=[
            {"level": 2, "trigger_config": {"count": 1, "check_window": 1}, "recovery_config": {"check_window": 1}}
        ],
    )
    save_resource = SaveStrategyV2Resource()
    result = save_resource.perform_request(save_resource.validate_request_data(strategy.to_dict()))
    strategy.id = result["id"]
    ItemModel.objects.filter(strategy_id=strategy.id).update(
        meta={"existing_metadata": {"value": "preserved"}}, time_delay=30, access_lookback_periods=12
    )
    return strategy.id


def snapshot(strategy_id):
    strategy = Strategy.from_models([StrategyModel.objects.get(id=strategy_id)])[0]
    strategy.restore()
    return strategy.to_dict(convert_dashboard=False)


def update(strategy_id, patch):
    current = snapshot(strategy_id)
    return management.manage_strategy_config(
        {
            "operation": "update",
            "bk_biz_id": current["bk_biz_id"],
            "strategy_id": strategy_id,
            "config_version": get_strategy_config_version(current),
            "config": patch,
            "confirmed": True,
            "operator": "synthetic-operator",
        }
    )


def test_structured_promql_structured_save_preserves_all_record_ids_and_other_config(stored_standard_strategy):
    strategy_id = stored_standard_strategy
    original = snapshot(strategy_id)
    original_queries = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
    original_meta = deepcopy(ItemModel.objects.get(strategy_id=strategy_id).meta)
    item = original["items"][0]
    output = {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": "A", "expression": "a"},
            {"reference_name": "B", "expression": "b"},
            {"reference_name": "C", "expression": "c"},
            {"reference_name": "RESULT", "expression": "a+b"},
        ],
    }
    update(
        strategy_id,
        {
            "items": [
                {
                    "id": item["id"],
                    "expression": "a+b",
                    "query_configs": [
                        {
                            "id": query["id"],
                            "data_source_label": "prometheus",
                            "data_type_label": "time_series",
                            "promql": f"vector({value})",
                            "expression_mode": "promql",
                        }
                        for query, value in zip(item["query_configs"], (1, 2, 9))
                    ],
                    "query_output_config": output,
                }
            ]
        },
    )
    actual = snapshot(strategy_id)
    assert actual["items"][0]["query_output_config"] == output
    for before, after in zip(original_queries, QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id")):
        assert after.id == before.id
        assert after.alias == before.alias
        assert after.data_source_label == "prometheus"
        assert after.config["agg_interval"] == before.config["agg_interval"]
        assert after.metric_id != before.metric_id
        assert set(after.config) == {"functions", "promql", "agg_interval", "expression_mode"}
    assert ItemModel.objects.get(strategy_id=strategy_id).meta == {**original_meta, "query_output_config": output}
    for field in ("detects", "notice", "actions", "is_enabled"):
        assert actual[field] == original[field]
    assert actual["items"][0]["algorithms"] == item["algorithms"]
    for field in ("time_delay", "access_lookback_periods"):
        assert actual["items"][0][field] == item[field]

    update(
        strategy_id,
        {
            "items": [
                {
                    "id": item["id"],
                    "query_configs": [{k: v for k, v in q.items() if k != "metric_id"} for q in item["query_configs"]],
                    "query_output_config": None,
                }
            ]
        },
    )
    restored = snapshot(strategy_id)
    assert restored["items"] == original["items"]
    for field in ("detects", "notice", "actions", "is_enabled"):
        assert restored[field] == original[field]
    assert ItemModel.objects.get(strategy_id=strategy_id).meta == original_meta
    for before, after in zip(original_queries, QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id")):
        assert after.id == before.id
        assert after.config == before.config
        assert after.metric_id == before.metric_id
    assert QueryConfigModel.objects.filter(strategy_id=strategy_id).count() == 3
    assert ItemModel.objects.filter(strategy_id=strategy_id).count() == 1
    assert AlgorithmModel.objects.filter(strategy_id=strategy_id).count() == 1
    assert DetectModel.objects.filter(strategy_id=strategy_id).count() == 1
    assert StrategyActionConfigRelation.objects.filter(strategy_id=strategy_id).count() == 2
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy_id, operate="update", status=True).count() == 2
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy_id).latest("id").create_user == "synthetic-operator"
    assert StrategyModel.objects.get(id=strategy_id).update_user == "synthetic-operator"


def test_standard_algorithm_patch_is_saved_using_its_real_serializer(stored_standard_strategy):
    strategy_id = stored_standard_strategy
    item = snapshot(strategy_id)["items"][0]
    algorithm = item["algorithms"][0]
    update(
        strategy_id,
        {
            "items": [
                {
                    "id": item["id"],
                    "algorithms": [
                        {"id": algorithm["id"], "type": "SimpleRingRatio", "config": {"floor": None, "ceil": 10}}
                    ],
                }
            ]
        },
    )
    saved = AlgorithmModel.objects.get(id=algorithm["id"])
    assert saved.type == "SimpleRingRatio"
    assert saved.config == {"floor": None, "ceil": 10.0}
    assert snapshot(strategy_id)["items"][0]["query_configs"] == item["query_configs"]


def test_standard_create_persists_non_log_queries_and_non_threshold_algorithm(stored_standard_strategy):
    current = snapshot(stored_standard_strategy)
    item = {key: value for key, value in current["items"][0].items() if key in Item.Serializer().fields and key != "id"}
    item["query_configs"] = [
        {
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "promql": "up",
            "agg_interval": 60,
        }
    ]
    item["expression"] = "a"
    item["algorithms"] = [{"type": "NewSeries", "level": 2, "config": {"detect_range": 600}}]
    config = {
        "name": "synthetic created standard strategy",
        "scenario": current["scenario"],
        "is_enabled": False,
        "items": [item],
        "detects": [{key: value for key, value in detect.items() if key != "id"} for detect in current["detects"]],
        "notice": {
            key: value
            for key, value in current["notice"].items()
            if key in NoticeRelation.Serializer().fields and key not in {"id", "config_id"}
        },
    }
    result = management.manage_strategy_config(
        {"operation": "create", "bk_biz_id": 2, "config": config, "confirmed": True, "operator": "synthetic-operator"}
    )
    saved = snapshot(result["strategy_id"])
    assert saved["is_enabled"] is False
    assert saved["items"][0]["query_configs"][0]["promql"] == "up"
    assert saved["items"][0]["algorithms"][0]["type"] == "NewSeries"
    assert saved["items"][0]["algorithms"][0]["config"]["effective_delay"] == 600
    assert StrategyModel.objects.get(id=result["strategy_id"]).create_user == "synthetic-operator"


def test_output_metadata_preserve_replace_and_clear_use_real_save(stored_standard_strategy):
    strategy_id = stored_standard_strategy
    original = snapshot(strategy_id)
    item_id = original["items"][0]["id"]
    output = {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": "A", "expression": "a"},
            {"reference_name": "RESULT", "expression": "a+b"},
        ],
    }
    update(strategy_id, {"items": [{"id": item_id, "query_output_config": output}]})
    update(strategy_id, {"name": "synthetic renamed strategy"})
    assert snapshot(strategy_id)["items"][0]["query_output_config"] == output
    replacement = {**output, "output_list": output["output_list"][-1:]}
    update(strategy_id, {"items": [{"id": item_id, "query_output_config": replacement}]})
    assert ItemModel.objects.get(id=item_id).meta == {
        "existing_metadata": {"value": "preserved"},
        "query_output_config": replacement,
    }
    update(strategy_id, {"items": [{"id": item_id, "query_output_config": None}]})
    assert ItemModel.objects.get(id=item_id).meta == {"existing_metadata": {"value": "preserved"}}
    assert snapshot(strategy_id)["items"] == original["items"]


@pytest.mark.parametrize(
    "kind",
    ["mixed_mode", "mixed_source", "duplicate_alias", "different_period", "output_mismatch", "inapplicable_field"],
)
def test_invalid_standard_patch_never_changes_persistent_config(stored_standard_strategy, kind):
    strategy_id = stored_standard_strategy
    original = snapshot(strategy_id)
    history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()
    item = original["items"][0]
    patch = {
        "id": item["id"],
        "query_configs": [
            {
                "id": query["id"],
                "data_source_label": "prometheus",
                "data_type_label": "time_series",
                "promql": f"vector({index})",
                "expression_mode": "promql",
            }
            for index, query in enumerate(item["query_configs"], 1)
        ],
    }
    if kind == "mixed_mode":
        patch["query_configs"][1].pop("expression_mode")
    elif kind == "mixed_source":
        patch["query_configs"][1] = {"id": item["query_configs"][1]["id"], "metric_field": "cpu_b"}
    elif kind == "duplicate_alias":
        patch["query_configs"][1]["alias"] = "a"
    elif kind == "different_period":
        patch["query_configs"][1]["agg_interval"] = 120
    elif kind == "inapplicable_field":
        patch["query_configs"][1]["agg_method"] = "AVG"
    else:
        patch["query_output_config"] = {
            "response_contract": "named_outputs/v1",
            "legacy_output_ref": "RESULT",
            "output_list": [{"reference_name": "RESULT", "expression": "a+b+c"}],
        }
    with pytest.raises((CustomException, ValidationError)):
        update(strategy_id, {"items": [patch]})
    assert snapshot(strategy_id) == original
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count() == history_count
