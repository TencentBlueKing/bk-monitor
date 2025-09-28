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
import mock
from django.test import TestCase
from bkmonitor.action.serializers.strategy import *  # noqa
from bkmonitor.models import UserGroup, DutyArrange, StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from core.drf_resource.exceptions import CustomException
from monitor_web.strategies.resources.v2 import SaveStrategyV2Resource

mock.patch(
    "core.drf_resource.api.bk_login.get_all_user",
    return_value={"results": [{"username": "admin", "display_name": "admin"}]},
).start()


def get_strategy_dict(noise_reduce_config=None):
    notice_action_config = {
        "execute_config": {
            "template_detail": {
                "interval_notify_mode": "standard",  # 间隔模式
                "notify_interval": 7200,  # 通知间隔
                "template": [  # 通知模板配置
                    {
                        "signal": "abnormal",
                    }
                ],
            }
        },
        "id": 55555,
        "plugin_id": 1,
        "plugin_type": "notice",
        "is_enabled": True,
        "bk_biz_id": 2,
        "name": "test_notice",
    }

    strategy_dict = {
        "type": "monitor",
        "bk_biz_id": 2,
        "scenario": "os",
        "name": "测试新策略",
        "labels": [],
        "is_enabled": True,
        "items": [
            {
                "name": "AVG(CPU单核使用率)",
                "no_data_config": {
                    "continuous": 5,
                    "is_enabled": False,
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "level": 2,
                },
                "target": [],
                "expression": "a",
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "result_table_id": "system.cpu_detail",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "device_name"],
                        "agg_condition": [],
                        "metric_field": "usage",
                        "unit": "percent",
                        "metric_id": "bk_monitor.system.cpu_detail.usage",
                        "index_set_id": "",
                        "query_string": "*",
                        "custom_event_name": "usage",
                        "functions": [],
                        "time_field": "time",
                        "bkmonitor_strategy_id": "usage",
                        "alert_name": "usage",
                    }
                ],
                "algorithms": [
                    {
                        "level": 1,
                        "type": "Threshold",
                        "config": [[{"method": "gte", "threshold": 0}]],
                        "unit_prefix": "%",
                    }
                ],
            }
        ],
        "detects": [
            {
                "level": 1,
                "expression": "",
                "trigger_config": {
                    "count": 1,
                    "check_window": 2,
                    "uptime": {"calendars": [], "time_ranges": [{"start": "00:00", "end": "23:59"}]},
                },
                "recovery_config": {"check_window": 5},
                "connector": "and",
            }
        ],
        "notice": {  # 通知设置
            "id": 1,
            "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
            "user_groups": [],  # 告警组ID
            "signal": ["abnormal", "recovered"],
            # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
            "options": {
                "converge_config": {
                    "is_enabled": True,
                    "converge_func": "collect",
                    "timedelta": 60,
                    "count": 1,
                    "condition": [
                        {"dimension": "strategy_id", "value": ["self"]},
                        {"dimension": "dimensions", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "notice_info", "value": ["self"]},
                    ],
                    "need_biz_converge": True,
                    "sub_converge_config": {
                        "timedelta": 60,
                        "count": 2,
                        "condition": [
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                        ],
                        "converge_func": "collect_alarm",
                    },
                },
                "noise_reduce_config": noise_reduce_config,
                "start_time": "00:00:00",
                "end_time": "23:59:59",
            },
            "config": notice_action_config["execute_config"]["template_detail"],
        },
        "actions": [],
        "notice_action_config": notice_action_config,
    }

    return strategy_dict


class TestDutyArrangeSlzResource(TestCase):
    def setUp(self):
        StrategyModel.objects.all().delete()

    def tearDown(self):
        StrategyModel.objects.all().delete()

    def test_create_strategy_dict(self):
        noise_reduce_config = {"is_enabled": True, "count": 10, "dimensions": ["bk_target_ip", "bk_cloud_id"]}
        strategy = get_strategy_dict(noise_reduce_config)
        save_request = SaveStrategyV2Resource()
        validated_strategy = save_request.validate_request_data(strategy)
        save_request.perform_request(validated_strategy)
        self.assertEqual(StrategyModel.objects.all().count(), 1)

        strategy_object = StrategyModel.objects.all()[0]

        strategy_obj = Strategy.from_models([strategy_object])[0]
        strategy_obj.restore()
        config = strategy_obj.to_dict()
        reduce_config_from_db = config["notice"]["options"]["noise_reduce_config"]

        for key in noise_reduce_config.keys():
            self.assertEqual(noise_reduce_config[key], reduce_config_from_db[key])

    def test_create_strategy_without_dimensions(self):
        noise_reduce_config = {"is_enabled": True, "count": 10, "dimensions": []}
        strategy = get_strategy_dict(noise_reduce_config)
        save_request = SaveStrategyV2Resource()
        with self.assertRaises(CustomException):
            save_request.validate_request_data(strategy)

    def test_create_strategy_without_count(self):
        noise_reduce_config = {"is_enabled": True, "count": 0, "dimensions": ["bk_target_ip", "bk_cloud_id"]}
        strategy = get_strategy_dict(noise_reduce_config)
        save_request = SaveStrategyV2Resource()
        with self.assertRaises(CustomException):
            save_request.validate_request_data(strategy)

    def test_create_strategy_without_reduce(self):
        noise_reduce_config = {
            "is_enabled": False,
        }
        strategy = get_strategy_dict(noise_reduce_config)
        save_request = SaveStrategyV2Resource()
        save_request.validate_request_data(strategy)
