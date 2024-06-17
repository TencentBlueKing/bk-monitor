# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging

from apm.core.discover.base import TopoHandler
from apm.utils.base import divide_biscuit

logger = logging.getLogger(__name__)


class TestTopoHandler:
    def test_calc_round_trace_count(self):
        test_cases = [
            {"all_span_count": 5000, "initial_per_trace_size": 1, "expect": 20},
            {"all_span_count": 12002, "initial_per_trace_size": 1, "expect": 8},
            {"all_span_count": 100, "initial_per_trace_size": 1, "expect": 100},
            {"all_span_count": 1000, "initial_per_trace_size": 1, "expect": 100},
            {"all_span_count": 3102, "initial_per_trace_size": 1, "expect": 32},
            {"all_span_count": 5000, "initial_per_trace_size": 10, "expect": 2},
            {"all_span_count": 12002, "initial_per_trace_size": 10, "expect": 1},
            {"all_span_count": 100, "initial_per_trace_size": 10, "expect": 100},
            {"all_span_count": 1000, "initial_per_trace_size": 10, "expect": 10},
            {"all_span_count": 3102, "initial_per_trace_size": 10, "expect": 3},
        ]

        for i in test_cases:
            get_spans_params = [
                (i, 10000, "") for i in divide_biscuit([i for i in range(100)], i["initial_per_trace_size"])
            ]
            avg_group_span_count = i["all_span_count"] / len(get_spans_params)
            per_trace_size = TopoHandler.calculate_round_count(avg_group_span_count)

            logger.info(
                f"initial_per_trace_size: {i['initial_per_trace_size']} "
                f"all_span_count: {i['all_span_count']} "
                f"avg_span_count: {avg_group_span_count} "
                f"change per_trace_size to: {per_trace_size}"
            )

            assert per_trace_size == i["expect"]
