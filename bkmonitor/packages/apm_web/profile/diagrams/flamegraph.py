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
from dataclasses import dataclass

from apm_web.profile.converter import Converter
from apm_web.profile.diagrams.base import FunctionNode, FunctionTree

logger = logging.getLogger("apm")


def function_node_to_element_and_add_diff_info(function_node: FunctionNode, comparison_map: dict) -> dict:
    baseline = function_node.value
    comparison = comparison_map.get(function_node.display_name, {}).get("total", 0)
    diff = comparison - baseline
    diff_info = {"baseline": baseline, "comparison": comparison, "diff": diff}
    return {
        "id": function_node.id,
        "name": function_node.display_name,
        "value": function_node.value,
        "self": function_node.self_time,
        "diff_info": diff_info,
        "children": [
            function_node_to_element_and_add_diff_info(child, comparison_map) for child in function_node.children
        ],
    }


def function_node_to_element(function_node: FunctionNode) -> dict:
    return {
        "id": function_node.id,
        "name": function_node.display_name,
        "value": function_node.value,
        "self": function_node.self_time,
        "children": [function_node_to_element(child) for child in function_node.children],
    }


@dataclass
class FlamegraphDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        tree = FunctionTree.load_from_profile(c)

        root = {"name": "total", "value": tree.root.value, "children": [], "id": 0}
        for r in tree.root.children:
            root["children"].append(function_node_to_element(r))

        return {"flame_data": root, **c.get_sample_type()}

    @classmethod
    def diff(cls, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        baseline_tree = FunctionTree.load_from_profile(base_doris_converter)
        comparison_tree = FunctionTree.load_from_profile(diff_doris_converter)

        comparison_nodes = list(comparison_tree.nodes_map.values())

        comparison_map = {
            x.display_name: {"id": x.id, "name": x.display_name, "self": x.self_time, "total": x.value}
            for x in comparison_nodes
        }

        root = {
            "name": "total",
            "value": baseline_tree.root.value,
            "children": [],
            "id": 0,
            "diff_info": {"baseline": baseline_tree.root.value, "comparison": baseline_tree.root.value, "diff": 0},
        }
        for r in baseline_tree.root.children:
            root["children"].append(function_node_to_element_and_add_diff_info(r, comparison_map))

        return {"flame_data": root, **base_doris_converter.get_sample_type()}
