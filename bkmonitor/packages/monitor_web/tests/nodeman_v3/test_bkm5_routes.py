from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apm.core.application_config import ApplicationConfig, SubscriptionConfig
from apm_web.meta.plugin.log_trace_plugin_config import LogTracePluginConfig
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from metadata.models.custom_report.subscription_config import CustomReportSubscription
from metadata.models.ping_server import PingServerSubscriptionConfig
from monitor_web.nodeman_integration.v3.policy import DeployPolicySubmission


class EmptySubscriptionQuerySet:
    def __init__(self):
        self.update_calls = []

    def first(self):
        return None

    def update_or_create(self, **kwargs):
        self.update_calls.append(kwargs)


class StaticSubscriptionManager:
    def __init__(self, queryset):
        self.queryset = queryset
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self.queryset


class RecordingPolicyService:
    def __init__(self):
        self.calls = []

    def ensure(self, **kwargs):
        self.calls.append(kwargs)
        return DeployPolicySubmission(binding_id=71, operation_id="operation-71", prepared=True)


def test_apm_application_config_routes_positive_deploy_to_v3(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    queryset = EmptySubscriptionQuerySet()
    monkeypatch.setattr(SubscriptionConfig, "objects", StaticSubscriptionManager(queryset))
    service = RecordingPolicyService()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManV3PolicyService",
        lambda: service,
    )
    application = SimpleNamespace(pk=7, bk_biz_id=2, bk_tenant_id="tenant-a", app_name="demo")
    config = ApplicationConfig.__new__(ApplicationConfig)
    config._application = application

    result = config.deploy("tenant-a", {"receiver": "otlp"}, [11])

    assert result == 71
    assert service.calls[0]["resource_key"] == "7"
    assert service.calls[0]["execution_bk_tenant_id"] == "tenant-a"
    assert queryset.update_calls[0]["defaults"]["config"]["node_man_backend"] == "v3"


def test_apm_log_trace_dynamic_scope_is_preserved_for_v3_policy(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    service = RecordingPolicyService()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManV3PolicyService",
        lambda: service,
    )
    application = SimpleNamespace(pk=7, bk_biz_id=2, bk_tenant_id="tenant-a")
    plugin_config = {
        "bk_biz_id": 2,
        "bk_data_id": 1001,
        "target_node_type": "DYNAMIC_GROUP",
        "target_object_type": "HOST",
        "target_nodes": [{"dynamic_group_id": "group-1"}],
        "data_encoding": "UTF-8",
        "paths": ["/var/log/demo.log"],
    }

    result = LogTracePluginConfig().release_log_trace_config(
        plugin_config,
        {"token": "token", "host": "collector.example"},
        application=application,
    )

    assert service.calls[0]["scope"] == {
        "bk_biz_id": 2,
        "node_type": "DYNAMIC_GROUP",
        "object_type": "HOST",
        "nodes": [{"dynamic_group_id": "group-1"}],
    }
    assert result["subscription_id"] == 71
    assert result["node_man_backend"] == "v3"


class DataIdQuerySet:
    def __init__(self, existing):
        self.existing = existing

    def first(self):
        return self.existing


class DataIdManager:
    def __init__(self, existing_by_data_id):
        self.existing_by_data_id = existing_by_data_id

    def filter(self, **kwargs):
        return DataIdQuerySet(self.existing_by_data_id.get(kwargs["bk_data_id"]))


def test_custom_report_batch_preflights_every_data_id_before_first_v3_write(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    existing_v2 = SimpleNamespace(config={}, subscription_id=81)
    monkeypatch.setattr(CustomReportSubscription, "objects", DataIdManager({1002: existing_v2}))
    create_or_update = Mock()
    monkeypatch.setattr(CustomReportSubscription, "create_or_update_config", create_or_update)

    with pytest.raises(NodeManV3PayloadError, match="V2 subscription"):
        CustomReportSubscription.create_subscription(
            bk_tenant_id="tenant-a",
            bk_biz_id=2,
            data_id_configs=[({"bk_data_id": 1001}, "json"), ({"bk_data_id": 1002}, "json")],
            bk_host_ids=[11],
        )

    create_or_update.assert_not_called()


class IterablePingQuerySet:
    def __init__(self, configs):
        self.configs = configs

    def filter(self, **kwargs):
        return self

    def __iter__(self):
        return iter(self.configs)


class RecordingPingManager(IterablePingQuerySet):
    def __init__(self):
        super().__init__([])
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs)


def test_ping_server_batch_preflights_every_host_before_first_v3_write(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    monkeypatch.setattr(
        "metadata.models.ping_server.transaction.get_connection",
        lambda: SimpleNamespace(in_atomic_block=True),
    )
    monkeypatch.setattr("metadata.models.ping_server.is_ipv6_biz", lambda _bk_biz_id: False)
    monkeypatch.setattr(
        "metadata.models.ping_server.api.cmdb.get_host_without_biz",
        lambda **_kwargs: {"hosts": []},
    )
    existing_v2 = SimpleNamespace(
        bk_host_id=12,
        bk_biz_id=2,
        ip="host-12.example",
        config={},
        subscription_id=82,
    )
    monkeypatch.setattr(
        PingServerSubscriptionConfig,
        "objects",
        IterablePingQuerySet([existing_v2]),
    )
    service = Mock()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManV3PolicyService",
        service,
    )

    with pytest.raises(NodeManV3PayloadError, match="V2 subscription"):
        PingServerSubscriptionConfig.create_subscription(
            bk_tenant_id="tenant-a",
            bk_cloud_id=3,
            items={11: [], 12: []},
            target_hosts=[
                {"bk_host_id": 11, "bk_biz_id": 2, "ip": "host-11.example", "ipv6": ""},
                {"bk_host_id": 12, "bk_biz_id": 2, "ip": "host-12.example", "ipv6": ""},
            ],
            plugin_name="bk-collector",
        )

    service.assert_not_called()


def test_ping_server_policy_name_isolated_by_target_business(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    monkeypatch.setattr(
        "metadata.models.ping_server.transaction.get_connection",
        lambda: SimpleNamespace(in_atomic_block=True),
    )
    monkeypatch.setattr("metadata.models.ping_server.is_ipv6_biz", lambda _bk_biz_id: False)
    monkeypatch.setattr(
        "metadata.models.ping_server.api.cmdb.get_host_without_biz",
        lambda **_kwargs: {"hosts": []},
    )
    manager = RecordingPingManager()
    monkeypatch.setattr(PingServerSubscriptionConfig, "objects", manager)
    service = RecordingPolicyService()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManV3PolicyService",
        lambda: service,
    )
    host = {"bk_host_id": 11, "bk_biz_id": 2, "ip": "host-11.example", "ipv6": ""}

    for bk_biz_id in (11, 12):
        PingServerSubscriptionConfig.create_subscription(
            bk_tenant_id="tenant-a",
            bk_cloud_id=3,
            items={11: []},
            target_hosts=[host],
            plugin_name="bk-collector",
            bk_biz_id=bk_biz_id,
        )

    assert [call["policy_name"] for call in service.calls] == [
        "bkm-ping-server-11-3-11-bk-collector",
        "bkm-ping-server-12-3-11-bk-collector",
    ]


def test_log_trace_lifecycle_remains_fail_closed_until_reverse_contract_lands(monkeypatch):
    monkeypatch.setattr("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", lambda: "v3_fresh")
    from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked

    with pytest.raises(NodeManV3CapabilityBlocked, match="reverse field"):
        from apm_web.models.application import Application

        Application._block_v3_log_trace_lifecycle("stop")
