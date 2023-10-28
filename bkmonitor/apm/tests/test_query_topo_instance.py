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
from apm.models import TopoInstance
from apm.resources import QueryTopoInstanceResource

pytestmark = pytest.mark.django_db


BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"


@pytest.mark.django_db
class TestTopoInstance(django.test.TestCase):
    databases = {
        'default',
        'monitor_api',
    }

    def setUp(self):

        need_create_instances = {
            ("demo", "mysql:::3306", "component", "db", "mysql", "opentelemetry", "1.11.1", "python"),
            ("demo01", "es:::", "component", "db", "es", "opentelemetry", "1.11.1", "python"),
            ("demo02", "python:demo02::127.0.0.1:", "service", None, None, "opentelemetry", "1.11.1", "python"),
            ("demo03", "python::demo03", "service", None, None, "opentelemetry", "1.11.1", "python"),
        }

        TopoInstance.objects.bulk_create(
            [
                TopoInstance(
                    bk_biz_id=BK_BIZ_ID,
                    app_name=APP_NAME,
                    topo_node_key=i[0],
                    instance_id=i[1],
                    instance_topo_kind=i[2],
                    component_instance_category=i[3],
                    component_instance_predicate_value=i[4],
                    sdk_name=i[5],
                    sdk_version=i[6],
                    sdk_language=i[7],
                )
                for i in need_create_instances
            ]
        )

    def test_query_topo_instance(self):
        """
        正常查询
        """

        request_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "filters": {}, "service_name": []}

        mock.patch(
            "apm.core.handlers.discover_handler.DiscoverHandler.get_retention_utc_filter_params",
            return_value={"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME},
        ).start()

        mock.patch("apm.core.handlers.instance_handlers.InstanceHandler.get_cache_data", return_value={}).start()

        obj = QueryTopoInstanceResource()

        res = obj.perform_request(request_data)

        assert res["total"] == len(res["data"])

    def test_query_topo_instance_sort(self):
        """
        排序测试
        """

        request_data = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "filters": {},
            "service_name": [],
            "sort": "-updated_at",
        }

        mock.patch(
            "apm.core.handlers.discover_handler.DiscoverHandler.get_retention_utc_filter_params",
            return_value={"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME},
        ).start()

        mock.patch("apm.core.handlers.instance_handlers.InstanceHandler.get_cache_data", return_value={}).start()

        obj = QueryTopoInstanceResource()

        res = obj.perform_request(request_data)

        len(res["data"]) == 4

    def test_query_topo_instance_page(self):
        """
        分页测试
        """

        request_data = {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "filters": {},
            "service_name": [],
            "page": 1,
            "page_size": 2,
        }

        mock.patch(
            "apm.core.handlers.discover_handler.DiscoverHandler.get_retention_utc_filter_params",
            return_value={"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME},
        ).start()

        mock.patch("apm.core.handlers.instance_handlers.InstanceHandler.get_cache_data", return_value={}).start()

        obj = QueryTopoInstanceResource()

        res = obj.perform_request(request_data)

        assert res["total"] == 4

        assert len(res["data"]) == 2
