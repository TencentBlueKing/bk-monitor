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
import requests
from monitor_web.strategies.resources import (
    GetStrategyListV2Resource,
    GetStrategyV2Resource,
)

from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.strategy.new_strategy import Strategy

pytestmark = pytest.mark.django_db


class TestStrategyDetailResourceV2:
    Config = {
        "id": 0,
        "bk_biz_id": 2,
        "name": "测试策略",
        "type": "monitor",
        "source": "bk_monitor",
        "scenario": "os",
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

    def test_get_strategy_with_user_group_list(self, clean_model):
        requests.packages.urllib3.disable_warnings()
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

        response_data = GetStrategyListV2Resource().request(dict(bk_biz_id=2, with_user_group=1))
        strategy_actions = response_data["strategy_config_list"][0]["actions"]

        assert "user_group_list" in strategy_actions[0]
        group_detail = dict(UserGroupDetailSlz(instance=user_slz.instance).data)
        group_detail.pop("duty_arranges")
        assert strategy_actions[0]["user_group_list"] == [group_detail]

    def test_get_strategy_detail(self, clean_model):
        requests.packages.urllib3.disable_warnings()
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
        strategy = Strategy(**self.Config)
        strategy.save()

        group_detail = dict(UserGroupDetailSlz(instance=user_slz.instance).data)
        group_detail.pop("duty_arranges")

        response_data = GetStrategyV2Resource().request({"bk_biz_id": 2, "id": strategy.id})

        strategy_dict = strategy.to_dict()
        response_data["create_time"] = strategy_dict["create_time"]
        response_data["update_time"] = strategy_dict["update_time"]
        strategy_dict["actions"][0]["user_group_list"] = [group_detail]
        assert strategy_dict == response_data
