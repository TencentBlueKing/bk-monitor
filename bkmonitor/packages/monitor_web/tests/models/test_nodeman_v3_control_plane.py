import importlib

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from monitor_web.models.collecting import DeploymentConfigVersion
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManResourceType,
    StaleNodeManGenerationError,
    build_nodeman_resource_key,
)


@pytest.mark.parametrize(
    ("resource_type", "components", "expected"),
    [
        (NodeManResourceType.COLLECT_CONFIG, {"object_id": 12}, "12"),
        (NodeManResourceType.APM_PLATFORM_CONFIG, {}, "platform"),
        (NodeManResourceType.APM_APPLICATION_CONFIG, {"object_id": 13}, "13"),
        (NodeManResourceType.APM_LOG_TRACE_CONFIG, {"object_id": 14}, "14"),
        (NodeManResourceType.CUSTOM_REPORT, {"data_id": 15}, "data_id:15"),
        (
            NodeManResourceType.PING_SERVER,
            {"bk_cloud_id": 0, "bk_host_id": 16, "plugin_name": "bkmonitorbeat"},
            "cloud:0:host:16:plugin:bkmonitorbeat",
        ),
        (
            NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT,
            {"bk_cloud_id": 1, "bk_host_id": 17, "plugin_name": "bk-collector"},
            "cloud:1:host:17:plugin:bk-collector",
        ),
        (
            NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT,
            {"bk_host_id": 18, "plugin_name": "bkmonitorbeat"},
            "host:18:plugin:bkmonitorbeat",
        ),
        (NodeManResourceType.MONITOR_PLUGIN, {"plugin_id": "mysql_exporter"}, "mysql_exporter"),
    ],
)
def test_resource_key_contract(resource_type, components, expected):
    assert build_nodeman_resource_key(resource_type, **components) == expected


def test_resource_key_rejects_missing_or_unexpected_identity_components():
    with pytest.raises(ValueError, match="bk_host_id"):
        build_nodeman_resource_key(NodeManResourceType.PING_SERVER, bk_cloud_id=0, plugin_name="bkmonitorbeat")

    with pytest.raises(ValueError, match="unexpected"):
        build_nodeman_resource_key(NodeManResourceType.APM_PLATFORM_CONFIG, object_id=1)


def test_binding_unique_identity_and_non_nullable_business_contract():
    constraint = next(
        constraint
        for constraint in NodeManIntegrationBinding._meta.constraints
        if constraint.name == "uniq_nodeman_binding_identity"
    )

    assert constraint.fields == (
        "resource_type",
        "owner_bk_tenant_id",
        "execution_bk_tenant_id",
        "bk_biz_id",
        "resource_key",
    )
    assert NodeManIntegrationBinding._meta.get_field("resource_key").max_length == 255
    assert NodeManIntegrationBinding._meta.get_field("bk_biz_id").null is False
    assert NodeManIntegrationBinding._meta.get_field("bk_biz_id").default == 0


def test_operation_status_transition_contract():
    assert MonitorNodeManOperation._meta.get_field("status").default == NodeManOperationStatus.DISPATCHING
    operation = MonitorNodeManOperation(status=NodeManOperationStatus.PENDING)

    operation.transition_to(NodeManOperationStatus.DISPATCHING, save=False)
    operation.transition_to(NodeManOperationStatus.UNKNOWN, save=False)
    operation.transition_to(NodeManOperationStatus.SUCCESS, save=False)

    with pytest.raises(ValidationError, match="cannot transition"):
        operation.transition_to(NodeManOperationStatus.RUNNING, save=False)


def test_collect_target_requires_collect_config_binding():
    binding = NodeManIntegrationBinding(
        resource_type=NodeManResourceType.APM_APPLICATION_CONFIG,
        resource_key="1",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    target = CollectDeploymentTarget(
        binding=binding,
        config_meta_id=1,
        generation=1,
        identity_key="host:1",
        observed_target={},
        remote_target={},
        execution_bk_host_id=1,
        plugin_name="mysql_exporter",
    )

    with pytest.raises(ValidationError, match="COLLECT_CONFIG"):
        target.clean()


def test_migration_only_creates_v3_tables_and_keeps_v2_fields_unchanged():
    migration_module = importlib.import_module("monitor_web.migrations.0078_nodeman_v3_control_plane")

    assert migration_module.Migration.dependencies == [("monitor_web", "0077_collectorpluginmeta_id")]
    assert {operation.__class__.__name__ for operation in migration_module.Migration.operations} == {"CreateModel"}
    assert {operation.name for operation in migration_module.Migration.operations} == {
        "NodeManIntegrationBinding",
        "MonitorNodeManOperation",
        "MonitorNodeManWorkflow",
        "NodeManExecutionLease",
        "CollectDeploymentTarget",
    }
    assert DeploymentConfigVersion._meta.get_field("subscription_id").default == 0
    assert DeploymentConfigVersion._meta.get_field("task_ids").default is None


@pytest.mark.django_db(transaction=True)
def test_binding_identity_is_unique_and_generation_update_is_guarded():
    attributes = {
        "resource_type": NodeManResourceType.COLLECT_CONFIG,
        "resource_key": "1",
        "owner_bk_tenant_id": "tenant-a",
        "execution_bk_tenant_id": "tenant-a",
        "bk_biz_id": 2,
    }
    binding = NodeManIntegrationBinding.objects.create(**attributes)

    with pytest.raises(IntegrityError), transaction.atomic():
        NodeManIntegrationBinding.objects.create(**attributes)

    binding.advance_generation(expected_generation=1)
    assert binding.generation == 2
    with pytest.raises(StaleNodeManGenerationError):
        binding.advance_generation(expected_generation=1)


@pytest.mark.django_db(transaction=True)
def test_one_operation_aggregates_multiple_unique_workflows():
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key="1",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    operation = MonitorNodeManOperation.objects.create(binding=binding, operation_type="install", generation=1)
    MonitorNodeManWorkflow.objects.create(
        monitor_operation=operation,
        workflow_id="workflow-1",
        batch_index=0,
        target_summary={"host_ids": [1]},
        target_count=1,
    )
    MonitorNodeManWorkflow.objects.create(
        monitor_operation=operation,
        workflow_id="workflow-2",
        batch_index=1,
        target_summary={"host_ids": [2]},
        target_count=1,
    )

    assert list(operation.workflows.values_list("workflow_id", flat=True)) == ["workflow-1", "workflow-2"]
    with pytest.raises(IntegrityError), transaction.atomic():
        MonitorNodeManWorkflow.objects.create(
            monitor_operation=operation,
            workflow_id="workflow-1",
            batch_index=2,
            target_summary={},
            target_count=0,
        )


@pytest.mark.django_db(transaction=True)
def test_binding_can_be_removed_after_external_cleanup_without_losing_operation_history():
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.MONITOR_PLUGIN,
        resource_key="mysql_exporter",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    operation = MonitorNodeManOperation.objects.create(binding=binding, operation_type="plugin_retire", generation=1)

    binding.delete()
    operation.refresh_from_db()

    assert operation.binding_id is None
