"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from graphviz import Digraph
from graphviz.backend import CalledProcessError, ExecutableNotFound

from django.utils.translation import override

from apm_web.profile.diagrams import callgraph
from core.drf_resource.exceptions import CustomException, custom_exception_handler


def make_callgraph_data(node_count=0, edge_count=0):
    return {
        "call_graph_data": {
            "call_graph_nodes": [{}] * node_count,
            "call_graph_relation": [{}] * edge_count,
        },
        "call_graph_all": 0,
    }


def test_call_graph_size_limits_are_inclusive():
    callgraph._validate_call_graph_size(
        callgraph.CALLGRAPH_MAX_NODES,
        callgraph.CALLGRAPH_MAX_EDGES,
        callgraph.CALLGRAPH_MAX_DOT_BYTES,
    )


@pytest.mark.parametrize(
    ("node_count", "edge_count"),
    [
        (callgraph.CALLGRAPH_MAX_NODES + 1, 0),
        (0, callgraph.CALLGRAPH_MAX_EDGES + 1),
    ],
)
def test_generate_svg_data_rejects_oversized_graph_before_building_dot(node_count, edge_count):
    with (
        patch.object(callgraph, "Digraph") as digraph,
        pytest.raises(CustomException, match="请缩小查询时间范围") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(node_count=node_count, edge_count=edge_count),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    digraph.assert_not_called()


def test_generate_svg_data_rejects_oversized_dot_before_rendering(monkeypatch):
    monkeypatch.setattr(callgraph, "CALLGRAPH_MAX_DOT_BYTES", 1)

    with (
        patch.object(Digraph, "pipe") as pipe,
        pytest.raises(CustomException, match="请缩小查询时间范围") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    pipe.assert_not_called()


def test_generate_svg_data_returns_translated_oversized_error(monkeypatch):
    monkeypatch.setattr(callgraph, "CALLGRAPH_MAX_NODES", 0)

    with (
        override("en"),
        pytest.raises(CustomException, match="The call graph contains too many functions") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(node_count=1),
            unit="nanoseconds",
        )

    assert str(exc_info.value).startswith("Custom exception:")


def test_generate_svg_data_allows_values_at_limit(monkeypatch):
    monkeypatch.setattr(callgraph, "CALLGRAPH_MAX_NODES", 0)
    monkeypatch.setattr(callgraph, "CALLGRAPH_MAX_EDGES", 0)
    monkeypatch.setattr(callgraph, "CALLGRAPH_MAX_DOT_BYTES", 1024)

    with patch.object(Digraph, "pipe", return_value=b"<svg><title>callgraph</title><text>ok</text></svg>") as pipe:
        result = callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    pipe.assert_called_once_with(format="svg")
    assert result["call_graph_data"] == "<svg><text>ok</text></svg>"


def test_generate_svg_data_converts_broken_pipe_to_readable_error():
    original_error = BrokenPipeError(32, "Broken pipe")

    with (
        patch.object(Digraph, "pipe", side_effect=original_error),
        pytest.raises(CustomException, match="调用图生成失败") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    assert exc_info.value.__cause__ is original_error
    assert custom_exception_handler(exc_info.value, {}).data["code"] == 3300002


def test_generate_svg_data_converts_nonzero_graphviz_exit_to_readable_error():
    original_error = CalledProcessError(1, ["dot"], stderr=b"killed")

    with (
        patch.object(Digraph, "pipe", side_effect=original_error),
        pytest.raises(CustomException, match="调用图生成失败") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    assert exc_info.value.__cause__ is original_error


def test_generate_svg_data_reports_missing_graphviz_executable():
    original_error = ExecutableNotFound(["dot"])

    with (
        patch.object(Digraph, "pipe", side_effect=original_error),
        pytest.raises(CustomException, match="调用图渲染服务暂不可用") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    assert exc_info.value.__cause__ is original_error
