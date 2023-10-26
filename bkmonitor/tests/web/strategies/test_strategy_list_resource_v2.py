# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import pytest
from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.strategy.new_strategy import Strategy
from monitor_web.strategies.resources import GetStrategyListV2Resource
from bkmonitor.models import ActionConfig

pytestmark = pytest.mark.django_db


class TestStrategyListResourceV2:
    Config = {
        "id": 0,
        "bk_biz_id": 2,
        "name": "测试策略",
        "type": "monitor",
        "source": "bk_monitor",
        "scenario": "os",
        "type": "monitor",
        "is_enabled": True,
        "create_time": "2021-06-13T09:22:27.113718+00:00",
        "create_user": "system",
        "update_time": "2021-06-13T09:22:27.113718+00:00",
        "update_user": "system",
        "items": [
            {
                "id": 1,
                "name": "name",
                "expression": "a + b",
                "origin_sql": "test",
                "no_data_config": {},
                "target": [[]],
                "algorithms": [
                    {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}
                ],
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "A",
                        "id": 1,
                        "metric_id": "bk_monitor.xxxx.aaa",
                        "result_table_id": "xxxx",
                        "metric_field": "aaa",
                        "unit": "xxx",
                        "agg_method": "avg",
                        "agg_condition": [],
                        "agg_dimension": [],
                        "agg_interval": 60,
                        "functions": [],
                    }
                ],
            }
        ],
        "actions": [],
        "detects": [
            {
                "id": 1,
                "level": 1,
                "expression": "",
                "trigger_config": {"count": 1, "check_window": 2},
                "recovery_config": {"check_window": 2},
                "connector": "and",
            }
        ],
        "labels": [],
        "version": "v2",
    }

    user_group_config = {
        "name": "测试用户组",
        "desc": "用户组的说明",
        "bk_biz_id": 2,
        "duty_arranges": [
            {
                "duty_type": "always",
                "work_time": "all_day",
                "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
            },
            {
                "duty_type": "week",
                "work_time": "all_day",
                "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
            },
        ],
    }

    action_config = [
        {
            "name": "测试全局业务套餐名搜索",
            "bk_biz_id": 0,
        },
        {
            "name": "测试套餐名搜索",
            "bk_biz_id": 2,
        },
    ]

    def test_get_strategy_config_list(self, clean_model):
        user_slz = UserGroupDetailSlz(data=self.user_group_config)
        user_slz.is_valid(raise_exception=True)
        user_slz.save()
        self.Config["actions"].append(
            {
                "signal": "abnormal",
                "config_id": 1,
                "user_groups": [user_slz.instance.id],
                "is_combined": True,
                "id": None,
            }
        )

        strategy = Strategy(**self.Config)
        strategy.save()

        user_groups = [{"user_group_id": user_slz.instance.id, "user_group_name": "测试用户组", "count": 1}]
        actions = strategy.to_dict()["actions"]

        response_data = GetStrategyListV2Resource().request(dict(bk_biz_id=2))
        assert response_data["user_group_list"] == user_groups
        strategies = response_data["strategy_config_list"]
        assert len(strategies) == 1
        assert strategies[0]["actions"] == actions

    def test_get_strategy_config_list_by_user_group(self, clean_model):
        user_slz = UserGroupDetailSlz(data=self.user_group_config)
        user_slz.is_valid(raise_exception=True)
        user_slz.save()

        self.user_group_config["name"] = "测试用户组1"
        user_slz2 = UserGroupDetailSlz(data=self.user_group_config)
        user_slz2.is_valid(raise_exception=True)
        user_slz2.save()

        self.Config["actions"].append(
            {
                "signal": "abnormal",
                "config_id": 1,
                "user_groups": [user_slz.instance.id, user_slz2.instance.id],
                "is_combined": True,
                "id": None,
            }
        )

        strategy = Strategy(**self.Config)
        strategy.save()

        user_groups = [
            {"user_group_id": user_slz2.instance.id, "user_group_name": "测试用户组1", "count": 1},
            {"user_group_id": user_slz.instance.id, "user_group_name": "测试用户组", "count": 1},
        ]
        actions = strategy.to_dict()["actions"]

        request_data = {
            "conditions": [
                {"key": "user_group_name", "value": ["测试用户组2"]},
            ],
            "bk_biz_id": 2,
        }

        response_data = GetStrategyListV2Resource().request(request_data)
        assert response_data["user_group_list"] == user_groups
        strategies = response_data["strategy_config_list"]
        assert len(strategies) == 1
        assert strategies[0]["actions"] == actions

    def test_get_fta_strategy_config_list(self, clean_model):
        user_slz = UserGroupDetailSlz(data=self.user_group_config)
        user_slz.is_valid(raise_exception=True)
        user_slz.save()
        self.Config["actions"] = [
            {
                "signal": "abnormal",
                "config_id": 1,
                "user_groups": [user_slz.instance.id],
                "is_combined": True,
                "id": None,
            }
        ]
        self.Config["type"] = "fta"
        strategy = Strategy(**self.Config)
        strategy.save()

        user_groups = [{"user_group_id": user_slz.instance.id, "user_group_name": "测试用户组1", "count": 1}]
        actions = strategy.to_dict()["actions"]

        response_data = GetStrategyListV2Resource().request(dict(bk_biz_id=2, type="fta"))
        assert response_data["user_group_list"] == user_groups
        strategies = response_data["strategy_config_list"]
        assert len(strategies) == 1
        assert strategies[0]["actions"] == actions

    def test_filter_by_action_name(self, clean_model):
        actions = []
        for config in self.action_config:
            actions.append(ActionConfig.objects.create(**config))

        self.Config["actions"] = [
            {
                "signal": "abnormal",
                "config_id": action.id,
                "user_groups": [1, 2, 3],
                "is_combined": True,
                "id": None,
            }
            for action in actions
        ]
        self.Config["type"] = "monitor"

        strategy = Strategy(**self.Config)
        strategy.save()

        response_data = GetStrategyListV2Resource().request(
            dict(bk_biz_id=2, conditions=[{"key": "action_name", "value": [actions[0].name]}])
        )
        assert [config["id"] for config in response_data["strategy_config_list"]] == [strategy.id]

        response_data = GetStrategyListV2Resource().request(
            dict(bk_biz_id=2, conditions=[{"key": "action_name", "value": [actions[1].name]}])
        )
        assert [config["id"] for config in response_data["strategy_config_list"]] == [strategy.id]

        response_data = GetStrategyListV2Resource().request(
            dict(bk_biz_id=2, conditions=[{"key": "action_name", "value": [action.name for action in actions]}])
        )
        assert [config["id"] for config in response_data["strategy_config_list"]] == [strategy.id]

        response_data = GetStrategyListV2Resource().request(
            dict(bk_biz_id=2, conditions=[{"key": "action_name", "value": ["随便写一个"]}])
        )
        assert len(response_data["strategy_config_list"]) == 0

    def test_filter_by_monitor_source_app(self, clean_model):
        self.Config["actions"] = [
            {
                "signal": "abnormal",
                "config_id": 1,
                "user_groups": [1, 2, 3],
                "is_combined": True,
                "id": None,
            }
        ]
        self.Config["items"] = [
            {
                "id": 1,
                "name": "name",
                "expression": "a + b",
                "origin_sql": "test",
                "no_data_config": {},
                "target": [[]],
                "algorithms": [
                    {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}
                ],
                "query_configs": [
                    {
                        "data_source_label": "bk_fta",
                        "data_type_label": "event",
                        "alias": "A",
                        "id": 1,
                        "metric_id": "bk_monitor.xxxx.aaa",
                        "result_table_id": "xxxx",
                        "metric_field": "aaa",
                        "alert_name": "bbb",
                        "unit": "xxx",
                        "agg_method": "avg",
                        "agg_condition": [],
                        "agg_dimension": [],
                        "agg_interval": 60,
                        "functions": [],
                    }
                ],
            }
        ]

        strategy = Strategy(**self.Config)
        strategy.save()

        response_data = GetStrategyListV2Resource().request(dict(bk_biz_id=2))
        assert len(response_data["strategy_config_list"]) == 1
