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

import pytest

from monitor_web.statistics.v2.business import BusinessCollector


class TestBusinessCollector:
    """测试 BusinessCollector 收集方法。"""

    @pytest.fixture
    def unify_query(self, mocker):
        """模拟 unify_query 查询。"""
        mocked_time_series_data = {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "group_keys": ["bk_biz_id"],
                    "group_values": ["2"],
                    "metric_name": "",
                    "name": "_result0",
                    "types": ["float", "float"],
                    "values": [[1704179460000, 2]],
                },
                {
                    "columns": ["_time", "_value"],
                    "group_keys": ["bk_biz_id"],
                    "group_values": ["2"],
                    "metric_name": "",
                    "name": "_result1",
                    "types": ["float", "float"],
                    "values": [[1704179520000, 2]],
                },
            ]
        }
        mocker.patch(
            "api.unify_query.default.QueryDataResource.perform_request",
            return_value=mocked_time_series_data,
        )

    def test_host_biz_count(self, unify_query):
        """测试主机的业务数量指标。"""
        assert BusinessCollector().host_biz_count == 1

    def test_process_biz_count(self, unify_query):
        """测试进程的业务数量指标。"""
        assert BusinessCollector().process_biz_count == 1
