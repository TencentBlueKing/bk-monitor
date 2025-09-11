"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

    @classmethod
    def _align_agg_interval(cls, t, interval):
        return int(t / interval) * interval

    def convert(self, raw: Any, agg_method: str | None = None, agg_interval: int = 60) -> FunctionTree:
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
        self.build_tree(tree, samples_info, agg_method, agg_interval)

        # 计算出一共有多少个时间点的数据，相同时间点的数据只算一次
        snapshot_len = len(
            {self._align_agg_interval(int(s["dtEventTimeStamp"]), agg_interval * 1000) for s in samples_info}
        )
        # 不同数据类型的节点 value 计算方式有所不同
        ValueCalculator.calculate_nodes(tree, self.get_sample_type(), snapshot_len, agg_method)

        self.tree = tree
        return self.tree

    @classmethod
    def build_tree(cls, tree: FunctionTree, samples, agg_method=None, agg_interval=60):
        if agg_method == "LAST":
            # 只保留最后一个时间戳的所有 sample 数据
            interval = agg_interval * 1000
            last_snapshot = max({cls._align_agg_interval(int(s["dtEventTimeStamp"]), interval) for s in samples})
            samples = [
                s for s in samples if cls._align_agg_interval(int(s["dtEventTimeStamp"]), interval) == last_snapshot
            ]

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
                            parent=parent,
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
                            parent=map_parent,
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
