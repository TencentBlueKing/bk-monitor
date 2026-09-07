from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.models.node_man import NodeManBindingState, NodeManOperationStatus, NodeManResourceType
from monitor_web.nodeman_integration.v3.operation import NodeManExecutionLeaseConflict
from monitor_web.nodeman_integration.v3.plugin_deployment import NodeManV3PluginDeploymentService
from monitor_web.nodeman_integration.v3.policy import (
    DeployPolicySubmission,
    NodeManV3HostScopeResolver,
    NodeManV3PolicyService,
    SubscriptionDeployPolicyPayloadBuilder,
    ensure_v3_record_ownership,
    mark_v3_config,
)


def _host_scope(*host_ids):
    return {
        "object_type": "HOST",
        "node_type": "INSTANCE",
        "nodes": [{"bk_host_id": host_id} for host_id in host_ids],
    }


def _config_step():
    return {
        "type": "PLUGIN",
        "config": {
            "plugin_name": "bk-collector",
            "plugin_version": "latest",
            "config_templates": [{"name": "bk-collector-application.conf", "version": "latest"}],
        },
        "params": {"context": {"bk_data_id": 1001}},
    }


def test_shared_subscription_builder_uses_documented_template_sub_config_spec():
    payload = SubscriptionDeployPolicyPayloadBuilder().build(
        name="bkm-custom-report-1001",
        description="custom report",
        bk_biz_id=2,
        scope=_host_scope(11, 12),
        steps=[_config_step()],
    )

    assert payload == {
        "name": "bkm-custom-report-1001",
        "description": "custom report",
        "enabled": True,
        "specs": [
            {
                "type": "specify_plugin_sub_config_template",
                "param": {
                    "plugin_name": "bk-collector",
                    "config_files_detail": [
                        {"template_name": "bk-collector-application.conf", "is_main_config": False}
                    ],
                    "custom_config_context": {"bk_data_id": 1001},
                },
            }
        ],
        "scopes": [
            {
                "type": "instance",
                "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [11, 12]},
            }
        ],
    }


def test_shared_subscription_builder_uses_documented_plugin_install_spec():
    step = _config_step()
    step["config"]["config_templates"] = []
    step["config"]["plugin_version"] = "1.2.3"

    payload = SubscriptionDeployPolicyPayloadBuilder().build(
        name="bkm-official-plugin",
        description="plugin",
        bk_biz_id=2,
        scope=_host_scope(11),
        steps=[step],
    )

    assert payload["specs"] == [
        {
            "type": "specify_plugin",
            "param": {
                "plugin_name": "bk-collector",
                "version": "1.2.3",
                "custom_config_context": {"bk_data_id": 1001},
            },
        }
    ]


class FakeHostClient:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def list(self, payload, *, context):
        self.calls.append((payload, context))
        return {"total": len(self.items), "items": self.items}


def test_explicit_host_scope_is_grouped_by_nodeman_business_identity():
    client = FakeHostClient(
        [
            {"bk_host_id": 11, "info": {"bk_biz_id": 2}},
            {"bk_host_id": 12, "info": {"bk_biz_id": 3}},
        ]
    )
    resolver = NodeManV3HostScopeResolver(client=client)

    scopes = resolver.resolve(
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=0,
        scope=_host_scope(12, 11),
        payload_builder=SubscriptionDeployPolicyPayloadBuilder(),
    )

    assert scopes == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [11]}},
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 3, "instance_ids": [12]}},
    ]
    payload, context = client.calls[0]
    assert payload["exact_include_conditions"] == {"bk_host_id": [11, 12]}
    assert context.bk_biz_id == 0


def test_explicit_host_scope_rejects_partially_resolved_targets():
    resolver = NodeManV3HostScopeResolver(client=FakeHostClient([{"bk_host_id": 11, "info": {"bk_biz_id": 2}}]))

    with pytest.raises(NodeManV3PayloadError, match=r"\[12\]"):
        resolver.resolve(
            owner_bk_tenant_id="tenant-a",
            execution_bk_tenant_id="tenant-a",
            bk_biz_id=2,
            scope=_host_scope(11, 12),
            payload_builder=SubscriptionDeployPolicyPayloadBuilder(),
        )


def test_persisted_v2_identifier_is_blocked_before_it_can_be_reinterpreted():
    with pytest.raises(NodeManV3PayloadError, match="V2 subscription"):
        ensure_v3_record_ownership(config={}, persisted_identifier=101, resource="custom report")

    ensure_v3_record_ownership(
        config=mark_v3_config({}),
        persisted_identifier=101,
        resource="custom report",
    )


class FakeBindingLookup:
    def __init__(self, binding_id):
        self.binding_id = binding_id
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def values_list(self, *args, **kwargs):
        assert args == ("pk",)
        assert kwargs == {"flat": True}
        return self

    def first(self):
        return self.binding_id


def test_persisted_v3_identifier_must_match_the_exact_binding_identity(monkeypatch):
    lookup = FakeBindingLookup(binding_id=102)
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManIntegrationBinding",
        SimpleNamespace(objects=lookup),
    )
    identity = {
        "resource_type": NodeManResourceType.CUSTOM_REPORT,
        "resource_key": "data_id:1001",
        "owner_bk_tenant_id": "tenant-a",
        "execution_bk_tenant_id": "tenant-a",
        "bk_biz_id": 2,
    }

    with pytest.raises(NodeManV3PayloadError, match="unexpected V3 binding 101"):
        ensure_v3_record_ownership(
            config=mark_v3_config({}),
            persisted_identifier=101,
            resource="custom report",
            binding_identity=identity,
        )

    assert lookup.filters == [identity]


class FakeScopeResolver:
    def resolve(self, **kwargs):
        return [
            {
                "type": "instance",
                "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [11]},
            }
        ]


class FakeBindingManager:
    def __init__(self):
        self.calls = []

    def get_or_create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(pk=9), True


class RecordingPolicyService(NodeManV3PolicyService):
    def __init__(self, **kwargs):
        kwargs.setdefault("gateway", SimpleNamespace())
        kwargs.setdefault("operation_service", SimpleNamespace())
        super().__init__(**kwargs)
        self.prepared = SimpleNamespace(operation=SimpleNamespace(pk="operation-1"))
        self.prepared_calls = []
        self.dispatched = []

    def _prepare(self, binding, payload, *, force):
        self.prepared_calls.append((binding, payload, force))
        return self.prepared

    def _dispatch(self, prepared, payload):
        self.dispatched.append((prepared, payload))


def test_shared_policy_validates_payload_then_persists_and_dispatches(monkeypatch):
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.transaction.get_connection",
        lambda: SimpleNamespace(in_atomic_block=True),
    )
    binding_manager = FakeBindingManager()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManIntegrationBinding",
        SimpleNamespace(objects=binding_manager),
    )
    callbacks = []
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.transaction.on_commit",
        lambda callback: callbacks.append(callback),
    )
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.plugin_deployment.transaction.atomic",
        nullcontext,
    )
    resolved_versions = []

    def resolve_version(**kwargs):
        resolved_versions.append(kwargs)
        return "1.2.3"

    service = RecordingPolicyService(
        scope_resolver=FakeScopeResolver(),
        plugin_version_resolver=resolve_version,
    )

    submission = service.ensure(
        resource_type=NodeManResourceType.CUSTOM_REPORT,
        resource_key="data_id:1001",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
        policy_name="bkm-custom-report-1001",
        description="custom report",
        scope=_host_scope(11),
        steps=[_config_step()],
    )

    assert submission == DeployPolicySubmission(binding_id=9, operation_id="operation-1", prepared=True)
    assert resolved_versions == [{"bk_tenant_id": "tenant-a", "plugin_name": "bk-collector"}]
    assert [call["resource_type"] for call in binding_manager.calls] == [
        NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT,
        NodeManResourceType.CUSTOM_REPORT,
    ]
    assert binding_manager.calls[0]["bk_biz_id"] == 0
    assert [call[1]["specs"][0]["type"] for call in service.prepared_calls] == [
        "specify_plugin",
        "specify_plugin_sub_config_template",
    ]
    assert service.prepared_calls[0][1]["specs"][0]["param"]["version"] == "1.2.3"
    assert service.dispatched == []
    for callback in callbacks:
        callback()
    assert service.dispatched == [
        (service.prepared, service.prepared_calls[0][1]),
        (service.prepared, service.prepared_calls[1][1]),
    ]


class FakeOperationLookup:
    def __init__(self, active_operation):
        self.active_operation = active_operation

    def filter(self, **kwargs):
        assert kwargs == {"result_state": "write_result_unknown"}
        return SimpleNamespace(exists=lambda: False)

    def exclude(self, **kwargs):
        assert set(kwargs["status__in"]) == {"success", "partial_failed", "failed", "cancelled"}
        return self

    def order_by(self, *fields):
        assert fields == ("-created_at",)
        return self

    def first(self):
        return self.active_operation


class FakeLockedBindingManager:
    def __init__(self, binding):
        self.binding = binding

    def select_for_update(self):
        return self

    def get(self, **kwargs):
        assert kwargs == {"pk": self.binding.pk}
        return self.binding


def test_shared_policy_reuses_identical_inflight_reconciliation(monkeypatch):
    service = NodeManV3PolicyService(
        gateway=SimpleNamespace(),
        operation_service=SimpleNamespace(),
        scope_resolver=FakeScopeResolver(),
    )
    payload = SubscriptionDeployPolicyPayloadBuilder().build(
        name="bkm-official-plugin",
        description="plugin",
        bk_biz_id=2,
        scope=_host_scope(11),
        steps=[
            {
                "type": "PLUGIN",
                "config": {"plugin_name": "bk-collector", "plugin_version": "1.2.3"},
                "params": {"context": {}},
            }
        ],
    )
    active = SimpleNamespace(
        status=NodeManOperationStatus.DISPATCHING,
        request_summary={"deploy_policy_fingerprint": service.payload_builder.fingerprint(payload)},
    )
    locked = SimpleNamespace(
        pk=9,
        state=NodeManBindingState.ACTIVE,
        operations=FakeOperationLookup(active),
    )
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManIntegrationBinding",
        SimpleNamespace(objects=FakeLockedBindingManager(locked)),
    )
    monkeypatch.setattr("monitor_web.nodeman_integration.v3.policy.transaction.atomic", nullcontext)

    assert service._prepare(SimpleNamespace(pk=9), payload, force=False) is None

    changed_payload = {**payload, "description": "changed"}
    with pytest.raises(NodeManExecutionLeaseConflict, match="not reached a terminal state"):
        service._prepare(SimpleNamespace(pk=9), changed_payload, force=False)


class RejectingScopeResolver:
    def resolve(self, **kwargs):
        raise NodeManV3PayloadError("unresolved host")


def test_shared_policy_does_not_persist_a_binding_when_preflight_fails(monkeypatch):
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.transaction.get_connection",
        lambda: SimpleNamespace(in_atomic_block=True),
    )
    binding_manager = FakeBindingManager()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManIntegrationBinding",
        SimpleNamespace(objects=binding_manager),
    )

    with pytest.raises(NodeManV3PayloadError, match="unresolved host"):
        RecordingPolicyService(scope_resolver=RejectingScopeResolver()).ensure(
            resource_type=NodeManResourceType.CUSTOM_REPORT,
            resource_key="data_id:1002",
            owner_bk_tenant_id="tenant-a",
            execution_bk_tenant_id="tenant-a",
            bk_biz_id=2,
            policy_name="bkm-custom-report-1002",
            description="custom report",
            scope=_host_scope(11),
            steps=[_config_step()],
        )

    assert binding_manager.calls == []


def test_shared_policy_requires_outer_transaction_before_persisting(monkeypatch):
    binding_manager = FakeBindingManager()
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.NodeManIntegrationBinding",
        SimpleNamespace(objects=binding_manager),
    )
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.policy.transaction.get_connection",
        lambda: SimpleNamespace(in_atomic_block=False),
    )

    with pytest.raises(RuntimeError, match="transaction.atomic"):
        RecordingPolicyService(scope_resolver=FakeScopeResolver()).ensure(
            resource_type=NodeManResourceType.CUSTOM_REPORT,
            resource_key="data_id:1002",
            owner_bk_tenant_id="tenant-a",
            execution_bk_tenant_id="tenant-a",
            bk_biz_id=2,
            policy_name="bkm-custom-report-1002",
            description="custom report",
            scope=_host_scope(11),
            steps=[_config_step()],
        )

    assert binding_manager.calls == []


class FakePolicyService:
    def __init__(self):
        self.payload_builder = SubscriptionDeployPolicyPayloadBuilder()
        self.scope_resolver = FakeScopeResolverForPlugins()
        self.calls = []

    def ensure(self, **kwargs):
        self.calls.append(kwargs)
        return DeployPolicySubmission(binding_id=len(self.calls), operation_id=str(len(self.calls)), prepared=True)


class FakeScopeResolverForPlugins:
    def resolve(self, **kwargs):
        return [
            {
                "type": "instance",
                "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [11]},
            },
            {
                "type": "instance",
                "scope": {"granularity": "host", "bk_biz_id": 3, "instance_ids": [12]},
            },
        ]


def test_plugin_deployment_keeps_one_policy_identity_per_host(monkeypatch):
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.plugin_deployment.transaction.atomic",
        nullcontext,
    )
    policy_service = FakePolicyService()
    deployments = NodeManV3PluginDeploymentService(policy_service=policy_service).ensure_hosts(
        resource_type=NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT,
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=0,
        plugin_name="bkmonitorproxy",
        plugin_version="1.2.3",
        bk_cloud_id=9,
        bk_host_ids=[12, 11, 12],
    )

    assert [deployment.bk_host_id for deployment in deployments] == [11, 12]
    assert [call["resource_key"] for call in policy_service.calls] == [
        "cloud:9:host:11:plugin:bkmonitorproxy",
        "cloud:9:host:12:plugin:bkmonitorproxy",
    ]
    assert [call["resolved_scopes"][0]["scope"] for call in policy_service.calls] == [
        {"granularity": "host", "bk_biz_id": 2, "instance_ids": [11]},
        {"granularity": "host", "bk_biz_id": 3, "instance_ids": [12]},
    ]


def test_official_plugin_deployment_uses_host_global_binding_identity(monkeypatch):
    monkeypatch.setattr(
        "monitor_web.nodeman_integration.v3.plugin_deployment.transaction.atomic",
        nullcontext,
    )
    policy_service = FakePolicyService()

    NodeManV3PluginDeploymentService(policy_service=policy_service).ensure_hosts(
        resource_type=NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT,
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
        plugin_name="bk-collector",
        plugin_version="1.2.3",
        bk_host_ids=[11],
    )

    assert policy_service.calls[0]["resource_key"] == "host:11:plugin:bk-collector"
    assert policy_service.calls[0]["bk_biz_id"] == 0
