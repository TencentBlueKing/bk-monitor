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
from typing import List, Optional

from django.utils.translation import ugettext_lazy as _

from apm_web.profile.diagrams.base import FunctionNode
from apm_web.profile.diagrams.diff import DiffNode
from apm_web.profile.diagrams.tree_converter import TreeConverter

logger = logging.getLogger("apm")


def function_node_to_element(function_node: FunctionNode, level=0) -> dict:
    return {
        "id": function_node.id,
        "name": function_node.name,
        "value": function_node.value,
        "self": function_node.self_time,
        "level": level,
        "children": [
            function_node_to_element(child, level + 1) for child in function_node.children
        ],  # 当function_node的children有两个child时，两个child都分别+1
    }


def diff_node_to_element(diff_node: Optional[DiffNode]) -> dict:
    return {
        **diff_node.default.to_dict(),
        "diff_info": diff_node.diff_info,
        "children": [diff_node_to_element(child) for child in diff_node.children],
    }


@dataclass
class GrafanaFlameDiagrammer:
    def convert(
        self,
        node: FunctionNode,
        level: int = 0,
        levels: List[int] = None,
        labels: List[str] = None,
        selfs: List[int] = None,
        values: List[int] = None,
    ):

        if levels is None:
            levels = []
        if labels is None:
            labels = []
        if selfs is None:
            selfs = []
        if values is None:
            values = []

        levels.append(level)
        labels.append(node.id)
        values.append(node.value)
        selfs.append(node.self_time)

        for c in node.children:
            self.convert(c, level + 1, levels, labels, selfs, values)

        return levels, labels, selfs, values

    def draw(self, c: TreeConverter, **_) -> dict:
        levels, labels, selfs, values = self.convert(c.tree.root)
        return {
            "flame_data": {
                "levels": levels,
                "labels": labels,
                "selfs": selfs,
                "values": values,
            }
        }

    def diff(self, base_tree_c: TreeConverter, diff_tree_c: TreeConverter, **kwargs) -> dict:
        raise ValueError(_("Grafana 模式下不支持对比 Profiling 视图"))
