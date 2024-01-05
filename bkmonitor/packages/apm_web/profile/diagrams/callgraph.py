"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import deque
from dataclasses import dataclass
from typing import Any, List

from apm_web.profile.converter import Converter
from apm_web.profile.diagrams.base import FunctionNode, FunctionTree


@dataclass
class CallGraphDiagrammer:
    @classmethod
    def build_edge_relation(cls, node_list: List[FunctionNode]) -> list:
        edges = []
        queue = deque(node_list)
        while queue:
            node = queue.popleft()
            for child in node.children:
                edges.append({"source_id": node.id, "target_id": child.id, "value": child.value})
                queue.append(child)
        return edges

    def draw(self, c: Converter, **options) -> Any:
        tree = FunctionTree.load_from_profile(c)
        nodes = list(tree.nodes_map.values())
        edges = self.build_edge_relation(tree.root.children)
        return {
            "call_graph_data": {
                "call_graph_nodes": [
                    {"id": node.id, "name": node.display_name, "value": node.value, "self": node.self_time}
                    for node in nodes
                ],
                "call_graph_relation": edges,
            },
            "call_graph_all": tree.root.value,
            **c.get_sample_type(),
        }

    @classmethod
    def diff(cls, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        # 结构保持一致性
        return {
            "call_graph_data": {"call_graph_nodes": [], "call_graph_relation": []},
            "call_graph_base_all": 0,
            "call_graph_diff_all": 0,
            **base_doris_converter.get_sample_type(),
        }
