"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest
from django.db import connections, router, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError

from bkmonitor.dataflow.constant import VisualType
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
from bkmonitor.strategy.new_strategy import Algorithm, Detect, Item, QueryConfig, Strategy
from bkmonitor.strategy.partial_update import StrategyConfigUpdater
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource.exceptions import CustomException
from monitor_web.strategies.resources.v2 import UpdatePartialStrategyV2Resource

pytestmark = pytest.mark.django_db(databases="__all__")

BK_BIZ_ID = 2


@pytest.mark.parametrize("labels", [["z", "a", "a", "parent", "parent/child"], []])
def test_partial_label_update_normalizes_once(strategy_config_fixture: dict[str, Any], labels: list[str]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    with mock.patch.object(Strategy, "normalize_labels", wraps=Strategy.normalize_labels) as normalize_labels:
        perform_strategy_config_patch([strategy.id], {"labels": labels})
    assert normalize_labels.call_count == 1
    assert_labels(strategy.id, ["a", "parent/child", "z"] if labels else [])


def test_multiple_item_patches_follow_ids_instead_of_request_order(strategy_config_fixture: dict[str, Any]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    first_item: ItemModel = strategy_config_fixture["first_item"]
    second_item: ItemModel = strategy_config_fixture["second_item"]
    patch: dict[str, Any] = {
        "items": [
            {"id": second_item.id, "name": "second updated"},
            {"id": first_item.id, "name": "first updated"},
        ]
    }
    original_patch: dict[str, Any] = copy.deepcopy(patch)
    perform_strategy_config_patch([strategy.id], patch)
    first_item.refresh_from_db()
    second_item.refresh_from_db()
    assert first_item.name == "first updated"
    assert second_item.name == "second updated"
    assert patch == original_patch


def test_full_and_partial_label_saves_preserve_their_order_and_duplicate_contracts(
    strategy_config_fixture: dict[str, Any],
) -> None:
    model: StrategyModel = strategy_config_fixture["strategy"]
    strategy: Strategy = Strategy.from_models([model])[0]
    labels: list[str] = ["z", "/a/", "a", "parent", "parent/child", "parentish"]
    strategy.labels = list(labels)
    strategy.save_labels()
    assert strategy.labels == ["/z/", "/a/", "/a/", "/parent/child/", "/parentish/"]
    assert (
        list(StrategyLabel.objects.filter(strategy_id=model.id).order_by("id").values_list("label_name", flat=True))
        == strategy.labels
    )

    perform_strategy_config_patch([model.id], {"labels": labels})
    assert_labels(model.id, ["z", "a", "parent/child", "parentish"])
    assert labels == ["z", "/a/", "a", "parent", "parent/child", "parentish"]
    model.refresh_from_db()
    updated_at: datetime.datetime = model.update_time
    perform_strategy_config_patch([model.id], {"labels": labels[::-1]})
    model.refresh_from_db()
    assert model.update_time == updated_at
    assert StrategyHistoryModel.objects.filter(strategy_id=model.id).count() == 1


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("length", [126, 127])
def test_label_length_boundary_is_shared_by_save_paths(
    strategy_config_fixture: dict[str, Any], partial: bool, length: int
) -> None:
    model: StrategyModel = strategy_config_fixture["strategy"]
    original_labels: list[str] = list(
        StrategyLabel.objects.filter(strategy_id=model.id).order_by("id").values_list("label_name", flat=True)
    )
    labels: list[str] = ["x" * length]

    def save_labels() -> None:
        if partial:
            perform_strategy_config_patch([model.id], {"labels": labels})
        else:
            strategy: Strategy = Strategy.from_models([model])[0]
            strategy.labels = labels
            strategy.save_labels()

    if length == 127:
        with pytest.raises(ValidationError, match="标签长度超长"):
            save_labels()
        assert (
            list(StrategyLabel.objects.filter(strategy_id=model.id).order_by("id").values_list("label_name", flat=True))
            == original_labels
        )
    else:
        save_labels()
        assert_labels(model.id, labels)


@pytest.mark.parametrize(
    ("patch", "query_count"),
    [
        ({}, 0),
        ({"items": []}, 0),
        ({"notice": {}}, 0),
        ({"items": [{"name": "updated"}]}, 3),
        ({"notice": {"user_groups": []}}, 1),
        ({"labels": []}, 1),
        ({"detects": []}, 1),
    ],
)
def test_empty_patch_skips_only_unnecessary_child_locks(
    strategy_config_fixture: dict[str, Any], patch: dict[str, Any], query_count: int
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    database: str = router.db_for_write(StrategyModel)
    with transaction.atomic(using=database):
        with CaptureQueriesContext(connections[database]) as queries:
            StrategyConfigUpdater.lock_related(strategy.id, patch)
    assert len(queries) == query_count


def make_query_config_payload(alias: str, metric_field: str, *, query_config_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "data_source_label": DataSourceLabel.CUSTOM,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "alias": alias,
        "metric_id": f"custom.2_bkmonitor_time_series_500.{metric_field}",
        "result_table_id": "2_bkmonitor_time_series_500",
        "agg_method": "AVG",
        "agg_interval": 60,
        "agg_dimension": ["bk_target_ip"],
        "agg_condition": [],
        "metric_field": metric_field,
        "unit": "count",
        "functions": [],
    }
    if query_config_id is not None:
        payload["id"] = query_config_id
    return payload


def make_algorithm_payload(level: int, threshold: int, *, algorithm_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "Threshold",
        "level": level,
        "unit_prefix": "",
        "config": [[{"method": "gte", "threshold": threshold}]],
    }
    if algorithm_id is not None:
        payload["id"] = algorithm_id
    return payload


def make_detect_payload(level: int, count: int, *, detect_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "level": level,
        "expression": "",
        "connector": "and",
        "trigger_config": {"count": count, "check_window": 5},
        "recovery_config": {"check_window": 3, "status_setter": "recovery"},
    }
    if detect_id is not None:
        payload["id"] = detect_id
    return payload


def make_item_patch(
    name: str,
    *,
    item_id: int | None = None,
    query_configs: list[dict[str, Any]] | None = None,
    algorithms: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "query_configs": query_configs or [make_query_config_payload("patched", "patched_metric")],
        "algorithms": algorithms or [make_algorithm_payload(2, 100)],
    }
    if item_id is not None:
        payload["id"] = item_id
    return payload


def perform_strategy_config_patch(strategy_ids: list[int], strategy_config: dict[str, Any] | None) -> list[int]:
    resource = UpdatePartialStrategyV2Resource()
    request_data: dict[str, Any] = {
        "bk_biz_id": BK_BIZ_ID,
        "ids": strategy_ids,
        "edit_data": {"strategy_config": strategy_config},
    }
    validated_data = resource.validate_request_data(request_data)
    return resource.perform_request(validated_data)


def perform_legacy_patch(strategy_ids: list[int], edit_data: dict[str, Any]) -> list[int]:
    resource = UpdatePartialStrategyV2Resource()
    request_data: dict[str, Any] = {"bk_biz_id": BK_BIZ_ID, "ids": strategy_ids, "edit_data": edit_data}
    validated_data = resource.validate_request_data(request_data)
    return resource.perform_request(validated_data)


def assert_invalid_strategy_config_patch(strategy_ids: list[int], strategy_config: dict[str, Any] | None) -> None:
    with pytest.raises((CustomException, ValidationError)):
        perform_strategy_config_patch(strategy_ids, strategy_config)


def assert_labels(strategy_id: int, expected_labels: list[str]) -> None:
    labels = list(
        StrategyLabel.objects.filter(strategy_id=strategy_id)
        .order_by("label_name")
        .values_list("label_name", flat=True)
    )
    assert labels == sorted(f"/{label.strip('/')}/" for label in expected_labels)


def assert_strategy_metadata_unchanged(
    strategy: StrategyModel, update_time: datetime.datetime, update_user: str
) -> None:
    strategy.refresh_from_db()
    assert strategy.update_time == update_time
    assert strategy.update_user == update_user
    assert strategy.hash == "origin-hash"
    assert strategy.snippet == "origin-snippet"
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == 0


@pytest.fixture
def strategy_config_fixture() -> dict[str, Any]:
    strategy = StrategyModel.objects.create(
        bk_biz_id=BK_BIZ_ID,
        name="strategy_config_patch_origin",
        scenario="os",
        source="custom_source",
        type=StrategyModel.StrategyType.Monitor,
        is_enabled=False,
        is_invalid=True,
        invalid_type=StrategyModel.InvalidType.INVALID_METRIC,
        priority=10,
        priority_group_key="PGK:custom-key",
        hash="origin-hash",
        snippet="origin-snippet",
    )
    first_item = ItemModel.objects.create(
        strategy_id=strategy.id,
        name="origin_item_a",
        expression="a",
        functions=[],
        origin_sql="origin sql a",
        no_data_config={"is_enabled": True, "continuous": 5, "agg_dimension": ["bk_target_ip"]},
        target=[[{"field": "bk_target_ip", "method": "eq", "value": [{"bk_target_ip": "127.0.0.1"}]}]],
        metric_type=DataTypeLabel.TIME_SERIES,
        time_delay=30,
    )
    second_item = ItemModel.objects.create(
        strategy_id=strategy.id,
        name="origin_item_b",
        expression="b",
        functions=[],
        origin_sql="origin sql b",
        no_data_config={"is_enabled": False, "continuous": 1, "agg_dimension": []},
        target=[[]],
        metric_type=DataTypeLabel.TIME_SERIES,
    )
    query_config_a = QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=first_item.id,
        alias="a",
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="custom.2_bkmonitor_time_series_500.origin_a",
        config={
            "result_table_id": "2_bkmonitor_time_series_500",
            "agg_method": "MAX",
            "agg_interval": 120,
            "agg_dimension": ["bk_target_ip"],
            "agg_condition": [],
            "metric_field": "origin_a",
            "unit": "count",
            "functions": [],
        },
    )
    query_config_extra = QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=first_item.id,
        alias="extra",
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="custom.2_bkmonitor_time_series_500.origin_extra",
        config={
            "result_table_id": "2_bkmonitor_time_series_500",
            "agg_method": "COUNT",
            "agg_interval": 120,
            "agg_dimension": ["bk_target_ip"],
            "agg_condition": [],
            "metric_field": "origin_extra",
            "unit": "count",
            "functions": [],
        },
    )
    algorithm_a = AlgorithmModel.objects.create(
        strategy_id=strategy.id,
        item_id=first_item.id,
        type="Threshold",
        level=3,
        unit_prefix="",
        config=[[{"method": "gte", "threshold": 1}]],
    )
    algorithm_extra = AlgorithmModel.objects.create(
        strategy_id=strategy.id,
        item_id=first_item.id,
        type="Threshold",
        level=2,
        unit_prefix="",
        config=[[{"method": "gte", "threshold": 2}]],
    )
    query_config_b = QueryConfigModel.objects.create(
        strategy_id=strategy.id,
        item_id=second_item.id,
        alias="b",
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_id="custom.2_bkmonitor_time_series_500.origin_b",
        config={
            "result_table_id": "2_bkmonitor_time_series_500",
            "agg_method": "MAX",
            "agg_interval": 120,
            "agg_dimension": ["bk_target_ip"],
            "agg_condition": [],
            "metric_field": "origin_b",
            "unit": "count",
            "functions": [],
        },
    )
    algorithm_b = AlgorithmModel.objects.create(
        strategy_id=strategy.id,
        item_id=second_item.id,
        type="Threshold",
        level=3,
        unit_prefix="",
        config=[[{"method": "gte", "threshold": 3}]],
    )
    detect_a = DetectModel.objects.create(
        strategy_id=strategy.id,
        level=3,
        expression="",
        connector="or",
        trigger_config={"count": 1, "check_window": 1},
        recovery_config={"check_window": 1, "status_setter": "recovery"},
    )
    detect_extra = DetectModel.objects.create(
        strategy_id=strategy.id,
        level=2,
        expression="",
        connector="and",
        trigger_config={"count": 2, "check_window": 2},
        recovery_config={"check_window": 2, "status_setter": "recovery"},
    )
    notice_config = ActionConfig.objects.create(
        name="origin_notice_config",
        desc="origin notice",
        bk_biz_id=str(BK_BIZ_ID),
        plugin_id=ActionConfig.NOTICE_PLUGIN_ID,
        execute_config={
            "template_detail": {
                "need_poll": False,
                "notify_interval": 600,
                "interval_notify_mode": "standard",
                "template": [{"signal": "abnormal", "message_tmpl": "origin notice template"}],
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
        options={"start_time": "08:00:00", "end_time": "20:00:00", "origin": True},
    )
    action_config = ActionConfig.objects.create(
        name="origin_action_config",
        desc="origin action",
        bk_biz_id=str(BK_BIZ_ID),
        plugin_id="webhook",
        execute_config={"template_detail": {"url": "https://example.test/origin"}},
    )
    action_relation = StrategyActionConfigRelation.objects.create(
        strategy_id=strategy.id,
        config_id=action_config.id,
        relate_type=StrategyActionConfigRelation.RelateType.ACTION,
        signal=["abnormal"],
        user_groups=[201],
        user_type="main",
        options={
            "start_time": "09:00:00",
            "end_time": "21:00:00",
            "converge_config": {"is_enabled": False},
            "origin": True,
        },
    )
    StrategyLabel.objects.bulk_create(
        [
            StrategyLabel(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/origin/"),
            StrategyLabel(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/keep_before_patch/"),
        ]
    )
    return {
        "strategy": strategy,
        "first_item": first_item,
        "second_item": second_item,
        "query_config_a": query_config_a,
        "query_config_extra": query_config_extra,
        "query_config_b": query_config_b,
        "algorithm_a": algorithm_a,
        "algorithm_extra": algorithm_extra,
        "algorithm_b": algorithm_b,
        "detect_a": detect_a,
        "detect_extra": detect_extra,
        "notice_config": notice_config,
        "notice_relation": notice_relation,
        "action_config": action_config,
        "action_relation": action_relation,
    }


def test_strategy_config_patch_updates_selected_fields_and_preserves_missing_config(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    first_item: ItemModel = strategy_config_fixture["first_item"]
    second_item: ItemModel = strategy_config_fixture["second_item"]
    notice_relation: StrategyActionConfigRelation = strategy_config_fixture["notice_relation"]
    action_relation: StrategyActionConfigRelation = strategy_config_fixture["action_relation"]
    origin_action_relation: dict[str, Any] = copy.deepcopy(
        StrategyActionConfigRelation.objects.filter(id=action_relation.id).values().get()
    )
    origin_action_config: dict[str, Any] = copy.deepcopy(
        ActionConfig.objects.filter(id=strategy_config_fixture["action_config"].id).values().get()
    )

    result = perform_strategy_config_patch(
        [strategy.id],
        {
            "name": "strategy_config_patch_renamed",
            "scenario": "host_process",
            "items": [
                {
                    "id": first_item.id,
                    "name": "patched_item_a",
                    "query_configs": [make_query_config_payload("patched", "patched_metric")],
                    "algorithms": [make_algorithm_payload(2, 100)],
                }
            ],
            "detects": [make_detect_payload(2, 4)],
            "labels": ["final_label", "final_parent/final_child"],
            "notice": {"user_groups": [301, 302]},
        },
    )

    assert result == [strategy.id]

    strategy.refresh_from_db()
    first_item.refresh_from_db()
    second_item.refresh_from_db()
    notice_relation.refresh_from_db()
    action_relation.refresh_from_db()

    assert strategy.name == "strategy_config_patch_renamed"
    assert strategy.scenario == "host_process"
    assert strategy.source == "custom_source"
    assert strategy.is_enabled is False
    assert strategy.is_invalid is True
    assert strategy.invalid_type == StrategyModel.InvalidType.INVALID_METRIC
    assert strategy.priority == 10
    assert strategy.priority_group_key == "PGK:custom-key"

    assert first_item.name == "patched_item_a"
    assert first_item.expression == "a"
    assert first_item.origin_sql == "origin sql a"
    assert first_item.no_data_config["continuous"] == 5
    assert first_item.time_delay == 30
    assert second_item.name == "origin_item_b"

    query_configs = list(QueryConfigModel.objects.filter(item_id=first_item.id).order_by("alias"))
    assert [(query_config.alias, query_config.config["metric_field"]) for query_config in query_configs] == [
        ("patched", "patched_metric")
    ]
    algorithms = list(AlgorithmModel.objects.filter(item_id=first_item.id).order_by("level"))
    assert [(algorithm.level, algorithm.config[0][0]["threshold"]) for algorithm in algorithms] == [(2, 100.0)]
    detects = list(DetectModel.objects.filter(strategy_id=strategy.id).order_by("level"))
    assert [(detect.level, detect.trigger_config["count"]) for detect in detects] == [(2, 4)]

    assert_labels(strategy.id, ["final_label", "final_parent/final_child"])
    assert notice_relation.user_groups == [301, 302]
    assert StrategyActionConfigRelation.objects.filter(id=action_relation.id).values().get() == origin_action_relation
    assert ActionConfig.objects.filter(id=origin_action_config["id"]).values().get() == origin_action_config


def test_strategy_config_patch_allows_single_item_patch_without_id(strategy_config_fixture: dict[str, Any]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    second_item: ItemModel = strategy_config_fixture["second_item"]
    ItemModel.objects.filter(id=strategy_config_fixture["first_item"].id).delete()
    QueryConfigModel.objects.filter(item_id=strategy_config_fixture["first_item"].id).delete()
    AlgorithmModel.objects.filter(item_id=strategy_config_fixture["first_item"].id).delete()

    result = perform_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                make_item_patch(
                    "single_item_patch_without_id",
                    query_configs=[make_query_config_payload("single", "single_metric")],
                    algorithms=[make_algorithm_payload(3, 300)],
                )
            ],
        },
    )

    assert result == [strategy.id]
    second_item.refresh_from_db()
    assert second_item.name == "single_item_patch_without_id"
    assert list(QueryConfigModel.objects.filter(item_id=second_item.id).values_list("alias", flat=True)) == ["single"]
    assert list(AlgorithmModel.objects.filter(item_id=second_item.id).values_list("level", flat=True)) == [3]


@pytest.mark.parametrize(
    "strategy_config",
    [
        {"unknown": "value"},
        {"expected_labels": []},
        {"name": None},
        {"items": [{"id": 1, "unknown": "value"}]},
        {"items": [{"id": 1, "name": None}]},
        {"notice": {"unknown": "value"}},
        {"notice": {"user_groups": None}},
        None,
    ],
)
def test_strategy_config_patch_rejects_unknown_empty_and_null_fields(
    strategy_config_fixture: dict[str, Any], strategy_config: dict[str, Any] | None
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]

    assert_invalid_strategy_config_patch([strategy.id], strategy_config)


def test_strategy_config_patch_rejects_legacy_fields_mixed_with_strategy_config(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    resource = UpdatePartialStrategyV2Resource()

    with pytest.raises((CustomException, ValidationError)):
        resource.validate_request_data(
            {
                "bk_biz_id": BK_BIZ_ID,
                "ids": [strategy.id],
                "edit_data": {"is_enabled": True, "strategy_config": {"name": "mixed_name"}},
            }
        )


@pytest.mark.parametrize(
    "items",
    [
        [{"name": "missing_id_on_multi_item"}],
        [{"id": 999999, "name": "invalid_item_id"}],
    ],
)
def test_strategy_config_patch_rejects_invalid_item_identity(
    strategy_config_fixture: dict[str, Any], items: list[dict[str, Any]]
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]

    assert_invalid_strategy_config_patch([strategy.id], {"items": items})


def test_strategy_config_patch_rejects_duplicate_item_ids(strategy_config_fixture: dict[str, Any]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    first_item: ItemModel = strategy_config_fixture["first_item"]

    assert_invalid_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                {"id": first_item.id, "name": "first_patch"},
                {"id": first_item.id, "name": "duplicate_patch"},
            ]
        },
    )


@pytest.mark.parametrize("strategy_config", [{}, {"items": []}, {"notice": {}}])
def test_strategy_config_patch_empty_payload_keeps_metadata_and_history(
    strategy_config_fixture: dict[str, Any], strategy_config: dict[str, Any]
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    origin_update_time: datetime.datetime = strategy.update_time
    origin_update_user: str = strategy.update_user

    result = perform_strategy_config_patch([strategy.id], strategy_config)

    assert result == [strategy.id]
    assert_strategy_metadata_unchanged(strategy, origin_update_time, origin_update_user)


def test_strategy_config_patch_same_collection_with_different_order_keeps_metadata(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    algorithm_a: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    algorithm_extra: AlgorithmModel = strategy_config_fixture["algorithm_extra"]
    detect_a: DetectModel = strategy_config_fixture["detect_a"]
    detect_extra: DetectModel = strategy_config_fixture["detect_extra"]
    origin_update_time: datetime.datetime = strategy.update_time
    origin_update_user: str = strategy.update_user

    result = perform_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                {
                    "id": strategy_config_fixture["first_item"].id,
                    "algorithms": [
                        algorithm.to_dict() for algorithm in Algorithm.from_models([algorithm_a, algorithm_extra])
                    ][::-1],
                }
            ],
            "detects": [detect.to_dict() for detect in Detect.from_models([detect_a, detect_extra])][::-1],
        },
    )

    assert result == [strategy.id]
    assert_strategy_metadata_unchanged(strategy, origin_update_time, origin_update_user)


def test_strategy_config_patch_can_add_query_configs_algorithms_and_detects(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    second_item: ItemModel = strategy_config_fixture["second_item"]

    result = perform_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                {
                    "id": second_item.id,
                    "query_configs": [
                        make_query_config_payload(
                            "b", "origin_b", query_config_id=strategy_config_fixture["query_config_b"].id
                        ),
                        make_query_config_payload("b_extra", "added_metric"),
                    ],
                    "algorithms": [
                        make_algorithm_payload(
                            strategy_config_fixture["algorithm_b"].level,
                            strategy_config_fixture["algorithm_b"].config[0][0]["threshold"],
                            algorithm_id=strategy_config_fixture["algorithm_b"].id,
                        ),
                        make_algorithm_payload(2, 200),
                    ],
                }
            ],
            "detects": [
                make_detect_payload(
                    strategy_config_fixture["detect_a"].level,
                    strategy_config_fixture["detect_a"].trigger_config["count"],
                    detect_id=strategy_config_fixture["detect_a"].id,
                ),
                make_detect_payload(
                    strategy_config_fixture["detect_extra"].level,
                    strategy_config_fixture["detect_extra"].trigger_config["count"],
                    detect_id=strategy_config_fixture["detect_extra"].id,
                ),
                make_detect_payload(1, 3),
            ],
        },
    )

    assert result == [strategy.id]
    query_config_aliases: list[str] = list(
        QueryConfigModel.objects.filter(item_id=second_item.id).order_by("alias").values_list("alias", flat=True)
    )
    algorithm_levels: list[int] = list(
        AlgorithmModel.objects.filter(item_id=second_item.id).order_by("level").values_list("level", flat=True)
    )
    detect_levels: list[int] = list(
        DetectModel.objects.filter(strategy_id=strategy.id).order_by("level").values_list("level", flat=True)
    )
    assert query_config_aliases == ["b", "b_extra"]
    assert algorithm_levels == [2, 3]
    assert detect_levels == [1, 2, 3]


@pytest.mark.parametrize("with_ids", [False, True])
@pytest.mark.parametrize("changed", [False, True])
def test_algorithm_reordering_preserves_identity_and_backend_config(
    strategy_config_fixture: dict[str, Any], with_ids: bool, changed: bool
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    algorithms: list[AlgorithmModel] = [
        strategy_config_fixture["algorithm_a"],
        strategy_config_fixture["algorithm_extra"],
    ]
    payloads: list[dict[str, Any]] = []
    for index, algorithm in enumerate(algorithms):
        algorithm.type = AlgorithmModel.AlgorithmChoices.IntelligentDetect
        algorithm.config = {
            "plan_id": 1,
            "args": {"sensitivity": 1, "backend_parameter": index},
            "service_name": f"service-{index}",
            "grey_to_bkfara": True,
            "enable_week_compare": False,
            "visual_type": VisualType.NONE,
        }
        algorithm.save()
        payload: dict[str, Any] = {
            "type": algorithm.type,
            "level": algorithm.level,
            "config": {"plan_id": 1, "args": {"sensitivity": 2 if changed and index == 1 else 1}},
        }
        if with_ids:
            payload["id"] = algorithm.id
        payloads.append(payload)

    original_update_time: datetime.datetime = strategy.update_time
    original_update_user: str = strategy.update_user
    patch: dict[str, Any] = {"items": [{"id": item.id, "algorithms": payloads[::-1]}]}
    perform_strategy_config_patch([strategy.id], patch)
    assert set(AlgorithmModel.objects.filter(item_id=item.id).values_list("id", flat=True)) == {
        algorithm.id for algorithm in algorithms
    }
    for index, algorithm in enumerate(algorithms):
        original_level: int = algorithm.level
        algorithm.refresh_from_db()
        assert algorithm.level == original_level
        assert algorithm.config["service_name"] == f"service-{index}"
        assert algorithm.config["grey_to_bkfara"] is True
        assert algorithm.config["args"] == {
            "sensitivity": 2 if changed and index == 1 else 1,
            "backend_parameter": index,
        }
    if not changed:
        assert_strategy_metadata_unchanged(strategy, original_update_time, original_update_user)

    strategy.refresh_from_db()
    updated_at: datetime.datetime = strategy.update_time
    perform_strategy_config_patch([strategy.id], patch)
    strategy.refresh_from_db()
    assert strategy.update_time == updated_at
    assert StrategyHistoryModel.objects.filter(strategy_id=strategy.id).count() == int(changed)


def test_algorithm_replacement_keeps_matched_id_and_creates_unmatched_record(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    kept: AlgorithmModel = strategy_config_fixture["algorithm_extra"]
    deleted: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    other_item_algorithm: AlgorithmModel = strategy_config_fixture["algorithm_b"]
    other_config: Any = copy.deepcopy(other_item_algorithm.config)
    perform_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                {
                    "id": item.id,
                    "algorithms": [
                        make_algorithm_payload(1, 100, algorithm_id=other_item_algorithm.id),
                        make_algorithm_payload(kept.level, 200),
                    ],
                }
            ]
        },
    )
    kept.refresh_from_db()
    assert kept.config[0][0]["threshold"] == 200
    assert not AlgorithmModel.objects.filter(id=deleted.id).exists()
    created: AlgorithmModel = AlgorithmModel.objects.get(item_id=item.id, level=1)
    assert created.id not in {kept.id, deleted.id, other_item_algorithm.id}
    other_item_algorithm.refresh_from_db()
    assert other_item_algorithm.config == other_config


def test_algorithm_explicit_id_takes_precedence_over_type_and_level(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    first: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    second: AlgorithmModel = strategy_config_fixture["algorithm_extra"]
    first_level: int = first.level
    second_level: int = second.level
    perform_strategy_config_patch(
        [strategy.id],
        {
            "items": [
                {
                    "id": item.id,
                    "algorithms": [
                        make_algorithm_payload(first_level, 100, algorithm_id=second.id),
                        make_algorithm_payload(second_level, 200, algorithm_id=first.id),
                    ],
                }
            ]
        },
    )
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.level, first.config[0][0]["threshold"]) == (second_level, 200)
    assert (second.level, second.config[0][0]["threshold"]) == (first_level, 100)


def test_full_item_algorithm_save_keeps_positional_id_reuse(strategy_config_fixture: dict[str, Any]) -> None:
    model: StrategyModel = strategy_config_fixture["strategy"]
    strategy: Strategy = Strategy.from_models([model])[0]
    item: Item = next(item for item in strategy.items if item.id == strategy_config_fixture["first_item"].id)
    first: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    second: AlgorithmModel = strategy_config_fixture["algorithm_extra"]
    item.algorithms = [Algorithm(item.strategy_id, item.id, **make_algorithm_payload(1, 100, algorithm_id=second.id))]
    item.save_algorithms()
    first.refresh_from_db()
    assert (first.level, first.config[0][0]["threshold"]) == (1, 100)
    assert not AlgorithmModel.objects.filter(id=second.id).exists()


def test_algorithm_ambiguous_key_does_not_inherit_an_arbitrary_record(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    first: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    second: AlgorithmModel = strategy_config_fixture["algorithm_extra"]
    second.level = first.level
    second.save()
    perform_strategy_config_patch(
        [strategy.id], {"items": [{"id": item.id, "algorithms": [make_algorithm_payload(first.level, 100)]}]}
    )
    algorithm: AlgorithmModel = AlgorithmModel.objects.get(item_id=item.id)
    assert algorithm.id not in {first.id, second.id}


def test_algorithm_duplicate_match_is_rejected_without_writes(strategy_config_fixture: dict[str, Any]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    algorithm: AlgorithmModel = strategy_config_fixture["algorithm_a"]
    original: list[dict[str, Any]] = list(AlgorithmModel.objects.filter(item_id=item.id).order_by("id").values())
    with pytest.raises(ValidationError, match="同一条算法"):
        perform_strategy_config_patch(
            [strategy.id],
            {
                "items": [
                    {
                        "id": item.id,
                        "algorithms": [
                            make_algorithm_payload(algorithm.level, 100, algorithm_id=algorithm.id),
                            make_algorithm_payload(algorithm.level, 200),
                        ],
                    }
                ]
            },
        )
    assert list(AlgorithmModel.objects.filter(item_id=item.id).order_by("id").values()) == original


@pytest.mark.parametrize("component", [Algorithm, Detect])
def test_algorithm_and_detect_writes_roll_back_after_component_save(
    strategy_config_fixture: dict[str, Any], component: type[Algorithm] | type[Detect]
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    original_algorithms: list[dict[str, Any]] = list(
        AlgorithmModel.objects.filter(strategy_id=strategy.id).order_by("id").values()
    )
    original_detects: list[dict[str, Any]] = list(
        DetectModel.objects.filter(strategy_id=strategy.id).order_by("id").values()
    )
    original_save: Callable[[Any], None] = component.save

    def save_then_fail(config: Algorithm | Detect) -> None:
        original_save(config)
        raise RuntimeError("fail after component saved")

    with mock.patch.object(component, "save", autospec=True, side_effect=save_then_fail) as save_mock:
        with pytest.raises(RuntimeError, match="fail after component saved"):
            perform_strategy_config_patch(
                [strategy.id],
                {
                    "items": [{"id": item.id, "algorithms": [make_algorithm_payload(1, 100)]}],
                    "detects": [make_detect_payload(1, 3)],
                },
            )
    assert save_mock.call_count == 1
    assert list(AlgorithmModel.objects.filter(strategy_id=strategy.id).order_by("id").values()) == original_algorithms
    assert list(DetectModel.objects.filter(strategy_id=strategy.id).order_by("id").values()) == original_detects
    assert StrategyHistoryModel.objects.get(strategy_id=strategy.id).status is False


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("count", [0, 1, 3])
def test_full_and_partial_detect_saves_preserve_replacement_contracts(
    strategy_config_fixture: dict[str, Any], partial: bool, count: int
) -> None:
    model: StrategyModel = strategy_config_fixture["strategy"]
    original_ids: list[int] = list(
        DetectModel.objects.filter(strategy_id=model.id).order_by("id").values_list("id", flat=True)
    )
    payloads: list[dict[str, Any]] = [make_detect_payload(level, level + 1) for level in range(1, count + 1)]
    if partial:
        if not payloads:
            # 局部入口的完整配置校验不允许清空检测配置，保留这个既有约束。
            with pytest.raises(ValidationError, match="detects"):
                perform_strategy_config_patch([model.id], {"detects": []})
            assert (
                list(DetectModel.objects.filter(strategy_id=model.id).order_by("id").values_list("id", flat=True))
                == original_ids
            )
            return
        perform_strategy_config_patch([model.id], {"detects": payloads})
    else:
        strategy: Strategy = Strategy.from_models([model])[0]
        strategy.detects = [Detect(strategy.id, **payload) for payload in payloads]
        strategy.save()

    detects: list[DetectModel] = list(DetectModel.objects.filter(strategy_id=model.id).order_by("id"))
    assert [detect.id for detect in detects[: len(original_ids)]] == original_ids[:count]
    assert [(detect.level, detect.trigger_config["count"]) for detect in detects] == [
        (level, level + 1) for level in range(1, count + 1)
    ]


def test_strategy_config_patch_can_clear_labels_and_notice_user_groups(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    notice_relation: StrategyActionConfigRelation = strategy_config_fixture["notice_relation"]

    result = perform_strategy_config_patch([strategy.id], {"labels": [], "notice": {"user_groups": []}})

    assert result == [strategy.id]
    assert_labels(strategy.id, [])
    notice_relation.refresh_from_db()
    assert notice_relation.user_groups == []


@pytest.mark.parametrize("priority_group_key", ["", "automatic-key-before"])
def test_strategy_config_patch_name_and_labels_do_not_recalculate_priority_group_key(
    strategy_config_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch, priority_group_key: str
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    strategy.priority_group_key = priority_group_key
    strategy.save(update_fields=["priority_group_key"])
    get_priority_group_key = mock.Mock(side_effect=AssertionError("不应重算优先级分组"))
    monkeypatch.setattr(Strategy, "get_priority_group_key", get_priority_group_key)

    perform_strategy_config_patch([strategy.id], {"name": "name_only_patch", "labels": ["label_only_patch"]})

    strategy.refresh_from_db()
    assert strategy.name == "name_only_patch"
    assert strategy.priority_group_key == priority_group_key
    assert get_priority_group_key.call_count == 0
    assert_labels(strategy.id, ["label_only_patch"])


def test_strategy_config_patch_validates_merged_config_and_rolls_back(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    first_item: ItemModel = strategy_config_fixture["first_item"]
    origin_item = copy.deepcopy(ItemModel.objects.filter(id=first_item.id).values().get())
    origin_query_configs = list(QueryConfigModel.objects.filter(item_id=first_item.id).order_by("id").values())
    origin_algorithms = list(AlgorithmModel.objects.filter(item_id=first_item.id).order_by("id").values())

    with pytest.raises((CustomException, ValidationError)):
        perform_strategy_config_patch(
            [strategy.id],
            {
                "items": [
                    {
                        "id": first_item.id,
                        "name": "invalid_algorithm_patch",
                        "algorithms": [{"type": "Threshold", "level": 2, "config": [[{"method": "gte"}]]}],
                    }
                ]
            },
        )

    assert ItemModel.objects.filter(id=first_item.id).values().get() == origin_item
    assert list(QueryConfigModel.objects.filter(item_id=first_item.id).order_by("id").values()) == origin_query_configs
    assert list(AlgorithmModel.objects.filter(item_id=first_item.id).order_by("id").values()) == origin_algorithms


def test_strategy_config_patch_rolls_back_after_child_save_failure(
    strategy_config_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    first_item: ItemModel = strategy_config_fixture["first_item"]
    origin_item = copy.deepcopy(ItemModel.objects.filter(id=first_item.id).values().get())
    origin_query_configs = list(QueryConfigModel.objects.filter(item_id=first_item.id).order_by("id").values())
    save_calls = 0
    original_save = QueryConfig.save

    def fail_after_query_config_saved(self: QueryConfig, instance: Any = None) -> None:
        nonlocal save_calls
        save_calls += 1
        original_save(self, instance)
        saved_query_config: QueryConfigModel = QueryConfigModel.objects.get(id=self.id)
        assert saved_query_config.config["metric_field"] == "rollback_metric"
        raise RuntimeError("fail after query config saved")

    monkeypatch.setattr(QueryConfig, "save", fail_after_query_config_saved)

    with pytest.raises(RuntimeError, match="fail after query config saved"):
        perform_strategy_config_patch(
            [strategy.id],
            {
                "items": [
                    {
                        "id": first_item.id,
                        "name": "should_rollback",
                        "query_configs": [make_query_config_payload("rollback", "rollback_metric")],
                    }
                ]
            },
        )

    assert save_calls == 1
    assert ItemModel.objects.filter(id=first_item.id).values().get() == origin_item
    assert list(QueryConfigModel.objects.filter(item_id=first_item.id).order_by("id").values()) == origin_query_configs


def test_legacy_is_enabled_partial_update_keeps_existing_behavior(strategy_config_fixture: dict[str, Any]) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]

    result = perform_legacy_patch([strategy.id], {"is_enabled": True})

    assert result == [strategy.id]
    strategy.refresh_from_db()
    assert strategy.is_enabled is True


def test_strategy_config_patch_rejects_query_incompatible_with_saved_outputs(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    meta: dict[str, Any] = {
        "query_output_config": {
            "response_contract": "named_outputs/v1",
            "legacy_output_ref": "A",
            "output_list": [
                {"reference_name": "A", "expression": "a"},
                {"reference_name": "Extra", "expression": "extra"},
            ],
        }
    }
    ItemModel.objects.filter(id=item.id).update(meta=meta)
    original_queries: list[dict[str, Any]] = list(
        QueryConfigModel.objects.filter(item_id=item.id).order_by("id").values()
    )

    with pytest.raises(ValidationError, match="query_output_config"):
        perform_strategy_config_patch(
            [strategy.id],
            {"items": [{"id": item.id, "query_configs": [make_query_config_payload("a", "replacement")]}]},
        )

    item.refresh_from_db()
    assert item.meta == meta
    assert list(QueryConfigModel.objects.filter(item_id=item.id).order_by("id").values()) == original_queries
    assert not StrategyHistoryModel.objects.filter(strategy_id=strategy.id).exists()


def test_strategy_config_patch_rejects_stale_labels_without_writing(
    strategy_config_fixture: dict[str, Any],
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    expected_labels: list[str] = ["origin", "keep_before_patch"]
    StrategyLabel.objects.create(bk_biz_id=BK_BIZ_ID, strategy_id=strategy.id, label_name="/concurrent-label/")
    original_update_time: datetime.datetime = strategy.update_time

    with pytest.raises(ValidationError, match="策略标签已变化"):
        perform_strategy_config_patch(
            [strategy.id],
            {"name": "must_not_write", "labels": ["replacement"], "expected_labels": expected_labels},
        )

    assert_strategy_metadata_unchanged(strategy, original_update_time, strategy.update_user)
    assert strategy.name == "strategy_config_patch_origin"
    assert_labels(strategy.id, [*expected_labels, "concurrent-label"])


def test_strategy_config_patch_supplements_static_target_query_dimensions(
    strategy_config_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    strategy: StrategyModel = strategy_config_fixture["strategy"]
    item: ItemModel = strategy_config_fixture["first_item"]
    query_config: dict[str, Any] = make_query_config_payload("a", "cpu_usage")
    query_config.update(data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR, agg_dimension=[])
    monkeypatch.setattr("bkmonitor.strategy.new_strategy.is_ipv6_biz", lambda bk_biz_id: False)

    perform_strategy_config_patch([strategy.id], {"items": [{"id": item.id, "query_configs": [query_config]}]})

    persisted_query: QueryConfigModel = QueryConfigModel.objects.get(item_id=item.id)
    assert set(persisted_query.config["agg_dimension"]) == {"bk_target_ip", "bk_target_cloud_id"}
