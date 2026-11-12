"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock

import pytest

from kernel_api.resource import log_search
from kernel_api.resource.log_search import get_log_unify_query_table

TEST_INDEX_SET_ID = 0
TEST_SIGNATURE = "test-signature"


@pytest.mark.parametrize(
    ("conditions", "query_string", "expected_table"),
    [
        (None, "*", "bklog_index_set_0"),
        (
            {"field_list": [{"field_name": "test_field", "op": "eq", "value": ["test-value"]}]},
            "*",
            "bklog_index_set_0",
        ),
        (
            {"field_list": [{"field_name": "__dist_05", "op": "eq", "value": [TEST_SIGNATURE]}]},
            "*",
            "bklog_index_set_0_clustered",
        ),
        (
            {"field_list": [{"field_name": "__dist_03", "op": "eq", "value": [TEST_SIGNATURE]}]},
            "*",
            "bklog_index_set_0_clustered",
        ),
        (None, f"__dist_05:{TEST_SIGNATURE}", "bklog_index_set_0_clustered"),
    ],
)
def test_get_log_unify_query_table(conditions, query_string, expected_table):
    assert get_log_unify_query_table(TEST_INDEX_SET_ID, conditions, query_string) == expected_table


@pytest.mark.parametrize(
    ("conditions", "dimensions", "has_route", "expected_table"),
    [
        (
            {"field_list": [{"field_name": "signature", "op": "eq", "value": [TEST_SIGNATURE]}]},
            None,
            True,
            "bklog_index_set_0_clustered",
        ),
        (None, ["signature"], True, "bklog_index_set_0_clustered"),
        # 未注册聚类路由时，同名业务字段仍查普通表。
        (None, ["signature"], False, "bklog_index_set_0"),
    ],
)
def test_get_log_unify_query_table_by_signature(monkeypatch, conditions, dimensions, has_route, expected_table):
    has_log_clustered_route = MagicMock(return_value=has_route)
    monkeypatch.setattr(log_search, "has_log_clustered_route", has_log_clustered_route)
    monkeypatch.setattr(log_search, "bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "system")

    assert get_log_unify_query_table(TEST_INDEX_SET_ID, conditions, "*", 2, dimensions) == expected_table
    has_log_clustered_route.assert_called_once_with("system", "0")
