from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.collecting.deploy.nodeman_v3.scopes import CollectDeployPolicyScopeBuilder


@pytest.mark.parametrize(
    "object_type, node_type, nodes, expected",
    [
        ("HOST", "INSTANCE", [{"bk_host_id": 42}, {"bk_host_id": 41}, {"bk_host_id": 41}], {"instance_ids": [41, 42]}),
        ("SERVICE", "INSTANCE", [{"bk_inst_id": 101}], {"instance_ids": [101]}),
        (
            "HOST",
            "TOPO",
            [{"bk_obj_id": "module", "bk_inst_id": 3}],
            {"paths": [{"topo_obj_id": "module", "topo_inst_id": 3}]},
        ),
        (
            "SERVICE",
            "TOPO",
            [{"bk_obj_id": "module", "bk_inst_id": 3}],
            {"paths": [{"topo_obj_id": "module", "topo_inst_id": 3}]},
        ),
        ("HOST", "SERVICE_TEMPLATE", [{"bk_inst_id": 8}], {"service_template_ids": [8]}),
        ("SERVICE", "SERVICE_TEMPLATE", [{"bk_inst_id": 8}], {"service_template_ids": [8]}),
        ("HOST", "SET_TEMPLATE", [{"bk_inst_id": 9}], {"set_template_ids": [9]}),
        ("SERVICE", "SET_TEMPLATE", [{"bk_inst_id": 9}], {"set_template_ids": [9]}),
        ("HOST", "DYNAMIC_GROUP", [{"bk_inst_id": "group-1"}], {"dynamic_group_ids": ["group-1"]}),
    ],
)
def test_declared_scope_is_preserved_without_expanding_cmdb_members(object_type, node_type, nodes, expected):
    # An empty CMDB facade makes unexpected target expansion fail immediately.
    builder = CollectDeployPolicyScopeBuilder(cmdb=SimpleNamespace())
    actual = builder.build(
        SimpleNamespace(target_object_type=object_type, bk_biz_id=2),
        SimpleNamespace(target_node_type=node_type, target_nodes=nodes),
    )
    assert actual == [
        {
            "type": node_type.lower(),
            "scope": {
                "granularity": "host" if object_type == "HOST" else "service_instance",
                "bk_biz_id": 2,
                **expected,
            },
        }
    ]


def test_ip_selection_resolves_only_identity_and_preserves_cloud(monkeypatch):
    calls = []
    cmdb = SimpleNamespace(
        get_host_by_ip=lambda **kwargs: calls.append(kwargs)
        or [
            SimpleNamespace(bk_host_id=41, bk_host_innerip="127.0.0.1", bk_cloud_id=0),
            SimpleNamespace(bk_host_id=42, bk_host_innerip="127.0.0.1", bk_cloud_id=1),
        ]
    )
    ids = CollectDeployPolicyScopeBuilder(cmdb=cmdb)._host_ids(
        [{"ip": "127.0.0.1", "bk_cloud_id": 0}, {"ip": "127.0.0.1", "bk_cloud_id": 1}],
        bk_biz_id=2,
    )
    assert ids == [41, 42]
    assert calls[0]["bk_biz_id"] == 2
    assert sorted(node["bk_cloud_id"] for node in calls[0]["ips"]) == [0, 1]


@pytest.mark.parametrize("nodes", [[], [{}], [{"bk_host_id": True}], [{"bk_host_id": 0}], [{"bk_host_id": "bad"}]])
def test_invalid_static_scope_is_rejected_before_writes(nodes):
    with pytest.raises(NodeManV3PayloadError):
        CollectDeployPolicyScopeBuilder(cmdb=SimpleNamespace()).build(
            SimpleNamespace(target_object_type="HOST", bk_biz_id=2),
            SimpleNamespace(target_node_type="INSTANCE", target_nodes=nodes),
        )


def test_unresolved_ip_is_not_silently_removed_from_scope():
    builder = CollectDeployPolicyScopeBuilder(cmdb=SimpleNamespace(get_host_by_ip=lambda **kwargs: []))
    with pytest.raises(NodeManV3PayloadError, match="could not be resolved"):
        builder._host_ids([{"ip": "127.0.0.1", "bk_cloud_id": 0}], bk_biz_id=2)
