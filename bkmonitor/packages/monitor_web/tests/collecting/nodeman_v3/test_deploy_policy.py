from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.client import NodeManV3RequestContext
from monitor_web.collecting.deploy.nodeman_v3.deploy_policy import (
    CollectDeployPolicyPayloadBuilder,
    NodeManV3DeployPolicyGateway,
)
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.plugin.constant import PluginType


def _target(*, identity_key="service:101", service_instance_id=101, deploy_policy_id=None):
    return SimpleNamespace(
        pk=1,
        config_meta_id=7,
        identity_key=identity_key,
        observed_target={"bk_host_id": 41, "service_instance_id": service_instance_id},
        execution_bk_host_id=41,
        remote_target={},
        service_instance_id=service_instance_id,
        desired_enabled=True,
        node_man_deploy_policy_id=deploy_policy_id,
    )


def _exporter_steps(*, collector_port="9107"):
    return [
        {
            "config": {"plugin_name": "mysql_exporter", "plugin_version": "1.2.3"},
            "params": {"context": {"listen": ":9107"}},
        },
        {
            "config": {
                "plugin_name": "bkmonitorbeat",
                "plugin_version": "latest",
                "config_templates": [{"name": "bkmonitorbeat_prometheus.conf", "version": "latest"}],
            },
            "params": {"context": {"port": collector_port}},
        },
    ]


def test_step_builder_uses_plugin_manager_extension_point_without_v2_installer(monkeypatch):
    captured = []
    manager = SimpleNamespace(
        get_deploy_steps_params=lambda version, params, nodes: captured.append((version, params, nodes)) or ["step"]
    )
    plugin = SimpleNamespace(plugin_id="script_plugin", plugin_type=PluginType.SCRIPT)
    collect_config = SimpleNamespace(pk=7, bk_biz_id=2, data_id=1001, plugin=plugin)
    version = SimpleNamespace(config=SimpleNamespace(config_json=[]))
    deployment = SimpleNamespace(
        params={"collector": {"period": 60, "timeout": 30}, "plugin": {}},
        plugin_version=version,
        subscription_id=0,
        target_nodes=[{"bk_host_id": 41}],
    )
    monkeypatch.setattr(
        "monitor_web.collecting.deploy.nodeman_v3.deploy_policy.PluginManagerFactory.get_manager",
        lambda *, plugin: manager,
    )

    assert CollectDeployPolicyPayloadBuilder._build_existing_steps(collect_config, deployment) == ["step"]
    assert captured[0][0] is version
    assert captured[0][2] == [{"bk_host_id": 41}]
    collector = captured[0][1]["collector"]
    assert collector | {"labels": None} == {
        "period": "60",
        "timeout": "30",
        "task_id": "7",
        "bk_biz_id": "2",
        "config_name": "script_plugin",
        "config_version": "1.0",
        "namespace": "script_plugin",
        "max_timeout": "30",
        "dataid": "1001",
        "labels": None,
    }
    assert collector["labels"]["$body"]["bk_collect_config_id"] == 7
    assert collector["labels"]["$body"]["bk_target_service_instance_id"] == "{{ cmdb_instance.service.id }}"


def test_exporter_service_instance_maps_to_package_and_independent_subconfig_specs():
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))

    specs = CollectDeployPolicyPayloadBuilder._build_specs(
        collect_config,
        _target(),
        _exporter_steps(),
    )

    assert specs == [
        {
            "type": "specify_plugin_pkg",
            "param": {
                "plugin_pkg_name": "mysql_exporter",
                "version": "1.2.3",
                "custom_config_context": {"listen": ":9107"},
            },
        },
        {
            "type": "specify_plugin_sub_config_template",
            "param": {
                "plugin_name": "bkmonitorbeat",
                "config_files_detail": [
                    {
                        "template_name": "bkmonitorbeat_prometheus.conf",
                        "content": "",
                        "is_main_config": False,
                    }
                ],
                "custom_config_context": {"port": "9107"},
            },
        },
    ]


def test_exporter_host_scope_is_blocked_before_sending_invalid_package_policy():
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))
    host_target = _target(identity_key="host:41", service_instance_id=None)

    with pytest.raises(NodeManV3CapabilityBlocked, match="service-instance scope"):
        CollectDeployPolicyPayloadBuilder._build_specs(collect_config, host_target, _exporter_steps())


def test_dynamic_plugin_config_file_template_is_blocked_instead_of_being_dropped():
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))
    steps = _exporter_steps()
    steps[0]["config"]["config_templates"] = [
        {"name": "env.yaml", "version": "1"},
        {"name": "{{file1}}", "version": "1", "content": "{{file1_content}}"},
    ]

    with pytest.raises(NodeManV3CapabilityBlocked, match="dynamic config file templates"):
        CollectDeployPolicyPayloadBuilder._build_specs(collect_config, _target(), steps)


def test_v2_cross_step_context_is_blocked_instead_of_being_sent_unresolved():
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))

    with pytest.raises(NodeManV3CapabilityBlocked, match="step_data"):
        CollectDeployPolicyPayloadBuilder._build_specs(
            collect_config,
            _target(),
            _exporter_steps(collector_port="{{ step_data.mysql_exporter.control_info.listen_port }}"),
        )


def test_bkmonitorbeat_without_config_template_is_blocked_instead_of_succeeding_without_effect():
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.SCRIPT))
    steps = [
        {
            "config": {"plugin_name": "bkmonitorbeat", "config_templates": []},
            "params": {"context": {"dataid": "1001"}},
        }
    ]

    with pytest.raises(NodeManV3CapabilityBlocked, match="no config template"):
        CollectDeployPolicyPayloadBuilder._build_specs(collect_config, _target(), steps)


def test_policy_name_is_stable_without_relying_on_database_primary_key():
    first = _target(identity_key="service:101")
    first.pk = None
    second = _target(identity_key="service:101")
    second.pk = 999

    assert CollectDeployPolicyPayloadBuilder.policy_name(first) == CollectDeployPolicyPayloadBuilder.policy_name(second)
    assert CollectDeployPolicyPayloadBuilder.policy_name(first).startswith("bkm-collect-7-")


class FakeDeployPolicyClient:
    def __init__(self, *, listed=None):
        self.listed = listed or []
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append(("list", payload, context))
        return {"total": len(self.listed), "items": self.listed}

    def create(self, payload, *, context):
        self.calls.append(("create", payload, context))
        return {"deploy_policy_id": 301}

    def update(self, payload, *, context):
        self.calls.append(("update", payload, context))
        return {"deploy_policy_id": 301}

    def execute(self, payload, *, context):
        self.calls.append(("execute", payload, context))
        return {"trigger_id": "trigger-301"}


def test_gateway_creates_persists_and_executes_policy(monkeypatch):
    target = _target()
    client = FakeDeployPolicyClient()
    payload = {
        "name": "bkm-collect-7-stable",
        "description": "collect target",
        "enabled": True,
        "specs": [],
        "scopes": [],
    }
    builder = SimpleNamespace(
        build=lambda current_target: payload,
        update_payload=CollectDeployPolicyPayloadBuilder.update_payload,
    )
    persisted = []
    monkeypatch.setattr(
        NodeManV3DeployPolicyGateway,
        "_persist_policy_id",
        staticmethod(lambda current_target, policy_id: persisted.append((current_target, policy_id))),
    )
    gateway = NodeManV3DeployPolicyGateway(client=client, payload_builder=builder)
    context = NodeManV3RequestContext(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        monitor_operation_id="operation-1",
    )

    assert gateway.ensure_target(target, context=context) == {"trigger_id": "trigger-301"}
    assert persisted == [(target, 301)]
    assert [call[0] for call in client.calls] == ["list", "create", "execute"]
    assert client.calls[0][1] == {
        "page": {"offset": 0, "limit": 2},
        "exact_include_conditions": {"deploy_policy_name": ["bkm-collect-7-stable"]},
    }


def test_gateway_recovers_existing_policy_by_exact_stable_name_and_updates_it(monkeypatch):
    target = _target()
    payload = {
        "name": "bkm-collect-7-stable",
        "description": "collect target",
        "enabled": True,
        "specs": [{"type": "specify_plugin", "param": {}}],
        "scopes": [],
    }
    client = FakeDeployPolicyClient(listed=[{"deploy_policy_id": 301, "meta": {"name": "bkm-collect-7-stable"}}])
    builder = SimpleNamespace(
        build=lambda current_target: payload,
        update_payload=CollectDeployPolicyPayloadBuilder.update_payload,
    )
    persisted = []
    monkeypatch.setattr(
        NodeManV3DeployPolicyGateway,
        "_persist_policy_id",
        staticmethod(lambda current_target, policy_id: persisted.append((current_target, policy_id))),
    )
    gateway = NodeManV3DeployPolicyGateway(client=client, payload_builder=builder)
    context = NodeManV3RequestContext(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        monitor_operation_id="operation-1",
    )

    assert gateway.ensure_target(target, context=context) == {"trigger_id": "trigger-301"}
    assert [call[0] for call in client.calls] == ["list", "update", "execute"]
    assert client.calls[1][1]["deploy_policies"][0]["deploy_policy_id"] == 301
    assert persisted == [(target, 301)]


def test_gateway_blocks_target_update_until_existing_config_refresh_is_supported():
    client = FakeDeployPolicyClient()
    gateway = NodeManV3DeployPolicyGateway(client=client)

    with pytest.raises(NodeManV3CapabilityBlocked, match="cannot refresh existing template config"):
        gateway.update_target(
            _target(deploy_policy_id=301),
            context=NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2),
        )

    assert client.calls == []
