"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

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
