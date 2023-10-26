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

from bkmonitor.strategy.new_strategy import Strategy


class TestOldConfig:
    OldConfig = {
        "id": 140,
        "strategy_id": 140,
        "name": "CPU总使用率",
        "strategy_name": "CPU总使用率",
        "bk_biz_id": 2005000002,
        "scenario": "os",
        "create_time": 1606113481,
        "update_time": 1606113481,
        "create_user": "admin",
        "update_user": "admin",
        "is_enabled": True,
        "labels": [],
        "item_list": [
            {
                "rt_query_config_id": 140,
                "strategy_id": 140,
                "algorithm_list": [
                    {
                        "id": 176,
                        "algorithm_id": 176,
                        "algorithm_type": "Threshold",
                        "algorithm_unit": "%",
                        "algorithm_config": [[{"threshold": 95, "method": "gte"}]],
                        "trigger_config": {"count": 3, "check_window": 5},
                        "recovery_config": {"check_window": 5},
                        "level": 2,
                    }
                ],
                "id": 140,
                "item_id": 140,
                "name": "CPU使用率",
                "item_name": "CPU使用率",
                "metric_id": "bk_monitor.system.cpu_summary.usage",
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "no_data_config": {"is_enabled": False, "continuous": 5},
                "target": [
                    [
                        {
                            "field": "host_topo_node",
                            "method": "eq",
                            "value": [{"bk_inst_id": 2005000002, "bk_obj_id": "biz"}],
                        }
                    ]
                ],
                "result_table_id": "system.cpu_summary",
                "agg_method": "AVG",
                "agg_interval": 60,
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                "agg_condition": [],
                "unit": "percent",
                "unit_conversion": 1,
                "metric_field": "usage",
                "extend_fields": {
                    "data_source_label": "bk_monitor",
                    "related_id": "system",
                    "result_table_name": "CPU",
                },
            }
        ],
        "action_list": [
            {
                "id": 140,
                "action_id": 140,
                "config": {
                    "alarm_start_time": "00:00:00",
                    "alarm_end_time": "23:59:59",
                    "alarm_interval": 1440,
                    "send_recovery_alarm": False,
                },
                "action_type": "notice",
                "notice_template": {
                    "anomaly_template": """{{content.level}}
    {{content.begin_time}}
    {{content.time}}
    {{content.duration}}
    {{content.target_type}}
    {{content.data_source}}
    {{content.content}}
    {{content.current_value}}
    {{content.biz}}
    {{content.target}}
    {{content.dimension}}
    {{content.detail}}
    {{content.related_info}}""",
                    "recovery_template": "",
                },
                "notice_group_list": [69],
            }
        ],
    }

    def test_from_dict(self):
        s = Strategy.from_dict_v1(self.OldConfig)
        config = copy.deepcopy(self.OldConfig)
        config["item_list"][0]["extend_fields"] = {}
        new_config = s.to_dict_v1()
        config["update_time"] = new_config["update_time"]
        config["create_time"] = new_config["create_time"]
