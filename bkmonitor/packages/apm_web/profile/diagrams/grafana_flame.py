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
from collections import OrderedDict
from dataclasses import dataclass
from typing import List

from django.utils.translation import gettext_lazy as _

from apm_web.profile.diagrams.base import FunctionNode
from apm_web.profile.diagrams.tree_converter import TreeConverter

logger = logging.getLogger("apm")


@dataclass
class GrafanaFlameDiagrammer:
    default_unit = "int64"
    grafana_unit_mapping = {
        "nanoseconds": "ns",
        "bytes": "bytes",
    }

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

        for c in node.children.values():
            self.convert(c, level + 1, levels, labels, selfs, values)

        return levels, labels, selfs, values

    @classmethod
    def convert_to_string_table(cls, labels):
        """将列表转为 stringTable 格式"""
        values = OrderedDict()
        indices = []
        for s in labels:
            if s not in values:
                values[s] = len(values)
            indices.append(values[s])
        return indices, list(values.keys())

    def draw(self, c: TreeConverter, **_) -> dict:
        levels, labels, selfs, values = self.convert(c.tree.root)
        label_indices, label_enums = self.convert_to_string_table(labels)

        unit = c.get_sample_type().get("unit")
        unit = self.grafana_unit_mapping.get(unit, self.default_unit)

        return {
            "frame_data": {
                "schema": {
                    "name": "response",
                    "refId": "profile",
                    "meta": {"typeVersion": [0, 0], "preferredVisualisationType": "flamegraph"},
                    "fields": [
                        {"name": "level", "type": "number", "typeInfo": {"frame": "int64"}},
                        {"name": "value", "type": "number", "typeInfo": {"frame": "int64"}, "config": {"unit": unit}},
                        {"name": "self", "type": "number", "typeInfo": {"frame": "int64"}, "config": {"unit": unit}},
                        {
                            "name": "label",
                            "type": "enum",
                            "typeInfo": {"frame": "enum"},
                            "config": {"type": {"enum": {"text": label_enums}}},
                        },
                    ],
                },
                "data": {
                    "values": [
                        levels,
                        values,
                        selfs,
                        label_indices,
                    ]
                },
            }
        }

    def diff(self, base_tree_c: TreeConverter, diff_tree_c: TreeConverter, **kwargs) -> dict:
        raise ValueError(_("Grafana 模式下不支持对比 Profiling 视图"))
