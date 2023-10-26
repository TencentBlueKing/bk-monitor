from apm_web.trace.diagram.topo import trace_data_to_topo_data

from .utils import read_trace_list


class TestTopoDiagram:
    def test_simple(self, default_trace_tree_config):
        trace_data = read_trace_list("simple")
        # root -> span1
        #      -> span2
        #      -> span3
        #      -> span4
        #      -> span5
        topo_data = trace_data_to_topo_data(trace_data, default_trace_tree_config)
        assert len(topo_data["nodes"]) == 6
        assert len(topo_data["relations"]) == 5

    def test_grouping(self, default_trace_tree_config, forced_group_trace_tree_config):
        # level0 -> level1_1 -> level2_1 -> level3_1
        #                              -> level3_2
        #        -> level1_2 -> level2_2 -> level3_3
        #                              -> level3_4
        #        -> level1_3 -> level2_3 -> level3_5
        #                              -> level3_6
        #                              -> level3_7
        trace_data = read_trace_list("grouping_same_children", category="topo")

        no_grouped_topo_data = trace_data_to_topo_data(trace_data, default_trace_tree_config)
        no_group_relations = no_grouped_topo_data["relations"]
        no_group_nodes = no_grouped_topo_data["nodes"]
        # 3 + 3 + 7
        assert len(no_group_relations) == 13
        assert len(no_group_nodes) == 14

        grouped_topo_data = trace_data_to_topo_data(trace_data, forced_group_trace_tree_config)
        # level0 -> level1 x2 -> level2 x2 -> level3 x4
        #        -> level1_3  -> level2_3  -> level3 x3
        relations = grouped_topo_data["relations"]
        nodes = grouped_topo_data["nodes"]
        # 2 + 2 + 2
        assert len(relations) == 6
        assert len(nodes) == 7
        assert {
            ("level0",),
            ("level1_1", "level1_2"),
            ("level1_3",),
            ("level2_1", "level2_2"),
            ("level2_3",),
            ("level3_1", "level3_2", "level3_3", "level3_4"),
            ("level3_5", "level3_6", "level3_7"),
        } == {tuple(x["spans"]) for x in nodes}
