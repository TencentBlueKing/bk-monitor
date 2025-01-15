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
