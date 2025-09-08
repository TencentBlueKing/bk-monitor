"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import logging
from dataclasses import dataclass, field

from apm_web.profile.diagrams.base import ROOT_DISPLAY_NAME, FunctionNode, FunctionTree
from apm_web.profile.diagrams.tree_converter import TreeConverter

logger = logging.getLogger("root")


@dataclass
class EbpfConverter(TreeConverter):
    """
    ebpf 数据格式转换
    """

    sample_type: dict = field(default_factory=lambda: {"unit": "microseconds"})

    # deepflow 时间单位是微秒
    def empty(self) -> bool:
        return not bool(self.tree)

    def get_sample_type(self) -> dict:
        return self.sample_type

    def convert(self, raw: list, data_type: str) -> FunctionTree:
        """
        ebpf 的数据格式是平铺的列表 每个元素为字典 其格式为
            {
                'profile_location_str': '',
                'node_id': '',
                'parent_node_id': '',
                'self_value': 0,
                'total_value': 10101
            }
        """
        if not raw or len(raw) == 0:
            return self.tree
        if raw[0]["parent_node_id"] != "-1":
            raise ValueError(
                "Invalid data format: the first result of ebpf must be the root node with parent_node_id '-1'."
            )
        # 构建 FunctionTree
        tree = FunctionTree(
            root=FunctionNode(
                id=ROOT_DISPLAY_NAME,
                name=ROOT_DISPLAY_NAME,
                system_name="",
                filename="",
                values=[raw[0]["total_value"]],
                value=raw[0]["total_value"],
            ),
            map_root=FunctionNode(
                id=ROOT_DISPLAY_NAME,
                name=ROOT_DISPLAY_NAME,
                system_name="",
                filename="",
                values=[],
            ),
        )
        self.function_name_map = {}
        self.sample_type.update({"type": data_type})
        for result in raw:
            # # 创建 FunctionNode 对象并存储在 function_node_map 中 建立映射关系
            node = FunctionNode(
                id=result["node_id"],
                name=result["profile_location_str"],
                system_name="",  # 字段留空
                filename="",  # 字段留空
                value=result["total_value"],
                values=[result["self_value"]],
            )
            tree.function_node_map[node.id] = node
            if node.name not in self.function_name_map:
                self.function_name_map[node.name] = copy.deepcopy(node)
            else:
                self.function_name_map[node.name].add_value(result["self_value"])
                # 叠加调用值

        # 构建树结构 value 已经由 server 计算过 父子关系由 parent id 和 node id 可直接获得 server 已经计算过
        for result in raw:
            node_id = result["node_id"]
            parent_id = result["parent_node_id"]
            node = tree.function_node_map[node_id]
            graph_node = self.function_name_map[node.name]

            if tree.function_node_map.get(parent_id, None):
                # 检查是否有父节点
                parent_node = tree.function_node_map[parent_id]
                parent_node.add_child(node)
            else:
                # 如果没有父节点，则挂到根节点
                tree.root.add_child(node)

            # 构建图结构
            parent = tree.function_node_map.get(parent_id, None)
            # 增加父子关系 没有父节点则挂到根节点
            if not parent:
                tree.map_root.add_child(graph_node)
            else:
                self.function_name_map[parent.name].add_child(graph_node)

        self.tree = tree
        return self.tree
