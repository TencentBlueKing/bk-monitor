"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import django
import pytest

from apm_web.db.resources import ListDbSystemResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"
APPLICATION_ID = 10


@pytest.mark.django_db(databases="__all__")
class TestListDbSystem(django.test.TestCase):
    databases = {
        "default",
        "monitor_api",
    }

    def test_list_db_system(self):
        """
        正常查询
        """

        request_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "group_by_key": "attributes.db.system"}

        return_value = {
            "took": 58,
            "timed_out": False,
            "_shards": {"total": 6, "successful": 6, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 10000, "relation": "gte"}, "max_score": None, "hits": []},
            "aggregations": {
                "attributes.db.system": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {"key": "mysql", "doc_count": 200761},
                        {"key": "elasticsearch", "doc_count": 6777},
                        {"key": "redis", "doc_count": 9},
                    ],
                }
            },
        }
        mock.patch("core.drf_resource.api.apm_api.query_es", return_value=return_value).start()

        obj = ListDbSystemResource()

        res = obj.perform_request(request_data)

        assert len(res) == 3
