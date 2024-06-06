"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from apm_web.profile.diagrams.base import FunctionNode, FunctionTree
from apm_web.profile.diagrams.tree_converter import TreeConverter

logger = logging.getLogger(__name__)


@dataclass
class ProfileDiffer:
    baseline: "FunctionTree"
    comparison: "FunctionTree"

    @classmethod
    def from_raw(
        cls,
        base_tree_converter: TreeConverter,
        diff_tree_converter: TreeConverter,
    ) -> "ProfileDiffer":
        return ProfileDiffer(base_tree_converter.tree, diff_tree_converter.tree)

    def _diff_node(self, diff_tree: "DiffTree", base: "FunctionNode", comp: "FunctionNode") -> "DiffNode":
        """Diff a node."""
        # If the root node is different, the whole tree is different
        if base.id != comp.id:
            # we don't need to diff the rest of the tree
            return DiffNode(base, comp, DiffMark.ADDED)

        # this node exists
        diff_node = DiffNode(base, comp, DiffMark.CHANGED if base.value != comp.value else DiffMark.UNCHANGED)

        for base_child in base.children:
            similar = self.comparison.find_similar_child(base_child)

            if similar is None:
                diff_tree.add_node(diff_node, DiffNode(base_child, None, DiffMark.ADDED))
                continue

            diff_tree.add_node(diff_node, self._diff_node(diff_tree, base_child, similar))

        return diff_node

    def diff_tree(self) -> "DiffTree":
        """Diff the two profile data."""

        diff_tree = DiffTree()

        if self.baseline.root and self.comparison.root:
            diff_tree.add_root(self._diff_node(diff_tree, self.baseline.root, self.comparison.root))

        return diff_tree


class DiffMark(Enum):
    """A mark for a diff node."""

    REMOVED = "removed"
    ADDED = "added"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass
class DiffNode:
    baseline: Optional[FunctionNode]
    comparison: Optional[FunctionNode]
    mark: DiffMark

    parent: Optional["DiffNode"] = None
    children: List["DiffNode"] = field(default_factory=list)

    @property
    def delta(self) -> Optional[float]:
        """Node delta as percentage."""
        if self.mark == DiffMark.CHANGED:
            if self.comparison.value > self.baseline.value:
                return -round(((self.comparison.value - self.baseline.value) / self.comparison.value), 4)
            else:
                return round(((self.baseline.value - self.comparison.value) / self.baseline.value), 4)
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

        diff_info["diff"] = self.delta
        return diff_info

    @property
    def default(self) -> FunctionNode:
        if self.mark in [DiffMark.CHANGED, DiffMark.UNCHANGED, DiffMark.ADDED]:
            return self.baseline

        if self.mark == DiffMark.REMOVED:
            return self.comparison

    def add_child(self, node: "DiffNode"):
        """Add a child node to the baseline node."""
        node.parent = self
        self.children.append(node)


@dataclass
class DiffTree:
    roots: List[DiffNode] = field(default_factory=list)

    # id -> DiffNode, quick access for DiffNode
    children_map: Dict[str, DiffNode] = field(default_factory=dict)

    def add_root(self, root: DiffNode):
        self.roots.append(root)
        self.children_map[root.default.id] = root

    def add_node(self, parent: DiffNode, node: DiffNode):
        parent.add_child(node)
        self.children_map[node.default.id] = node
