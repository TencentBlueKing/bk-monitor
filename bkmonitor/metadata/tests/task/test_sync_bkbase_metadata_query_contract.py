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


def _sync_function() -> ast.FunctionDef:
    source_path = Path(__file__).parents[2] / "utils" / "bkbase.py"
    module = ast.parse(source_path.read_text())
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == "sync_bkbase_result_table_meta":
            return node
    raise AssertionError("sync_bkbase_result_table_meta not found")


def _model_filter_keywords(function_node: ast.FunctionDef, model_name: str) -> list[set[str]]:
    filter_keywords = []
    for node in ast.walk(function_node):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "filter"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "objects"
            and isinstance(node.func.value.value, ast.Attribute)
            and node.func.value.value.attr == model_name
        ):
            continue
        filter_keywords.append({keyword.arg for keyword in node.keywords})
    return filter_keywords


def _uses_table_field_values_list(function_node: ast.FunctionDef) -> bool:
    for node in ast.walk(function_node):
        if not (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "values_list"
        ):
            continue
        arg_values = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
        if arg_values[:2] == ["table_id", "field_name"]:
            return True
    return False


def test_sync_bkbase_result_table_meta_limits_existing_table_and_field_queries():
    function_node = _sync_function()

    result_table_filters = _model_filter_keywords(function_node, "ResultTable")
    result_table_field_filters = _model_filter_keywords(function_node, "ResultTableField")

    assert any("table_id__in" in keywords for keywords in result_table_filters)
    assert any({"table_id__in", "field_name__in"}.issubset(keywords) for keywords in result_table_field_filters)
    assert _uses_table_field_values_list(function_node)
