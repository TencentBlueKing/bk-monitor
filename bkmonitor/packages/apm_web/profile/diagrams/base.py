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
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("apm")

ROOT_DISPLAY_NAME = "root"


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: str
    name: str
    system_name: str
    filename: str

    is_root: bool = False
    has_parent: bool = False
    children: List["FunctionNode"] = field(default_factory=list)
    value: int = 0
    values: List[int] = field(default=list)

    lock: threading.Lock = field(default=threading.Lock())

    @property
    def self_time(self) -> int:
        """self time"""
        sub = self.value - sum(x.value for x in self.children)
        return sub if sub > 0 else 0

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "self": self.self_time,
            "name": self.name,
            "system_name": self.system_name,
            "filename": self.filename,
        }

    def add_child(self, child):
        self.lock.acquire()
        child.has_parent = True
        self.children.append(child)
        self.lock.release()

    def add_value(self, value):
        self.lock.acquire()
        self.values.append(value)
        self.lock.release()

    @classmethod
    def generate_id(cls, stacktrace_line):
        """根据 sample 的堆栈信息生成功能节点的 ID"""
        return "".join(
            [
                stacktrace_line["function"]["systemName"],
                stacktrace_line["function"]["fileName"],
                stacktrace_line["function"]["name"],
            ]
        )


@dataclass
class FunctionTree:
    root: FunctionNode
    function_node_map: Dict[str, FunctionNode] = field(default_factory=dict)
    lock: threading.Lock = field(default=threading.Lock())

    def find_similar_child(self, other_child: "FunctionNode") -> Optional["FunctionNode"]:
        for node in self.function_node_map.values():
            if node.id == other_child.id:
                return node
        return None

    @classmethod
    def combine(cls, tree, other_tree, sample_type):
        """合并两个 FunctionTree 树"""

        def merge_node(node1, node2):
            node1.values.extend(node2.values)

            child_map = {child.id: child for child in node1.children}
            for child2 in node2.children:
                if child2.id in child_map:
                    merge_node(child_map[child2.id], child2)
                else:
                    node1.add_child(child2)

        for other_node_id, other_node in other_tree.function_node_map.items():
            if other_node_id in tree.function_node_map:
                node = tree.function_node_map[other_node_id]
                merge_node(node, other_node)
            else:
                parent_node = None
                if other_node.has_parent:
                    # 寻找 other_node 的 parent 节点
                    for possible_parent in other_tree.function_node_map.items():
                        if other_node in possible_parent.children:
                            parent_node = possible_parent
                            break

                if parent_node:
                    if parent_node.id in tree.function_node_map:
                        tree.function_node_map[parent_node.id].add_child(other_node)
                    else:
                        # 如果找不到父节点(tree 可能有问题正常情况下不会走到这里) 则添加到 root
                        tree.root.add_child(other_node)
                else:
                    # 如果没有父节点 则添加到 root
                    tree.root.add_child(other_node)

                tree.function_node_map[other_node.id] = other_node

        ValueCalculator.calculate_nodes(tree, sample_type)
        return tree


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
        for node in tree.function_node_map.values():
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
