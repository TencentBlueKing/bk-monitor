# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import math
from unittest.mock import sentinel

import pytest

from core.drf_resource import api


class TestBatchQueryTimeSeriesGroups:
    LIMIT = 500

    @pytest.fixture
    def mock_single_query(self, mocker, request):
        """mock 单个查询。根据 page 返回不同数量的查询结果。"""
        time_series_group_count = request.param

        def _mocked_response(params):
            remaining = time_series_group_count - (params["page"] - 1) * self.LIMIT
            return_count = min(remaining, self.LIMIT)
            return {
                "count": time_series_group_count,
                "info": [sentinel.some_dict] * return_count,
            }

        return mocker.patch(
            "api.metadata.default.SingleQueryTimeSeriesGroupResource.perform_request",
            side_effect=_mocked_response,
        )

    @pytest.mark.parametrize(
        'mock_single_query, expected_count',
        [
            (0, 0),
            (300, 300),
            (1000, 1000),
            (1500, 1500),
        ],
        indirect=['mock_single_query'],
    )
    def test_batch_query(self, mock_single_query, expected_count):
        """测试批量查询。"""
        groups = api.metadata.query_time_series_group()
        expected_call_count = math.ceil(expected_count / self.LIMIT) + 1  # 额外的一次请求以计算 count
        actual_call_count = mock_single_query.call_count

        assert actual_call_count == expected_call_count
        assert len(groups) == expected_count
        # 测试返回的第一个组是否符合预期的结构
        if groups:
            assert groups[0] is sentinel.some_dict
