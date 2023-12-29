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
from prometheus_client import REGISTRY

from api.cmdb.define import Business
from monitor_web.statistics.v2.host import HostCollector


class TestHostReportCount:
    """测试 host_report_count 收集方法。"""

    EXPECTED_MAX_TIME_SERIES_VALUE = 8
    EXPECTED_RUNNING_COUNT = 10

    @pytest.fixture(scope="class")
    def unify_query(self, class_mocker):
        """模拟 unify_query 查询 system.cpu_summary。"""
        mocked_time_series_data = {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "group_keys": ["bk_biz_id", "bk_cloud_id"],
                    "group_values": ["2", "0"],
                    "metric_name": "",
                    "name": "_result0",
                    "types": ["float", "float"],
                    "values": [[1704179460000, self.EXPECTED_MAX_TIME_SERIES_VALUE]],
                },
                {
                    "columns": ["_time", "_value"],
                    "group_keys": ["bk_biz_id", "bk_cloud_id"],
                    "group_values": ["2", "0"],
                    "metric_name": "",
                    "name": "_result1",
                    "types": ["float", "float"],
                    "values": [[1704179520000, self.EXPECTED_MAX_TIME_SERIES_VALUE - 1]],
                },
            ]
        }
        class_mocker.patch(
            "api.unify_query.default.QueryDataResource.perform_request",
            return_value=mocked_time_series_data,
        )

    @pytest.fixture(scope="class")
    def businesses(self, class_mocker):
        """模拟 cmdb 查询业务。"""
        mocked_businesses = [
            Business(bk_biz_id=2, bk_biz_name="蓝鲸"),
        ]
        class_mocker.patch(
            "api.cmdb.default.GetBusiness.perform_request",
            return_value=mocked_businesses,
        )

    @pytest.fixture(scope="class")
    def clouds(self, class_mocker):
        """模拟 cmdb 查询云区域。"""
        mocked_clouds = [{"bk_cloud_id": 0, "bk_cloud_name": "default area"}]
        class_mocker.patch(
            "api.cmdb.default.SearchCloudArea.perform_request",
            return_value=mocked_clouds,
        )

    @pytest.fixture(scope="class")
    def nodeman_collector_stats(self, class_mocker):
        """模拟 HostCollector 查询节点管理数据库中采集器数据。"""
        mocked_collector_stats = [
            {
                "bk_biz_id": 2,
                "count": self.EXPECTED_RUNNING_COUNT,
                "bk_cloud_id": 0,
                "status": "RUNNING",
                "name": "bkmonitorbeat",
            },
            {"bk_biz_id": 2, "count": 1, "bk_cloud_id": 0, "status": "TERMINATED", "name": "bkmonitorbeat"},
        ]
        class_mocker.patch(
            "monitor_web.statistics.v2.host.HostCollector.biz_monitor_collector_status_list",
            new_callable=class_mocker.PropertyMock,
            return_value=mocked_collector_stats,
        )

    @pytest.fixture(scope="class")
    def collect(self, unify_query, businesses, clouds, nodeman_collector_stats):
        return HostCollector().host_report_count()

    def test_normal_metric(self, collect):
        """测试正常指标值。"""
        actual_value = REGISTRY.get_sample_value(
            "host_report_count",
            {
                "bk_biz_id": "2",
                "bk_biz_name": "蓝鲸",
                "data_status": "NORMAL",
                "target_cloud_id": "0",
                "target_cloud_name": "default area",
            },
        )
        assert actual_value == self.EXPECTED_MAX_TIME_SERIES_VALUE

    def test_no_data_metric(self, collect):
        """测试无数据指标值。"""
        actual_value = REGISTRY.get_sample_value(
            "host_report_count",
            {
                "bk_biz_id": "2",
                "bk_biz_name": "蓝鲸",
                "data_status": "NO_DATA_REPORT",
                "target_cloud_id": "0",
                "target_cloud_name": "default area",
            },
        )
        assert actual_value == self.EXPECTED_RUNNING_COUNT - self.EXPECTED_MAX_TIME_SERIES_VALUE
