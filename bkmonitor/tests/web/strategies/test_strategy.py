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


import copy

from bkmonitor.models import (
    Action,
    ActionNoticeMapping,
    DetectAlgorithm,
    Item,
    NoticeGroup,
    ResultTableSQLConfig,
    Strategy,
)
from bkmonitor.strategy.strategy import StrategyConfig

STRATEGY_DICT = dict(
    [
        ("bk_biz_id", 2),
        ("name", "test"),
        ("scenario", "os"),
        (
            "item_list",
            [
                dict(
                    [
                        ("name", "\u7a7a\u95f2\u7387"),
                        ("metric_field", "idle"),
                        ("data_source_label", "bk_monitor"),
                        ("data_type_label", "time_series"),
                        ("result_table_id", "system.cpu_detail"),
                        ("agg_method", "AVG"),
                        ("agg_interval", "60"),
                        ("agg_dimension", ["ip", "bk_cloud_id"]),
                        ("agg_condition", []),
                        ("unit", "%"),
                        ("unit_conversion", 1.0),
                        ("metric_id", "system.cpu_detail.idle"),
                        ("no_data_config", dict([("is_enabled", True), ("continuous", 5)])),
                        (
                            "algorithm_list",
                            [
                                dict(
                                    [
                                        ("algorithm_config", dict([("method", "gte"), ("threshold", "10")])),
                                        ("trigger_config", dict([("count", 1), ("check_window", 5)])),
                                        ("algorithm_type", "Threshold"),
                                        ("recovery_config", dict([("check_window", 5), ("level", 1)])),
                                    ]
                                )
                            ],
                        ),
                    ]
                )
            ],
        ),
        (
            "action_list",
            [
                dict(
                    [
                        ("action_type", "notice"),
                        (
                            "config",
                            dict(
                                [
                                    ("alarm_end_time", "23:59:59"),
                                    ("send_recovery_alarm", True),
                                    ("alarm_start_time", "00:00:00"),
                                    ("alarm_interval", 120),
                                ]
                            ),
                        ),
                        ("notice_group_list", [1]),
                    ]
                )
            ],
        ),
        ("source_type", "BKMONITOR"),
        (
            "target",
            [
                [
                    dict(
                        [
                            ("field", "ip"),
                            ("method", "eq"),
                            (
                                "value",
                                [
                                    dict([("ip", "10.0.1.10"), ("bk_supplier_id", 0), ("bk_cloud_id", 0)]),
                                    dict([("ip", "10.0.1.11"), ("bk_supplier_id", 0), ("bk_cloud_id", 0)]),
                                    dict([("ip", "10.0.1.16"), ("bk_supplier_id", 0), ("bk_cloud_id", 0)]),
                                    dict([("ip", "10.0.1.8"), ("bk_supplier_id", 0), ("bk_cloud_id", 0)]),
                                    dict([("ip", "10.0.1.4"), ("bk_supplier_id", 0), ("bk_cloud_id", 0)]),
                                ],
                            ),
                        ]
                    )
                ]
            ],
        ),
    ]
)

strategy_instance = Strategy()
strategy_instance.id = 1
strategy_instance.target = [
    [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}]}]
]
sql_instance = ResultTableSQLConfig()
sql_instance.result_table_id = 1
item_instance = Item()
item_instance.id = 1
item_instance.rt_query_config_id = 1
detect_instance = DetectAlgorithm()
detect_instance.id = 1
action_instance = Action()
action_instance.id = 1
notice_group_instance = NoticeGroup()
action_notice_map_instance = ActionNoticeMapping()
action_notice_map_instance.id = 1


class TestStrategy(object):
    def test_create(self, mocker):
        create_strategy_dict = copy.deepcopy(STRATEGY_DICT)
        mocker.patch.object(Strategy.objects, "create", return_value=strategy_instance)
        mocker.patch.object(ResultTableSQLConfig.objects, "create", return_value=sql_instance)
        mocker.patch.object(ResultTableSQLConfig.objects, "filter", return_value=[sql_instance])
        mocker.patch.object(ResultTableSQLConfig.objects, "get", return_value=sql_instance)
        mocker.patch.object(Item.objects, "create", return_value=item_instance)
        mocker.patch.object(Item.objects, "filter", return_value=[item_instance])
        mocker.patch.object(DetectAlgorithm.objects, "create", return_value=detect_instance)
        mocker.patch.object(Action.objects, "create", return_value=action_instance)
        mocker.patch.object(NoticeGroup.objects, "get", return_value=notice_group_instance)
        mocker.patch.object(ActionNoticeMapping.objects, "create", return_value=action_notice_map_instance)
        mocker.patch(
            "api.metadata.default.CreateResultTableMetricSplitResource",
            return_value={"table_id": "test.test_cmdb_level"},
        )
        StrategyConfig.create(create_strategy_dict)

    def test_update(self, mocker):
        update_strategy_dict = copy.deepcopy(STRATEGY_DICT)
        update_strategy_dict["item_list"][0]["id"] = 1
        update_strategy_dict["action_list"][0]["id"] = 1
        mocker.patch.object(StrategyConfig, "get_object", return_value=None)
        instance = StrategyConfig(2, 1)
        instance.strategy = strategy_instance

        mocker.patch.object(Strategy, "save", return_value=strategy_instance)
        mocker.patch.object(Item.objects, "filter", return_value=[item_instance])
        mocker.patch.object(ResultTableSQLConfig.objects, "create", return_value=sql_instance)
        mocker.patch.object(Item.objects, "create", return_value=item_instance)
        mocker.patch.object(ResultTableSQLConfig.objects, "filter", return_value=[sql_instance])
        mocker.patch.object(DetectAlgorithm.objects, "create", return_value=detect_instance)
        mocker.patch.object(Action.objects, "create", return_value=action_instance)
        mocker.patch.object(NoticeGroup.objects, "get", return_value=notice_group_instance)
        mocker.patch.object(ActionNoticeMapping.objects, "create", return_value=action_notice_map_instance)
        instance.update(update_strategy_dict)

    def test_delete(self, mocker):
        pass
