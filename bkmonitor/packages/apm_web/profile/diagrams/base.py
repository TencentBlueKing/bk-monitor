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

from apm_web.profile.models import Function, Profile


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: int
    value: int
    is_root: bool = False
    parent: Optional["FunctionNode"] = None
    children: List["FunctionNode"] = field(default_factory=list)

    _function: Optional[Function] = None
    ROOT_DISPLAY_NAME: ClassVar[str] = "root"

    @property
    def display_name(self) -> str:
        """display name"""
        if self.is_root:
            return self.ROOT_DISPLAY_NAME

        return self._function.name


@dataclass
class FunctionTree:
    """Function based flame tree"""

    root: FunctionNode

    nodes_map: Dict[int, FunctionNode] = field(default_factory=dict)

    def add_function_node(self, f: Function, v: int, parent: FunctionNode) -> FunctionNode:
        """Add function node to tree"""
        node = FunctionNode(id=f.id, value=v, _function=f)
        self.nodes_map[f.id] = node

        if parent is not None:
            node.parent = parent
            parent.children.append(node)

        return node

    @classmethod
    def load_from_profile(cls, profile: "Profile") -> "FunctionTree":
        root = FunctionNode(id=0, value=0, is_root=True)
        tree = cls(root=root)

        for sample in profile.samples:
            sample_value = sample.values[0]
            parent_node = None
            for location in sample.locations:
                # 同一个 Location 下的 Line 列表形成一个调用关系
                for line in location.lines:
                    node = tree.nodes_map.get(line.function.id)
                    if node is None:
                        node = tree.add_function_node(line.function, sample_value, parent_node)
                    else:
                        node.value += sample_value

                    parent_node = node

        for _, node in tree.nodes_map.items():
            if not node.parent:
                node.parent = root
                root.value += node.value
                root.children.append(node)

        return tree
