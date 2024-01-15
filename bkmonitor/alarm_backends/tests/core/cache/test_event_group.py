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


import mock
from django.test import TestCase

from alarm_backends.core.cache.event_group import EventGroupCacheManager
from constants.data_source import DataSourceLabel
from core.drf_resource import APIResource


class TestEventGroupCacheSource(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch.object(APIResource, "perform_request")
    def test_refresh(self, mock_api):
        event_group_info = [
            {
                "bk_biz_id": 0,
                "bk_data_id": 1500213,
                "create_time": "2020-03-23 07:10:24",
                "creator": "user1",
                "event_group_id": 111,
                "event_group_name": "hoffer39",
                "event_info_list": [
                    {
                        "dimension_list": ["bk_target_ip", "bk_cloud_id"],
                        "event_id": 25,
                        "event_name": "Bridget Holloman",
                    },
                    {"dimension_list": ["bk_target_ip", "bk_cloud_id"], "event_id": 26, "event_name": "Carolyn Kramer"},
                ],
                "is_enable": True,
                "label": "other_rt",
                "last_modify_time": "2020-03-23 07:10:24",
                "last_modify_user": "user1",
                "table_id": "bkmonitor_event_1500213",
            }
        ]
        event_info = {
            "bk_biz_id": 0,
            "bk_data_id": 1500213,
            "create_time": "2020-03-23 07:10:24",
            "creator": "user1",
            "event_group_id": 111,
            "event_group_name": "hoffer39",
            "event_info_list": [
                {"dimension_list": ["bk_target_ip", "bk_cloud_id"], "event_id": 25, "event_name": "Bridget Holloman"},
                {"dimension_list": ["bk_target_ip", "bk_cloud_id"], "event_id": 26, "event_name": "Carolyn Kramer"},
            ],
            "is_enable": True,
            "label": "other_rt",
            "last_modify_time": "2020-03-23 07:10:24",
            "last_modify_user": "user1",
            "shipper_list": [
                {
                    "auth_info": {"password": "", "username": ""},
                    "cluster_config": {"domain_name": "10.0.1.11", "is_ssl_verify": False, "port": 9200},
                    "cluster_type": "elasticsearch",
                    "storage_config": {"base_index": "bkmonitor_event_1500213"},
                }
            ],
            "table_id": "bkmonitor_event_1500213",
        }
        mock_api.side_effect = [event_group_info, event_info]
        EventGroupCacheManager.refresh()
        ret = EventGroupCacheManager.get_connect_info(DataSourceLabel.CUSTOM, "bkmonitor_event_1500213")
        expect_ret = {
            "doc_type": "_doc",
            "event_group_name": "hoffer39",
            "datasource_info": {
                "is_ssl_verify": False,
                "auth_info": {"username": "", "password": ""},
                "domain_name": "10.0.1.11",
                "port": 9200,
            },
            "event_info_list": [
                {"event_id": 25, "dimension_list": ["bk_target_ip", "bk_cloud_id"], "event_name": "Bridget Holloman"},
                {"event_id": 26, "dimension_list": ["bk_target_ip", "bk_cloud_id"], "event_name": "Carolyn Kramer"},
            ],
            "table_id": "bkmonitor_event_1500213",
            "base_index": "bkmonitor_event_1500213",
            "bk_event_group_id": 111,
        }
        self.assertEqual(expect_ret, ret)
