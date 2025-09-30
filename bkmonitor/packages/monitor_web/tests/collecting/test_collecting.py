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


import json
import os

import mock
from django.test import TestCase

from bkmonitor.utils.local import local
from config import celery_app
from core.drf_resource import APIResource, resource
from monitor_web.models import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    PluginVersionHistory,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.custom_report import CustomEventGroup, CustomEventItem
from monitor_web.models.plugin import CollectorPluginMeta


class Base(object):
    pass


request = Base()
request.user = Base()
request.user.username = "admin"
request.COOKIES = ""
request.GET = ""


class TestCollectingViewSet(TestCase):
    def setUp(self):
        self.delete_model()
        celery_app.conf.task_always_eager = True

    def tearDown(self):
        self.delete_model()

    def delete_model(self):
        CollectorPluginMeta.objects.all().delete()
        CollectorPluginInfo.objects.all().delete()
        CollectorPluginConfig.objects.all().delete()
        PluginVersionHistory.objects.all().delete()
        CustomEventItem.objects.all().delete()
        CustomEventGroup.objects.all().delete()
        CollectConfigMeta.objects.all().delete()
        celery_app.conf.task_always_eager = False

    @mock.patch.object(APIResource, "perform_request")
    def test_create_collect(self, mock_api):
        group_info = {
            "bk_biz_id": 2,
            "event_group_id": "456",
            "label": "component",
            "event_group_name": "test_create",
            "bk_data_id": "123",
            "table_id": "2_bkmonitor_plugin",
            "event_info_list": [
                {
                    "event_id": "234",
                    "event_group_id": "111",
                    "event_name": "test_event",
                    "dimension_list": [{"dimension_name": "test_ip"}],
                }
            ],
        }

        def mock_request(*args, **kwargs):
            if "data_name" in args[0]:
                return {"bk_data_id": "123"}
            elif "bk_data_id" in args[0]:
                return group_info
            elif "scope" in args[0]:
                return {"subscription_id": "123456", "task_id": "234567"}

        mock_api.side_effect = mock_request
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "test.json")
        with open(file_path, "r") as fp:
            post_data = json.load(fp)
        local.current_request = request
        content = resource.collecting.save_collect_config.request(post_data)
        self.assert_(content["deployment_id"], DeploymentConfigVersion.objects.last().pk)
