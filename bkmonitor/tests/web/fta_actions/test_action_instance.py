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
from unittest import skip
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings

from bkmonitor.action.serializers import ActionConfigDetailSlz
from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.documents.action import ActionInstanceDocument
from bkmonitor.models.fta import ActionInstance, ConvergeRelation
from constants.action import ActionSignal, ActionStatus
from fta_web.action.resources.backend_resources import (
    BatchCreateActionResource,
    GetActionParamsByConfigResource,
)
from fta_web.action.resources.frontend_resources import (
    AssignAlertResource,
    BatchCreateResource,
    GetActionConfigByAlerts,
    GetActionParamsResource,
)
from fta_web.action.utils import compile_assign_action_config

patch("fta_web.action.tasks.notify_to_appointee.delay", MagicMock(return_value=True)).start()
patch("bkmonitor.documents.AlertDocument.bulk_create", MagicMock(return_value=True)).start()
patch("bkmonitor.documents.AlertLog.bulk_create", MagicMock(return_value=True)).start()


class TestBatchCreateResource(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        ActionInstance.objects.all().delete()
        ConvergeRelation.objects.all().delete()
        self.alert_id = str(int(time.time()))
        self.ac_data = {
            "id": 123,
            "execute_config": {
                "template_id": 1000037,
                "template_detail": {"1000002": "hello, {{alert.alert_name}}"},
                "notify_config": {
                    "notify_type": [
                        {"level": 3, "type": "mail,weixin"},
                        {"level": 2, "type": "mail"},
                        {"level": 1, "type": "sms"},
                    ],
                },
                "timeout": 60,
                "failed_retry": {"is_enabled": True, "max_retry_times": 2, "retry_interval": 30},
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
        }
        self.config_validate_patch = patch(
            "bkmonitor.action.serializers.action.ActionConfigBaseInfoSlz.run_validation",
            MagicMock(return_value=self.ac_data),
        )
        self.config_validate_patch.start()
        event_time = int(time.time())
        event = EventDocument(
            **{
                "event_id": int(time.time()),
                "plugin_id": "fta-test",
                "alert_name": "test context-{}".format(event_time),
                "time": int(time.time()),
                "tags": [{"key": "device", "value": "cpu{}".format(event_time)}],
                "target": "127.0.0.1|0",
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "severity": 2,
                "description": "test event",
                "dedupe_keys": ["alert_name", "tags.device", "ip"],
            }
        )

        self.alerts = [
            AlertDocument(
                **{
                    "id": self.alert_id,
                    "alert_name": "告警名称",
                    "begin_time": int(time.time()),
                    "create_time": int(time.time()),
                    "end_time": int(time.time()),
                    "latest_time": int(time.time()),
                    "content_template": int(time.time()),
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

        self.alert_ids = [alert.id for alert in self.alerts]

        ac_dict_slz = ActionConfigDetailSlz(data=self.ac_data)
        ac_dict_slz.is_valid(raise_exception=True)
        self.ac = ac_dict_slz.save()

        self.alert_document_mock = patch(
            "bkmonitor.documents.AlertDocument.mget",
            MagicMock(return_value=self.alerts),
        )

        self.alert_document_mock.start()

    def tearDown(self):
        ActionInstance.objects.all().delete()
        ConvergeRelation.objects.all().delete()
        ActionConfigDetailSlz.Meta.model.objects.all().delete()
        self.config_validate_patch.stop()
        self.alert_document_mock.stop()

    def test_get_action_params_resource(self):
        request_data = {"alert_ids": [self.alert_id], "config_ids": [123], "bk_biz_id": 2}
        backend_mock = patch(
            "api.monitor.default.GetActionParamsBackendResource.request",
            MagicMock(
                return_value={
                    "action_configs": [
                        {
                            "id": 123,
                            "execute_config": {
                                "template_id": 1000037,
                                "template_detail": {"1000002": "hello, 告警名称"},
                                "notify_config": {
                                    "notify_type": [
                                        {"level": 3, "type": "mail,weixin"},
                                        {"level": 2, "type": "mail"},
                                        {"level": 1, "type": "sms"},
                                    ],
                                },
                                "timeout": 60,
                                "failed_retry": {"is_enabled": True, "max_retry_times": 2, "retry_interval": 30},
                            },
                            "name": "uwork重启",
                            "desc": "这是描述，这是描述",
                            "is_enabled": True,
                            "plugin_id": 3,
                            "bk_biz_id": 2,
                        }
                    ]
                }
            ),
        )
        template_detail_mock = patch(
            "fta_web.action.resources.frontend_resources.GetTemplateDetailResource.request",
            MagicMock(
                return_value={
                    "params": [
                        {
                            "formItemProps": {
                                "label": "测试变量",
                                "required": True,
                                "property": "1000002",
                                "help_text": "请输入",
                            },
                            "type": "input",
                            "key": "1000002",
                            "value": "",
                            "formChildProps": {"placeholder": "hihihi"},
                            "rules": [{"message": "必填项不可为空", "required": True, "trigger": "blur"}] if True else [],
                        }
                    ]
                }
            ),
        )
        backend_mock.start()
        template_detail_mock.start()
        response_data = GetActionParamsResource().request(**request_data)
        print("action params %s" % response_data)
        self.assertEqual(len(response_data), 1)
        self.assertTrue("params" in response_data[0])
        backend_mock.stop()
        template_detail_mock.stop()

    def test_assign(self):
        request_data = {
            "alert_ids": [self.alert_id],
            "bk_biz_id": 2,
            "appointees": ["admin", "yunweixiaoge"],
            "reason": "告警分派给负责人",
            "notice_ways": ["weixin"],
        }
        r = AssignAlertResource()
        data = r.perform_request(request_data)
        self.assertEqual({"yunweixiaoge"}, data["notice_receivers"])

    def test_get_action_params_by_custom_config(self):
        request_data = {
            "alert_ids": [self.alert_id],
            "config_ids": [],
            "action_configs": [
                {
                    "execute_config": {
                        "template_detail": {
                            "title": "hello-蓝鲸监控 | {{user_title}}",
                            "message": "hihihihih{{content.assign_reason}} {{content.appointees}} {{user_content}}",
                        },
                        "context_inputs": {
                            "title_tmpl": "{{alarm.name}}",
                            "appointees": ["admin", "yunweixiaoge"],
                            "assign_reason": "当前负责人",
                            "notice_way": msg_type,
                        },
                    },
                    "plugin_id": 1,
                    "name": "告警分派",
                    "is_enabled": True,
                    "bk_biz_id": 2,
                    "config_id": None,
                }
                for msg_type in ["sms", "mail", "weixin"]
            ],
            "bk_biz_id": 2,
        }
        r = GetActionParamsByConfigResource()
        params = r.perform_request(request_data)
        for item in params["action_configs"]:
            template_detail = item["execute_config"]["template_detail"]
            print(template_detail["title"], template_detail["message"])
            self.assertEqual("hello-蓝鲸监控 | 告警名称", template_detail["title"])

    def test_get_action_params_by_assign_template(self):
        request_data = {
            "alert_ids": [self.alert_id],
            "operator": "pppp",
            "appointees": ["admin", "yunweixiaoge"],
            "notice_ways": ["sms", "mail", "weixin", "voice"],
            "reason": "测试分派内容",
            "bk_biz_id": 2,
        }

        action_configs = compile_assign_action_config(request_data)
        request_data.update({"action_configs": action_configs})

        r = GetActionParamsByConfigResource()
        params = r.perform_request(request_data)
        for item in params["action_configs"]:
            template_detail = item["execute_config"]["template_detail"]
            notice_way = item["execute_config"]["context_inputs"]["notice_way"]
            print(notice_way, template_detail["title"], template_detail["message"])
            self.assertEqual(template_detail["title"], "蓝鲸监控 | pppp给您分派了告警【告警名称(%s)】" % self.alerts[0].id)

    def test_assign_template_with_multi_alerts(self):
        request_data = {
            "alert_ids": [self.alert_id, "%stest" % self.alert_id],
            "operator": "pppp",
            "appointees": ["admin", "yunweixiaoge"],
            "notice_ways": ["sms", "mail", "weixin", "voice"],
            "reason": "测试分派内容",
            "bk_biz_id": 2,
        }
        action = ActionInstance.objects.create(
            signal=ActionSignal.MANUAL,
            action_plugin={"id": 1},
            status=ActionStatus.SUCCESS,
            action_config={
                "plugin_id": 1,
                "name": "告警分派",
                "is_enabled": True,
                "bk_biz_id": request_data["bk_biz_id"],
                "config_id": None,
            },
            bk_biz_id=request_data["bk_biz_id"],
            strategy_id=0,
            action_config_id=0,
            alerts=request_data["alert_ids"],
            inputs=request_data,
        )

        action_configs = compile_assign_action_config(request_data)
        request_data.update({"action_configs": action_configs, "action_id": action.id})

        r = GetActionParamsByConfigResource()
        params = r.perform_request(request_data)
        print(params)
        for item in params["action_configs"]:
            template_detail = item["execute_config"]["template_detail"]
            notice_way = item["execute_config"]["context_inputs"]["notice_way"]
            print(notice_way, template_detail["title"], template_detail["message"])
            self.assertEqual(template_detail["title"], "蓝鲸监控 | pppp给您分派了【告警名称】等2个告警")

    @skip("skipping")
    def test_batch_create_resource(self):
        create_data = {
            "bk_biz_id": 2,
            "operate_data_list": [
                {
                    "alert_ids": [str(int(time.time()))],
                    "action_configs": [self.ac_data],
                }
            ],
            "creator": "admin",
        }
        response_data = BatchCreateResource().request(**create_data)
        self.assertTrue(response_data["result"])
        self.assertEqual(len(response_data["actions"]), 2)

    @skip("skipping")
    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    def test_batch_create_api(self):
        request_data = {
            "bk_biz_id": 2,
            "create_data": [
                {
                    "alert_ids": self.alert_ids[:4],
                    "config_ids": [self.ac.id],
                },
                {
                    "alert_ids": self.alert_ids[5:],
                    "config_ids": [self.ac.id],
                },
            ],
        }
        c = Client()
        response = c.post(
            "/fta/action/instances/batch_create/", data=json.dumps(request_data), content_type="application/json"
        )
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])
        self.assertEqual(len(response.data["actions"]), 2)

    @skip("skipping")
    def test_get_action_config_by_alert(self):
        """
        根据告警信息获取对应的套餐列表
        """
        create_data = {
            "bk_biz_id": 2,
            "operate_data_list": [
                {
                    "alert_ids": [str(int(time.time()))],
                    "action_configs": [self.ac_data],
                }
            ],
            "creator": "admin",
        }
        BatchCreateActionResource().request(**create_data)
        # sync_actions_sharding_task(resp["actions"])
        time.sleep(1)
        request_data = {"bk_biz_id": 2, "alert_ids": self.alert_ids}
        response = GetActionConfigByAlerts().request(**request_data)
        self.assertTrue(len(response) == 1)
        action_configs = response[0]["action_configs"]
        self.assertTrue(len(action_configs) == 1)
        self.assertTrue(action_configs[0]["id"] == self.ac.id)

    @skip("skipping")
    def test_sync_action_instances(self):
        action_ids = []
        actions = []
        for i in range(10):
            ai = ActionInstance.objects.create(
                signal="abnormal",
                strategy_id=1,
                alerts=",".join(["123213213"]),
                status="success",
                bk_biz_id=2,
                action_config={},
                action_plugin={"plugin_type": "job"},
            )
            ConvergeRelation.objects.create(
                converge_id=100,
                related_type="action",
                related_id=ai.id,
                converge_status="executed" if i == 0 else False,
                is_primary=True if i == 0 else False,
            )
            actions.append(ai.id)

            action_ids.append("{}{}".format(int(ai.create_time.timestamp()), ai.id))

        # sync_actions_sharding_task(actions)
        time.sleep(3)
        hits = ActionInstanceDocument.mget(ids=action_ids)
        self.assertEqual(len(hits), 10)

        search_obj = ActionInstanceDocument.compile_search(action_ids).filter("terms", id=action_ids)
        search_obj = search_obj.filter("term", converge_id=100)
        converge_hits = search_obj.execute()
        self.assertEqual(len(converge_hits), 10)

        search_obj = search_obj.filter("term", is_converge_primary=False)
        self.assertEqual(ConvergeRelation.objects.filter(is_primary=True).count(), 1)
        self.assertEqual(len(search_obj.execute()), 9)
