# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
from dataclasses import dataclass
from typing import Any

from apm_web.profile.diagrams.base import (
    ROOT_DISPLAY_NAME,
    FunctionNode,
    FunctionTree,
    ValueCalculator,
)


@dataclass
class TreeConverter:
    """
    将 doris 查询出来的原始数据直接转为 FunctionTree 而不经过 ProfileConverter
    """

    tree: FunctionTree = None
    sample_type: dict = None

    def empty(self) -> bool:
        return not bool(self.tree)

    def get_sample_type(self) -> dict:
        return self.sample_type

    def convert(self, raw: Any) -> FunctionTree:
        samples_info = raw["list"]
        if not samples_info:
            return self.tree

        first_item_sample_type = samples_info[0]["sample_type"].split("/")
        self.sample_type = {"type": first_item_sample_type[0], "unit": first_item_sample_type[1]}

        # 构建 FunctionTree
        tree = FunctionTree(
            root=FunctionNode(
                id=ROOT_DISPLAY_NAME,
                name=ROOT_DISPLAY_NAME,
                system_name="",
                filename="",
                values=[],
            ),
            map_root=FunctionNode(
                id=ROOT_DISPLAY_NAME,
                name=ROOT_DISPLAY_NAME,
                system_name="",
                filename="",
                values=[],
            ),
        )
        self.build_tree(tree, samples_info)

        # 不同数据类型的节点 value 计算方式有所不同
        ValueCalculator.calculate_nodes(tree, self.get_sample_type())

        self.tree = tree
        return self.tree

    @classmethod
    def build_tree(cls, tree: FunctionTree, samples):
        for sample in samples:
            value = int(sample["value"])
            parent = tree.root
            map_parent = tree.map_root
            stacktraces = json.loads(sample["stacktrace"])

            visited_node = set()
            for stacktrace in reversed(stacktraces):
                if not stacktrace["lines"]:
                    # 将 parent 设置为空防止生成错误的调用关系
                    parent = tree.root
                    map_parent = tree.map_root
                    continue

                for line in reversed(stacktrace["lines"]):
                    if not line:
                        parent = tree.root
                        map_parent = tree.map_root
                        continue

                    pure_line = FunctionNode.replace_invalid_char(line)
                    node_id = FunctionNode.generate_id(pure_line)

                    # 1. 构造树
                    if node_id in parent.children:
                        node = parent.children.get(node_id)
                        node.add_value(value)
                        parent = node
                    else:
                        node = FunctionNode(
                            id=node_id,
                            name=pure_line["function"]["name"],
                            system_name=pure_line["function"]["systemName"],
                            filename=pure_line["function"]["fileName"],
                            values=[value],
                        )
                        parent.add_child(node)
                        parent = node

                    # 2. 构造图
                    if node_id not in tree.function_node_map:
                        map_node = FunctionNode(
                            id=node_id,
                            name=pure_line["function"]["name"],
                            system_name=pure_line["function"]["systemName"],
                            filename=pure_line["function"]["fileName"],
                            values=[value],
                        )
                        tree.function_node_map[node_id] = map_node
                        map_parent.add_child(map_node)
                        map_parent = map_node
                    else:
                        map_node = tree.function_node_map[node_id]
                        if node_id not in visited_node:
                            map_node.add_value(value)
                        map_parent.add_child(map_node)
                        map_parent = map_node

                    visited_node.add(node_id)
