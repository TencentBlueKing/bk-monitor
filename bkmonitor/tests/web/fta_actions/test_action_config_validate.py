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
from django.test import TestCase, override_settings, Client

from bkmonitor.action import serializers
from bkmonitor.action.serializers import ConvergeConfigSlz, HttpCallBackConfigSlz
from bkmonitor.models import ActionConfig, StrategyActionConfigRelation


class TestActionConfigValidate(TestCase):
    action_config = {
        "converge_config": {
            "timedelta": 2,
            "count": 10,
            "condition": [{"dimension": "idc_unit_name", "value": ["self"]}],
            "converge_func": "defense",
        },
        "execute_config": {
            "template_detail": {
                "method": "GET",
                "url": "https://www.google.com",
                "headers": [
                    {
                        "key": "content—type",
                        "value": "application/json",
                        "desc": "xxxx",
                        "is_builtin": True,
                        "is_enabled": True,
                    }
                ],
                "authorize": {
                    "auth_type": "basic_auth",
                    "auth_config": {
                        "username": "wxwork-bot,mail",
                        "password": "wwerwrxfsdfsfsdfdsfsdf12312sd",
                        "token": "xxxx, 当为token校验的时候",
                    },
                },
                "body": {
                    "data_type": "raw",
                    "content_type": "json",
                    "content": "{'bk_biz_id':2}",
                    "params": [{"key": "content—type", "value": "application/json", "desc": "xxxx"}],
                },
                "query_params": [{"key": "bk_biz_id", "value": "2", "desc": "url请求参数"}],
                "notify_interval": 60 * 60,
            },
            "timeout": 60,
            "failed_retry": {"is_enabled": True, "max_retry_times": 2, "retry_interval": 30},
        },
        "name": "测试重名",
        "bk_biz_id": 2,
        "desc": "",
        "is_enabled": True,
        "plugin_id": 2,
    }

    def setUp(self) -> None:
        ActionConfig.objects.all().exclude(bk_biz_id=0).delete()
        StrategyActionConfigRelation.objects.all().delete()

    def tearDown(self) -> None:
        ActionConfig.objects.all().exclude(bk_biz_id=0).delete()
        StrategyActionConfigRelation.objects.all().delete()

    def test_action_config(self):
        action_s = serializers.ActionConfigDetailSlz(data=self.action_config)
        self.assertTrue(action_s.is_valid(raise_exception=True))

    def test_action_name_duplicate_error(self):
        ActionConfig.objects.create(name="测试重名", bk_biz_id=2, plugin_id=2, converge_config={}, execute_config={})

        action_s = serializers.ActionConfigDetailSlz(data=self.action_config)
        self.assertFalse(action_s.is_valid())

    def test_builtin_action_name_duplicate_error(self):
        from copy import deepcopy

        action_config = deepcopy(self.action_config)
        action_config["name"] = "默认无数据告警通知"
        action_s = serializers.ActionConfigDetailSlz(data=action_config)
        self.assertFalse(action_s.is_valid())

    def test_same_action_name_true_config(self):
        action_instance = ActionConfig.objects.create(
            name="测试重名", bk_biz_id=2, plugin_id=2, converge_config={}, execute_config={}
        )
        action_s = serializers.ActionConfigDetailSlz(instance=action_instance, data=self.action_config)
        self.assertTrue(action_s.is_valid(raise_exception=True))

    def test_http_callback_config_true(self):
        http_config = {
            "method": "GET",
            "url": "https://www.baidu.com",
            "headers": [
                {
                    "key": "content—type",
                    "value": "application/json",
                    "desc": "xxxx",
                    "is_builtin": True,
                    "is_enabled": True,
                }
            ],
            "authorize": {
                "auth_type": "basic_auth",
                "auth_config": {"username": "wxwork-bot,mail", "password": "wwerwrxfsdfsfsdfdsfsdf12312sd"},
            },
            "body": {
                "data_type": "raw",
                "content_type": "json",
                "content": "{'bk_biz_id':2}",
                "params": [{"key": "content—type", "value": "application/json", "desc": "xxxx"}],
            },
            "query_params": [{"key": "content—type", "value": "application/json", "desc": "xxxx"}],
            "notify_interval": 60 * 60,
        }
        hs = HttpCallBackConfigSlz(data=http_config)
        self.assertTrue(hs.is_valid(raise_exception=True))

    def test_authorize_config(self):
        auth_data = {
            "auth_type": "basic_auth",
            "auth_config": {"username": "wxwork-bot,mail", "password": "wwerwrxfsdfsfsdfdsfsdf12312sd"},
        }
        auth_s = serializers.AuthorizeConfigSlz(data=auth_data)
        self.assertTrue(auth_s.is_valid(raise_exception=True))

    def test_true_converge_config(self):
        converge_config = {
            "timedelta": "2",
            "count": 10,
            "condition": [{"dimension": "idc_unit_name", "value": ["self"]}],
            "converge_func": "defense",
        }
        cs = ConvergeConfigSlz(data=converge_config)

        self.assertTrue(cs.is_valid())

    def test_converge_config_false_with_string_timedelta(self):
        converge_config = {
            "timedelta": "2xx",
            "count": 10,
            "condition": [
                {"dimension": "idc_unit_name", "value": ["self"]},
                {"dimension": "alarm_type", "value": ["os-restart", 1, "agent"]},
            ],
            "converge_func": "defense",
        }
        cs = ConvergeConfigSlz(data=converge_config)

        self.assertFalse(cs.is_valid())

    def test_converge_config_false_with_string_value(self):
        converge_config = {
            "timedelta": "2",
            "count": 10,
            "condition": [
                {"dimension": "idc_unit_name", "value": "self"},
                {"dimension": "alarm_type", "value": ["os-restart", 1, "agent"]},
            ],
            "converge_func": "defense",
        }
        cs = ConvergeConfigSlz(data=converge_config)

        self.assertFalse(cs.is_valid())

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    def test_delete_success_config(self):
        ac = ActionConfig.objects.create(name="测试重名", bk_biz_id=2, plugin_id=2, converge_config={}, execute_config={})

        c = Client()
        response = c.delete(path="/fta/action/config/%s/" % ac.id, data={"bk_biz_id": 2})
        print(response.data)
        self.assertEqual(response.status_code, 200)

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    def test_delete_failed_config(self):
        ac = ActionConfig.objects.create(name="测试重名", bk_biz_id=2, plugin_id=2, converge_config={}, execute_config={})
        StrategyActionConfigRelation.objects.create(config_id=ac.id, strategy_id=1, user_groups=[1, 2])

        c = Client()
        response = c.delete(path="/fta/action/config/%s/" % ac.id)
        self.assertEqual(response.status_code, 400)
