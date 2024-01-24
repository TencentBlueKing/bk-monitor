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
from io import BytesIO
from typing import Any, List

from graphviz import Digraph

from apm_web.profile.constants import CallGraphResponseDataMode
from apm_web.profile.converter import Converter
from apm_web.profile.diagrams.base import FunctionNode, FunctionTree


def build_edge_relation(node_list: List[FunctionNode]) -> list:
    edges = []
    queue = deque(node_list)
    while queue:
        node = queue.popleft()
        for child in node.children:
            edges.append({"source_id": node.id, "target_id": child.id, "value": child.value})
            queue.append(child)
    return edges


def generate_svg_data(data: dict):
    """
    生成 svg 图片数据
    :param data call_graph 数据
    """

    dot = Digraph(comment="The Round Table", format="svg")
    dot.attr("node", shape="rectangle")
    call_graph_data = data.get("call_graph_data", {})
    for node in call_graph_data.get("call_graph_nodes", []):
        ratio = 0.00 if data["call_graph_all"] == 0 else node["value"] / data["call_graph_all"]
        ratio_str = f"{ratio:.2%}"
        title = f"""
        {node["name"]}
        {node["self"]} of {node["value"]} ({ratio_str})
        """
        dot.node(str(node["id"]), label=title)

    for edge in call_graph_data.get("call_graph_relation", []):
        dot.edge(str(edge["source_id"]), str(edge["target_id"]), label=f'{edge["value"]} {data["unit"]}')

    svg_data = dot.pipe(format="svg")
    try:
        with BytesIO(svg_data) as svg_buffer:
            res = svg_buffer.read().decode()
    except Exception as e:
        raise ValueError(f"generate_svg_data, read call graph data failed , error: {e}")
    data["call_graph_data"] = res
    return data


@dataclass
class CallGraphDiagrammer:
    def draw(self, c: Converter, **options) -> Any:
        tree = FunctionTree.load_from_profile(c)
        nodes = list(tree.nodes_map.values())
        edges = build_edge_relation(tree.root.children)
        data = {
            "call_graph_data": {
                "call_graph_nodes": [
                    {"id": node.id, "name": node.display_name, "value": node.value, "self": node.self_time}
                    for node in nodes
                ],
                "call_graph_relation": edges,
            },
            "call_graph_all": tree.root.value,
        }
        if options.get("data_mode") and options.get("data_mode") == CallGraphResponseDataMode.IMAGE_DATA_MODE:
            return generate_svg_data(data)
        return data

    def diff(self, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        raise ValueError("CallGraph not support diff mode")
