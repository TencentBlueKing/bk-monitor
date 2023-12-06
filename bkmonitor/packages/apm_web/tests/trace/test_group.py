from apm_web.trace.diagram.base import TraceTree

from .utils import read_trace_list


class TestTraceTreeGroup:
    """Test Trace Tree"""

    def test_create_tree_with_group(self, group_and_parallel_trace_tree_config):
        """test create group tree"""
        group_and_parallel_trace_tree_config.min_group_members = 2
        tree_with_parallel = TraceTree.from_raw(read_trace_list("simple"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()

        # 5 siblings, 1 root
        # SELECT, SET, SELECT, SELECT, SELECT
        root = tree_with_parallel.roots[0]
        assert len(root.children) == 5
        assert root.children[0].group is None
        assert root.children[1].group is None
        assert root.children[2].group is not None
        assert root.children[2].group == root.children[3].group == root.children[4].group

        group_and_parallel_trace_tree_config.min_group_members = 4
        tree_with_parallel = TraceTree.from_raw(read_trace_list("simple"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()

        root = tree_with_parallel.roots[0]
        assert len(root.children) == 5
        assert all([x.group is None for x in root.children])

    def test_create_tree_with_group_ignore_sequence(self, group_and_parallel_trace_tree_config):
        """test create group tree"""
        group_and_parallel_trace_tree_config.min_group_members = 2
        group_and_parallel_trace_tree_config.group_ignore_sequence = True
        tree_with_parallel = TraceTree.from_raw(read_trace_list("simple"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()

        # 5 siblings, 1 root
        # SELECT, SET, SELECT, SELECT, SELECT
        root = tree_with_parallel.roots[0]
        assert len(root.children) == 5
        assert root.children[1].group is None
        assert root.children[2].group is not None
        assert root.children[0].group == root.children[2].group == root.children[3].group == root.children[4].group

    def test_small_span_no_group(self, group_and_parallel_trace_tree_config):
        """Test small span no group"""
        tree_with_parallel = TraceTree.from_raw(read_trace_list("simple"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()
        # 5 siblings, 1 root, default min_group_spans_count is 5, so groups exist.
        # SELECT, SET, SELECT, SELECT, SELECT
        root = tree_with_parallel.roots[0]
        assert len(root.children) == 5
        assert root.children[1].group is None
        assert root.children[2].group is not None

        # 6 spans in simple, so we set min_group_spans_count to 7
        group_and_parallel_trace_tree_config.min_group_spans_count = 7
        tree_with_parallel2 = TraceTree.from_raw(read_trace_list("simple"), group_and_parallel_trace_tree_config)
        tree_with_parallel2.build_extras()
        # 5 siblings, 1 root
        # SELECT, SET, SELECT, SELECT, SELECT
        root = tree_with_parallel2.roots[0]
        assert len(root.children) == 5
        for c in root.children:
            assert c.group is None
