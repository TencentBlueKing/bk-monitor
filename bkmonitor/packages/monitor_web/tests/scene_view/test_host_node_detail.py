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
from rest_framework.exceptions import ValidationError

from monitor_web.performance import resources as performance_resources
from monitor_web.scene_view.resources import host as host_resources


def build_topo_tree(bk_obj_id: str, bk_inst_id: int, child_count: int):
    node = SimpleNamespace(
        bk_obj_id=bk_obj_id,
        bk_inst_id=bk_inst_id,
        bk_obj_name={"biz": "业务", "set": "集群", "module": "模块"}[bk_obj_id],
        bk_inst_name=f"{bk_obj_id}-{bk_inst_id}",
        child=[object() for _ in range(child_count)],
    )
    node.get_all_nodes_with_relation = lambda: {f"{bk_obj_id}|{bk_inst_id}": node}
    return node


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


def read_detail(endpoint, bk_biz_id, bk_obj_id, bk_inst_id):
    params = {"bk_biz_id": bk_biz_id, "bk_obj_id": bk_obj_id, "bk_inst_id": bk_inst_id}
    if endpoint == "scene":
        return host_resources.GetHostOrTopoNodeDetailResource.get_node_info(**params)
    return performance_resources.HostTopoNodeDetailResource().perform_request(params)


@pytest.fixture
def detail_queries(monkeypatch):
    calls = SimpleNamespace(hosts=[], strategies=[], alarms=[], modules=[])
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_topo_node",
        lambda **kwargs: calls.hosts.append(kwargs) or [object(), object()],
    )
    monkeypatch.setattr(host_resources.api.cmdb, "get_module", lambda **kwargs: calls.modules.append(kwargs) or [])
    monkeypatch.setattr(
        performance_resources.resource.cc,
        "get_topo_strategy_count",
        lambda **kwargs: calls.strategies.append(kwargs) or (1, 0),
    )
    monkeypatch.setattr(
        performance_resources.HostTopoNodeDetailResource,
        "get_alarm_count",
        staticmethod(lambda bk_biz_id, hosts: calls.alarms.append(bk_biz_id) or 0),
    )
    return calls


@pytest.mark.parametrize("endpoint", ["scene", "legacy"])
@pytest.mark.parametrize(("space_id", "node_id"), [(2, 2), (-100, -100), (-100, 2)])
def test_detail_resolves_business_root_without_replacing_space(
    monkeypatch, detail_queries, endpoint, space_id, node_id
):
    topo_calls = []
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_topo_tree",
        lambda **kwargs: topo_calls.append(kwargs) or build_topo_tree("biz", 2, 3),
    )

    result = read_detail(endpoint, space_id, "biz", node_id)

    assert topo_calls == [{"bk_biz_id": space_id}]
    assert detail_queries.hosts == [{"bk_biz_id": space_id}]
    if endpoint == "scene":
        assert result_value(result, "节点ID") == 2
        assert result_value(result, "节点名称") == "biz-2"
        assert result_value(result, "子级数量") == 3
        assert result_value(result, "主机数量") == 2
    else:
        assert result["bk_inst_id"] == 2
        assert result["bk_inst_name"] == "biz-2"
        assert result["child_count"] == 3
        assert result["host_count"] == 2
        assert result["alarm_strategy"] == {"enabled": 1, "disabled": 0}
        assert detail_queries.strategies == [{"bk_biz_id": space_id, "bk_obj_id": "biz", "bk_inst_id": 2}]
        assert detail_queries.alarms == [space_id]


@pytest.mark.parametrize("endpoint", ["scene", "legacy"])
def test_detail_keeps_unrelated_space_empty_root(monkeypatch, detail_queries, endpoint):
    monkeypatch.setattr(host_resources.api.cmdb, "get_topo_tree", lambda **kwargs: build_topo_tree("biz", -100, 0))
    monkeypatch.setattr(host_resources.api.cmdb, "get_host_by_topo_node", lambda **kwargs: [])

    result = read_detail(endpoint, -100, "biz", -100)

    if endpoint == "scene":
        assert result_value(result, "节点ID") == -100
        assert result_value(result, "子级数量") == 0
        assert result_value(result, "主机数量") == 0
    else:
        assert result["bk_inst_id"] == -100
        assert result["child_count"] == 0
        assert result["host_count"] == 0


@pytest.mark.parametrize("endpoint", ["scene", "legacy"])
@pytest.mark.parametrize(("bk_obj_id", "node_id", "child_count"), [("set", 3, 1), ("module", 4, 0)])
def test_detail_keeps_non_business_node_identity(
    monkeypatch, detail_queries, endpoint, bk_obj_id, node_id, child_count
):
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_topo_tree",
        lambda **kwargs: build_topo_tree(bk_obj_id, node_id, child_count),
    )

    result = read_detail(endpoint, -100, bk_obj_id, node_id)

    assert detail_queries.hosts == [{"bk_biz_id": -100, "topo_nodes": {bk_obj_id: [node_id]}}]
    if endpoint == "scene":
        assert result_value(result, "节点ID") == node_id
        assert result_value(result, "节点名称") == f"{bk_obj_id}-{node_id}"
        assert result_value(result, "子级数量") == (2 if bk_obj_id == "module" else child_count)
    else:
        assert result["bk_inst_id"] == node_id
        assert result["bk_inst_name"] == f"{bk_obj_id}-{node_id}"
        assert result["child_count"] == (2 if bk_obj_id == "module" else child_count)


@pytest.mark.parametrize("endpoint", ["scene", "legacy"])
@pytest.mark.parametrize("bk_obj_id", ["set", "module"])
def test_detail_returns_empty_for_missing_node(monkeypatch, detail_queries, endpoint, bk_obj_id):
    monkeypatch.setattr(host_resources.api.cmdb, "get_topo_tree", lambda **kwargs: build_topo_tree("biz", 2, 0))

    assert read_detail(endpoint, -100, bk_obj_id, 999) == ([] if endpoint == "scene" else {})
    assert detail_queries.hosts == []
    assert detail_queries.strategies == []
    assert detail_queries.alarms == []
    assert detail_queries.modules == []


@pytest.mark.parametrize("endpoint", ["scene", "legacy"])
@pytest.mark.parametrize(("space_id", "node_id"), [(2, 999), (-100, 999), (-100, -101)])
def test_detail_rejects_other_business_root(monkeypatch, detail_queries, endpoint, space_id, node_id):
    monkeypatch.setattr(host_resources.api.cmdb, "get_topo_tree", lambda **kwargs: build_topo_tree("biz", 2, 0))

    with pytest.raises(ValidationError):
        read_detail(endpoint, space_id, "biz", node_id)

    assert detail_queries.hosts == []
    assert detail_queries.strategies == []
    assert detail_queries.alarms == []
