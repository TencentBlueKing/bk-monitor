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
import json
from unittest.mock import Mock, call

import fakeredis
import pytest

from alarm_backends.core.cache import strategy as module
from alarm_backends.core.cache.cmdb import TopoManager
from alarm_backends.core.cache.strategy import StrategyCacheManager as Manager
from bkmonitor.models import MetricListCache, StrategyModel
from constants.strategy import TargetFieldType


@pytest.fixture
def strategy_config():
    return {
        "id": 1,
        "bk_biz_id": 999,
        "is_invalid": True,
        "invalid_type": StrategyModel.InvalidType.INVALID_METRIC,
        "update_time": "2026-10-26T00:00:00Z",
        "create_time": "2026-10-26T00:00:00Z",
        "items": [
            {
                "id": 10,
                "target": [[{"field": TargetFieldType.host_topo, "value": [{"bk_obj_id": "set", "bk_inst_id": 999}]}]],
                "algorithms": [{"type": "Threshold", "unit_prefix": "invalid_unit"}],
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "metric_id": "bk_monitor.missing.metric",
                        "unit": "invalid_unit",
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize("invalid_type", [value for value, _ in StrategyModel.InvalidType.Choices])
def test_cache_refresh_clears_invalid_status_without_validity_queries(monkeypatch, strategy_config, invalid_type):
    strategy_config["invalid_type"] = invalid_type
    normal_strategy = copy.deepcopy(strategy_config)
    normal_strategy.update(id=2, is_invalid=False, invalid_type="")
    normal_strategy["items"][0]["id"] = 20
    list_strategies = Mock(return_value={"data": [strategy_config, normal_strategy]})
    monkeypatch.setattr(module, "list_strategy", list_strategies)
    model_filter = Mock()
    monkeypatch.setattr(StrategyModel.objects, "filter", model_filter)
    monkeypatch.setattr(module.BusinessManager, "keys", Mock(side_effect=AssertionError("business validity query")))
    monkeypatch.setattr(MetricListCache.objects, "filter", Mock(side_effect=AssertionError("metric validity query")))
    monkeypatch.setattr(TopoManager, "mget", Mock(side_effect=AssertionError("target validity query")))
    monkeypatch.setattr(Manager, "add_source_identity", Mock())
    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(Manager, "cache", cache)

    strategies = Manager.get_strategies_map([999])
    Manager.refresh_strategy(list(strategies.values()))

    assert set(strategies) == {1, 2}
    cached_strategy = json.loads(cache.get(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1)))
    assert cached_strategy["is_invalid"] is False
    assert cached_strategy["invalid_type"] == ""
    assert cached_strategy["items"][0]["query_md5"]
    list_strategies.assert_called_once_with(apply_converters=False, is_enabled=True, bk_biz_ids=[999])
    model_filter.assert_called_once_with(id__in=[1], is_invalid=True)
    model_filter.return_value.update.assert_called_once_with(is_invalid=False, invalid_type="")


def test_cache_refresh_does_not_update_normal_strategies(monkeypatch, strategy_config):
    strategy_config.update(is_invalid=False, invalid_type="")
    monkeypatch.setattr(module, "list_strategy", Mock(return_value={"data": [strategy_config]}))
    model_filter = Mock()
    monkeypatch.setattr(StrategyModel.objects, "filter", model_filter)

    strategies = Manager.get_strategies_map([999])

    assert strategies[1]["is_invalid"] is False
    model_filter.assert_not_called()


@pytest.mark.parametrize("failed_batch", [None, 0, 1])
def test_invalid_status_updates_are_batched_and_continue_after_failure(monkeypatch, strategy_config, failed_batch):
    configs = []
    for strategy_id in range(1, 1002):
        config = copy.deepcopy(strategy_config)
        config["id"] = strategy_id
        configs.append(config)
    monkeypatch.setattr(module, "list_strategy", Mock(return_value={"data": configs}))
    batches = [Mock(), Mock()]
    if failed_batch is not None:
        batches[failed_batch].update.side_effect = RuntimeError("status update failed")
    model_filter = Mock(side_effect=batches)
    monkeypatch.setattr(StrategyModel.objects, "filter", model_filter)

    strategies = Manager.get_strategies_map([999])

    assert len(strategies) == 1001
    assert all(strategy["is_invalid"] is False for strategy in strategies.values())
    assert model_filter.call_args_list == [
        call(id__in=list(range(1, 1001)), is_invalid=True),
        call(id__in=[1001], is_invalid=True),
    ]
    for batch in batches:
        batch.update.assert_called_once_with(is_invalid=False, invalid_type="")


@pytest.mark.parametrize("refresh_method", ["refresh", "smart_refresh"])
def test_status_update_failure_does_not_block_cache_refresh(monkeypatch, strategy_config, caplog, refresh_method):
    monkeypatch.setattr(module, "list_strategy", Mock(return_value={"data": [strategy_config]}))
    model_filter = Mock()
    model_filter.return_value.update.side_effect = RuntimeError("status update failed")
    monkeypatch.setattr(StrategyModel.objects, "filter", model_filter)
    histories = Mock()
    histories.exists.return_value = refresh_method == "smart_refresh"
    histories.values.return_value = []
    monkeypatch.setattr(module.StrategyHistoryModel.objects, "filter", Mock(return_value=histories))
    monkeypatch.setattr(Manager, "handle_history_strategies", Mock(return_value=({999}, set())))
    monkeypatch.setattr(module.BusinessManager, "keys", lambda: [999])
    monkeypatch.setattr(module.metrics, "report_all", Mock())
    for name in ("add_source_identity", "add_target_shield_condition", "add_enabled_cluster_condition"):
        monkeypatch.setattr(Manager, name, Mock(__name__=name))
    cache = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(Manager, "cache", cache)
    cache.set(Manager.BK_BIZ_IDS_CACHE_KEY, "[999]")
    cache.set(Manager.IDS_CACHE_KEY, "[1]")
    cache.set(Manager.LAST_UPDATED_CACHE_KEY, 900)
    cache.set(Manager.CACHE_KEY_TEMPLATE.format(strategy_id=1), json.dumps({"id": 1, "is_invalid": True}))

    getattr(Manager, refresh_method)()

    cached_strategy = Manager.get_strategy_by_id(1)
    assert cached_strategy["is_invalid"] is False
    assert cached_strategy["invalid_type"] == ""
    query_md5 = cached_strategy["items"][0]["query_md5"]
    group = json.loads(cache.hget(Manager.STRATEGY_GROUP_CACHE_KEY, query_md5))
    assert group["1"] == [10]
    assert Manager.get_strategy_ids() == [1]
    model_filter.return_value.update.assert_called_once_with(is_invalid=False, invalid_type="")
    assert "reset invalid strategy status failed" in caplog.text
    assert "refresh strategy error when" not in caplog.text
    if refresh_method == "smart_refresh":
        assert int(cache.get(Manager.LAST_UPDATED_CACHE_KEY)) > 900


def test_related_strategy_is_cached_as_normal(strategy_config):
    query = strategy_config["items"][0]["query_configs"][0]
    query.update(data_type_label="alert", bkmonitor_strategy_id=999)
    strategy_config["invalid_type"] = StrategyModel.InvalidType.INVALID_RELATED_STRATEGY

    assert Manager.handle_strategy(strategy_config) is True
    assert strategy_config["is_invalid"] is False
    assert strategy_config["invalid_type"] == ""


@pytest.mark.parametrize(
    ("field", "manager", "object_id"),
    [
        (TargetFieldType.host_set_template, module.SetTemplateManager, "set"),
        (TargetFieldType.host_service_template, module.ServiceTemplateManager, "module"),
    ],
)
@pytest.mark.parametrize("instances", [[100, {"bk_inst_id": 101}], []])
def test_template_conversion_keeps_normal_status(monkeypatch, strategy_config, field, manager, object_id, instances):
    monkeypatch.setattr(module, "bk_biz_id_to_bk_tenant_id", lambda _: "tenant-a")
    get_template = Mock(return_value=instances)
    monkeypatch.setattr(manager, "get", get_template)
    target = strategy_config["items"][0]["target"][0][0]
    target.update(field=field, value=[{"bk_inst_id": 99}])

    assert Manager.handle_strategy(strategy_config) is bool(instances)
    assert target["field"] == TargetFieldType.host_topo
    assert (
        target["value"] == [{"bk_obj_id": object_id, "bk_inst_id": node_id} for node_id in (100, 101)][: len(instances)]
    )
    assert strategy_config["is_invalid"] is False
    assert strategy_config["invalid_type"] == ""
    get_template.assert_called_once_with(bk_tenant_id="tenant-a", id=99)


def test_bk_data_time_field_is_still_corrected_without_target(strategy_config):
    strategy_config["items"][0]["target"] = [[]]
    query = strategy_config["items"][0]["query_configs"][0]
    query.update(data_source_label="bk_data", time_field="time")

    assert Manager.handle_strategy(strategy_config) is True
    assert query["time_field"] == "dtEventTimeStamp"
