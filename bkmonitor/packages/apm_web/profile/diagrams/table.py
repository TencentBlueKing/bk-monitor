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
from apm_web.profile.diagrams.base import FunctionNode, FunctionTree


@dataclass
class TableDiagrammer:
    def draw(self, c: Converter, **options) -> dict:
        tree = FunctionTree.load_from_profile(c)

        nodes = list(tree.nodes_map.values())
        # 添加total节点
        total_node = FunctionNode(id=0, value=tree.root.value, name="total", filename="", system_name="")
        nodes.append(total_node)
        sort_map = {
            "name": lambda x: x.display_name,
            "self": lambda x: x.self_time,
            "total": lambda x: x.value,
            "location": lambda x: x.display_name,
        }

        sort = str(options.get("sort")).lower()
        sort_field = str(sort).replace("-", "")
        if sort and sort in ["-" + key for key in sort_map.keys()]:
            sorted_nodes = sorted(nodes, key=sort_map.get(sort_field), reverse=True)
        elif sort and sort in sort_map.keys():
            sorted_nodes = sorted(nodes, key=sort_map.get(sort_field))
        else:
            sorted_nodes = sorted(nodes, key=lambda x: x.value, reverse=True)
        return {
            "table_data": {
                "total": tree.root.value,
                "items": [
                    {"id": x.id, "name": x.display_name, "self": x.self_time, "total": x.value} for x in sorted_nodes
                ],
            }
        }

    def diff(self, base_doris_converter: Converter, diff_doris_converter: Converter, **options) -> dict:
        baseline_tree = FunctionTree.load_from_profile(base_doris_converter)
        comparison_tree = FunctionTree.load_from_profile(diff_doris_converter)

        baseline_nodes = list(baseline_tree.nodes_map.values())
        comparison_nodes = list(comparison_tree.nodes_map.values())

        baseline_map = {
            x.display_name: {"id": x.id, "name": x.display_name, "self": x.self_time, "value": x.value}
            for x in baseline_nodes
        }
        comparison_map = {
            x.display_name: {"id": x.id, "name": x.display_name, "self": x.self_time, "value": x.value}
            for x in comparison_nodes
        }

        # todo 后续肯能展示字段按需调整
        baseline_all = baseline_tree.root.value
        comparison_all = comparison_tree.root.value
        table_data = [
            {
                "name": "total",
                "baseline_node": {"id": 0, "name": "total", "self": 0, "value": baseline_all},
                "comparison_node": {"id": 0, "name": "total", "self": 0, "value": comparison_all},
                "baseline": baseline_all,
                "comparison": comparison_all,
                "diff": comparison_all - baseline_all,
            }
        ]
        default_comparison_node = {"id": 0, "name": "", "self": 0, "value": 0}
        for name in baseline_map.keys():
            baseline_node = baseline_map.get(name, {})
            comparison_node = comparison_map.get(name, default_comparison_node)
            baseline = baseline_node.get("value", 0)
            comparison = comparison_node.get("value", 0)
            diff = comparison - baseline
            table_data.append(
                {
                    "name": name,
                    "baseline_node": baseline_node,
                    "comparison_node": comparison_node,
                    "baseline": baseline,
                    "comparison": comparison,
                    "diff": diff,
                }
            )

        # 排序逻辑 对比图 table 数据 TODO
        sort = str(options.get("sort")).lower()
        sort_field = str(sort).replace("-", "")
        if sort and sort_field in ():
            pass

        sort_table_data = sorted(table_data, key=lambda x: x["baseline"], reverse=True)

        return {
            "table_data": sort_table_data,
            "table_baseline_all": baseline_all,
            "table_comparison_all": comparison_all,
        }
