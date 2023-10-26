from apm_web.trace.diagram.flamegraph import trace_to_flamegraph

from .utils import read_trace_list


class TestFlamegraph:
    def test_raw_simple(self):
        """Test raw simple flamegraph"""
        trace_data = read_trace_list("simple")
        # root -> span1
        #      -> span2
        #      -> span3
        #      -> span4
        #      -> span5
        flame_data = trace_to_flamegraph(trace_data)
        assert len(flame_data["flame_data"]) == 1
        assert len(flame_data["flame_data"][0]["children"]) == 5
        assert len(flame_data["aggregations_data"]) == 4

    def test_parallel(self, group_and_parallel_trace_tree_config):
        trace_data = read_trace_list("parallel")
        # 4 siblings, 1 root
        # first 2 siblings marked as parallel for execution overlapping
        # last 2 siblings marked as parallel for close start time
        flame_data = trace_to_flamegraph(trace_data)
        assert len(flame_data["flame_data"]) == 4
        assert len(flame_data["flame_data"][0]["children"]) == 1
        assert len(flame_data["flame_data"][1]["children"]) == 0
        assert len(flame_data["flame_data"][2]["children"]) == 0
        assert len(flame_data["flame_data"][3]["children"]) == 0

        group_and_parallel_trace_tree_config.min_parallel_gap = 10
        flame_data = trace_to_flamegraph(trace_data, group_and_parallel_trace_tree_config)
        assert len(flame_data["flame_data"]) == 3
