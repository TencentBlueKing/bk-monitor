from dataclasses import dataclass, field

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import StatusCode

from apm_web.handlers.trace_handler.base import TraceHandler
from apm_web.trace.diagram.base import Group, SpanNode, TraceTree, TreeBuildingConfig
from apm_web.trace.diagram.config import DiagramConfigController
from apm_web.trace.diagram.diff import DiffMark, DiffNode, DiffTree, TraceDiffer
from apm_web.trace.service_color import ServiceColorClassifier
from constants.apm import OtlpKey


@dataclass
class TopoDiagrammer:
    """Topo diagrammer"""

    def draw(self, trace_detail: list, **options) -> dict:
        return trace_data_to_topo_data(trace_data=trace_detail)

    def diff(self, base: list, comp: list, **options) -> dict:
        return trace_data_to_diff_topo(base, comp)


@dataclass
class TopoNode:
    """Topo node."""

    id: str

    duration: int
    spans: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    group: Group | None = None

    @classmethod
    def from_span_node(cls, span_node: SpanNode) -> "TopoNode":
        if span_node.group is None:
            return cls(
                id=span_node.id,
                duration=span_node.value,
                spans=[span_node.id],
                details=span_node.details,
            )

        return cls.from_group(span_node.group)

    @classmethod
    def from_group(cls, group: Group) -> "TopoNode":
        return cls(
            id=group.first.id,
            duration=group.absolute_duration,
            spans=group.member_ids,
            details=group.first.details,
            group=group,
        )

    @property
    def collapsed(self) -> bool:
        """Whether this node is collapsed."""
        return len(self.spans) > 1

    def to_dict(self, color_classifier: ServiceColorClassifier) -> dict:
        service_name = self.details[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME]
        info = {
            # we don't need the full id
            "id": self.id[:16],
            "duration": self.duration,
            "color": color_classifier.next(service_name),
            "service_name": service_name,
            "error": 1 if self.details[OtlpKey.STATUS]["code"] == StatusCode.ERROR.value else 0,
            "spans": self.spans,
            "icon": TraceHandler._get_span_classify(self.details)[0],  # noqa
            "operationName": self.details[OtlpKey.SPAN_NAME],
            "collapsed": self.collapsed,
        }

        return info


@dataclass
class GlobalNodes:
    color_classifier: ServiceColorClassifier
    _nodes: dict[str, TopoNode] = field(default_factory=dict)
    _nodes_dict: dict[str, dict] = field(default_factory=dict)

    def add(self, node: TopoNode):
        if node.id in self._nodes:
            return

        self._nodes[node.id] = node
        self._nodes_dict[node.id] = node.to_dict(self.color_classifier)

    def to_list(self):
        return list(self._nodes_dict.values())


@dataclass
class Relation:
    """Relation between two nodes."""

    source: str
    target: str

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
        }


@dataclass
class GlobalRelations:
    """Global Relations between nodes."""

    _relations: dict[tuple, Relation] = field(default_factory=dict)

    def add(self, source: TopoNode, target: TopoNode):
        if (source.id, target.id) in self._relations:
            return

        self._relations[(source.id, target.id)] = Relation(source.id, target.id)

    def to_list(self):
        return [r.to_dict() for r in self._relations.values()]


def make_virtual_group_from_node(members: list[SpanNode]) -> Group:
    """Make a virtual group from node."""
    group = Group.from_parent(members[0], members[0].config)
    group.members = members
    return group


def make_topo_node_from_span_node(
    span_node: SpanNode,
    global_relations: GlobalRelations,
    global_nodes: GlobalNodes,
    parent_group: Group | None = None,
) -> TopoNode:
    """Turn a span node to a topo node"""

    # when parent is grouped, means all the descendants of parent(include this one) should be same across all the
    # member of parent group. So we need to create a virtual group for those descendants which are not grouped, and
    # create a topo node for those which are grouped.
    if parent_group is not None:
        if span_node.group is None:
            # no grouped, so grouping all the same index children node
            # A1 -> B   A2 -> B
            #    -> C      -> C
            # --->
            # A x2 -> B x2
            #      -> C x2
            twins = []
            for m in parent_group.members:
                if len(m.children) > span_node.index:
                    twins.append(m.children[span_node.index])
        else:
            # already grouped, so grouping all the same index children group
            # A1 -> B1   A2 -> B2
            #    -> B1   A2 -> B2
            #    -> C1      -> C2
            # --->
            # A x2 -> B x4
            #      -> C x2
            twins = []
            for m in parent_group.members:
                if len(m.children) > span_node.index and m.children[span_node.index].group:
                    twins.extend(m.children[span_node.index].group.members)

        virtual_group = make_virtual_group_from_node(twins)
        topo_node = TopoNode.from_group(virtual_group)

        for child in span_node.children:
            child_node = make_topo_node_from_span_node(child, global_relations, global_nodes, virtual_group)
            global_nodes.add(child_node)
            global_relations.add(topo_node, child_node)

        return topo_node

    # parent not grouped, so we can create a topo node directly
    topo_node = TopoNode.from_span_node(span_node)
    for child in span_node.children:
        child_node = make_topo_node_from_span_node(child, global_relations, global_nodes, span_node.group)
        global_nodes.add(child_node)
        global_relations.add(topo_node, child_node)

    return topo_node


def trace_data_to_topo_data(trace_data: list, forced_config: TreeBuildingConfig | None = None) -> dict:
    """Convert trace data to topo data."""
    if not forced_config:
        config_controller = DiagramConfigController.read()
        if config_controller and config_controller.topo:
            configured_config = config_controller.topo.tree_building_config
        else:
            configured_config = TreeBuildingConfig(with_group=True, group_ignore_sequence=True)

        config = configured_config
    else:
        config = forced_config

    tree = TraceTree.from_raw(trace_data, config)
    tree.build_extras(return_as_list=False)

    # disabled on production
    # from .debug import debug_print_topo_tree, debug_print_trace_tree

    # debug_print_trace_tree(tree)

    color_classifier = ServiceColorClassifier()
    global_nodes = GlobalNodes(color_classifier)
    global_relations = GlobalRelations()

    for root in tree.roots:
        root_node = make_topo_node_from_span_node(root, global_relations, global_nodes)
        global_nodes.add(root_node)

    # debug_print_topo_tree(global_relations.to_list(), global_nodes.to_list())

    return {"relations": global_relations.to_list(), "nodes": global_nodes.to_list()}


# -----------------
# Diff
# -----------------


@dataclass
class TopoDiffNode(TopoNode):
    """Topo diff node."""

    diff_info: dict = field(default_factory=dict)

    def to_dict(self, color_classifier: ServiceColorClassifier) -> dict:
        base = super().to_dict(color_classifier)
        base["diff_info"] = self.diff_info
        return base


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


def make_topo_diff_node_from_span_node(
    span_node: SpanNode, relations: dict, diff_mark: DiffMark, color_classifier: ServiceColorClassifier
) -> tuple[dict, dict]:
    """Make topo diff node from span node

    Diff Tree is not full of nodes if parent node is removed or added,
    so we need to make diff element from span node
    """
    nodes = {}
    if span_node.group:
        this_node = TopoDiffNode(
            id=span_node.group.members[0].id,
            duration=span_node.group.absolute_duration,
            spans=[x.id for x in span_node.group.members],
            details=span_node.details,
            diff_info={x.id: make_diff_info_from_span_node(x, diff_mark) for x in span_node.group.members},
        )
        return this_node.to_dict(color_classifier), nodes

    this_node = TopoDiffNode(
        id=span_node.id,
        duration=span_node.value,
        spans=[span_node.id],
        details=span_node.details,
        diff_info={span_node.id: make_diff_info_from_span_node(span_node, diff_mark)},
    )

    for child in span_node.children:
        _child_child_node, _nodes = make_topo_diff_node_from_span_node(child, relations, diff_mark, color_classifier)
        relations[(this_node.id, _child_child_node["id"])] = Relation(
            source=this_node.id, target=_child_child_node["id"]
        ).to_dict()

        nodes[_child_child_node["id"]] = _child_child_node
        nodes.update(_nodes)

    return this_node.to_dict(color_classifier), nodes


def diff_topo_nodes_from_diff_node(
    diff_node: DiffNode, relations: dict, color_classifier: ServiceColorClassifier, diff_tree: DiffTree
) -> tuple[dict, dict]:
    if diff_node.mark in [DiffMark.ADDED, DiffMark.REMOVED]:
        diff_topo_node_info, nodes = make_topo_diff_node_from_span_node(
            diff_node.default, relations, diff_node.mark, color_classifier
        )
    else:
        nodes = {}
        if diff_node.default.group:
            this_node = TopoDiffNode(
                id=diff_node.default.group.members[0].id,
                duration=diff_node.default.group.absolute_duration,
                spans=[x.id for x in diff_node.default.group.members],
                details=diff_node.default.details,
                diff_info={x.id: diff_tree.get_node_by_id(x.id).diff_info for x in diff_node.default.group.members},
            )
            return this_node.to_dict(color_classifier), nodes

        this_node = TopoDiffNode(
            id=diff_node.default.id,
            duration=diff_node.default.value,
            spans=[diff_node.default.id],
            details=diff_node.default.details,
            diff_info={diff_node.default.id: diff_node.diff_info},
        )

        for child in diff_node.children:
            _child_child_node, _nodes = diff_topo_nodes_from_diff_node(child, relations, color_classifier, diff_tree)
            relations[(this_node.id, _child_child_node["id"])] = Relation(
                source=this_node.id, target=_child_child_node["id"]
            ).to_dict()

            nodes[_child_child_node["id"]] = _child_child_node
            nodes.update(_nodes)

        diff_topo_node_info = this_node.to_dict(color_classifier)

    return diff_topo_node_info, nodes


def trace_data_to_diff_topo(base: list, comp: list) -> dict:
    """Trace data to diff topo."""
    config_controller = DiagramConfigController.read()
    if config_controller and config_controller.topo:
        config = config_controller.topo.tree_building_config
    else:
        config = TreeBuildingConfig(with_group=True, group_ignore_sequence=True)

    diff_tree = TraceDiffer.from_raw(base, comp, config=config).diff_tree()
    diff_tree.build_extras()

    nodes = {}
    relations: dict = {}
    color_classifier = ServiceColorClassifier()
    for root in diff_tree.roots:
        # TODO: when diff_tree is passing means this could be an inner method
        root_node, child_nodes = diff_topo_nodes_from_diff_node(root, relations, color_classifier, diff_tree)

        nodes[root_node["id"]] = root_node
        nodes.update(child_nodes)

    # disabled on production
    # from .debug import debug_print_diff_tree
    #
    # debug_print_diff_tree(diff_tree)

    return {
        "relations": list(relations.values()),
        "nodes": list(nodes.values()),
        "similarity_check": diff_tree.calculate_level_similarity(),
        "similarity_map": {k: v.percentage for k, v in diff_tree.level_similarity_map.items()},
    }
