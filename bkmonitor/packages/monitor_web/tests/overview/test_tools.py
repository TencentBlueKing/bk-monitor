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

from monitor_web.overview.tools import MonitorStatus, OsMonitorInfo


class TestOsMonitorInfo:
    """测试 TestOsMonitorInfo。"""

    @pytest.fixture
    def unify_query(self, mocker):
        """模拟 unify_query 查询。"""
        mocked_time_series_data = {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "group_keys": [],
                    "group_values": [],
                    "metric_name": "",
                    "name": "_result0",
                    "types": ["float", "float"],
                    "values": [[1704707100000, 32]],
                }
            ]
        }

        mocker.patch(
            "api.unify_query.default.QueryDataByPromqlResource.perform_request",
            return_value=mocked_time_series_data,
        )

    def test_normal_status(self, unify_query):
        """测试正常状态。"""
        os_info = OsMonitorInfo(bk_biz_id=2, alerts=[])
        assert os_info.status == MonitorStatus.NORMAL
