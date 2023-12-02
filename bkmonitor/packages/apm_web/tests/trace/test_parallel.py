from apm_web.trace.diagram.base import TraceTree

from .utils import read_trace_list


class TestTraceTreeParallel:
    """Test Trace Tree"""

    def test_create_tree_with_parallel(self, group_and_parallel_trace_tree_config):
        """test create parallel tree"""
        # 4 siblings, 1 root
        # first 2 siblings marked as parallel for execution overlapping
        # last 2 siblings marked as parallel for close start time
        group_and_parallel_trace_tree_config.min_parallel_gap = 10
        tree_with_parallel = TraceTree.from_raw(read_trace_list("parallel"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()

        root = tree_with_parallel.roots[0]
        assert len(root.children) == 4
        assert root.children[0].parallel is not None
        assert len({x.parallel.id for x in root.children[:1]}) == 1
        assert root.children[3].parallel is not None

        assert len({x.parallel.id for x in root.children[2:4]}) == 1
        assert root.children[1].parallel.id != root.children[3].parallel.id

    def test_create_tree_with_parallel_min_gap(self, group_and_parallel_trace_tree_config):
        """test create parallel tree with min gap"""
        group_and_parallel_trace_tree_config.min_parallel_gap = 1
        tree_with_parallel = TraceTree.from_raw(read_trace_list("parallel"), group_and_parallel_trace_tree_config)
        tree_with_parallel.build_extras()

        root = tree_with_parallel.roots[0]
        assert len(root.children) == 4
        assert root.children[1].parallel is not None
        assert len({x.parallel.id for x in root.children[:2]}) == 1
        # gap will larger than 1
        assert root.children[3].parallel is None
