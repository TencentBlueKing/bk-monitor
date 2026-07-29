"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from apm_web.profile.diagrams.table import TableDiagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter


def make_stacktrace(*root_to_leaf: str) -> str:
    """Doris stacktraces are stored leaf-first; TreeConverter reverses them when building the tree."""
    return json.dumps(
        [
            {
                "lines": [
                    {
                        "line": 1,
                        "function": {
                            "name": name,
                            "systemName": name,
                            "fileName": "repro.go",
                            "startLine": 1,
                        },
                    }
                ]
            }
            for name in reversed(root_to_leaf)
        ]
    )


def make_sample(value: int, timestamp: int, *root_to_leaf: str) -> dict:
    return {
        "value": str(value),
        "dtEventTimeStamp": str(timestamp),
        "sample_type": "inuse_objects/count",
        "stacktrace": make_stacktrace(*root_to_leaf),
    }


def get_map_node(converter: TreeConverter, name: str):
    return next(node for node in converter.tree.function_node_map.values() if node.name == name)


def test_sum_self_is_accumulated_from_leaf_samples():
    converter = TreeConverter()
    converter.convert(
        {
            "list": [
                make_sample(200, 1_000, "A"),
                make_sample(50, 1_000, "A", "shared"),
                make_sample(100, 1_000, "B", "shared"),
            ]
        },
        agg_method="SUM",
        agg_interval=1,
    )

    node_a = get_map_node(converter, "A")
    node_b = get_map_node(converter, "B")
    shared = get_map_node(converter, "shared")

    assert converter.tree.root.value == 350
    assert node_a.value == 250
    assert node_a.self_time == 200
    assert node_b.value == 100
    assert node_b.self_time == 0
    assert shared.value == 150
    assert shared.self_time == 150

    table_items = {item["name"]: item for item in TableDiagrammer().draw(converter)["table_data"]["items"]}
    assert table_items["A"]["self"] == 200


def test_recursive_function_total_is_deduplicated_but_leaf_self_is_retained():
    converter = TreeConverter()
    converter.convert(
        {"list": [make_sample(10, 1_000, "recursive", "recursive")]},
        agg_method="SUM",
        agg_interval=1,
    )

    map_node = get_map_node(converter, "recursive")
    assert map_node.value == 10
    assert map_node.self_time == 10
    assert map_node.children[map_node.id] is map_node

    outer_node = converter.tree.root.children[map_node.id]
    inner_node = outer_node.children[map_node.id]
    assert outer_node.value == 10
    assert outer_node.self_time == 0
    assert inner_node.value == 10
    assert inner_node.self_time == 10


def test_avg_uses_same_snapshot_denominator_for_total_and_self():
    converter = TreeConverter()
    converter.convert(
        {
            "list": [
                make_sample(100, 1_000, "A"),
                make_sample(100, 2_000, "A", "shared"),
            ]
        },
        agg_method="AVG",
        agg_interval=1,
    )

    node_a = get_map_node(converter, "A")
    shared = get_map_node(converter, "shared")

    assert converter.tree.root.value == 100
    assert node_a.value == 100
    assert node_a.self_time == 50
    assert shared.value == 50
    assert shared.self_time == 50
