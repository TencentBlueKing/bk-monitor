from dataclasses import dataclass
from typing import Optional, Union

from apm_web.handlers.trace_handler.base import TraceHandler
from apm_web.trace.diagram.base import SpanNode, TraceTree, TreeBuildingConfig
from apm_web.trace.diagram.diff import DiffMark, DiffNode, TraceDiffer

from constants.apm import OtlpKey


@dataclass
class FlamegraphDiagrammer:
    """Flamegraph diagrammer"""

    def draw(self, trace_detail: list, **options) -> dict:
        return trace_to_flamegraph(trace_detail)

    def diff(self, base: list, comp: list, **options) -> dict:
        return trace_diff_to_flamegraph(base, comp)


def get_last_parallel_sibling_id(span: SpanNode) -> Optional[str]:
    """Get last sibling id in a parallel group"""
    if not span.parallel:
        return None

    index = [x.id for x in span.parallel.members].index(span.id)
    if index > 0:
        return span.parallel.members[index - 1].id

    # self is the first child
    return None


# -----------------------------
# Normal FlameGraph
# -----------------------------
def elements_from_span_info(span: SpanNode) -> dict:
    """Turn span info to flamegraph node"""
    # TODO: auto call finalize_candidates when travel the tree
    span.finalize_candidates()

    _, icon_type = TraceHandler._get_span_classify(span.details)  # noqa

    element = {
        "name": f"{span.service_name} {span.name}",
        "value": span.absolute_duration,
        "children": [],
        "id": span.id,
        "parallel_id": span.parallel.id if span.parallel else None,
        "last_sibling_id": get_last_parallel_sibling_id(span),
        "icon_type": icon_type,
        "start_time": span.details[OtlpKey.START_TIME],
        "end_time": span.details[OtlpKey.END_TIME],
        "kind": span.details[OtlpKey.KIND],
        "level": span.level,
        "status": span.details[OtlpKey.STATUS],
    }
    return element


def drain_parallel_from_span_node(span_node: SpanNode, global_elements: list) -> dict:
    """Drain parallel from span node"""
    parallel_in_stack = None
    element = elements_from_span_info(span_node)

    for child in span_node.children:

        if child.parallel is None:
            element["children"].append(drain_parallel_from_span_node(child, global_elements))
            continue

        if parallel_in_stack is None:
            parallel_in_stack = child.parallel
            element["children"].append(drain_parallel_from_span_node(child, global_elements))
            continue

        if parallel_in_stack.id != child.parallel.id:
            parallel_in_stack = child.parallel
            element["children"].append(drain_parallel_from_span_node(child, global_elements))
            continue

        if parallel_in_stack.id == child.parallel.id:
            global_elements.append(drain_parallel_from_span_node(child, global_elements))

    return element


def aggregations_to_info(aggregation: dict) -> list:
    """Convert aggregations to info"""
    info = []
    for agg_type, (agg_map, agg_cls) in aggregation.items():
        info.append(
            {
                "aggregation_key": agg_type,
                "display_name": agg_cls.agg_display_name,
                "items": [{"key": k, "display_name": v.display_name, "values": v.values} for k, v in agg_map.items()],
            }
        )
    return info


def trace_to_flamegraph(trace_data: list, forced_config: Optional[TreeBuildingConfig] = None) -> dict:
    """Convert trace detail to flamegraph data"""
    flamegraph_data = []

    if not forced_config:
        config = TreeBuildingConfig(with_parallel_detection=True)
    else:
        config = forced_config

    trace_tree = TraceTree.from_raw(trace_data, config)
    global_elements = []
    for root in trace_tree.roots:
        element = drain_parallel_from_span_node(root, global_elements)
        flamegraph_data.append(element)

    global_elements.sort(key=lambda x: x["level"])
    flamegraph_data.extend(global_elements)
    return {
        "flame_data": flamegraph_data,
        "aggregations_data": aggregations_to_info(trace_tree.aggregations),
    }


# -----------------------------
# Diff FlameGraph
# -----------------------------
def make_diff_info_from_span_node(span_node: SpanNode, diff_mark: DiffMark):
    """Make a diff info from SpanNode."""

    diff_info = {"mark": diff_mark.value}

    if diff_mark == DiffMark.REMOVED:
        diff_info["baseline"] = 0
        diff_info["comparison"] = span_node.value
    elif diff_mark == DiffMark.ADDED:
        diff_info["baseline"] = span_node.value
        diff_info["comparison"] = 0

    return diff_info


def drain_parallel_from_node(
    node: Union[SpanNode, DiffNode], global_elements: list, mark: Optional[DiffMark] = None
) -> dict:
    """Drain parallel from union node"""

    # use multiple type for less duplicate function
    diff_node = None
    if isinstance(node, SpanNode):
        span_node = node
    else:
        diff_node = node
        span_node = node.default
        mark = node.mark

    # if mark is removed, means it's totally came from comparison tree which will not show in flamegraph diffing.
    if mark == DiffMark.REMOVED:
        return {}

    element = elements_from_span_info(span_node)
    element["diff_info"] = make_diff_info_from_span_node(span_node, mark)

    if mark == DiffMark.ADDED:
        # ADDED or REMOVED means diff_node is a leaf node, but we still need to fulfill the rest part of the SpanNode
        parallel_in_stack = None
        for child in span_node.children:
            child_element = drain_parallel_from_node(child, global_elements, mark=DiffMark.ADDED)
            if not child_element:
                continue

            if child.parallel is None:
                element["children"].append(child_element)
                continue

            if parallel_in_stack is None:
                parallel_in_stack = child.parallel
                element["children"].append(child_element)
                continue

            if parallel_in_stack.id != child.parallel.id:
                parallel_in_stack = child.parallel
                element["children"].append(child_element)
                continue

            if parallel_in_stack.id == child.parallel.id:
                global_elements.append(child_element)

    else:
        # CHANGED or UNCHANGED means diff_node is a branch node, traversing the rest of diff tree
        parallel_in_stack = None
        element["diff_info"].update(diff_node.diff_info)
        for child in diff_node.children:
            child_element = drain_parallel_from_node(child, global_elements)
            if not child_element:
                continue

            if child.default.parallel is None:
                element["children"].append(child_element)
                continue

            if parallel_in_stack is None:
                parallel_in_stack = child.default.parallel
                element["children"].append(child_element)
                continue

            if parallel_in_stack.id != child.default.parallel.id:
                parallel_in_stack = child.default.parallel
                element["children"].append(child_element)
                continue

            if parallel_in_stack.id == child.default.parallel.id:
                global_elements.append(child_element)

    return element


def trace_diff_to_flamegraph(former: list, latter: list) -> dict:
    """Convert trace diff to flamegraph data"""
    config = TreeBuildingConfig(with_parallel_detection=True)
    diff_tree = TraceDiffer.from_raw(former, latter, config).diff_tree()
    flamegraph_data = []
    global_elements = []

    for root in diff_tree.roots:
        element = drain_parallel_from_node(root, global_elements)
        if element:
            flamegraph_data.append(element)

    global_elements.sort(key=lambda x: x["level"])
    flamegraph_data.extend(global_elements)
    return {"flame_data": flamegraph_data}
