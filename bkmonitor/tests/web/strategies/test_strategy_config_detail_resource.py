"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db.models.query import QuerySet
from unittest.mock import PropertyMock

from bkmonitor.models import Item, NoticeGroup, Strategy
from core.drf_resource import resource
from bkmonitor.strategy.strategy import StrategyConfig
from bk_monitor_base.uptime_check import UptimeCheckTaskModel


class TestStrategyConfigDetailResource:
    def test_get_strategy_detail(self, mocker):
        item_instance = Item()
        item_instance.data_type_label = "time_series"
        notice_group_instance = NoticeGroup()
        notice_group_instance.id = 1
        notice_group_instance.name = "test"
        strategy_instance = Strategy()
        strategy_instance.target = [{"bk_obj_id": "biz", "bk_inst_id": 2}]
        strategy_instance.bk_biz_id = 2
        strategy_dict = {
            "bk_biz_id": 2,
            "is_enabled": True,
            "update_time": "2019-09-10 09:27:42",
            "update_user": "admin",
            "name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "scenario": "host_process",
            "create_user": "admin",
            "strategy_id": 1,
            "item_list": [
                {
                    "agg_condition": [],
                    "metric_id": "exporter_mysql_exporter_test3.basic.mysql_global_status_bytes_received",
                    "extend_fields": "",
                    "algorithm_list": [
                        {
                            "algorithm_config": [{"threshold": 112.0, "method": "gte"}],
                            "trigger_config": {"count": 1, "check_window": 5},
                            "level": 1,
                            "algorithm_type": "Threshold",
                            "recovery_config": {"check_window": 5},
                            "algorithm_id": 1,
                            "id": 1,
                        }
                    ],
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "data_source_label": "bk_monitor",
                    "result_table_id": "exporter_mysql_exporter_test3.basic",
                    "item_name": "Bytes_received",
                    "no_data_config": {"is_enabled": False, "continuous": 5},
                    "unit_conversion": 1.0,
                    "agg_method": "AVG",
                    "item_id": 1,
                    "agg_interval": 60,
                    "data_type_label": "time_series",
                    "metric_field": "mysql_global_status_bytes_received",
                    "id": 1,
                    "unit": "",
                    "name": "Bytes_received",
                }
            ],
            "action_list": [
                {
                    "notice_group_list": [1],
                    "action_type": "notice",
                    "notice_template": {"anomaly_template": "", "recovery_template": ""},
                    "config": {
                        "alarm_end_time": "23:59:59",
                        "send_recovery_alarm": True,
                        "alarm_start_time": "00:00:00",
                        "alarm_interval": 120,
                    },
                    "id": 1,
                    "action_id": 1,
                }
            ],
            "source_type": "BKMONITOR",
            "strategy_name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "create_time": "2019-09-10 09:27:42",
            "id": 1,
            "target": [
                [
                    {
                        "field": "ip",
                        "method": "eq",
                        "value": [
                            {"ip": "10.0.1.10", "bk_cloud_id": 0, "bk_supplier_id": 0},
                            {"ip": "10.0.1.11", "bk_cloud_id": 0, "bk_supplier_id": 0},
                        ],
                    }
                ]
            ],
        }
        target_detail = {
            "bk_target_type": "INSTANCE",
            "bk_obj_type": "HOST",
            "bk_target_detail": [
                {
                    "ip": "10.0.1.10",
                    "bk_cloud_name": "default area",
                    "agent_status": "normal",
                    "bk_cloud_id": 0,
                    "bk_supplier_id": 0,
                    "bk_os_type": "linux",
                },
                {
                    "ip": "10.0.1.11",
                    "bk_cloud_name": "default area",
                    "agent_status": "normal",
                    "bk_cloud_id": 0,
                    "bk_supplier_id": 0,
                    "bk_os_type": "linux",
                },
            ],
        }

        mocker.patch.object(NoticeGroup.objects, "filter", return_value=[notice_group_instance])
        mocker.patch.object(QuerySet, "first", side_effect=[strategy_instance, item_instance])
        mocker.patch.object(StrategyConfig, "get_object", return_value=None)
        mocker.patch.object(StrategyConfig, "strategy_dict", new_callable=PropertyMock, return_value=strategy_dict)
        mocker.patch.object(StrategyConfig, "get_target_detail", return_value=target_detail)
        assert resource.strategies.strategy_config_detail(bk_biz_id=2, id=1) == {
            "is_enabled": True,
            "bk_target_type": "INSTANCE",
            "update_time": "2019-09-10 09:27:42",
            "update_user": "admin",
            "action_list": [
                {
                    "notice_group_id_list": [1],
                    "notice_group_list": [{"display_name": "test", "id": 1}],
                    "action_type": "notice",
                    "config": {
                        "alarm_end_time": "23:59:59",
                        "send_recovery_alarm": True,
                        "alarm_start_time": "00:00:00",
                        "alarm_interval": 120,
                    },
                    "id": 1,
                    "action_id": 1,
                }
            ],
            "source_type": "BKMONITOR",
            "create_time": "2019-09-10 09:27:42",
            "message_template": "",
            "bk_target_detail": [
                {
                    "ip": "10.0.1.10",
                    "bk_cloud_id": 0,
                    "agent_status": "normal",
                    "bk_cloud_name": "default area",
                    "bk_supplier_id": 0,
                    "bk_os_type": "linux",
                },
                {
                    "ip": "10.0.1.11",
                    "bk_cloud_id": 0,
                    "agent_status": "normal",
                    "bk_cloud_name": "default area",
                    "bk_supplier_id": 0,
                    "bk_os_type": "linux",
                },
            ],
            "id": 1,
            "target": [
                [
                    {
                        "field": "ip",
                        "method": "eq",
                        "value": [
                            {"ip": "10.0.1.10", "bk_cloud_id": 0, "bk_supplier_id": 0},
                            {"ip": "10.0.1.11", "bk_cloud_id": 0, "bk_supplier_id": 0},
                        ],
                    }
                ]
            ],
            "bk_biz_id": 2,
            "item_list": [
                {
                    "detect_algorithm_list": [
                        {
                            "algorithm_list": [
                                {
                                    "algorithm_config": [{"threshold": 112.0, "method": "gte"}],
                                    "algorithm_type": "Threshold",
                                    "algorithm_id": 1,
                                    "id": 1,
                                }
                            ],
                            "level": 1,
                        }
                    ],
                    "agg_method": "AVG",
                    "metric_id": "exporter_mysql_exporter_test3.basic.mysql_global_status_bytes_received",
                    "name": "Bytes_received",
                    "trigger_config": {"count": 1, "check_window": 5},
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "item_id": 1,
                    "recovery_config": {"check_window": 5},
                    "data_source_label": "bk_monitor",
                    "id": 1,
                    "extend_fields": "",
                    "unit_conversion": 1.0,
                    "item_name": "Bytes_received",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "data_type_label": "time_series",
                    "result_table_id": "exporter_mysql_exporter_test3.basic",
                    "unit": "",
                    "metric_field": "mysql_global_status_bytes_received",
                }
            ],
            "name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "scenario": "host_process",
            "create_user": "admin",
            "bk_obj_type": "HOST",
            "strategy_id": 1,
            "strategy_name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "no_data_config": {"is_enabled": False, "continuous": 5},
        }

    def test_uptimecheck_strategy_detail(self, mocker):
        item_instance = Item()
        item_instance.data_type_label = "time_series"
        notice_group_instance = NoticeGroup()
        notice_group_instance.id = 1
        notice_group_instance.name = "test"
        strategy_instance = Strategy()
        strategy_instance.target = []
        strategy_instance.bk_biz_id = 2
        strategy_dict = {
            "bk_biz_id": 2,
            "is_enabled": True,
            "update_time": "2019-09-10 09:27:42",
            "update_user": "admin",
            "name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "scenario": "uptimecheck",
            "create_user": "admin",
            "strategy_id": 1,
            "item_list": [
                {
                    "agg_condition": [
                        {"value": "11", "method": "eq", "key": "task_id"},
                        {"value": 3003, "condition": "and", "method": "eq", "key": "error_code"},
                    ],
                    "metric_id": "uptimecheck.http.node_id",
                    "extend_fields": "",
                    "algorithm_list": [
                        {
                            "algorithm_config": [{"threshold": 112.0, "method": "gte"}],
                            "trigger_config": {"count": 1, "check_window": 5},
                            "level": 1,
                            "algorithm_type": "Threshold",
                            "recovery_config": {"check_window": 5},
                            "algorithm_id": 1,
                            "id": 1,
                        }
                    ],
                    "agg_dimension": ["task_id"],
                    "data_source_label": "bk_monitor",
                    "result_table_id": "uptimecheck.http",
                    "item_name": "期望响应码",
                    "no_data_config": {"is_enabled": False, "continuous": 5},
                    "unit_conversion": 1.0,
                    "agg_method": "COUNT",
                    "item_id": 1,
                    "agg_interval": 60,
                    "data_type_label": "time_series",
                    "metric_field": "node_id",
                    "id": 1,
                    "unit": "",
                    "name": "期望响应码",
                }
            ],
            "action_list": [
                {
                    "notice_group_list": [1],
                    "action_type": "notice",
                    "notice_template": {"anomaly_template": "", "recovery_template": ""},
                    "config": {
                        "alarm_end_time": "23:59:59",
                        "send_recovery_alarm": True,
                        "alarm_start_time": "00:00:00",
                        "alarm_interval": 120,
                    },
                    "id": 1,
                    "action_id": 1,
                }
            ],
            "source_type": "BKMONITOR",
            "strategy_name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "create_time": "2019-09-10 09:27:42",
            "id": 1,
            "target": [[]],
        }
        target_detail = {
            "bk_target_type": None,
            "bk_obj_type": "NONE",
            "bk_target_detail": None,
        }
        uptimecheck_instance = UptimeCheckTaskModel()
        uptimecheck_instance.name = "test_baidu"
        uptimecheck_instance.config = {"response_code": 200}

        mocker.patch.object(NoticeGroup.objects, "filter", return_value=[notice_group_instance])
        mocker.patch.object(QuerySet, "first", side_effect=[strategy_instance, item_instance])
        mocker.patch.object(StrategyConfig, "get_object", return_value=None)
        mocker.patch.object(StrategyConfig, "strategy_dict", new_callable=PropertyMock, return_value=strategy_dict)
        mocker.patch.object(StrategyConfig, "get_target_detail", return_value=target_detail)
        mocker.patch.object(UptimeCheckTaskModel.objects, "get", return_value=uptimecheck_instance)
        assert resource.strategies.strategy_config_detail(bk_biz_id=2, id=1) == {
            "is_enabled": True,
            "bk_target_type": None,
            "update_time": "2019-09-10 09:27:42",
            "update_user": "admin",
            "action_list": [
                {
                    "notice_group_id_list": [1],
                    "notice_group_list": [{"display_name": "test", "id": 1}],
                    "action_type": "notice",
                    "config": {
                        "alarm_end_time": "23:59:59",
                        "send_recovery_alarm": True,
                        "alarm_start_time": "00:00:00",
                        "alarm_interval": 120,
                    },
                    "id": 1,
                    "action_id": 1,
                }
            ],
            "source_type": "BKMONITOR",
            "create_time": "2019-09-10 09:27:42",
            "message_template": "",
            "bk_target_detail": None,
            "id": 1,
            "target": [[]],
            "bk_biz_id": 2,
            "item_list": [
                {
                    "related_id": 11,
                    "metric_field": "response_code",
                    "related_name": "test_baidu",
                    "recovery_config": {"check_window": 5},
                    "extend_fields": "",
                    "agg_interval": 60,
                    "agg_condition": [
                        {"value": 11, "method": "eq", "key": "task_id", "value_name": "11\uff08test_baidu\uff09"},
                        {"value": 200, "condition": "and", "method": "eq", "key": "response_code"},
                    ],
                    "method_list": ["COUNT"],
                    "id": 1,
                    "unit": "",
                    "detect_algorithm_list": [
                        {
                            "algorithm_list": [
                                {
                                    "algorithm_config": [{"threshold": 112.0, "method": "gte"}],
                                    "algorithm_type": "Threshold",
                                    "algorithm_id": 1,
                                    "id": 1,
                                }
                            ],
                            "level": 1,
                        }
                    ],
                    "item_name": "\u671f\u671b\u54cd\u5e94\u7801",
                    "agg_method": "COUNT",
                    "data_type_label": "time_series",
                    "result_table_id": "uptimecheck.http",
                    "trigger_config": {"count": 1, "check_window": 5},
                    "unit_conversion": 1.0,
                    "item_id": 1,
                    "name": "\u671f\u671b\u54cd\u5e94\u7801",
                    "metric_id": "uptimecheck.http.node_id",
                    "agg_dimension": ["task_id"],
                    "data_source_label": "bk_monitor",
                }
            ],
            "name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "scenario": "uptimecheck",
            "create_user": "admin",
            "bk_obj_type": "NONE",
            "strategy_id": 1,
            "strategy_name": "\u53bb\u95ee\u9a71\u868a\u5668\u6211",
            "no_data_config": {"is_enabled": False, "continuous": 5},
        }
