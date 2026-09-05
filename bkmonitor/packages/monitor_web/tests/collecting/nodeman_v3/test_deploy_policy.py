from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.client import NodeManV3RequestContext, NodeManV3UnknownResultError
from bkmonitor.nodeman_integration.v3.exceptions import (
    NodeManV3AdapterPending,
    NodeManV3PayloadError,
    NodeManV3ResultState,
)
from monitor_web.collecting.deploy.nodeman_v3.deploy_policy import (
    CollectDeployPolicyPayloadBuilder,
    NodeManV3DeployPolicyGateway,
)
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.models.node_man import NodeManIntegrationBinding, NodeManResourceType
from monitor_web.plugin.constant import PluginType


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


@pytest.mark.parametrize("plugin_type", [PluginType.EXPORTER, PluginType.JMX])
def test_custom_collectors_use_isolated_package_and_subconfig_specs(plugin_type):
    collect_config = SimpleNamespace(target_object_type="SERVICE", plugin=SimpleNamespace(plugin_type=plugin_type))
    specs = CollectDeployPolicyPayloadBuilder._build_specs(collect_config, _exporter_steps())
    assert specs[0] == {
        "type": "specify_plugin_pkg",
        "param": {
            "plugin_pkg_name": "mysql_exporter",
            "version": "1.2.3",
            "custom_config_context": {"listen": ":9107"},
        },
    }
    assert specs[1]["type"] == "specify_plugin_sub_config_template"
    assert specs[1]["param"]["plugin_name"] == "bkmonitorbeat"
    assert specs[1]["param"]["config_files_detail"] == [
        {
            "template_name": "bkmonitorbeat_prometheus.conf",
            "content": "",
            "is_main_config": False,
        }
    ]


def test_dynamic_plugin_config_file_template_is_blocked_instead_of_dropped():
    config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))
    steps = _exporter_steps()
    steps[0]["config"]["config_templates"] = [{"name": "{{file1}}", "content": "{{file1_content}}"}]
    with pytest.raises(NodeManV3CapabilityBlocked, match="dynamic config file templates"):
        CollectDeployPolicyPayloadBuilder._build_specs(config, steps)


def test_host_package_scope_keeps_the_documented_module_identity_boundary():
    config = SimpleNamespace(target_object_type="HOST", plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))
    with pytest.raises(NodeManV3AdapterPending, match="module identity"):
        CollectDeployPolicyPayloadBuilder._build_specs(config, _exporter_steps())


def test_v2_cross_step_context_is_blocked_instead_of_sent_unresolved():
    config = SimpleNamespace(target_object_type="SERVICE", plugin=SimpleNamespace(plugin_type=PluginType.EXPORTER))
    with pytest.raises(NodeManV3CapabilityBlocked, match="step_data") as error:
        CollectDeployPolicyPayloadBuilder._build_specs(
            config,
            _exporter_steps(collector_port="{{ step_data.mysql_exporter.control_info.listen_port }}"),
        )
    assert error.value.result_state == NodeManV3ResultState.UNSUPPORTED


def test_bkmonitorbeat_requires_a_config_template():
    config = SimpleNamespace(plugin=SimpleNamespace(plugin_type=PluginType.SCRIPT))
    with pytest.raises(NodeManV3PayloadError, match="no config template"):
        CollectDeployPolicyPayloadBuilder._build_specs(
            config,
            [{"config": {"plugin_name": "bkmonitorbeat", "config_templates": []}}],
        )


def test_policy_identity_is_the_collection_not_its_current_members():
    assert CollectDeployPolicyPayloadBuilder.policy_name(SimpleNamespace(pk=7)) == "bkm-collect-7"
    assert CollectDeployPolicyPayloadBuilder.policy_name(SimpleNamespace(pk=8)) == "bkm-collect-8"


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
        return {}

    def execute(self, payload, *, context):
        self.calls.append(("execute", payload, context))
        return {"trigger_id": "trigger-301"}


def policy_payload():
    return {
        "name": "bkm-collect-7",
        "description": "collect config",
        "enabled": True,
        "specs": [{"type": "specify_plugin", "param": {"plugin_name": "bkmonitorbeat", "version": "latest"}}],
        "scopes": [{"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [41, 42]}}],
    }


@pytest.fixture
def binding(db):
    return NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key="7",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )


@pytest.fixture
def context():
    return NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=2, monitor_operation_id="operation-1")


@pytest.mark.parametrize("existing", [None, "recovered", "bound"])
def test_gateway_creates_or_updates_one_policy_then_persists_before_execute(binding, context, existing):
    payload = policy_payload()
    client = FakeDeployPolicyClient(
        listed=[{"deploy_policy_id": 301, "meta": {"name": payload["name"]}}] if existing == "recovered" else []
    )
    if existing == "bound":
        binding.node_man_deploy_policy_id = 301
        binding.save()

    original_execute = client.execute

    def execute(payload, *, context):
        current = NodeManIntegrationBinding.objects.get(pk=binding.pk)
        assert current.node_man_deploy_policy_id == 301
        assert current.node_man_policy_fingerprint == CollectDeployPolicyPayloadBuilder.fingerprint(policy_payload())
        return original_execute(payload, context=context)

    client.execute = execute

    result = NodeManV3DeployPolicyGateway(client=client).ensure_policy(binding, payload, context=context)
    assert result == {"trigger_id": "trigger-301"}
    assert [call[0] for call in client.calls] == (
        ["update", "execute"] if existing == "bound" else ["list", "update" if existing else "create", "execute"]
    )
    assert all(call[2] == context for call in client.calls)


def test_generation_conflict_after_create_is_unknown_and_does_not_execute(binding, context):
    client = FakeDeployPolicyClient()
    NodeManIntegrationBinding.objects.filter(pk=binding.pk).update(generation=binding.generation + 1)
    with pytest.raises(NodeManV3UnknownResultError, match="changed while"):
        NodeManV3DeployPolicyGateway(client=client).ensure_policy(binding, policy_payload(), context=context)
    assert [call[0] for call in client.calls] == ["list", "create"]


@pytest.mark.parametrize("stage", ["create", "execute"])
def test_malformed_write_response_is_unknown(binding, context, stage):
    client = FakeDeployPolicyClient()
    setattr(client, stage, lambda *args, **kwargs: {})
    with pytest.raises(NodeManV3UnknownResultError):
        NodeManV3DeployPolicyGateway(client=client).ensure_policy(binding, policy_payload(), context=context)


def test_duplicate_stable_names_do_not_create_or_execute(binding, context):
    client = FakeDeployPolicyClient(
        listed=[{"deploy_policy_id": value, "meta": {"name": "bkm-collect-7"}} for value in (301, 302)]
    )
    with pytest.raises(NodeManV3PayloadError, match="multiple deploy policies"):
        NodeManV3DeployPolicyGateway(client=client).ensure_policy(binding, policy_payload(), context=context)
    assert [call[0] for call in client.calls] == ["list"]
