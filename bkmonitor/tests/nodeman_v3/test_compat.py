import pytest

from bkmonitor.nodeman_integration.v3.compat import (
    get_proxies,
    get_proxies_by_biz,
    ipchooser_host_detail,
    latest_enabled_plugin_version,
    plugin_exists,
    plugin_search_host_status,
)
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError


class FakeHostClient:
    def __init__(self, items=None):
        self.items = items
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        items = self.items or [
            {
                "bk_host_id": 101,
                "state": {"node_status": "running", "node_version": "2.0.0"},
            },
            {
                "bk_host_id": 102,
                "state": {"node_status": "unknown", "node_version": ""},
            },
        ]
        return {"total": len(items), "items": items}


class FakePluginClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        return {"total": len(self.items), "items": self.items}


def test_ipchooser_host_detail_maps_v3_host_state_to_legacy_alive_shape():
    client = FakeHostClient()
    result = ipchooser_host_detail(
        {
            "bk_tenant_id": "tenant-a",
            "host_list": [
                {"host_id": 101, "meta": {"bk_biz_id": 2}},
                {"host_id": 102, "meta": {"bk_biz_id": 2}},
            ],
            "scope_list": [{"scope_id": "2"}],
        },
        client=client,
    )

    assert result == [
        {"host_id": 101, "alive": 1, "version": "2.0.0"},
        {"host_id": 102, "alive": 0, "version": ""},
    ]
    payload, context = client.calls[0]
    assert payload == {
        "page": {"offset": 0, "limit": 2},
        "only_count": False,
        "exact_include_conditions": {"bk_host_id": [101, 102], "bk_biz_id": [2]},
    }
    assert context.bk_tenant_id == "tenant-a"
    assert context.bk_biz_id == 2


def test_plugin_exists_uses_exact_v3_plugin_name_query():
    client = FakePluginClient([{"name": "mysql_exporter"}])

    assert plugin_exists(
        bk_tenant_id="tenant-a",
        bk_biz_id=0,
        plugin_name="mysql_exporter",
        client=client,
    )
    payload, context = client.calls[0]
    assert payload == {
        "page": {"offset": 0, "limit": 2},
        "only_count": False,
        "exact_include_conditions": {"name": ["mysql_exporter"]},
    }
    assert context.bk_tenant_id == "tenant-a"


class FakePackageClient:
    def __init__(self):
        self.calls = []

    def list_plugin_releases(self, payload, *, context):
        self.calls.append((payload, context))
        return {
            "total": 3,
            "items": [
                {"release": {"version": "1.9.0"}},
                {"release": {"version": "1.10.0"}},
                {"release": {"version": "1.8.0"}},
            ],
        }


def test_latest_enabled_plugin_version_reads_nested_release_contract():
    client = FakePackageClient()

    assert (
        latest_enabled_plugin_version(
            bk_tenant_id="tenant-a",
            plugin_name="bk-collector",
            client=client,
        )
        == "1.10.0"
    )
    payload, context = client.calls[0]
    assert payload["exact_include_conditions"] == {"name": ["bk-collector"], "enabled": [True]}
    assert context.bk_tenant_id == "tenant-a"


class FakeProcessClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        return {"total": len(self.items), "items": self.items}


def test_plugin_search_host_status_joins_host_and_process_contracts():
    host_client = FakeHostClient()
    host_client.items = [
        {
            "bk_host_id": 101,
            "info": {
                "bk_biz_id": 2,
                "bk_networkarea_id": 3,
                "bk_host_innerip_list": ["10.0.0.1"],
                "bk_host_innerip_v6_list": [],
            },
            "state": {"node_status": "running"},
        }
    ]
    process_client = FakeProcessClient(
        [
            {
                "bk_host_id": 101,
                "plugin_name": "bkmonitorbeat",
                "process_info": {"version": "3.1.0", "status": "running"},
                "process_identity": {"setup_path": "/data/bkce"},
            }
        ]
    )

    assert plugin_search_host_status(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        bk_host_ids=[101],
        plugin_names=["bkmonitorbeat"],
        host_client=host_client,
        process_client=process_client,
    ) == [
        {
            "bk_host_id": 101,
            "bk_biz_id": 2,
            "bk_cloud_id": 3,
            "inner_ip": "10.0.0.1",
            "inner_ipv6": "",
            "status": "RUNNING",
            "plugin_status": [
                {
                    "name": "bkmonitorbeat",
                    "version": "3.1.0",
                    "status": "running",
                    "setup_path": "/data/bkce",
                }
            ],
        }
    ]


def test_plugin_search_host_status_rejects_partially_resolved_hosts():
    host_client = FakeHostClient(
        [
            {
                "bk_host_id": 101,
                "info": {"bk_biz_id": 2, "bk_networkarea_id": 3},
                "state": {"node_status": "running"},
            }
        ]
    )

    with pytest.raises(NodeManV3PayloadError, match=r"\[102\]"):
        plugin_search_host_status(
            bk_tenant_id="tenant-a",
            bk_biz_id=2,
            bk_host_ids=[101, 102],
            host_client=host_client,
            process_client=FakeProcessClient([]),
        )


class ProxyHostClient:
    def __init__(self):
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        conditions = payload["exact_include_conditions"]
        if "bk_biz_id" in conditions:
            return {
                "total": 1,
                "items": [{"bk_host_id": 201, "info": {"bk_biz_id": 2, "bk_networkarea_id": 3}}],
            }
        return {
            "total": 1,
            "items": [
                {
                    "bk_host_id": 301,
                    "info": {
                        "bk_biz_id": 1,
                        "bk_networkarea_id": 3,
                        "bk_host_innerip_list": ["10.0.0.3"],
                    },
                    "state": {"node_status": "running"},
                }
            ],
        }


def test_proxy_queries_use_host_role_and_business_network_areas():
    client = ProxyHostClient()

    assert get_proxies(bk_tenant_id="tenant-a", bk_cloud_id=3, client=client)[0]["bk_host_id"] == 301
    assert get_proxies_by_biz(bk_tenant_id="tenant-a", bk_biz_id=2, client=client)[0]["bk_host_id"] == 301
    assert client.calls[0][0]["exact_include_conditions"] == {
        "bk_networkarea_id": [3],
        "node_role": ["proxy"],
    }
    assert client.calls[1][0]["exact_include_conditions"] == {"bk_biz_id": [2]}
    assert client.calls[2][0]["exact_include_conditions"] == {
        "bk_networkarea_id": [3],
        "node_role": ["proxy"],
    }
