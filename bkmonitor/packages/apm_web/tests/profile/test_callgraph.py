"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import errno
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

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


def make_completed_process(stdout):
    return subprocess.CompletedProcess(args=["dot", "-Tsvg"], returncode=0, stdout=stdout)


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
        patch.object(callgraph.subprocess, "run") as run,
        pytest.raises(CustomException, match="请缩小查询时间范围") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    run.assert_not_called()


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

    with patch.object(
        callgraph.subprocess,
        "run",
        return_value=make_completed_process(b"<svg><title>callgraph</title><text>ok</text></svg>"),
    ) as run:
        result = callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    run.assert_called_once()
    assert run.call_args.args[0] == [callgraph.DOT_BINARY, "-Tsvg"]
    assert run.call_args.kwargs["timeout"] == callgraph.CALLGRAPH_RENDER_TIMEOUT_SECONDS
    assert result["call_graph_data"] == "<svg><text>ok</text></svg>"


def test_generate_svg_data_uses_bounded_layout_and_edge_xlabel():
    tree = SimpleNamespace(function_node_map={"a": SimpleNamespace(name="a"), "b": SimpleNamespace(name="b")})
    data = {
        "call_graph_data": {
            "call_graph_nodes": [
                {"id": "a", "name": "a", "value": 10, "self": 5},
                {"id": "b", "name": "b", "value": 5, "self": 5},
            ],
            "call_graph_relation": [{"source_id": "a", "target_id": "b", "value": 5}],
        },
        "call_graph_all": 10,
    }

    with patch.object(callgraph.subprocess, "run", return_value=make_completed_process(b"<svg></svg>")) as run:
        callgraph.generate_svg_data(tree, data, unit="nanoseconds")

    source = run.call_args.kwargs["input"].decode("utf-8")
    assert "graph [mclimit=0.3 nslimit=0.5 nslimit1=2]" in source
    assert "a -> b [color=" in source
    assert "xlabel=" in source
    assert " label=" not in source.split("a -> b", 1)[1]


def test_generate_svg_data_converts_timeout_to_readable_error():
    original_error = subprocess.TimeoutExpired(["dot", "-Tsvg"], callgraph.CALLGRAPH_RENDER_TIMEOUT_SECONDS)

    with (
        patch.object(callgraph.subprocess, "run", side_effect=original_error),
        pytest.raises(CustomException, match="调用图包含的函数或调用关系过多") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    assert exc_info.value.__cause__ is original_error


def test_generate_svg_data_converts_broken_pipe_to_readable_error():
    original_error = BrokenPipeError(32, "Broken pipe")

    with (
        patch.object(callgraph.subprocess, "run", side_effect=original_error),
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
    original_error = subprocess.CalledProcessError(1, ["dot", "-Tsvg"], stderr=b"killed")

    with (
        patch.object(callgraph.subprocess, "run", side_effect=original_error),
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
    original_error = FileNotFoundError(errno.ENOENT, "No such file or directory", "dot")

    with (
        patch.object(callgraph.subprocess, "run", side_effect=original_error),
        pytest.raises(CustomException, match="调用图渲染服务暂不可用") as exc_info,
    ):
        callgraph.generate_svg_data(
            SimpleNamespace(function_node_map={}),
            make_callgraph_data(),
            unit="nanoseconds",
        )

    assert exc_info.value.code == CustomException.code
    assert exc_info.value.__cause__ is original_error
