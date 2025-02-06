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

from metadata.models.record_rule import utils

from ...models.record_rule.utils import generate_pre_cal_table_id
from .conftest import SPACE_ID, SPACE_TYPE


@pytest.mark.parametrize(
    "table_id, expected",
    [
        ("test.demo", f"bkmonitor_{SPACE_TYPE}_{SPACE_ID}_test_demo.__default__"),
        ("test", f"bkmonitor_{SPACE_TYPE}_{SPACE_ID}_test.__default__"),
        ("test/test1/test2", f"bkmonitor_{SPACE_TYPE}_{SPACE_ID}_test_test1_test2.__default__"),
        ("test/test1-test2", f"bkmonitor_{SPACE_TYPE}_{SPACE_ID}_test_test1_test2.__default__"),
    ],
)
def test_generate_table_id(table_id, expected):
    assert utils.generate_table_id(SPACE_TYPE, SPACE_ID, table_id) == expected


@pytest.mark.parametrize(
    "src, dst",
    [
        ("test:test1:test2", "test_test1_test2"),
        ("test:test1:", "test_test1"),
        (":test:", "test"),
    ],
)
def test_transform_record_to_metric_name(src, dst):
    assert utils.transform_record_to_metric_name(src) == dst


def test_refine_bk_sql_and_metrics(mocker):
    promql = "max_over_time(mem_usage_avg:1h[1d])"
    all_rule_record = ["mem_usage_max_avg_1d", "mem_usage_max_avg:1h"]

    # mocker promql to struct
    mocker.patch(
        "core.drf_resource.api.unify_query.promql_to_struct",
        return_value={
            "data": {
                "query_list": [
                    {
                        "data_source": "bkmonitor",
                        "field_name": "mem_usage_avg_1h",
                        "is_regexp": False,
                        "function": None,
                        "time_aggregation": {"function": "max_over_time", "window": "24h0m0s", "node_index": 2},
                        "reference_name": "a",
                        "conditions": {},
                    }
                ],
                "metric_merge": "a",
                "instant": False,
            }
        },
    )

    # mocker struct to promql
    mocker.patch(
        "core.drf_resource.api.unify_query.struct_to_promql",
        return_value={
            "promql": "max_over_time(mem_usage_avg_1h[1d])",
            "start": "",
            "end": "",
            "step": "",
            "bk_biz_ids": None,
            "look_back_delta": "",
            "instant": False,
        },
    )
    data = utils.refine_bk_sql_and_metrics(promql, all_rule_record)

    # 校验数据
    assert data["promql"] == "max_over_time(mem_usage_avg_1h[1d])"
    assert data["metrics"] == {"mem_usage_avg_1h"}


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_generate_pre_cal_table_id():
    """
    测试 generate_pre_cal_table_id 的各种实际输入场景
    """
    # Case 1: 正常输入
    space_type = "bkcc"
    space_id = "12345"
    record_name = "cpu_usage"
    expected = "bkprecal_bkcc_12345_cpu_usage.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    # Case 2: space_type 为 bksaas，含有合法的 record_name
    space_type = "bksaas"
    space_id = "67890"
    record_name = "memory_usage"
    expected = "bkprecal_bksaas_67890_memory_usage.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    # Case 3: record_name 含非法字符，需替换为下划线
    space_type = "bkci"
    space_id = "54321"
    record_name = "http.requests-total"
    expected = "bkprecal_bkci_54321_http_requests_total.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    # Case 4: record_name 含多种非法字符，且有连续非法字符
    space_type = "bkci"
    space_id = "67890"
    record_name = "http-requests//total.usage"
    expected = "bkprecal_bkci_67890_http_requests_total_usage.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    # Case 5: 超长 record_name，需截断
    space_type = "bksaas"
    space_id = "12345"
    record_name = "a" * 120  # 长度超过 110
    truncated_record_name = "a" * (110 - len("bkprecal_bksaas_12345_"))
    expected = f"bkprecal_bksaas_12345_{truncated_record_name}.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    # Case 6: space_id 为非标字符串，验证正常处理
    space_type = "bkci"
    space_id = "game-test"
    record_name = "disk_io"
    expected = "bkprecal_bkci_game_test_disk_io.__default__"
    assert generate_pre_cal_table_id(space_type, space_id, record_name) == expected

    print("All tests passed!")
