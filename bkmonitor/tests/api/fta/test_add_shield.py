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
import datetime
import time

from django.test import TestCase
from fta_web.alert.resources import QuickAlertAck, QuickAlertShield
from monitor_web.shield.resources.backend_resources import (
    AddShieldResource,
    BulkAddAlertShieldResource,
    ShieldListResource,
)
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.tests import mock

from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.models import ActionInstance, Shield
from bkmonitor.utils.common_utils import count_md5
from constants.action import ActionPluginType, ActionStatus


class TestBatchShieldResource(TestCase):
    def setUp(self):
        Shield.objects.all().delete()
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

        alert = AlertDocument(
            **{
                "id": 12345,
                "alert_name": "告警名称",
                "begin_time": int(time.time()),
                "create_time": int(time.time()),
                "end_time": int(time.time()),
                "latest_time": int(time.time()),
                "content_template": int(time.time()),
                "severity": 1,
                "status": "ABNORMAL",
                "strategy_id": 0,
                "is_shielded": False,
                "is_handled": True,
                "is_ack": False,
                "assignee": ["admin"],
                "dimensions": [{"key": "ip", "value": "127.0.0.1"}],
                "event": event,
            }
        )
        self.alert_mget_mock = mock.patch(
            "bkmonitor.documents.AlertDocument.mget", mock.MagicMock(return_value=[alert])
        )
        self.alert_get_mock = mock.patch("bkmonitor.documents.AlertDocument.get", mock.MagicMock(return_value=alert))
        self.alert_create_mock = mock.patch(
            "bkmonitor.documents.AlertDocument.bulk_create", mock.MagicMock(return_value=[alert])
        )
        self.alert_log_save_mock = mock.patch("bkmonitor.documents.AlertLog.save", mock.MagicMock(return_value=True))
        self.alert_mget_mock.start()
        self.alert_get_mock.start()
        self.alert_create_mock.start()
        self.alert_log_save_mock.start()

    def tearDown(self):
        self.alert_get_mock.stop()
        self.alert_mget_mock.stop()
        self.alert_create_mock.stop()
        self.alert_log_save_mock.stop()
        Shield.objects.all().delete()

    def test_add_shield_resource(self):
        request_data = {
            "category": "alert",
            "begin_time": "2021-05-27 17:11:45",
            "end_time": "2021-05-27 17:41:45",
            "dimension_config": {"alert_ids": [12345]},
            "cycle_config": {"begin_time": "", "type": 1, "day_list": [], "week_list": [], "end_time": ""},
            "shield_notice": False,
            "description": "这是原因",
            "is_quick": True,
            "bk_biz_id": 2,
        }
        BulkAddAlertShieldResource().request(**request_data)
        self.assertIsNotNone(Shield.objects.filter(category="alert"))

    def test_add_dimension_shield(self):
        request_data = {
            "category": "dimension",
            "begin_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_config": {"begin_time": "", "end_time": "", "day_list": [], "week_list": [], "type": 1},
            "shield_notice": False,
            "notice_config": {},
            "description": "",
            "dimension_config": {
                "dimension_conditions": [
                    {"key": "bk_target_ip", "value": ["10.1.1.1", "127.0.0.1"], "method": "eq"},
                    {"key": "bk_target_cloud_id", "value": ["0", "2"], "method": "eq"},
                ]
            },
            "bk_biz_id": 2,
        }

        shield_id = AddShieldResource().request(request_data)["id"]
        self.assertIsNotNone(Shield.objects.filter(category="dimension"))
        params = {"bk_biz_id": 2, "conditions": [{"key": "id", "value": [shield_id]}]}

        search_results = ShieldListResource().request(params)

        self.assertEqual(1, search_results["count"])

    def test_add_strategy_shield(self):
        request_data = {
            "category": "strategy",
            "begin_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_config": {"begin_time": "", "end_time": "", "day_list": [], "week_list": [], "type": 1},
            "shield_notice": False,
            "notice_config": {},
            "description": "",
            "dimension_config": {
                "id": [123],
                "dimension_conditions": [
                    {"key": "bk_target_ip", "value": ["10.1.1.1", "127.0.0.1"], "method": "eq"},
                    {"key": "bk_target_cloud_id", "value": ["0", "2"], "method": "eq"},
                ],
            },
            "bk_biz_id": 2,
        }

        AddShieldResource().request(request_data)
        self.assertIsNotNone(Shield.objects.filter(category="dimension"))
        match_info = {"strategy_id": 123, "level": [1, 2, 3]}

        shield_info = ShieldDetectManager(2, "strategy").check_shield_status(match_info)
        self.assertFalse(shield_info["is_shielded"])

    def test_weixin_quick_shield(self):
        alert = AlertDocument.get("12345")
        action = ActionInstance.objects.create(
            id=123,
            alerts=["12345", "23456"],
            signal="abnormal",
            strategy_id=0,
            alert_level=alert.severity,
            status=ActionStatus.SUCCESS,
            bk_biz_id=2,
            inputs={},
            action_config={},
            action_config_id=0,
            action_plugin={
                "plugin_type": ActionPluginType.NOTICE,
                "name": "通知",
                "plugin_key": ActionPluginType.NOTICE,
            },
        )

        request_data = {
            "bk_biz_id": 2,
            "action_id": "1234567890123",
            "username": "admin",
            "token": count_md5(["1234567890123", int(action.create_time.timestamp())]),
        }

        r = QuickAlertShield()
        validated_data = r.validate_request_data(request_data)
        r.perform_request(validated_data)
        self.assertIsNotNone(Shield.objects.filter(category="alert"))
        assert Shield.objects.filter(category="alert").count() == 2

        cr = QuickAlertAck()
        validated_data = cr.validate_request_data(request_data)
        result = cr.perform_request(validated_data)
        self.assertTrue("完成快捷确认" in result)
