"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeStrategyQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filter_kwargs = None
        self.order_by_args = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def order_by(self, *args):
        self.order_by_args = args
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeStrategyManager:
    def __init__(self, detail_row=None, list_queryset=None):
        self.detail_row = detail_row
        self.list_queryset = list_queryset
        self.get_kwargs = None

    def get(self, **kwargs):
        self.get_kwargs = kwargs
        return self.detail_row

    def filter(self, **kwargs):
        self.list_queryset.filter_kwargs = kwargs
        return self.list_queryset


class FakeStrategyObject:
    def __init__(self, config):
        self.config = config
        self.restored = False

    def restore(self):
        self.restored = True

    def to_dict(self):
        return dict(self.config)


def test_inspect_strategy_config_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("inspect-strategy-config")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.inspect_strategy_config")

    assert op.func_name == "bkm_cli.inspect_strategy_config"
    assert op.capability_level == "inspect"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_inspect_strategy_config_reads_current_shared_group_members(monkeypatch):
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    monkeypatch.setattr(
        StrategyCacheManager,
        "get_strategy_group_detail",
        classmethod(
            lambda cls, group_key: {
                "2": [20],
                "1": [10, 11],
                "bk_biz_id": 7,
                "interval_list": [60],
            }
        ),
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-strategy-config",
            "params": {"operation": "shared_group", "strategy_group_key": "group-a"},
        }
    )

    assert result["result"] == {
        "operation": "shared_group",
        "strategy_group_key": "group-a",
        "found": True,
        "bk_biz_id": 7,
        "members": [
            {"strategy_id": 1, "item_ids": [10, 11]},
            {"strategy_id": 2, "item_ids": [20]},
        ],
    }


def test_inspect_strategy_config_detail_uses_strategy_aggregation(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import strategy

    model = SimpleNamespace(id=121950, bk_biz_id=7)
    strategy.StrategyModel.objects = FakeStrategyManager(detail_row=model)
    strategy_obj = FakeStrategyObject(
        {
            "id": 121950,
            "bk_biz_id": 7,
            "name": "demo strategy",
            "scenario": "os",
            "type": "monitor",
            "source": "bkmonitorv3",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "priority": 1,
            "priority_group_key": "PGK:demo",
            "items": [{"id": 1, "query_configs": [{"metric_field": "cpu_usage"}]}],
            "detects": [{"id": 2, "trigger_config": {"count": 3}}],
            "actions": [{"id": 3, "user_groups": [10]}],
            "notice": {"id": 4, "user_groups": [10]},
            "issue_config": {"enabled": True},
        }
    )
    filled_configs = []

    monkeypatch.setattr(strategy.Strategy, "from_models", lambda rows: [strategy_obj])
    monkeypatch.setattr(strategy.Strategy, "fill_user_groups", lambda configs: filled_configs.extend(configs))

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-strategy-config",
            "params": {
                "operation": "detail",
                "bk_biz_id": 7,
                "strategy_id": 121950,
                "include_user_groups": True,
            },
        }
    )

    assert strategy.StrategyModel.objects.get_kwargs == {"bk_biz_id": 7, "id": 121950}
    assert strategy_obj.restored is True
    assert len(filled_configs) == 1
    assert result["result"]["operation"] == "detail"
    assert result["result"]["strategy"]["id"] == 121950
    assert result["result"]["strategy"]["priority_group_key"] == "PGK:demo"
    assert result["result"]["strategy"]["items"][0]["query_configs"][0]["metric_field"] == "cpu_usage"


def test_inspect_strategy_config_list_by_priority_group_returns_summary(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import strategy

    rows = [
        SimpleNamespace(
            id=119278,
            bk_biz_id=7,
            name="main strategy",
            scenario="os",
            type="monitor",
            source="bkmonitorv3",
            is_enabled=False,
            is_invalid=True,
            invalid_type="deleted_related_strategy",
            priority=0,
            priority_group_key="PGK:demo",
            update_time="2026-04-24 10:00:00",
            update_user="admin",
        ),
        SimpleNamespace(
            id=121950,
            bk_biz_id=7,
            name="follower strategy",
            scenario="os",
            type="monitor",
            source="bkmonitorv3",
            is_enabled=True,
            is_invalid=False,
            invalid_type="",
            priority=1,
            priority_group_key="PGK:demo",
            update_time="2026-04-24 11:00:00",
            update_user="operator",
        ),
    ]
    queryset = FakeStrategyQuerySet(rows)
    strategy.StrategyModel.objects = FakeStrategyManager(list_queryset=queryset)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-strategy-config",
            "params": {
                "operation": "list_by_priority_group",
                "bk_biz_id": "7",
                "priority_group_key": "PGK:demo",
                "include_disabled": True,
                "include_invalid": True,
            },
        }
    )

    assert queryset.filter_kwargs == {"bk_biz_id": 7, "priority_group_key": "PGK:demo"}
    assert queryset.order_by_args == ("priority", "id")
    assert result["result"]["operation"] == "list_by_priority_group"
    assert result["result"]["count"] == 2
    assert result["result"]["strategies"][0]["id"] == 119278
    assert result["result"]["strategies"][1]["priority"] == 1


def test_inspect_strategy_config_rejects_missing_required_params():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "inspect-strategy-config",
                "params": {
                    "operation": "detail",
                    "bk_biz_id": 7,
                },
            }
        )

    assert "strategy_id" in str(exc.value)


def _eligible_query_config(metric_field: str) -> dict:
    """time_series 命中 alarm_backends eligibility 三类之一；测试最小覆盖字段。"""
    return {"data_source_label": "bk_monitor", "data_type_label": "time_series", "metric_field": metric_field}


def test_inspect_strategy_config_detail_default_injects_strategy_group_key(monkeypatch):
    """detail 对 eligible item 默认基于 StrategyCacheManager.get_query_md5 注入 strategy_group_key。"""
    from kernel_api.rpc.functions.bkm_cli import strategy

    model = SimpleNamespace(id=148631, bk_biz_id=100864)
    strategy.StrategyModel.objects = FakeStrategyManager(detail_row=model)
    strategy_obj = FakeStrategyObject(
        {
            "id": 148631,
            "bk_biz_id": 100864,
            "name": "access pull demo",
            "scenario": "os",
            "type": "monitor",
            "source": "bkmonitorv3",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "priority": 1,
            "priority_group_key": "PGK:demo",
            "items": [
                {"id": 1, "query_configs": [_eligible_query_config("pro_exist")]},
                {"id": 2, "query_configs": [_eligible_query_config("fd_num")]},
            ],
            "detects": [],
            "actions": [],
            "notice": {},
            "issue_config": {},
        }
    )

    captured_calls = []

    def fake_get_query_md5(bk_biz_id, item):
        captured_calls.append((bk_biz_id, item["id"]))
        return f"md5-{item['id']}"

    monkeypatch.setattr(strategy.Strategy, "from_models", lambda rows: [strategy_obj])
    monkeypatch.setattr(strategy.Strategy, "fill_user_groups", lambda configs: None)
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    monkeypatch.setattr(StrategyCacheManager, "get_query_md5", classmethod(lambda cls, b, i: fake_get_query_md5(b, i)))

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-strategy-config", "params": {"operation": "detail", "strategy_id": 148631}}
    )

    items = result["result"]["strategy"]["items"]
    assert items[0]["strategy_group_key"] == "md5-1"
    assert items[1]["strategy_group_key"] == "md5-2"
    assert captured_calls == [(100864, 1), (100864, 2)]


def test_inspect_strategy_config_detail_skips_ineligible_data_types(monkeypatch):
    """非 alarm_backends eligibility 范围的 item 不应注入 strategy_group_key。

    与 alarm_backends/core/cache/strategy.py:571-577 写入条件严格对齐——否则 agent
    拿假 key 去 Redis 查 TokenBucket / checkpoint / duplicate 会被带偏。
    """
    from kernel_api.rpc.functions.bkm_cli import strategy

    model = SimpleNamespace(id=777, bk_biz_id=7)
    strategy.StrategyModel.objects = FakeStrategyManager(detail_row=model)
    strategy_obj = FakeStrategyObject(
        {
            "id": 777,
            "bk_biz_id": 7,
            "name": "mixed eligibility",
            "scenario": "os",
            "type": "monitor",
            "source": "bkmonitorv3",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "priority": 1,
            "priority_group_key": "",
            "items": [
                # eligible: time_series
                {"id": 1, "query_configs": [_eligible_query_config("cpu")]},
                # 非 eligible: bk_monitor + alert
                {
                    "id": 2,
                    "query_configs": [
                        {"data_source_label": "bk_monitor", "data_type_label": "alert", "metric_field": "x"}
                    ],
                },
                # eligible: custom + event
                {
                    "id": 3,
                    "query_configs": [{"data_source_label": "custom", "data_type_label": "event", "metric_field": "y"}],
                },
                # 非 eligible: bk_data + alert（既不命中 series 也不命中 event 子条件）
                {
                    "id": 4,
                    "query_configs": [
                        {"data_source_label": "bk_data", "data_type_label": "alert", "metric_field": "z"}
                    ],
                },
                # 边界：query_configs 为空
                {"id": 5, "query_configs": []},
            ],
            "detects": [],
            "actions": [],
            "notice": {},
            "issue_config": {},
        }
    )

    monkeypatch.setattr(strategy.Strategy, "from_models", lambda rows: [strategy_obj])
    monkeypatch.setattr(strategy.Strategy, "fill_user_groups", lambda configs: None)
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    monkeypatch.setattr(StrategyCacheManager, "get_query_md5", classmethod(lambda cls, b, i: f"md5-{i['id']}"))

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-strategy-config", "params": {"operation": "detail", "strategy_id": 777}}
    )

    by_id = {item["id"]: item for item in result["result"]["strategy"]["items"]}
    assert by_id[1]["strategy_group_key"] == "md5-1"
    assert "strategy_group_key" not in by_id[2]
    assert by_id[3]["strategy_group_key"] == "md5-3"
    assert "strategy_group_key" not in by_id[4]
    assert "strategy_group_key" not in by_id[5]


def test_is_strategy_group_eligible_matches_alarm_backends_three_classes():
    """直接锁定 _is_strategy_group_eligible 的真值表，与 alarm_backends line 571-574 对齐。

    若 alarm_backends 修改了写入 STRATEGY_GROUP_CACHE_KEY 的 eligibility 条件，
    本测试会暴露差异；同步更新 _is_strategy_group_eligible 后再调整本测试。
    """
    from kernel_api.rpc.functions.bkm_cli.strategy import _is_strategy_group_eligible

    # is_series
    assert _is_strategy_group_eligible(
        {"query_configs": [{"data_source_label": "bk_monitor", "data_type_label": "time_series"}]}
    )
    assert _is_strategy_group_eligible(
        {"query_configs": [{"data_source_label": "bk_log_search", "data_type_label": "log"}]}
    )
    # is_custom_event
    assert _is_strategy_group_eligible({"query_configs": [{"data_source_label": "custom", "data_type_label": "event"}]})
    # is_fta_event
    assert _is_strategy_group_eligible({"query_configs": [{"data_source_label": "bk_fta", "data_type_label": "event"}]})
    # 不在任一类
    assert not _is_strategy_group_eligible(
        {"query_configs": [{"data_source_label": "bk_monitor", "data_type_label": "alert"}]}
    )
    assert not _is_strategy_group_eligible(
        {"query_configs": [{"data_source_label": "bk_data", "data_type_label": "event"}]}
    )
    # 空 query_configs / 缺字段
    assert not _is_strategy_group_eligible({"query_configs": []})
    assert not _is_strategy_group_eligible({})
    assert not _is_strategy_group_eligible({"query_configs": [{}]})
    # 只看 query_configs[0]（与 alarm_backends line 531 一致）
    assert _is_strategy_group_eligible(
        {
            "query_configs": [
                {"data_source_label": "bk_monitor", "data_type_label": "time_series"},
                {"data_source_label": "bk_monitor", "data_type_label": "alert"},  # 被忽略
            ]
        }
    )


def test_inspect_strategy_config_detail_silent_on_group_key_failure(monkeypatch):
    """eligible item 上注入失败时不应阻塞 detail 主路径。"""
    from kernel_api.rpc.functions.bkm_cli import strategy

    model = SimpleNamespace(id=999, bk_biz_id=7)
    strategy.StrategyModel.objects = FakeStrategyManager(detail_row=model)
    strategy_obj = FakeStrategyObject(
        {
            "id": 999,
            "bk_biz_id": 7,
            "name": "edge",
            "scenario": "os",
            "type": "monitor",
            "source": "bkmonitorv3",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "priority": 0,
            "priority_group_key": "",
            "items": [{"id": 1, "query_configs": [_eligible_query_config("x")]}],
            "detects": [],
            "actions": [],
            "notice": {},
            "issue_config": {},
        }
    )

    monkeypatch.setattr(strategy.Strategy, "from_models", lambda rows: [strategy_obj])
    monkeypatch.setattr(strategy.Strategy, "fill_user_groups", lambda configs: None)
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    def boom(cls, bk_biz_id, item):
        raise RuntimeError("simulated md5 failure")

    monkeypatch.setattr(StrategyCacheManager, "get_query_md5", classmethod(boom))

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-strategy-config", "params": {"operation": "detail", "strategy_id": 999}}
    )

    # 主路径仍然返回成功，item 上没有 strategy_group_key 字段
    assert result["result"]["operation"] == "detail"
    assert "strategy_group_key" not in result["result"]["strategy"]["items"][0]


def test_inspect_strategy_config_detail_without_bk_biz_id(monkeypatch):
    """strategy_id is globally unique — bk_biz_id should be optional for detail."""
    from kernel_api.rpc.functions.bkm_cli import strategy

    model = SimpleNamespace(id=51, bk_biz_id=100900)
    strategy.StrategyModel.objects = FakeStrategyManager(detail_row=model)
    strategy_obj = FakeStrategyObject(
        {
            "id": 51,
            "bk_biz_id": 100900,
            "name": "cross-biz strategy",
            "scenario": "os",
            "type": "monitor",
            "source": "bkmonitorv3",
            "is_enabled": True,
            "is_invalid": False,
            "invalid_type": "",
            "priority": 1,
            "priority_group_key": "PGK:cross",
            "items": [],
            "detects": [],
            "actions": [],
            "notice": {},
            "issue_config": {},
        }
    )

    monkeypatch.setattr(strategy.Strategy, "from_models", lambda rows: [strategy_obj])
    monkeypatch.setattr(strategy.Strategy, "fill_user_groups", lambda configs: None)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-strategy-config",
            "params": {
                "operation": "detail",
                "strategy_id": 51,
            },
        }
    )

    # Queried by id alone, no bk_biz_id filter
    assert strategy.StrategyModel.objects.get_kwargs == {"id": 51}
    assert result["result"]["operation"] == "detail"
    assert result["result"]["strategy_id"] == 51
    assert result["result"]["bk_biz_id"] == 100900  # returned from the model
    assert result["result"]["strategy"]["id"] == 51


class FakeRouteQuerySet:
    """记录 filter/order_by/values 调用链，供路由区间折算断言使用。"""

    def __init__(self, rows):
        self.rows = rows
        self.filter_kwargs = None
        self.order_by_args = None
        self.values_args = None

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def order_by(self, *args):
        self.order_by_args = args
        return self

    def values(self, *args):
        self.values_args = args
        return list(self.rows)


def _patch_cache_router(monkeypatch, rows):
    import bkmonitor.models as models_module
    from alarm_backends.core import cluster as cluster_module

    queryset = FakeRouteQuerySet(rows)
    monkeypatch.setattr(models_module.CacheRouter, "objects", queryset, raising=False)
    monkeypatch.setattr(cluster_module, "get_cluster", lambda: SimpleNamespace(name="default"))
    return queryset


def _patch_strategy_cache(monkeypatch, strategy_ids, groups, configs=None):
    """替换策略缓存读取，并统计读取次数以固化"读取次数与分页无关"。"""
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    calls = {"ids": 0, "groups": 0, "configs": 0}
    configs = configs or []

    def fake_ids(cls):
        calls["ids"] += 1
        return list(strategy_ids)

    def fake_groups(cls):
        calls["groups"] += 1
        return dict(groups)

    def fake_configs(cls, wanted_ids):
        calls["configs"] += 1
        wanted = set(wanted_ids)
        return [config for config in configs if config.get("id") in wanted]

    monkeypatch.setattr(StrategyCacheManager, "get_strategy_ids", classmethod(fake_ids))
    monkeypatch.setattr(StrategyCacheManager, "get_all_groups", classmethod(fake_groups))
    monkeypatch.setattr(StrategyCacheManager, "get_strategy_by_ids", classmethod(fake_configs))
    return calls


def _detect_config(strategy_id, interval, *, trigger_window=5, recovery_window=5):
    """构造能让生产 detect_result_point_required / get_interval 正常求值的最小策略配置。"""
    return {
        "id": strategy_id,
        "items": [{"id": strategy_id * 10, "query_configs": [{"agg_interval": interval}], "algorithms": []}],
        "detects": [
            {
                "level": 1,
                "trigger_config": {"check_window": trigger_window, "count": 1},
                "recovery_config": {"check_window": recovery_window},
            }
        ],
    }


def _group(strategy_items, *, bk_biz_id=7, interval_list=(60,)):
    payload = {str(key): list(value) for key, value in strategy_items.items()}
    payload["bk_biz_id"] = bk_biz_id
    payload["interval_list"] = list(interval_list)
    payload["strategy_source"] = [["bk_monitor", "time_series"]]
    return json.dumps(payload)


def _call_list_enabled(params):
    return BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-strategy-config", "params": {"operation": "list_enabled", **params}}
    )["result"]


def test_list_enabled_aggregates_items_across_groups(monkeypatch):
    """同一策略跨多个共享组时，item_ids / group keys / interval_list 需并集聚合。"""
    calls = _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[3, 1, 2],
        groups={
            "md5-a": _group({1: [10, 11], 2: [20]}, interval_list=(60,)),
            "md5-b": _group({1: [12]}, interval_list=(300,)),
        },
    )

    result = _call_list_enabled({})

    assert result["population"]["total"] == 3
    assert result["filter"]["mode"] == "all"
    assert result["filter"]["matched"] == 3
    assert result["group_coverage"]["in_group"] == 2
    assert result["group_coverage"]["not_in_group"] == 1
    assert result["group_coverage"]["malformed_groups"] == 0
    # 升序返回，缺失组的策略也在列，只是标记 in_strategy_group=False
    assert [item["strategy_id"] for item in result["strategies"]] == [1, 2, 3]
    first = result["strategies"][0]
    assert first["item_ids"] == [10, 11, 12]
    assert first["item_count"] == 3
    assert first["strategy_group_keys"] == ["md5-a", "md5-b"]
    assert first["interval_list"] == [60, 300]
    assert first["bk_biz_id"] == 7
    assert result["strategies"][2] == {"strategy_id": 3, "in_strategy_group": False}
    # 关键非回归：只读一次 ID 列表 + 一次策略组，不逐策略读 .strategy_{id}
    assert calls == {"ids": 1, "groups": 1, "configs": 0}


def test_list_enabled_ignores_group_reserved_fields(monkeypatch):
    """bk_biz_id / interval_list / strategy_source 是保留字段，不能被当成策略 ID。"""
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1],
        groups={"md5-a": _group({1: [10]})},
    )

    result = _call_list_enabled({})

    assert [item["strategy_id"] for item in result["strategies"]] == [1]
    assert result["group_coverage"]["in_group"] == 1


def test_list_enabled_counts_malformed_group_without_failing(monkeypatch):
    """单个组 JSON 损坏只计数，不能让整次枚举失败。"""
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1, 2],
        groups={"md5-a": _group({1: [10]}), "md5-broken": "{not-json", "md5-list": "[1,2]"},
    )

    result = _call_list_enabled({})

    assert result["group_coverage"]["malformed_groups"] == 2
    assert result["group_coverage"]["in_group"] == 1
    assert [item["strategy_id"] for item in result["strategies"]] == [1, 2]


def test_list_enabled_node_filter_matches_cache_router_score_range(monkeypatch):
    """按节点过滤的区间口径必须与 list-cache-routing 的 score_range 一致。

    路由 ``score=100 -> node1`` 覆盖 ``[1, 99]``，``score=200 -> node2`` 覆盖
    ``[100, 199]``，``score=300 -> node1`` 覆盖 ``[200, 299]``；``score=-1`` 是保留
    记录，不参与区间划分。node1 因此有两段不相邻区间。
    """
    queryset = _patch_cache_router(
        monkeypatch,
        [
            {"node_id": 1, "strategy_score": 100},
            {"node_id": 2, "strategy_score": 200},
            {"node_id": 1, "strategy_score": 300},
        ],
    )
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1, 99, 100, 199, 200, 299],
        groups={"md5-a": _group({1: [10], 200: [30]})},
    )

    result = _call_list_enabled({"node_id": 1})

    assert queryset.filter_kwargs == {"cluster_name": "default", "strategy_score__gt": 0}
    assert result["filter"]["mode"] == "node_id"
    assert result["filter"]["intervals"] == [{"min": 1, "max": 99}, {"min": 200, "max": 299}]
    assert [item["strategy_id"] for item in result["strategies"]] == [1, 99, 200, 299]
    assert result["filter"]["matched"] == 4


def test_list_enabled_node_filter_rejects_node_without_range(monkeypatch):
    """节点只挂在保留记录上时没有覆盖区间，应显式报错而不是返回空列表。"""
    _patch_cache_router(monkeypatch, [{"node_id": 2, "strategy_score": 100}])
    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    with pytest.raises(CustomException):
        _call_list_enabled({"node_id": 1})


def test_list_enabled_node_filter_rejects_empty_routing_table(monkeypatch):
    _patch_cache_router(monkeypatch, [])
    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    with pytest.raises(CustomException):
        _call_list_enabled({"node_id": 1})


def test_list_enabled_rejects_conflicting_filters(monkeypatch):
    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    with pytest.raises(CustomException):
        _call_list_enabled({"node_id": 1, "strategy_id_min": 10})


def test_list_enabled_explicit_range_is_inclusive_and_open_ended(monkeypatch):
    _patch_strategy_cache(monkeypatch, strategy_ids=[1, 5, 10, 20], groups={})

    bounded = _call_list_enabled({"strategy_id_min": 5, "strategy_id_max": 10})
    assert [item["strategy_id"] for item in bounded["strategies"]] == [5, 10]
    assert bounded["filter"]["intervals"] == [{"min": 5, "max": 10}]

    # 省略上界表示无上界，而不是退化成只取下界那一条
    open_ended = _call_list_enabled({"strategy_id_min": 10})
    assert [item["strategy_id"] for item in open_ended["strategies"]] == [10, 20]
    assert open_ended["filter"]["intervals"] == [{"min": 10, "max": None}]


def test_list_enabled_rejects_inverted_range(monkeypatch):
    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    with pytest.raises(CustomException):
        _call_list_enabled({"strategy_id_min": 10, "strategy_id_max": 5})


def test_list_enabled_paginates_without_extra_redis_reads(monkeypatch):
    calls = _patch_strategy_cache(monkeypatch, strategy_ids=list(range(1, 6)), groups={})

    page_one = _call_list_enabled({"page_size": 2})
    assert [item["strategy_id"] for item in page_one["strategies"]] == [1, 2]
    assert page_one["page"] == {
        "number": 1,
        "size": 2,
        "returned": 2,
        "total_pages": 3,
        "has_more": True,
    }

    page_three = _call_list_enabled({"page": 3, "page_size": 2})
    assert [item["strategy_id"] for item in page_three["strategies"]] == [5]
    assert page_three["page"]["has_more"] is False

    beyond = _call_list_enabled({"page": 9, "page_size": 2})
    assert beyond["strategies"] == []
    assert beyond["page"]["has_more"] is False

    # 每次调用固定两次读取，与页码、页大小无关
    assert calls == {"ids": 3, "groups": 3, "configs": 0}


def test_list_enabled_caps_page_size(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import strategy

    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    result = _call_list_enabled({"page_size": strategy.MAX_PAGE_SIZE + 1000})

    assert result["page"]["size"] == strategy.MAX_PAGE_SIZE


@pytest.mark.parametrize("bad_pagination", [{"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": -1}])
def test_list_enabled_rejects_non_positive_pagination(monkeypatch, bad_pagination):
    """0 必须被拒绝而不是当成缺省值，否则会掩盖调用方按 0 基分页的差一错误。"""
    _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={})

    with pytest.raises(CustomException):
        _call_list_enabled(bad_pagination)


def test_list_enabled_can_omit_item_ids(monkeypatch):
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1],
        groups={"md5-a": _group({1: [10, 11]})},
    )

    result = _call_list_enabled({"include_item_ids": False})

    entry = result["strategies"][0]
    assert "item_ids" not in entry
    assert entry["item_count"] == 2


def test_list_enabled_detect_profile_is_off_by_default(monkeypatch):
    calls = _patch_strategy_cache(monkeypatch, strategy_ids=[1], groups={}, configs=[_detect_config(1, 60)])

    result = _call_list_enabled({})

    assert "detect_profile" not in result["strategies"][0]
    assert result["redis_commands"]["base"] == 2
    assert result["redis_commands"]["detect_profile_mget_chunks"] == 0
    assert result["detect_profile_coverage"] == {"requested": 0, "resolved": 0}
    assert calls["configs"] == 0


def test_list_enabled_detect_profile_uses_periodic_reference(monkeypatch):
    """两小时周期公式继续作为主要容量参考，但不是精确字节上界。"""
    calls = _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1, 2, 3],
        groups={},
        configs=[_detect_config(1, 30), _detect_config(2, 60), _detect_config(3, 300)],
    )

    result = _call_list_enabled({"include_detect_profile": True})
    profiles = {item["strategy_id"]: item["detect_profile"] for item in result["strategies"]}

    assert profiles[1]["point_required"] == 30
    assert profiles[1]["model_scope"] == "periodic_reference"
    assert profiles[1]["is_safe_upper_bound"] is False
    assert profiles[1]["interval"] == 30
    assert profiles[1]["clean_interval_seconds"] == 7200
    assert profiles[1]["growth_per_clean_cycle"] == 240
    assert profiles[1]["check_result_peak_per_series"] == 270
    assert profiles[1]["overshoot_ratio"] == 9.0
    assert profiles[2]["check_result_peak_per_series"] == 150
    # 长周期下差异最刺眼：取大写法给 30，实际上界 54
    assert profiles[3]["check_result_peak_per_series"] == 54
    assert result["detect_profile_coverage"] == {"requested": 3, "resolved": 3}
    assert result["redis_commands"]["detect_profile_mget_chunks"] == 1
    assert calls["configs"] == 1


def test_list_enabled_detect_profile_preserves_measured_legacy_reference(monkeypatch):
    """历史样本只保留为旧周期口径参考，不再声明为当前安全上界。"""
    _patch_strategy_cache(monkeypatch, strategy_ids=[8361], groups={}, configs=[_detect_config(8361, 30)])

    profile = _call_list_enabled({"include_detect_profile": True})["strategies"][0]["detect_profile"]

    assert profile["check_result_peak_per_series"] >= 261
    assert profile["is_safe_upper_bound"] is False


def test_list_enabled_detect_profile_uses_legacy_strategy_point_required(monkeypatch):
    """旧策略级参考值仍随窗口放大，不恒等于下限 30。"""
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1],
        groups={},
        configs=[_detect_config(1, 60, trigger_window=20, recovery_window=20)],
    )

    profile = _call_list_enabled({"include_detect_profile": True})["strategies"][0]["detect_profile"]

    assert profile["point_required"] == 80
    assert profile["check_result_peak_per_series"] == 200


def test_list_enabled_detect_profile_reports_missing_and_broken_config(monkeypatch):
    """配置缺失记 None、单条求值失败记 error，都不影响同页其余策略。"""
    _patch_strategy_cache(
        monkeypatch,
        strategy_ids=[1, 2, 3],
        groups={},
        # 策略 2 缺 detects，生产函数会抛错；策略 3 完全没有缓存配置
        configs=[_detect_config(1, 60), {"id": 2, "items": [{"query_configs": [{"agg_interval": 60}]}]}],
    )

    result = _call_list_enabled({"include_detect_profile": True})
    profiles = {item["strategy_id"]: item["detect_profile"] for item in result["strategies"]}

    assert profiles[1]["check_result_peak_per_series"] == 150
    assert "error" in profiles[2]
    assert profiles[3] is None
    assert result["detect_profile_coverage"] == {"requested": 3, "resolved": 2}


def test_list_enabled_detect_profile_mget_chunks_follow_page_size(monkeypatch):
    """分块数由页大小决定而非策略总数，保证不退化成 N+1。"""
    _patch_strategy_cache(monkeypatch, strategy_ids=list(range(1, 2501)), groups={}, configs=[])

    result = _call_list_enabled({"include_detect_profile": True, "page_size": 2000})

    assert result["page"]["returned"] == 2000
    assert result["redis_commands"]["detect_profile_mget_chunks"] == 2


def test_list_enabled_tolerates_dirty_population_entries(monkeypatch):
    """缓存里混入非整数 ID 时跳过，不影响其余枚举。"""
    _patch_strategy_cache(monkeypatch, strategy_ids=[1, "2", None, "abc", True, 1], groups={})

    result = _call_list_enabled({})

    # 去重 + 跳过 None/"abc"/布尔
    assert [item["strategy_id"] for item in result["strategies"]] == [1, 2]
    assert result["population"]["total"] == 2
