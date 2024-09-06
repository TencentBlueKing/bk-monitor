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

from apm_web.db.resources import ListDbStatisticsResource

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "test_demo"
APP_ALIAS = "test_demo"
DESCRIPTION = "this is demo"
APPLICATION_ID = 10


@pytest.mark.django_db
class TestListDbStatistics(django.test.TestCase):
    databases = {
        'default',
        'monitor_api',
    }

    def test_list_db_statistics(self):
        """
        正常查询
        """

        request_data = {
            "app_name": APP_NAME,
            "filter_params": {"resource.service.name": "bk_monitorv3_web", "attributes.db.system": "redis"},
            "group_by_key": "attributes.db.statement",
            "metric_list": [
                "request_count",
                "avg_duration",
                "error_request_count",
                "slow_request_count",
                "slow_command_rate",
            ],
            "component_instance_id": ["redis::::"],
            "start_time": 1694517684,
            "end_time": 1894521284,
            "filter": "",
            "sort": "",
            "filter_dict": {},
            "page": 1,
            "page_size": 3,
            "keyword": "",
            "condition_list": [],
            "bk_biz_id": BK_BIZ_ID,
        }

        return_value = {
            "took": 48,
            "timed_out": False,
            "_shards": {"total": 6, "successful": 6, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 0, "relation": "eq"}, "max_score": None, "hits": []},
            "aggregations": {
                "attributes.db.statement": {
                    "meta": {},
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [],
                }
            },
        }

        mock.patch("core.drf_resource.api.apm_api.query_es", return_value=return_value).start()

        obj = ListDbStatisticsResource()

        res = obj.perform_request(request_data)

        assert len(res.get("data")) == 0
