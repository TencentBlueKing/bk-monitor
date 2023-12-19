import pytest

from apm_web.trace.diagram.diff import DiffMark, TraceDiffer

from .utils import dynamic_make_trace_list, read_trace_list


class TestDiff:
    """Test Diff Tree"""

    def test_create_diff_tree(self, group_and_parallel_trace_tree_config):
        """test create diff tree"""
        baseline_data = read_trace_list("simple")
        comparison_data = read_trace_list("diff_simple")

        diff_tree = TraceDiffer.from_raw(baseline_data, comparison_data).diff_tree()

        assert len(diff_tree.roots) == 1
        root = diff_tree.roots[0]
        assert root.mark == DiffMark.CHANGED

    @pytest.mark.parametrize(
        "baseline,comparison,expected",
        [
            (
                [
                    ("", "span0", "span0", 100),
                    ("span0", "span1", "SET", 100),
                    ("span1", "span2", "SET", 100),
                    ("span2", "span3", "SET", 200),
                    ("span3", "span4", "SET", 200),
                ],
                [
                    ("", "span0", "span0", 20),
                    ("span0", "span1", "SET", 100),
                    ("span1", "span2", "SET", 100),
                    ("span2", "span3", "SET", 200),
                    ("span3", "span4", "SET", 100),
                ],
                [
                    ("", "span0", "span0", DiffMark.CHANGED),
                    ("span0", "span1", "SET", DiffMark.UNCHANGED),
                    ("span1", "span2", "SET", DiffMark.UNCHANGED),
                    ("span2", "span3", "SET", DiffMark.UNCHANGED),
                    ("span3", "span4", "SET", DiffMark.CHANGED),
                ],
            ),
            (
                # 0 -> 1
                #   -> 2 -> 3
                #        -> 4
                #   -> 6 -> 7
                [
                    ("", "span0", "span0", 100),
                    ("span0", "span1", "SET1", 100),
                    ("span0", "span2", "SET2", 120),
                    ("span0", "span6", "SET6", 120),
                    ("span2", "span3", "SET3", 200),
                    ("span2", "span4", "SET4", 200),
                    ("span6", "span7", "SET7", 120),
                ],
                # 0 -> 1
                #   -> 2 -> 3
                #   -> 5
                [
                    ("", "span0", "span0", 100),
                    ("span0", "span1", "SET1", 50),
                    ("span0", "span2", "SET2", 100),
                    ("span0", "span5", "SET5", 700),
                    ("span2", "span3", "SET3", 100),
                ],
                [
                    ("", "span0", "span0", DiffMark.UNCHANGED),
                    ("span0", "span1", "SET1", DiffMark.CHANGED),
                    ("span0", "span2", "SET2", DiffMark.CHANGED),
                    ("span2", "span3", "SET3", DiffMark.CHANGED),
                    ("span2", "span4", "SET4", DiffMark.ADDED),
                    ("span0", "span6", "SET6", DiffMark.ADDED),
                    ("span0", "span5", "SET5", DiffMark.REMOVED),
                ],
            ),
            (
                # 0 -> 1
                # 2 -> 3
                # 4 -> 5
                [
                    ("", "span0", "span0", 100),
                    ("span0", "span1", "SET1", 100),
                    ("", "span2", "span2", 100),
                    ("span2", "span3", "SET3", 200),
                    ("", "span4", "span4", 100),
                    ("span4", "span5", "SET5", 300),
                ],
                # 0 -> 1
                # 4 -> 6
                # 7 -> 8
                [
                    # parent_id, span_id, span_name
                    # span_name is diff key so span_id will not affect the diff results
                    ("", "span0_a", "span0", 100),
                    ("span0_a", "span1", "SET1", 200),
                    ("", "span4", "span4", 200),
                    ("span4", "span6", "SET6", 300),
                    ("", "span7", "span7", 100),
                    ("span7", "span8", "SET8", 300),
                ],
                [
                    ("", "span0", "span0", DiffMark.UNCHANGED),
                    ("span0", "span1", "SET1", DiffMark.CHANGED),
                    ("", "span2", "span2", DiffMark.ADDED),
                    ("", "span4", "span4", DiffMark.CHANGED),
                    ("span4", "span5", "SET5", DiffMark.ADDED),
                    ("span4", "span6", "SET6", DiffMark.REMOVED),
                    ("", "span7", "span7", DiffMark.REMOVED),
                ],
            ),
        ],
    )
    def test_diff_tree(self, baseline, comparison, expected):
        """test diff tree"""
        baseline_data = dynamic_make_trace_list(baseline)
        comparison_data = dynamic_make_trace_list(comparison)

        differ = TraceDiffer.from_raw(baseline_data, comparison_data)
        diff_tree = differ.diff_tree()

        # from apm_web.trace.diagram.debug import debug_print_trace_tree, debug_print_diff_tree
        #
        # debug_print_trace_tree(differ.baseline)
        # debug_print_trace_tree(differ.comparison)
        #
        # debug_print_diff_tree(diff_tree)

        # got pre-order travel VLR
        stack = [*diff_tree.roots]
        result = []
        while stack:
            node = stack[0]
            result.append(
                (
                    node.parent.default.id if node.parent else "",
                    node.default.id,
                    node.default.name,
                    node.mark,
                )
            )

            stack = [*node.children, *stack[1:]]

        assert result == expected
