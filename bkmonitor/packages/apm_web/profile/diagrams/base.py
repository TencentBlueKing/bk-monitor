"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional

from apm_web.profile.converter import Converter


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: int
    name: str
    system_name: str
    filename: str

    is_root: bool = False
    parent: Optional["FunctionNode"] = None
    children: List["FunctionNode"] = field(default_factory=list)
    value: int = 0
    values: List[int] = field(default=list)
    ROOT_DISPLAY_NAME: ClassVar[str] = "root"

    @property
    def self_time(self) -> int:
        """self time"""
        sub = self.value - sum(x.value for x in self.children)
        return sub if sub > 0 else 0

    @property
    def display_name(self) -> str:
        """display name"""
        if self.is_root:
            return self.ROOT_DISPLAY_NAME

        return self.name

    @property
    def unique_together(self) -> tuple:
        return self.name, self.system_name, self.filename

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "self": self.self_time,
            "name": self.display_name,
            "system_name": self.system_name,
            "filename": self.filename,
        }


@dataclass
class FunctionTree:
    """Function based flame tree"""

    root: FunctionNode

    nodes_map: Dict[int, FunctionNode] = field(default_factory=dict)

    def add_function_node(self, function_id: int, v: int, parent: FunctionNode, converter: Converter) -> FunctionNode:
        """Add function node to tree"""
        f = converter.get_function(function_id)
        node = FunctionNode(
            id=f.id,
            name=converter.get_string(f.name),
            system_name=converter.get_string(f.system_name),
            filename=converter.get_string(f.filename),
            values=[v],
        )
        self.nodes_map[f.id] = node

        if parent:
            node.parent = parent
            parent.children.append(node)

        return node

    @classmethod
    def load_from_profile(cls, converter: Converter) -> "FunctionTree":
        root = FunctionNode(
            id=0,
            is_root=True,
            name=FunctionNode.ROOT_DISPLAY_NAME,
            system_name="",
            filename="",
            values=[],
        )
        tree = cls(root=root)

        for sample in converter.profile.sample:
            value = sample.value[0]
            parent = None

            for stacktrace_id in reversed(sample.location_id):
                stacktrace = converter.get_location(stacktrace_id)
                if not stacktrace.line:
                    parent = None
                    continue

                for line in stacktrace.line:
                    if not line:
                        parent = None
                        continue

                    if line.function_id not in tree.nodes_map:
                        node = tree.add_function_node(line.function_id, value, parent, converter)
                    else:
                        node = tree.nodes_map[line.function_id]
                        node.values.append(value)
                    parent = node

        for node in tree.nodes_map.values():
            if not node.parent:
                node.parent = root
                root.children.append(node)

        ValueCalculator.calculate_nodes(tree, converter.get_sample_type())

        return tree

    def find_similar_child(self, other_child: "FunctionNode") -> Optional["FunctionNode"]:
        for node in self.nodes_map.values():
            if node.unique_together == other_child.unique_together:
                return node
        return None


class ValueCalculator:
    @classmethod
    def mapping(cls):
        return {
            "goroutine": {
                "count": cls.GoroutineCount,
            }
        }

    @classmethod
    def calculate_nodes(cls, tree, sample_type):
        c = cls.mapping().get(sample_type["type"], {}).get(sample_type["unit"], cls.Default)
        for node in tree.nodes_map.values():
            node.value = c.calculate(node.values)

        tree.root.value = cls.adjust_node_values(tree.root)

    @classmethod
    def adjust_node_values(cls, node: FunctionNode):
        if not node.children:
            return node.value

        total_child_value = sum(cls.adjust_node_values(child) for child in node.children)
        node.value = max(node.value, total_child_value)
        return node.value

    class GoroutineCount:
        type = "goroutine"
        unit = "count"

        @classmethod
        def calculate(cls, values):
            if not values:
                return 0

            return int(sum(values) / len(values))

    class Default:
        @classmethod
        def calculate(cls, values):
            return sum(values)
