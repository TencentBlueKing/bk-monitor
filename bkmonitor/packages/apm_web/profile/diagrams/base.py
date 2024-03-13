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
from apm_web.profile.models import Function


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: int
    value: int
    name: str
    system_name: str
    filename: str

    is_root: bool = False
    parent: Optional["FunctionNode"] = None
    children: List["FunctionNode"] = field(default_factory=list)

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

    def add_function_node(self, f: Function, v: int, parent: FunctionNode, converter: Converter) -> FunctionNode:
        """Add function node to tree"""
        node = FunctionNode(
            id=f.id,
            value=v,
            name=converter.get_string(f.name),
            system_name=converter.get_string(f.system_name),
            filename=converter.get_string(f.filename),
        )
        self.nodes_map[f.id] = node

        if parent is not None:
            node.parent = parent
            parent.children.append(node)

        return node

    @classmethod
    def load_from_profile(cls, converter: Converter) -> "FunctionTree":
        profile = converter.profile
        root = FunctionNode(
            id=0, value=0, is_root=True, name=FunctionNode.ROOT_DISPLAY_NAME, system_name="", filename=""
        )
        tree = cls(root=root)

        for sample in profile.sample:
            sample_value = sample.value[0]
            parent_node = None

            # "The leaf is at location_id[0]." from profile.proto
            # so build the tree reversely
            for location_id in reversed(sample.location_id):
                location = converter.get_location(location_id)

                for line in location.line:
                    node = tree.nodes_map.get(line.function_id)

                    if node is None:
                        function = converter.get_function(line.function_id)
                        node = tree.add_function_node(function, sample_value, parent_node, converter)
                    else:
                        node.value += sample_value

                    parent_node = node

        for _, node in tree.nodes_map.items():
            if not node.parent:
                node.parent = root
                root.value += node.value
                root.children.append(node)

        return tree

    def find_similar_child(self, other_child: "FunctionNode") -> Optional["FunctionNode"]:
        for node in self.nodes_map.values():
            if node.unique_together == other_child.unique_together:
                return node
        return None
