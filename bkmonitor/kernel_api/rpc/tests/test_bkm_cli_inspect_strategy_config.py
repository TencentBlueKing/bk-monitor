"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

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
