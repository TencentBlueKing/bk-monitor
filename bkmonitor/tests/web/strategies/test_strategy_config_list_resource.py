# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import pytest
from django.db.models.query import QuerySet

from bkmonitor.models import Action, ActionNoticeMapping, Item, NoticeGroup, ResultTableSQLConfig, Shield, Strategy
from core.drf_resource import resource
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.strategies.constant import Scenario

from .data import (
    ALL_LABEL_MSG,
    HOST_INFO,
    MODULE_SERVICE_CATEGORY_INFO,
    SERVICE_CATEGORY_INFO,
    SERVICE_INFO,
    TOPO_TREE_INFO,
)


class RequestInstance(object):
    user = "admin"


class BizInstance(object):
    id = 2


@pytest.mark.usefixtures("mock_cache")
class TestStrategyConfigListResource(object):
    def test_get_strategy_config_list(self, mocker):
        def get_cache_msg(*args):
            return_value_map = {
                "host_info": HOST_INFO,
                "service_info": SERVICE_INFO,
                "module_service_category_info": MODULE_SERVICE_CATEGORY_INFO,
                "topo_tree_info": TOPO_TREE_INFO,
                "service_category_info": SERVICE_CATEGORY_INFO,
            }
            return return_value_map[args[0]]

        def handel_shield_filter(*args, **kwargs):
            strategy_instance = Strategy()
            strategy_instance.id = 1
            if "is_quick" in kwargs:
                return []
            else:
                return Shield.objects

        def handel_strategy_filter(**kwargs):
            strategy_instance = Strategy()
            strategy_instance.id = 1
            if kwargs.get("scenario") == Scenario.UPTIME_CHECK:
                return [strategy_instance]
            else:
                return Strategy.objects

        notice_group_instance = NoticeGroup()
        notice_group_instance.id = 1
        notice_group_instance.name = "test"
        action_map_instance = ActionNoticeMapping()
        action_map_instance.action_id = 1
        action_instance = Action()
        action_instance.strategy_id = 1
        item_instance = Item()
        item_instance.strategy_id = 1
        item_instance.rt_query_config_id = 1
        item_instance.data_source_label = "bk_monitor"
        item_instance.data_type_label = "time_series"
        rt_sql_instance = ResultTableSQLConfig()
        rt_sql_instance.agg_condition = [{"value": "1", "method": "eq", "key": "task_id"}]
        strategy_instance = Strategy()
        strategy_instance.target = [
            [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}]}]
        ]
        strategy_instance.bk_biz_id = 2
        strategy_list_values = [
            {
                "id": 1,
                "name": "test",
                "update_user": "admin",
                "scenario": "os",
                "target": [
                    [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}]}]
                ],
                "update_time": "2019-09-16 13:03:01",
                "is_enabled": True,
                "bk_biz_id": 2,
            }
        ]

        mocker.patch(
            "monitor_web.commons.data.resources.api.metadata.get_label",
            return_value={"result_table_label": ALL_LABEL_MSG},
        )
        mocker.patch("monitor_web.commons.cc.utils.cache.get", side_effect=get_cache_msg)
        mocker.patch("monitor_web.commons.cc.utils.CmdbUtil.update_cache_data", return_value=None)
        mocker.patch.object(Shield.objects, "filter", side_effect=handel_shield_filter)
        mocker.patch.object(NoticeGroup.objects, "filter", return_value=[notice_group_instance])
        mocker.patch.object(NoticeGroup.objects, "get", return_value=notice_group_instance)
        mocker.patch.object(ActionNoticeMapping.objects, "filter", return_value=[action_map_instance])
        mocker.patch.object(Action.objects, "filter", return_value=[action_instance])
        mocker.patch.object(Action.objects, "get", return_value=action_instance)
        mocker.patch.object(Strategy.objects, "filter", side_effect=handel_strategy_filter)
        mocker.patch.object(Item.objects, "filter", side_effect=[[item_instance], Item.objects, [item_instance]])
        mocker.patch.object(Item.objects, "first", return_value=item_instance)
        mocker.patch.object(ResultTableSQLConfig.objects, "get", return_value=rt_sql_instance)
        mocker.patch("monitor_web.strategies.resources.get_request", return_value=RequestInstance())
        mocker.patch("monitor_web.strategies.resources.resource.cc.get_app_by_user", return_value=[BizInstance()])
        mocker.patch.object(Strategy.objects, "all", return_value=Strategy.objects)
        mocker.patch.object(QuerySet, "count", side_effect=[1, 2, 3, 5, 4, 1, 2])
        mocker.patch.object(QuerySet, "values", return_value=strategy_list_values)
        mocker.patch.object(QuerySet, "iterator", return_value=[strategy_instance])
        mocker.patch.object(ShieldDetectManager, "check_shield_status", return_value={"is_shield": False})
        assert resource.strategies.strategy_config_list(
            task_id=1, notice_group_name="test", service_category="Default-Default", bk_biz_id=2
        ) == {
            "scenario_list": [
                {"count": 2, "sort_msg": 1.1, "display_name": "\u670d\u52a1\u62e8\u6d4b", "id": "uptimecheck"},
                {"count": 1, "sort_msg": 1.2, "display_name": "\u4e1a\u52a1\u5e94\u7528", "id": "application_check"},
                {"count": 5, "sort_msg": 2.1, "display_name": "\u670d\u52a1\u6a21\u5757", "id": "service_module"},
                {"count": 3, "sort_msg": 2.2, "display_name": "\u7ec4\u4ef6", "id": "component"},
                {"count": 4, "sort_msg": 3.1, "display_name": "\u8fdb\u7a0b", "id": "host_process"},
                {"count": 1, "sort_msg": 3.2, "display_name": "\u64cd\u4f5c\u7cfb\u7edf", "id": "os"},
                {"count": 2, "sort_msg": 4.1, "display_name": "\u5176\u4ed6", "id": "other_rt"},
            ],
            "strategy_config_list": [
                {
                    "is_enabled": True,
                    "bk_biz_id": 2,
                    "update_time": "2019-09-16 13:03:01",
                    "update_user": "admin",
                    "name": "test",
                    "scenario": "os",
                    "shield_info": {"is_shield": False},
                    "second_label_name": "\u64cd\u4f5c\u7cfb\u7edf",
                    "second_label": "os",
                    "first_label_name": "\u4e3b\u673a",
                    "add_allowed": True,
                    "notice_group_id_list": [{"display_name": "test", "id": 1}],
                    "first_label": "hosts",
                    "total_instance_count": 6,
                    "service_category_data": [
                        {"second": "Default", "first": "Default"},
                        {"second": "esb", "first": "PaaS"},
                    ],
                    "target_node_type": "TOPO",
                    "target_object_type": "HOST",
                    "data_source_type": "\u76d1\u63a7\u91c7\u96c6",
                    "id": 1,
                    "target_nodes_count": 1,
                }
            ],
        }
