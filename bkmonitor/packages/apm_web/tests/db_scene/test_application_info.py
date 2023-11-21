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

import django
import mock
import pytest
from apm_web.meta.resources import ApplicationInfoResource

pytestmark = pytest.mark.django_db


BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"
APPLICATION_ID = 10


@pytest.mark.django_db
class TestApplicationInfo(django.test.TestCase):
    databases = {
        'default',
        'monitor_api',
    }

    def test_application_info(self):
        """
        正常查询
        """

        request_data = {"application_id": APPLICATION_ID}
        mock.patch("apm_web.meta.resources.ApplicationInfoResource.ResponseSerializer.handle_apdex_config").start()
        mock.patch(
            "apm_web.meta.resources.ApplicationInfoResource.ResponseSerializer.handle_instance_name_config"
        ).start()
        mock.patch("apm_web.meta.resources.ApplicationInfoResource.ResponseSerializer.handle_es_storage_shards").start()
        mock.patch("apm_web.meta.resources.ApplicationInfoResource.ResponseSerializer.handle_sampler_config").start()

        obj = ApplicationInfoResource()

        app = obj.perform_request(request_data)

        res = obj.ResponseSerializer(app).data

        assert res.get("application_db_config") is not None
