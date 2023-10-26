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


import datetime

from django.test import Client, TestCase, override_settings

from monitor_web.tests.mock import *  # noqa
from monitor_web.tests.mock_settings import *  # noqa

# import json


TEST_BK_USERNAME = "admin"
TEST_TIMEZONE = pytz.timezone("Asia/Shanghai")
TEST_ANOMALY_RECORD = {
    "anomaly_id": 1,
    "source_time": TEST_TIMEZONE.localize(datetime.datetime(year=2019, month=12, day=1, minute=0)),
    "create_time": TEST_TIMEZONE.localize(datetime.datetime(year=2019, month=12, day=1, minute=0)),
    "strategy_id": 1,
    "origin_alarm": {"anomaly": {"1": {"anomaly_message": "anomaly_message1"}}},
}
TEST_EVENT = {
    "id": 1,
    "create_time": TEST_TIMEZONE.localize(datetime.datetime(year=2019, month=12, day=1, minute=0)),
    "begin_time": TEST_TIMEZONE.localize(datetime.datetime(year=2019, month=12, day=1, minute=1)),
    "end_time": TEST_TIMEZONE.localize(datetime.datetime(year=2019, month=12, day=1, minute=2)),
    "bk_biz_id": 2,
    "event_id": 1,
    "strategy_id": 1,
    "origin_alarm": {},
    "origin_config": {},
    "level": 1,
    "status": "RECOVERED",
    "is_ack": False,
    "p_event_id": "",
    "is_shielded": 1,
    "target_key": "target_key",
    "latest_anomaly_record": TEST_ANOMALY_RECORD,
}
TEST_EVENT_ACTIONS = [
    {"status": "SUCCESS", "extend_info": {}},
    {"status": "SHIELDED", "extend_info": {}},
    {"status": "FAILED", "extend_info": {"empty_receiver": False}},
    {"status": "FAILED", "extend_info": {"empty_receiver": True}},
    {"status": "PARTIAL_SUCCESS", "extend_info": {}},
]


class TestEventCenterViewSet(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_info_patcher = patch(
            CORE_DRF_RESOURCE_CONTRIB_API_MAKE_USERINFO, MagicMock(return_value={"bk_username": TEST_BK_USERNAME})
        )
        self.biz_access_permission = patch(MONITOR_WEB_ALERT_EVENTS_VIEWS_GET_PERMISSIONS, MagicMock(reture_value=[]))

        self.user_info_patcher.start()
        self.biz_access_permission.start()

    def tearDown(self):
        self.user_info_patcher.stop()
        self.biz_access_permission.stop()

    # @override_settings(MIDDLEWARE_CLASSES=())
    # def test_list_event(self):
    #     path = '/rest/v2/event_center/list_event/'
    #     data = {
    #         'bk_biz_ids': [2],
    #         'time_range': '2019-12-20T10:00:00+08:00 -- 2019-12-25T10:00:00+08:00'
    #     }
    #     response = self.client.post(path=path, data=data)
    #     self.assertEqual(response.status_code, 200)

    # @override_settings(MIDDLEWARE=())
    # @patch(BKMONITRO_RESOURCE_ALERT_EVENTS_GET_EVENT, MagicMock(return_value=MockEventModel(**TEST_EVENT)))
    # @patch(
    #     BKMONIT_MODELS_ANOMALYRECORD_OBJECTS_FILTER,
    #     MagicMock(return_value=MockQuerySet(aggregate_result={"source_time__min": TEST_EVENT["begin_time"]})),
    # )
    # @patch(
    #     BKMONIT_MODELS_EVENTACTION_OBJECTS_FILTER,
    #     MagicMock(return_value=[MockEventAction(**event_action) for event_action in TEST_EVENT_ACTIONS]),
    # )
    # def test_detail_event(self):
    #     path = "/rest/v2/event_center/detail_event/"
    #     data = {"bk_biz_id": 2, "id": 1}
    #     response = self.client.get(path=path, data=data)
    #     self.assertEqual(response.status_code, 200)
    # data = json.loads(response.content)
    # self.assertEqual(data, {
    #     'message': 'OK',
    #     'code': 200,
    #     'data': {
    #         'dimension_message': '',
    #         'event_begin_time': '2019-12-01 00:01:00+0800',
    #         'is_ack': False,
    #         'event_message': 'anomaly_message1',
    #         'event_status': 'RECOVERED',
    #         'hold_time': '1m',
    #         'id': 1,
    #         'bk_biz_id': 2,
    #         'dimensions': '',
    #         'level': 1,
    #         'strategy_id': 1,
    #         'alert_info': {
    #             'count': 5,
    #             'failed_count': 1,
    #             'empty_receiver_count': 1,
    #             'shielded_count': 1,
    #             'partial_count': 1, 'success_count': 1
    #         },
    #         'is_shielded': 1, 'strategy_name': '',
    #         'first_anomaly_time': '2019-12-01 00:00:00+0800',
    #         'relation_info': ''
    #     },
    #     'result': True
    # })
