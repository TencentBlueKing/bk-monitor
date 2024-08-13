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

from apm_web.db.resources import ListDbSpanResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"
APPLICATION_ID = 10

DB_SPAN_RES = {
    "total": 122508,
    "data": [
        {
            "span_name": "UPDATE",
            "parent_span_id": "f4ccfc345d0d80f4",
            "trace_id": "15c723bb38d08e91fd487b584efee331",
            "trace_state": "",
            "resource": {
                "telemetry.sdk.language": "python",
                "service.name": "bk_monitorv3_web",
                "bk.instance.id": "python::bk_monitorv3_web",
                "telemetry.sdk.version": "1.11.1",
                "net.host.ip": "127.0.0.1",
                "telemetry.sdk.name": "opentelemetry",
            },
            "span_id": "c641562a2b345b3e",
            "kind": 3,
            "end_time": 1698222288420775,
            "start_time": 1698222288418423,
            "elapsed_time": 2352,
            "attributes": {
                "net.peer.port": 3306,
                "db.statement": "UPDATE `session` SET `session_data` = %s WHERE `session`.`session_key` = %s",
                "db.system": "mysql",
                "apdex_type": "satisfied",
                "db.name": "",
            },
            "time": "1698222292000",
            "status": {"code": 0, "message": ""},
        },
        {
            "span_name": "UPDATE",
            "parent_span_id": "38abe905ce431a36",
            "trace_id": "15c723bb38d08e91fd487b584efee331",
            "trace_state": "",
            "resource": {
                "telemetry.sdk.language": "python",
                "bk.instance.id": "python::bk_monitorv3_web",
                "service.name": "bk_monitorv3_web",
                "telemetry.sdk.version": "1.11.1",
                "net.host.ip": "127.0.0.1",
                "telemetry.sdk.name": "opentelemetry",
            },
            "span_id": "2937dc464f049d36",
            "kind": 3,
            "end_time": 1698222288405198,
            "start_time": 1698222288402821,
            "elapsed_time": 2377,
            "attributes": {
                "net.peer.port": 3306,
                "db.statement": "UPDATE `django_cache` SET `value` = %s, `expires` = %s WHERE `cache_key` = %s",
                "db.system": "mysql",
                "apdex_type": "satisfied",
                "db.name": "",
            },
            "time": "1698222292000",
            "status": {"code": 0, "message": ""},
        },
        {
            "parent_span_id": "38abe905ce431a36",
            "span_name": "SELECT",
            "trace_id": "15c723bb38d08e91fd487b584efee331",
            "trace_state": "",
            "span_id": "86664bcf45e3aea5",
            "resource": {
                "telemetry.sdk.language": "python",
                "service.name": "bk_monitorv3_web",
                "bk.instance.id": "python::bk_monitorv3_web",
                "telemetry.sdk.version": "1.11.1",
                "net.host.ip": "127.0.0.1",
                "telemetry.sdk.name": "opentelemetry",
            },
            "kind": 3,
            "end_time": 1698222288398049,
            "start_time": 1698222288395145,
            "elapsed_time": 2903,
            "attributes": {
                "net.peer.port": 3306,
                "db.statement": "SELECT COUNT(*) FROM `django_cache`",
                "db.system": "mysql",
                "apdex_type": "satisfied",
                "db.name": "",
            },
            "time": "1698222292000",
            "status": {"code": 0, "message": ""},
        },
    ],
}


@pytest.mark.django_db
class TestListDbSpan(django.test.TestCase):
    databases = {
        'default',
        'monitor_api',
    }

    def test_list_db_span(self):
        """
        正常查询
        """

        request_data = {
            "app_name": "apm_demo",
            "filter_params": {"resource.service.name": "bk_monitorv3_web", "attributes.db.system": "mysql"},
            "component_instance_id": ["mysql::::"],
            "start_time": 1694517684,
            "end_time": 1894521284,
            "filter": "",
            "sort": "",
            "filter_dict": {},
            "check_filter_dict": {},
            "page": 1,
            "page_size": 3,
            "keyword": "",
            "condition_list": [],
            "bk_biz_id": 2,
        }

        mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=DB_SPAN_RES).start()

        obj = ListDbSpanResource()

        res = obj.perform_request(request_data)

        assert len(res.get("data")) > 0
