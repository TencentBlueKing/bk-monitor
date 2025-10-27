# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http:# opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import time
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from blueapps.account.models import User
from bkmonitor.models.fta import ActionInstance
from bkmonitor.documents import AlertDocument, EventDocument, ActionInstanceDocument
from bkmonitor.models import EventPlugin
from metadata.models import DataSource

patch("core.drf_resource.api.cmsi.get_msg_type", return_value=[{"type": "voice", "label": "语音"}]).start()


class TestSearchAlertByEventResource(TestCase):
    def setUp(self):
        User.objects.all().delete()
        EventPlugin.objects.all().delete()
        User.objects.create_user(username="admin", password="admin")

        EventPlugin.objects.create(
            **{
                "is_enabled": True,
                "is_deleted": False,
                "plugin_id": "uwork",
                "plugin_display_name": "uwork对接",
                "plugin_type": "http_push",
                "summary": "推送符合故障自愈标准格式的事件",
                "author": "蓝鲸智云",
                "data_id": 1500001,
                "package_dir": "833578fd-3167-4192-8e68-9d3668fe43d4",
                "bk_biz_id": 0,
                "tags": ["Restful", "标准格式"],
                "scenario": "MONITOR",
                "popularity": 0,
                "status": "ENABLED",
                "ingest_config": {"source_format": "json", "multiple_events": False, "events_path": ""},
                "normalization_config": [
                    {"field": "alert_name", "expr": "alert_name", "option": {}},
                    {"field": "event_id", "expr": "event_id", "option": {}},
                    {"field": "description", "expr": "description", "option": {}},
                    {"field": "metric", "expr": "metric", "option": {}},
                    {"field": "category", "expr": "category", "option": {}},
                    {"field": "assignee", "expr": "assignee", "option": {}},
                    {"field": "status", "expr": "status", "option": {}},
                    {"field": "target_type", "expr": "target_type", "option": {}},
                    {"field": "target", "expr": "target", "option": {}},
                    {"field": "severity", "expr": "severity", "option": {}},
                    {"field": "bk_biz_id", "expr": "bk_biz_id", "option": {}},
                    {"field": "tags", "expr": "tags", "option": {}},
                    {"field": "time", "expr": "time", "option": {}},
                    {"field": "anomaly_time", "expr": "anomaly_time", "option": {}},
                    {"field": "dedupe_md5", "expr": "dedupe_md5", "option": {}},
                ],
            }
        )

        data_source = DataSource(
            **{
                "bk_data_id": 1500001,
                "token": "0f1b0d84c3da475889f684ba84998dee",
                "data_name": "fta_uwork_push",
                "data_description": "fta_rest_push",
                "mq_cluster_id": 1,
                "mq_config_id": 23,
                "etl_config": "bk_fta_event",
                "is_custom_source": True,
                "creator": "admin",
                "type_label": "event",
                "source_label": "bk_monitor",
                "custom_label": None,
                "source_system": "bk_monitorv3",
                "is_enable": True,
                "transfer_cluster_id": "default",
            }
        )
        self.request_url = "/api/v4/alert_info/search_alert_by_event/?system=hihihi&signature=pi5ERY0tdLsrF2LbdgSwg3Xb1OAYBZDOayQKSBxwZEM="
        self.event_data = json.dumps({"event_id": "13860891", "create_time": int(time.time())})
        self.uwork_event_data = json.dumps(
            {
                "SystemId": "uwork",  # uwork调用
                "Action": "createTask",  # 统一为固定字符, 业务工具无需理会
                "Data": {
                    "IP": "127.0.0.1",  # 故障机器IP
                    "ServerBsi1": "",  # 一级业务集
                    "ServerBsi2": "",  # 二级业务
                    "ServerBsi3": "",  # 三级业务模块
                    "AlarmTypeID": "87",  # Uwork这边统一维护一份告警类型id表
                    "AlarmTypeName": "硬盘故障（有冗余）",  # Uwork这边统一维护一份告警类型id表
                    "UnitParameter": [{"Directory": "/"}, {"Directory": "/data"}],
                    # 硬盘只读传只读的目录列表，Ping告警为空字符串，Agent上报超时此字段为空
                    "InstanceID": "3860891",
                    "IfSupportTitanAutoRepair": "0",  # 是否支持Titan自动修复，0 不支持，1支持
                    "NeedShutDown": 0,
                    "JustStopBusiness": 0,
                    "IsDataLost": 0,
                    "IsNeedReinstallOS": 0,
                },
            }
        )
        self.data_source_get_mock = patch("metadata.models.DataSource.objects.get", MagicMock(return_value=data_source))

        self.event_document_mock = patch(
            "bkmonitor.documents.EventDocument.get_by_event_id",
            MagicMock(
                return_value=EventDocument(
                    **{
                        "dedupe_md5": 13860891,
                        "event_id": 13860891,
                        "create_time": int(time.time()),
                        "begin_time": int(time.time()),
                        "target_type": "host",
                        "target": "127.0.0.1|0",
                        "ip": "127.0.0.1",
                    }
                )
            ),
        )
        self.alert_document_mock = patch(
            "bkmonitor.documents.AlertDocument.get_by_dedupe_md5",
            MagicMock(
                return_value=AlertDocument(
                    **{
                        "id": 1111111,
                        "begin_time": int(time.time()),
                        "create_time": int(time.time()),
                        "end_time": int(time.time()),
                        "is_shielded": False,
                        "is_handled": True,
                        "is_ack": False,
                        "assignee": ["admin"],
                    }
                )
            ),
        )
        self.action_document_mock = patch(
            "bkmonitor.documents.ActionInstanceDocument.mget_by_alert",
            MagicMock(
                return_value=[
                    ActionInstanceDocument(**{"status": "success", "action_plugin_type": "job"}),
                    ActionInstanceDocument(
                        **{"status": "success", "operate_target_string": "语音", "action_plugin_type": "notice"}
                    ),
                ]
            ),
        )

        self.authorize_action_document_mock = patch(
            "bkmonitor.documents.ActionInstanceDocument.mget_by_alert",
            MagicMock(
                return_value=[ActionInstanceDocument(**{"status": "success", "action_plugin_type": "authorize"})]
            ),
        )

        self.no_action_document_mock = patch(
            "bkmonitor.documents.ActionInstanceDocument.mget_by_alert",
            MagicMock(return_value=[]),
        )
        self.data_source_get_mock.start()

    def tearDown(self):
        User.objects.all().delete()
        ActionInstance.objects.all().delete()
        EventPlugin.objects.all().delete()
        self.data_source_get_mock.stop()

    def start_mock(self):
        self.alert_document_mock.start()
        self.event_document_mock.start()
        self.action_document_mock.start()

    def stop_mock(self):
        self.alert_document_mock.stop()
        self.event_document_mock.stop()
        self.action_document_mock.stop()

    def test_search_alert_by_event_success(self):
        # 直接结单测试
        self.start_mock()
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        handle_actions = response.data["handle_actions"]
        self.assertTrue("success" in [a["status"] for a in handle_actions])
        self.stop_mock()

    def test_search_alert_by_event_running(self):
        # 直接结单测试
        self.action_document_mock = patch(
            "bkmonitor.documents.ActionInstanceDocument.mget_by_alert",
            MagicMock(return_value=[ActionInstanceDocument(**{"status": "running", "action_plugin_type": "job"})]),
        )
        self.start_mock()
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        handle_actions = response.data["handle_actions"]
        self.assertTrue("running" in [a["status"] for a in handle_actions])
        self.stop_mock()

    def test_search_alert_by_event_voice_failure(self):
        # 直接结单测试
        self.start_mock()
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        voice_notice_actions = response.data["voice_notice_actions"]
        self.assertTrue(bool(voice_notice_actions))
        self.stop_mock()

    def test_search_alert_by_event_failure(self):
        # 直接结单测试
        self.action_document_mock = patch(
            "bkmonitor.documents.ActionInstanceDocument.mget_by_alert",
            MagicMock(return_value=[ActionInstanceDocument(**{"status": "failure", "action_plugin_type": "job"})]),
        )
        self.start_mock()
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        print("failure alert ", response.data)
        handle_actions = response.data["handle_actions"]
        self.assertTrue("failure" in [a["status"] for a in handle_actions])
        self.stop_mock()

    def test_search_alert_by_event_not_handled(self):
        # 未处理
        self.event_document_mock.start()
        nohandled_alert_document_mock = patch(
            "bkmonitor.documents.AlertDocument.get_by_dedupe_md5",
            MagicMock(
                return_value=AlertDocument(
                    **{
                        "id": 1111111,
                        "begin_time": int(time.time()),
                        "create_time": int(time.time()),
                        "end_time": int(time.time()),
                        "is_shielded": False,
                        "is_handled": False,
                        "is_ack": False,
                        "assignee": ["admin"],
                    }
                )
            ),
        )
        self.no_action_document_mock.start()

        nohandled_alert_document_mock.start()
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        print("nohandled alert", response.data)
        self.assertEqual(len(response.data["handle_actions"]), 0)
        nohandled_alert_document_mock.stop()
        self.no_action_document_mock.stop()
        self.event_document_mock.stop()

    def test_search_alert_by_event_false(self):
        c = Client()
        response = c.post(self.request_url, data=self.event_data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
