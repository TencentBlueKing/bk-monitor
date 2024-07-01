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
from apm_web.utils import divide_biscuit
from bkmonitor.utils.thread_backend import ThreadPool


@dataclass
class TreeConverter:
    """
    将 doris 查询出来的原始数据直接转为 FunctionTree 而不经过 ProfileConverter
    """

    # 每批解析 samples 的最大数量
    BATCH_EXECUTE_SIZE = 1000

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
                id="",
                name=ROOT_DISPLAY_NAME,
                system_name="",
                filename="",
                values=[],
            )
        )
        params = [(tree, g) for g in divide_biscuit(samples_info, self.BATCH_EXECUTE_SIZE)]
        pool = ThreadPool()
        pool.map_ignore_exception(self.build_tree, params)

        # 补充根节点
        for node in tree.function_node_map.values():
            if not node.has_parent:
                tree.root.children.append(node)

        # 不同数据类型的节点 value 计算方式有所不同
        ValueCalculator.calculate_nodes(tree, self.get_sample_type())

        self.tree = tree
        return self.tree

    def build_tree(self, tree: FunctionTree, samples):
        for sample in samples:
            value = int(sample["value"])
            parent = None
            stacktraces = json.loads(sample["stacktrace"])

            for stacktrace in reversed(stacktraces):
                if not stacktrace["lines"]:
                    # 将 parent 设置为空防止生成错误的调用关系
                    parent = None
                    continue

                for line in stacktrace["lines"]:
                    if not line:
                        parent = None
                        continue

                    key = FunctionNode.generate_id(line)
                    tree.lock.acquire()
                    if key not in tree.function_node_map:
                        node = FunctionNode(
                            id=key,
                            name=line["function"]["name"],
                            system_name=line["function"]["systemName"],
                            filename=line["function"]["fileName"],
                            values=[value],
                        )
                        if parent:
                            parent.add_child(node)

                        tree.function_node_map[key] = node
                    else:
                        node = tree.function_node_map[key]
                        node.add_value(value)
                    tree.lock.release()
                    parent = node
