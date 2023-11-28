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

from .base import FunctionNode, FunctionTree

logger = logging.getLogger("apm")


def function_node_to_element(function_node: FunctionNode) -> dict:
    return {
        "id": function_node.id,
        "name": function_node.display_name,
        "value": function_node.value,
        "children": [function_node_to_element(child) for child in function_node.children],
    }


@dataclass
class FlamegraphDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        tree = FunctionTree.load_from_profile(c)

        root = {"name": "root", "value": tree.root.value, "children": [], "id": 0}
        for r in tree.root.children:
            root["children"].append(function_node_to_element(r))

        return {"flame_data": root, **c.get_sample_type()}
