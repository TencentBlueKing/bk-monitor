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

from core.drf_resource import api

START_TIME = 1716803600
END_TIME = 1716803660
BCS_CLUSTER_ID = "BCS-K8S-00000"
VALUE = 12.26802232870422


@pytest.fixture
def mock_query_data_by_promql(mocker):
    """mock unify_query。"""
    mocked_data = {
        "series": [
            {
                "name": "_result0",
                "metric_name": "",
                "columns": ["_time", "_value"],
                "types": ["float", "float"],
                "group_keys": ["bcs_cluster_id"],
                "group_values": [BCS_CLUSTER_ID],
                "values": [
                    [START_TIME * 1000, VALUE - 1],  # 实际上这里时间其实会对齐，不过不影响测试
                    [END_TIME * 1000, VALUE],
                ],
            }
        ]
    }
    return mocker.patch(
        "api.unify_query.default.QueryDataByPromqlResource.perform_request",
        return_value=mocked_data,
    )


def test_bulk_fetch_usage_ratios(mock_query_data_by_promql):
    """测试分组查询集群使用率数据。"""
    params = {
        "bk_biz_id": 2,
        "start_time": START_TIME,
        "end_time": END_TIME,
    }
    results = api.kubernetes.bulk_fetch_usage_ratios(params)

    # 验证返回结构
    expected_results = {
        BCS_CLUSTER_ID: {
            "cpu_usage_ratio": round(VALUE, 2),
            "memory_usage_ratio": round(VALUE, 2),
            "disk_usage_ratio": round(VALUE, 2),
        }
    }
    assert results == expected_results
