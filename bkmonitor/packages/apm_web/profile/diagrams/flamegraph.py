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
from typing import Optional

from apm_web.profile.diagrams.base import FunctionNode
from apm_web.profile.diagrams.diff import DiffNode, ProfileDiffer
from apm_web.profile.diagrams.tree_converter import TreeConverter

logger = logging.getLogger("apm")


def diff_node_to_element(diff_node: Optional[DiffNode]) -> dict:
    return {
        **diff_node.default.to_dict(),
        "diff_info": diff_node.diff_info,
        "children": [diff_node_to_element(child) for child in diff_node.children],
    }


@dataclass
class FlamegraphDiagrammer:
    def draw(self, c: TreeConverter, **_) -> dict:
        def function_node_to_element(function_node: FunctionNode) -> dict:
            return {
                "id": function_node.id,
                "name": function_node.name,
                "value": function_node.value,
                "self": function_node.self_time,
                "children": [function_node_to_element(child) for child in function_node.children.values()],
            }

        root = {"name": "total", "value": c.tree.root.value, "children": [], "id": 0}
        for r in c.tree.root.children.values():
            root["children"].append(function_node_to_element(r))

        return {"flame_data": root}

    def diff(self, base_tree_c: TreeConverter, comp_tree_c: TreeConverter, **_) -> dict:
        diff_tree = ProfileDiffer.from_raw(base_tree_c, comp_tree_c).diff_tree()
        diff_tree_root = diff_tree.root
        if diff_tree_root is None:
            return {"flame_data": {}}

        flame_data = [
            {
                **diff_tree_root.default.to_dict(),
                "diff_info": diff_tree_root.diff_info,
                "children": [diff_node_to_element(child) for child in diff_tree_root.children],
            }
        ]

        if not flame_data:
            logger.info("flame graph no data")
            return {"flame_data": {}}
        return {"flame_data": flame_data[0]}
