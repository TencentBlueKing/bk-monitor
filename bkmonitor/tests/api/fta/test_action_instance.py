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
import json
import time
from unittest.mock import MagicMock, patch

from blueapps.account.models import User
from django.test import Client, TestCase

from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.models import ActionConfig
from bkmonitor.models.fta import ActionInstance
from constants.action import ActionStatus
from fta_web.action.resources.backend_resources import ITSMCallbackResource


class TestActionInstanceResource(TestCase):
    def setUp(self):
        User.objects.all().delete()
        User.objects.create_user(username="admin", password="admin")

        self.ai = ActionInstance.objects.create(
            signal="abnormal",
            strategy_id=1,
            alerts=",".join(["123213213"]),
            status=ActionStatus.WAITING,
            bk_biz_id=2,
            action_config={},
            action_plugin={"plugin_type": "job"},
        )

        self.callback_data = {
            "sn": "23312312312312312",
            "title": "sjftestkwjrwer({})".format(self.ai.id),
            "approve_result": True,
            "updated_by": "selina",
            "token": "24234234",
        }

    def tearDown(self):
        User.objects.all().delete()
        ActionInstance.objects.all().delete()

    def test_itsm_callback(self):
        c = Client()
        response = c.post(
            "/api/v4/action_instance/itsm_callback/?system=itsm&signature=pi5ERY0tdLsrF2LbdgSwg3Xb1OAYBZDOayQKSBxwZEM=",
            data=self.callback_data,
        )
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["result"])

    def test_itsm_callback_resource(self):
        callback_data = {
            "sn": "23312312312312312",
            "title": "sjftestkwjrwer({})".format(self.ai.id),
            "approve_result": True,
            "updated_by": "selina",
            "token": "24234234",
        }
        self.assertFalse(ITSMCallbackResource().request(**callback_data)["result"])


class TestBatchCreateResource(TestCase):
    def setUp(self):
        ActionConfig.objects.all().delete()
        User.objects.create_user(username="admin", password="admin")

        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "{{alert.event.ip}}", "1000004_1": "hello, {{alert.event.ip}}"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "id": 4444,
        }
        self.ac = ActionConfig.objects.create(**job_config)
        self.request_data = {"alert_ids": ["1111111"], "config_ids": [self.ac.id], "bk_biz_id": 2}
        event = EventDocument(
            **{
                "bk_biz_id": 2,
                "ip": "127.0.0.1",
                "time": int(time.time()),
                "create_time": int(time.time()),
                "bk_cloud_id": 0,
                "id": 123,
            }
        )
        self.alert_document_mock = patch(
            "bkmonitor.documents.AlertDocument.mget",
            MagicMock(
                return_value=[
                    AlertDocument(
                        **{
                            "id": 1111111,
                            "begin_time": int(time.time()),
                            "create_time": int(time.time()),
                            "end_time": int(time.time()),
                            "severity": 1,
                            "strategy_id": 0,
                            "is_shielded": False,
                            "is_handled": True,
                            "is_ack": False,
                            "assignee": ["admin"],
                            "event": event,
                        }
                    )
                ]
            ),
        )

    def tearDown(self):
        User.objects.all().delete()
        ActionInstance.objects.all().delete()
        ActionConfig.objects.all().delete()

    def start_mock(self):
        self.alert_document_mock.start()

    def stop_mock(self):
        self.alert_document_mock.stop()

    def test_get_action_params_by_config(self):
        # 直接结单测试
        request_url = (
            "/api/v4/action_instance/get_action_params_by_config/?"
            "system=hihihi&signature=pi5ERY0tdLsrF2LbdgSwg3Xb1OAYBZDOayQKSBxwZEM="
        )
        self.start_mock()
        c = Client()
        webhook_config = {
            "plugin_id": 2,
            "desc": "",
            "execute_config": {
                "template_detail": {
                    "need_poll": True,
                    "notify_interval": 120,
                    "interval_notify_mode": "standard",
                    "method": "POST",
                    "url": "http://127.0.0.1:19800?ip={{target.host.bk_host_innerip}}",
                    "headers": [
                        {
                            "key": "Content-Type",
                            "value": "application/json",
                            "desc": "",
                            "is_builtin": False,
                            "is_enabled": True,
                        },
                        {
                            "key": "Host-Id",
                            "value": "{{target.host.bk_host_id}}",
                            "desc": "",
                            "is_builtin": False,
                            "is_enabled": True,
                        },
                    ],
                    "authorize": {
                        "auth_type": "basic_auth",
                        "auth_config": {"username": "testuser", "password": "{{target.business.bk_biz_name}}"},
                    },
                    "body": {
                        "data_type": "raw",
                        "params": [],
                        "content": "{{alarm.callback_message}}",
                        "content_type": "text",
                    },
                    "query_params": [
                        {
                            "key": "alarm_name",
                            "value": "{{alarm.name}}",
                            "desc": "",
                            "is_builtin": False,
                            "is_enabled": True,
                        },
                        {
                            "key": "level",
                            "value": "Level {{alarm.level}}",
                            "desc": "",
                            "is_builtin": False,
                            "is_enabled": True,
                        },
                    ],
                    "failed_retry": {"is_enabled": True, "timeout": 60, "max_retry_times": 4, "retry_interval": 3},
                },
                "timeout": 600,
            },
            "name": "测试webhook",
            "bk_biz_id": 2,
            "is_enabled": True,
        }

        web_ac = ActionConfig.objects.create(**webhook_config)
        self.request_data["config_ids"].append(web_ac.id)
        response = c.post(request_url, data=json.dumps(self.request_data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        action_configs = response.data["action_configs"]
        self.assertEqual(len(action_configs), 2)
        self.assertEqual(action_configs[1]["alert_ids"][0], "1111111")
        execute_config_detail = action_configs[1]["execute_config"]["template_detail"]
        self.assertIsNotNone(action_configs[1]["execute_config"]["origin_template_detail"])
        self.assertEqual(execute_config_detail["1000005_3"], "127.0.0.1")
        self.assertEqual(execute_config_detail["1000004_1"], "hello, 127.0.0.1")

        webhook_config_detail = action_configs[0]["execute_config"]["template_detail"]

        self.assertTrue("username" in webhook_config_detail["authorize"]["auth_config"])
        self.stop_mock()

    def test_batch_create_action(self):
        request_url = (
            "/api/v4/action_instance/batch_create_action/?"
            "system=hihihi&signature=pi5ERY0tdLsrF2LbdgSwg3Xb1OAYBZDOayQKSBxwZEM="
        )
        self.start_mock()
        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "127.0.0.1", "1000004_1": "hello, 127.0.0.1"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "config_id": self.ac.id,
            "id": self.ac.id,
        }
        request_data = {
            "operate_data_list": [{"alert_ids": ["1111111"], "action_configs": [job_config]}],
            "creator": "admin",
            "bk_biz_id": 2,
        }

        config_validate_patch = patch(
            "bkmonitor.action.serializers.action.ActionConfigBaseInfoSlz.run_validation",
            MagicMock(return_value=job_config),
        )
        config_validate_patch.start()
        c = Client()
        response = c.post(request_url, data=json.dumps(request_data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        print(response.data)
        actions = response.data["actions"]
        self.assertEqual(len(actions), 1)
        self.stop_mock()
        config_validate_patch.stop()
