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


@pytest.fixture
def mock_unify_query_data(mocker, request):
    """mock unify_query。"""
    mocked_data = [
        {
            "_result_": value,
            "_time_": 1727712000000,
            "container_name": "default_container",
            "namespace": "default_namespace",
            "pod_name": "default_pod",
        }
        for value in request.param
    ]
    return mocker.patch("bkmonitor.data_source.UnifyQuery.query_data", return_value=mocked_data)


@pytest.mark.parametrize(
    "mock_unify_query_data, expected_length",
    [
        pytest.param([], 0, id="nodata"),
        pytest.param([0.0008446444444444978], 1, id="data"),
    ],
    indirect=["mock_unify_query_data"],
)
def test_fetch_container_usage(mock_unify_query_data, expected_length):
    """测试返回结构。"""
    params = {
        "bk_biz_id": 2,
        "bcs_cluster_id": "BCS-K8S-00000",
        "group_by": ["namespace", "pod_name", "container_name"],
        "usage_type": "cpu",
    }
    result = api.kubernetes.fetch_container_usage(params)

    assert result["usage_type"] == "cpu"
    assert len(result["data"]) == expected_length
