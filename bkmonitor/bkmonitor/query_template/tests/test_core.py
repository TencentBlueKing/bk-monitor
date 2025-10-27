"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import Any

import pytest

from .. import core, mock_data


def _sorted_repr(item: Any) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def canonicalize(obj: Any):
    def _walk(node: Any, path: tuple[str, ...]):
        if isinstance(node, dict):
            return {k: _walk(v, path + (k,)) for k, v in node.items()}
        if isinstance(node, list):
            new_list = [_walk(v, path) for v in node]
            return sorted(new_list, key=_sorted_repr)

        return node

    return _walk(obj, ())


class TestQueryTemplateWrapper:
    @pytest.mark.parametrize(
        "template,expect,context",
        [
            [mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE, mock_data.CALLEE_SUCCESS_RATE_QUERY_INSTANCE, {}],
            [
                mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE,
                {
                    "bk_biz_id": 0,
                    "alias": "被调成功率（%）",
                    "name": "apm_rpc_callee_success_rate",
                    "namespace": "default",
                    "description": "",
                    "query_configs": [
                        {
                            "table": "APM.__default__",
                            "data_label": "APM",
                            "data_type_label": "time_series",
                            "data_source_label": "custom",
                            "interval": 60,
                            "promql": "",
                            "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
                            "where": [{"key": "code_type", "value": ["success"], "method": "eq"}],
                            "functions": [],
                            "group_by": ["service_name", "callee_service", "callee_method"],
                            "query_string": "*",
                        },
                        {
                            "table": "APM.__default__",
                            "data_label": "APM",
                            "data_type_label": "time_series",
                            "data_source_label": "custom",
                            "interval": 60,
                            "promql": "",
                            "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "b"}],
                            "where": [],
                            "functions": [],
                            "group_by": ["service_name", "callee_service", "callee_method"],
                            "query_string": "*",
                        },
                    ],
                    "expression": "(a or b < bool 0) / (b > 10) * 100",
                    "space_scope": [],
                    "functions": [{"id": "round", "params": []}],
                    "unit": "percent",
                },
                {
                    "FUNCTIONS": [],
                    "CONDITIONS": [],
                    "GROUP_BY": ["service_name", "callee_service", "callee_method"],
                    "ALARM_THRESHOLD_VALUE": 10,
                    "EXPRESSION_FUNCTIONS": [{"id": "round", "params": []}],
                },
            ],
            [
                mock_data.CALLEE_P99_QUERY_TEMPLATE,
                {
                    "bk_biz_id": 0,
                    "alias": "被调 P99 耗时（ms）",
                    "name": "apm_rpc_callee_p99",
                    "namespace": "default",
                    "description": "",
                    "expression": "(b > bool 0) * a * 1000",
                    "functions": [],
                    "query_configs": [
                        {
                            "data_label": "APM",
                            "data_source_label": "custom",
                            "data_type_label": "time_series",
                            "functions": [
                                {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.99}]},
                                {"id": "increase", "params": [{"id": "window", "value": "1m"}]},
                            ],
                            "group_by": ["callee_method", "le", "service_name"],
                            "interval": 60,
                            "metric_id": "custom.APM.__default__.rpc_server_handled_seconds_bucket",
                            "metrics": [{"alias": "a", "field": "rpc_server_handled_seconds_bucket", "method": "SUM"}],
                            "promql": "",
                            "table": "APM.__default__",
                            "where": [{"key": "rpc_system", "method": "eq", "value": [""]}],
                            "query_string": "*",
                        },
                        {
                            "data_label": "APM",
                            "data_source_label": "custom",
                            "data_type_label": "time_series",
                            "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                            "functions": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
                            "group_by": ["callee_method", "service_name"],
                            "interval": 60,
                            "metrics": [{"alias": "b", "field": "rpc_server_handled_total", "method": "SUM"}],
                            "promql": "",
                            "table": "APM.__default__",
                            "where": [
                                {"key": "code_type", "method": "eq", "value": ["success"]},
                                {"key": "rpc_system", "method": "eq", "value": [""]},
                            ],
                            "query_string": "*",
                        },
                    ],
                    "space_scope": [],
                    "unit": "ms",
                },
                {},
            ],
        ],
    )
    def test_render(self, template: dict[str, Any], expect: dict[str, Any], context: dict[str, Any]):
        w: core.QueryTemplateWrapper = core.QueryTemplateWrapper.from_dict(template)
        assert canonicalize(w.render(context)) == canonicalize(expect)
