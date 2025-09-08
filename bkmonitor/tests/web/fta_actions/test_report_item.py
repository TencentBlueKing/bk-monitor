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
from collections import namedtuple

import mock
from django.test import TestCase
from monitor_web.report.resources import (
    ReportCreateOrUpdateResource,
    ReportListResource,
)

from bkmonitor.models import ReportItems


class TestReportItem(TestCase):
    def setUp(self) -> None:
        ReportItems.objects.all().delete()

    def tearDown(self) -> None:
        ReportItems.objects.all().delete()

    @mock.patch(
        "monitor_web.report.resources.ReportCreateOrUpdateResource.fetch_group_members",
        return_value=[{"id": "admin", "is_enabled": True, "type": "user"}],
    )
    def test_create_report_item(self, fetch_group_members):
        r = ReportCreateOrUpdateResource()
        request_data = {
            "mail_title": "订阅测试",
            "receivers": [{"id": "admin", "is_enabled": True, "type": "user"}],
            "channels": [
                {
                    "channel_name": "email",
                    "is_enabled": True,
                    "subscribers": [
                        {
                            "username": "test@qq.com",
                        }
                    ],
                },
                {
                    "channel_name": "wxbot",
                    "is_enabled": True,
                    "subscribers": [
                        {
                            "username": "123456677777",
                        }
                    ],
                },
            ],
            "managers": [{"id": "admin", "type": "user"}],
            "frequency": {"type": 4, "run_time": "14:40:38", "day_list": [1], "week_list": [], "hour": ""},
            "report_contents": [
                {
                    "id": 5,
                    "report_item": 3,
                    "content_title": "123cesdfs",
                    "content_details": "",
                    "row_pictures_num": 2,
                    "graphs": ["2-bLlNuRLWz-8"],
                    "graph_name": [{"graph_id": "2-bLlNuRLWz-8", "graph_name": "Total Connections"}],
                }
            ],
            "time_range": "none",
            "bk_biz_id": 2,
        }
        r.request(request_data)
        self.assertEqual(fetch_group_members.call_count, 2)
        self.assertTrue(ReportItems.objects.all().count() == 1)

        r_item = ReportItems.objects.first()
        channels = {c["channel_name"]: c["subscribers"] for c in r_item.channels}
        self.assertTrue("email" in channels)
        self.assertTrue(len(channels["wxbot"]), 1)

    @mock.patch(
        "monitor_web.report.resources.ReportCreateOrUpdateResource.fetch_group_members",
        return_value=[{"id": "admin", "is_enabled": True, "type": "user"}],
    )
    @mock.patch("core.drf_resource.resource.report.group_list", return_value=[])
    @mock.patch(
        "monitor_web.report.resources.ReportListResource.get_request_user",
        return_value=namedtuple("user", {"username": "admin", "is_superuser": True}),
    )
    def test_get_report_items(self, request_user, group_list, fetch_group_members):
        item_data = {
            "mail_title": "订阅测试",
            "receivers": [{"id": "admin", "is_enabled": True, "type": "user"}],
            "channels": [
                {
                    "channel_name": "email",
                    "is_enabled": True,
                    "subscribers": [
                        {
                            "username": "test@qq.com",
                        }
                    ],
                },
                {
                    "channel_name": "wxbot",
                    "is_enabled": True,
                    "subscribers": [
                        {
                            "username": "123456677777",
                        }
                    ],
                },
            ],
            "managers": [{"id": "admin", "type": "user"}],
            "frequency": {"type": 4, "run_time": "14:40:38", "day_list": [1], "week_list": []},
            "report_contents": [
                {
                    "id": 5,
                    "report_item": 3,
                    "content_title": "123cesdfs",
                    "content_details": "",
                    "row_pictures_num": 2,
                    "graphs": ["2-bLlNuRLWz-8"],
                    "graph_name": [{"graph_id": "2-bLlNuRLWz-8", "graph_name": "Total Connections"}],
                }
            ],
            "time_range": "none",
            "bk_biz_id": 2,
        }
        ReportCreateOrUpdateResource().request(item_data)
        r_list = ReportListResource().request()
        self.assertEqual(len(r_list), 1)
        print(r_list[0])
        channels = {c["channel_name"]: c["subscribers"] for c in r_list[0]["channels"]}
        self.assertTrue("email" in channels)
        self.assertTrue(len(channels["wxbot"]), 1)
        self.assertTrue("user" in channels)

    @mock.patch(
        "monitor_web.report.resources.ReportCreateOrUpdateResource.fetch_group_members",
        return_value=[{"id": "admin", "is_enabled": True, "type": "user"}],
    )
    @mock.patch("core.drf_resource.resource.report.group_list", return_value=[])
    @mock.patch(
        "monitor_web.report.resources.ReportListResource.get_request_user",
        return_value=namedtuple("user", {"username": "admin", "is_superuser": True}),
    )
    def test_get_empty_channel_report_items(self, request_user, group_list, fetch_group_members):
        item_data = {
            "mail_title": "订阅测试",
            "receivers": [{"id": "admin", "is_enabled": True, "type": "user"}],
            "managers": [{"id": "admin", "type": "user"}],
            "frequency": {"type": 4, "run_time": "14:40:38", "day_list": [1], "week_list": []},
        }
        ReportItems.objects.create(**item_data)
        r_list = ReportListResource().request()
        self.assertEqual(len(r_list), 1)
        channels = {c["channel_name"]: c["subscribers"] for c in r_list[0]["channels"]}
        self.assertTrue("user" in channels)
