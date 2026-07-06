"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import ast
from pathlib import Path


def _find_monitor_metric_count() -> ast.FunctionDef:
    source_path = Path(__file__).parents[2] / "statistics" / "v2" / "monitor_metric.py"
    module = ast.parse(source_path.read_text())
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == "monitor_metric_count":
            return node
    raise AssertionError("monitor_metric_count not found")


def _call_chain(node: ast.AST) -> list[ast.Call]:
    calls = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        calls.append(node)
        node = node.func.value
    return list(reversed(calls))


def test_monitor_metric_count_filters_valid_businesses_before_grouping():
    function_node = _find_monitor_metric_count()
    monitor_metrics_assign = next(
        node
        for node in ast.walk(function_node)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "monitor_metrics" for target in node.targets)
    )
    calls = _call_chain(monitor_metrics_assign.value)
    call_names = [call.func.attr for call in calls]
    filter_call = calls[call_names.index("filter")]

    assert any(keyword.arg == "bk_biz_id__in" for keyword in filter_call.keywords)
    assert call_names.index("filter") < call_names.index("values")
