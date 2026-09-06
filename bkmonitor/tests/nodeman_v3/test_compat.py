from bkmonitor.nodeman_integration.v3.compat import ipchooser_host_detail, plugin_exists


class FakeHostClient:
    def __init__(self):
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        return {
            "total": 2,
            "items": [
                {
                    "bk_host_id": 101,
                    "state": {"node_status": "running", "node_version": "2.0.0"},
                },
                {
                    "bk_host_id": 102,
                    "state": {"node_status": "unknown", "node_version": ""},
                },
            ],
        }


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
