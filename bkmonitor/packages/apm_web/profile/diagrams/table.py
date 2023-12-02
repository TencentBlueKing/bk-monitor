"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from dataclasses import dataclass

from apm_web.profile.converter import Converter

from .base import FunctionTree


@dataclass
class TableDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        tree = FunctionTree.load_from_profile(c)

        nodes = list(tree.nodes_map.values())
        total_nodes = sorted(nodes, key=lambda x: x.value, reverse=True)
        self_nodes = sorted(nodes, key=lambda x: x.self_time, reverse=True)

        return {
            "table_data": {
                "self": [{"id": x.id, "func": x.display_name, "value": x.self_time} for x in self_nodes],
                "total": [{"id": x.id, "func": x.display_name, "value": x.value} for x in total_nodes],
            },
            "all": tree.root.value,
            **c.get_sample_type(),
        }
