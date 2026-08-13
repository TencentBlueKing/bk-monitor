"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from monitor_web.scene_view.resources import host as host_resources


def build_topo_tree(bk_obj_id: str, bk_inst_id: int, child_count: int):
    node = SimpleNamespace(
        bk_obj_name={"biz": "业务", "set": "集群", "module": "模块"}[bk_obj_id],
        bk_inst_name=f"{bk_obj_id}-{bk_inst_id}",
        child=[object() for _ in range(child_count)],
    )
    return SimpleNamespace(get_all_nodes_with_relation=lambda: {f"{bk_obj_id}|{bk_inst_id}": node})


def result_value(result: list[dict], name: str):
    return next(item["value"] for item in result if item["name"] == name)


def test_get_node_info_queries_all_unique_hosts_for_biz(monkeypatch):
    """业务根节点应查询业务全量唯一主机，不能把 biz 当作普通拓扑目标传给 CMDB。"""
    host_query_calls = []
    monkeypatch.setattr(host_resources.api.cmdb, "get_topo_tree", lambda **_kwargs: build_topo_tree("biz", 2, 3))
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_topo_node",
        lambda **kwargs: host_query_calls.append(kwargs) or [object(), object()],
    )

    result = host_resources.GetHostOrTopoNodeDetailResource.get_node_info(2, "biz", 2)

    assert host_query_calls == [{"bk_biz_id": 2}]
    assert result_value(result, "子级数量") == 3
    assert result_value(result, "主机数量") == 2


@pytest.mark.parametrize(
    ("bk_obj_id", "bk_inst_id", "child_count", "host_count", "expected_child_count"),
    [
        ("set", 3, 2, 3, 2),
        ("module", 4, 0, 2, 2),
    ],
)
def test_get_node_info_keeps_set_and_module_target_query(
    monkeypatch, bk_obj_id, bk_inst_id, child_count, host_count, expected_child_count
):
    """集群和模块仍应按原拓扑目标查询，保留各自的子级数量语义。"""
    host_query_calls = []
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_topo_tree",
        lambda **_kwargs: build_topo_tree(bk_obj_id, bk_inst_id, child_count),
    )
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_topo_node",
        lambda **kwargs: host_query_calls.append(kwargs) or [object() for _ in range(host_count)],
    )
    monkeypatch.setattr(host_resources.api.cmdb, "get_module", lambda **_kwargs: [])

    result = host_resources.GetHostOrTopoNodeDetailResource.get_node_info(2, bk_obj_id, bk_inst_id)

    assert host_query_calls == [{"bk_biz_id": 2, "topo_nodes": {bk_obj_id: [bk_inst_id]}}]
    assert result_value(result, "子级数量") == expected_child_count
    assert result_value(result, "主机数量") == host_count
