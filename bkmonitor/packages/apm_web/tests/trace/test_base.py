import signal
import sys

import pytest

from apm_web.trace.diagram.base import SpanNode, TraceTree

from .utils import (
    dynamic_make_trace_list,
    make_a_very_deep_trace,
    make_a_very_wide_roots_trace,
    make_a_very_wide_trace,
    read_trace_list,
)


class TestSpanNode:
    """Test Span Node"""

    def test_span_node_from_raw(self, default_trace_tree_config):
        """test span node from raw"""
        for span_info in read_trace_list():
            span_node = SpanNode.from_raw(span_info, default_trace_tree_config)

            assert span_node.service_name == span_info["resource"]["service.name"]


class Timeout:
    def __init__(self, seconds=1, error_message="Timeout"):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def span_node_strictly_increasing(nodes: list):
    return all(x.index_refer < y.index_refer for x, y in zip(nodes, nodes[1:]))


class TestTraceTree:
    """Test Trace Tree"""

    def assert_wide_tree(self, width: int, wide_trace: list, wide_tree: TraceTree):
        assert len(wide_tree.nodes_map) == len(wide_trace)
        assert len(wide_tree.roots[0].children) == width
        assert wide_tree.roots[0].children[0].id == "span1"
        assert span_node_strictly_increasing(wide_tree.roots[0].children)

    def test_create_very_wide_tree(self, group_and_parallel_trace_tree_config):
        """test create very wide tree"""
        width = 10000
        wide_trace = make_a_very_wide_trace(width)
        with Timeout(seconds=1):
            wide_tree = TraceTree.from_raw(wide_trace, group_and_parallel_trace_tree_config)

        self.assert_wide_tree(width, wide_trace, wide_tree)

    def test_create_very_wide_reverse_tree(self, group_and_parallel_trace_tree_config):
        """test create very wide reverse tree"""
        width = 10000
        wide_trace = make_a_very_wide_trace(width, reverse=True)
        with Timeout(seconds=10):
            # sometimes the order of the trace is not sure, force to sort by start time will speed up the building
            wide_tree = TraceTree.from_raw(wide_trace, group_and_parallel_trace_tree_config, force_sort=True)

        self.assert_wide_tree(width, wide_trace, wide_tree)

    def test_create_very_wide_reverse_virtual_return_tree(self, group_and_parallel_virtual_return_trace_tree_config):
        """test create very wide reverse and including virtual return tree"""
        width = 100
        wide_trace = make_a_very_wide_trace(width, reverse=True)
        with Timeout(seconds=1):
            # sometimes the order of the trace is not sure, force to sort by start time will speed up the building
            wide_tree = TraceTree.from_raw(
                wide_trace, group_and_parallel_virtual_return_trace_tree_config, force_sort=True
            )

        assert len(wide_tree.nodes_map) == len(wide_trace)
        # no parallel
        assert len(wide_tree.roots[0].children) == 2 * width
        assert wide_tree.roots[0].children[0].id == "span1"
        assert wide_tree.roots[0].children[1].id == "span1"
        assert wide_tree.roots[0].children[2 * width - 1].id == f"span{width}"
        assert wide_tree.roots[0].children[2 * width - 2].id == f"span{width}"

        # parallel may slow down the building with virtual return detection
        with Timeout(seconds=1):
            parallel_wide_tree = TraceTree.from_raw(
                make_a_very_wide_trace(width, reverse=True, parallel=True),
                group_and_parallel_virtual_return_trace_tree_config,
                force_sort=True,
            )

        assert span_node_strictly_increasing(parallel_wide_tree.roots[0].children)

    def test_create_very_wide_roots_tree(self, group_and_parallel_trace_tree_config):
        """test create very wide tree"""
        width = 10000
        wide_trace = make_a_very_wide_roots_trace(width)
        with Timeout(seconds=1):
            wide_tree = TraceTree.from_raw(wide_trace, group_and_parallel_trace_tree_config)

        assert len(wide_tree.nodes_map) == len(wide_trace)
        assert len(wide_tree.roots) == width

    def test_create_very_deep_tree(self, default_trace_tree_config):
        """test create very deep tree"""
        deep_trace = make_a_very_deep_trace(sys.getrecursionlimit() + 1)
        tree = TraceTree.from_raw(deep_trace, default_trace_tree_config)

        for _, node in tree.nodes_map.items():
            index = int(node.id[4:])
            if node.parent is None:
                assert node.id == "span0"
                continue

            assert node.parent.id == f"span{index-1}"

    @pytest.mark.parametrize(
        "relations",
        [
            # span0
            (["", "span0"],),
            # span0 -> span1
            (
                ["", "span0"],
                ["span0", "span1"],
            ),
            # span0 -> span1 -> span2
            #       -> span3 -> span4
            (
                ["", "span0"],
                ["span0", "span1"],
                ["span1", "span2"],
                ["span1", "span3"],
                ["span3", "span4"],
            ),
            # span0 -> span1 -> span2 -> span3 -> span4
            #                         -> span5
            #       -> span6 -> span7
            (
                ["", "span0"],
                ["span0", "span1"],
                ["span1", "span2"],
                ["span2", "span3"],
                ["span3", "span4"],
                ["span2", "span5"],
                ["span0", "span6"],
                ["span6", "span7"],
            ),
            # span0 -> span1 -> span2
            # span3 -> span4
            (
                ["", "span0"],
                ["span0", "span1"],
                ["span3", "span4"],
                ["span1", "span2"],
                ["", "span3"],
            ),
        ],
    )
    def test_create_tree(self, relations: list):
        """test create tree"""
        tree = TraceTree.from_raw(dynamic_make_trace_list(relations))

        for relation in relations:
            if tree.nodes_map[relation[1]].parent is None:
                assert tree.nodes_map[relation[1]].is_root
                continue

            assert tree.nodes_map[relation[1]].parent.id == relation[0]

    @pytest.mark.parametrize(
        "relations, expected",
        [
            # span0 -> span1 -> span2
            #       -> span3 -> span4
            (
                (
                    ["", "span0"],
                    ["span0", "span1"],
                    ["span1", "span2"],
                    ["span1", "span3"],
                    ["span3", "span4"],
                ),
                ["span0", "span1", "span2", "span3", "span4"],
            ),
            # span0 -> span1 -> span2 -> span3 -> span4
            #                         -> span5
            #       -> span6 -> span7
            (
                (
                    ["", "span0"],
                    ["span0", "span1"],
                    ["span1", "span2"],
                    ["span2", "span3"],
                    ["span3", "span4"],
                    ["span2", "span5"],
                    ["span0", "span6"],
                    ["span6", "span7"],
                ),
                ["span0", "span1", "span2", "span3", "span4", "span5", "span6", "span7"],
            ),
            # span0 -> span1 -> span2
            # span3 -> span4
            (
                (
                    ["span1", "span2"],
                    ["span0", "span1"],
                    ["span3", "span4"],
                    ["", "span0"],
                    ["", "span3"],
                ),
                ["span0", "span1", "span2", "span3", "span4"],
            ),
        ],
    )
    def test_to_pre_order_travel(self, relations: list, expected: list):
        """test pre-order travel"""
        tree = TraceTree.from_raw(dynamic_make_trace_list(relations))
        assert [x.id for x in tree.to_pre_order_tree_list()] == expected
