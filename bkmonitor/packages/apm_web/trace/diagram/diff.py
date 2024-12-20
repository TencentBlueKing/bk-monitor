import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from apm_web.trace.diagram.base import Group, SpanNode, TraceTree, TreeBuildingConfig

logger = logging.getLogger(__name__)


class DiffPolicy(str, Enum):
    """Diff policy."""

    # diff the tree with strict time order
    strict_time_order = "strict_time_order"
    # evaluate tree if they are the same
    same_tree_evaluation = "same_tree_evaluation"
    # whether baseline tree is complete or not
    # if not, the comparison will be the reference tree to fulfill baseline tree at first
    complete_baseline_tree = "complete_baseline_tree"


@dataclass
class TraceDiffer:
    baseline: "TraceTree"
    comparison: "TraceTree"

    build_config: "TreeBuildingConfig"

    policies: List[DiffPolicy] = field(default_factory=lambda: [DiffPolicy.strict_time_order])

    @classmethod
    def from_raw(
        cls,
        baseline: list,
        comparison: list,
        config: TreeBuildingConfig = TreeBuildingConfig.default(),
        policies: Optional[List[DiffPolicy]] = None,
    ) -> "TraceDiffer":
        baseline_tree = TraceTree.from_raw(baseline, config)
        comparison_tree = TraceTree.from_raw(comparison, config)
        return TraceDiffer(baseline_tree, comparison_tree, config, policies or [])

    def _diff_node(self, diff_tree: "DiffTree", base: "SpanNode", comp: "SpanNode") -> "DiffNode":
        """Diff a node."""
        # If the root node is different, the whole tree is different
        if base.unique_together != comp.unique_together:
            # we don't need to diff the rest of the tree
            return DiffNode(base, comp, DiffMark.ADDED)

        # this node exists
        diff_node = DiffNode(base, comp, DiffMark.CHANGED if base.value != comp.value else DiffMark.UNCHANGED)
        # only find the first similar child and never look back
        comparison_searching_index = 0
        for base_child in base.children:
            similar = comp.find_similar_child(comparison_searching_index, base_child)
            # no similar child found, this child is removed
            if similar is None:
                diff_tree.add_node(diff_node, DiffNode(base_child, None, DiffMark.ADDED))
                continue

            # found, if there are nodes between the last similar node and this one, they are added
            if similar.index > comparison_searching_index:
                for i in range(comparison_searching_index, similar.index):
                    diff_tree.add_node(diff_node, DiffNode(None, comp.children[i], DiffMark.REMOVED))

            # update the searching index
            comparison_searching_index = similar.index + 1
            diff_tree.add_node(diff_node, self._diff_node(diff_tree, base_child, similar))

        # all children of base handled, but still have children in comp, they are added
        if comparison_searching_index <= len(comp.children) - 1:
            for i in range(comparison_searching_index, len(comp.children)):
                diff_tree.add_node(diff_node, DiffNode(None, comp.children[i], DiffMark.REMOVED))

        return diff_node

    def diff_tree(self) -> "DiffTree":
        """Diff the two trees."""

        searching_root_index = 0
        diff_tree = DiffTree(config=self.build_config)

        for root in self.baseline.roots:
            # no similar root found, this root is removed
            similar = self.comparison.find_similar_root(searching_root_index, root)
            if similar is None:
                diff_tree.add_root(DiffNode(root, None, DiffMark.ADDED))
                continue

            # found, if there are nodes between the last similar node and this one, they are added
            if similar.index > searching_root_index:
                for j in range(searching_root_index, similar.index):
                    diff_tree.add_root(DiffNode(None, self.comparison.roots[j], DiffMark.REMOVED))

            # update the searching index
            searching_root_index = similar.index + 1
            try:
                diff_tree.add_root(self._diff_node(diff_tree, root, similar))
            except RecursionError:
                raise ValueError("The trace is too deep to be diffed")

        # all children of base handled, but still have children in comp, they are added
        if searching_root_index <= len(self.comparison.roots) - 1:
            for j in range(searching_root_index, len(self.comparison.roots)):
                diff_tree.add_root(DiffNode(None, self.comparison.roots[j], DiffMark.REMOVED))

        return diff_tree


class DiffMark(Enum):
    """A mark for a diff node."""

    REMOVED = "removed"
    ADDED = "added"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass
class DiffNode:
    baseline: Optional[SpanNode]
    comparison: Optional[SpanNode]
    mark: DiffMark

    parent: Optional["DiffNode"] = None
    children: List["DiffNode"] = field(default_factory=list)

    def __post_init__(self):
        if self.baseline is not None:
            self.baseline.extra_info["diff_node"] = self

        if self.comparison is not None:
            self.comparison.extra_info["diff_node"] = self

    def __repr__(self):
        return str(self)

    def __str__(self, level=0):
        indent = "\t" * level

        if self.mark == DiffMark.ADDED:
            ret = f"{indent}{self.baseline}:{self.delta}%\n"
        elif self.mark == DiffMark.REMOVED:
            ret = f"{indent}{self.comparison}:{self.delta}%\n"
        else:
            ret = f"{indent}{self.baseline}:{self.delta:.2f}%\n"

        for child in self.children:
            ret += child.__str__(level + 1)
        return ret

    @property
    def delta(self) -> Optional[float]:
        """Node delta as percentage."""
        if self.mark == DiffMark.CHANGED:
            return (self.comparison.value - self.baseline.value) / self.baseline.value * 100
        elif self.mark == DiffMark.UNCHANGED:
            return 0

        if self.mark in [DiffMark.REMOVED, DiffMark.ADDED]:
            return None

    @property
    def diff_info(self) -> dict:
        diff_info = {"mark": self.mark.value}

        if self.mark == DiffMark.REMOVED:
            diff_info["baseline"] = 0
            diff_info["comparison"] = self.default.value
        elif self.mark == DiffMark.ADDED:
            diff_info["baseline"] = self.default.value
            diff_info["comparison"] = 0
        else:
            diff_info["baseline"] = self.baseline.value
            diff_info["comparison"] = self.comparison.value

        return diff_info

    @property
    def default(self) -> SpanNode:
        if self.mark in [DiffMark.CHANGED, DiffMark.UNCHANGED, DiffMark.ADDED]:
            return self.baseline

        if self.mark == DiffMark.REMOVED:
            return self.comparison

    def add_child(self, node: "DiffNode"):
        """Add a child node to the baseline node."""
        node.parent = self
        self.children.append(node)


@dataclass
class DiffGroup(Group):
    def should_add_to_group(self, adding: "SpanNode") -> bool:
        """Check if the adding node should be added to the group.

        For diff group, members should have the same mark and same sign of delta.
        """
        # no group if error occurs
        if adding.has_error or adding.children_have_error:
            return False

        if not self.candidates:
            return True

        equality = super().should_add_to_group(adding)

        adding_diff_node: Optional[DiffNode] = adding.extra_info.get("diff_node")
        last_candidate_diff_node: Optional[DiffNode] = self.candidates[-1].extra_info.get("diff_node")
        if None in [adding_diff_node, last_candidate_diff_node]:
            return equality

        equality = equality and adding_diff_node.mark == last_candidate_diff_node.mark
        # added or removed means all elements in members are same sign
        if adding_diff_node.mark in [DiffMark.REMOVED, DiffMark.ADDED]:
            return equality

        # check if the two nodes have the same sign
        def zero_cmp(a, b):
            return (a > b) - (a < b)

        def check_same_sign(a, b):
            return zero_cmp(a, 0) == zero_cmp(b, 0)

        return equality and check_same_sign(adding_diff_node.delta, last_candidate_diff_node.delta)

    should_add = should_add_to_group


@dataclass
class SimilarityMap:
    _map: Dict[DiffMark, int] = field(default_factory=lambda: defaultdict(int))

    def __str__(self):
        return str(self.percentage)

    def __repr__(self):
        return str(self)

    def add(self, mark: DiffMark):
        self._map[mark] += 1

    @property
    def percentage(self) -> float:
        hit, total = self.hit_and_total
        return hit / total

    @property
    def missed(self) -> int:
        hit, total = self.hit_and_total
        return total - hit

    @property
    def hit_and_total(self) -> tuple:
        hit = 0
        total = 0
        for k, v in self._map.items():
            if k in [DiffMark.CHANGED, DiffMark.UNCHANGED]:
                hit += v

            if k in [DiffMark.CHANGED, DiffMark.UNCHANGED, DiffMark.ADDED]:
                total += v

        return hit, total


@dataclass
class DiffTree:
    roots: List[DiffNode] = field(default_factory=list)
    config: TreeBuildingConfig = field(default_factory=TreeBuildingConfig.default)
    level_similarity_map: Dict[int, SimilarityMap] = field(default_factory=lambda: defaultdict(SimilarityMap))

    # id -> DiffNode, quick access for DiffNode
    _children_map: Dict[str, DiffNode] = field(default_factory=dict)

    def calculate_level_similarity(
        self, similarity_decrease_percentage: float = 30, max_missed_threshold: int = 3
    ) -> bool:
        def get_similarity_percentage(_level: int) -> float:
            """Get the similarity percentage for a level."""
            return (100 - _level * similarity_decrease_percentage) / 100

        for level, similarity_map in self.level_similarity_map.items():
            _, total = similarity_map.hit_and_total
            # if absolute count of missed lower than threshold, ignore
            if total > max_missed_threshold >= similarity_map.missed:
                continue

            if similarity_map.percentage < get_similarity_percentage(level):
                logger.info(
                    f"Level {level} has low similarity, "
                    f"{similarity_map.percentage} < {get_similarity_percentage(level)}"
                )
                return False

        return True

    def add_root(self, root: DiffNode):
        self.roots.append(root)
        self._children_map[root.default.id] = root
        self.level_similarity_map[root.default.level].add(root.mark)

    def add_node(self, parent: DiffNode, node: DiffNode):
        parent.add_child(node)
        self._children_map[node.default.id] = node
        self.level_similarity_map[node.default.level].add(node.mark)

    # TODO: make a general tree & node for deduplicating
    def get_node_by_id(self, node_id: str) -> Optional[DiffNode]:
        return self._children_map.get(node_id)

    def build_extras(self):
        """Building extras like TraceTree"""

        def build_diff_node_extras(node: DiffNode):
            """Building extras for diff node"""

            for child in node.children:
                build_diff_node_extras(child)

                if self.config.with_group:
                    node.default.grouping(child.default, group_class=DiffGroup)

            node.default.finalize_candidates()

        for root in self.roots:
            build_diff_node_extras(root)
