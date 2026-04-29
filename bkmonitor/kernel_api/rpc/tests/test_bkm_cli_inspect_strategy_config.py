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
