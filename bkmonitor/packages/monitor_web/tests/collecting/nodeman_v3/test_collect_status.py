from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.client import NodeManV3TransportError
from monitor_web.collecting.constant import OperationResult
from monitor_web.collecting.deploy.nodeman_v3.status import NodeManV3CollectStatusService
from monitor_web.collecting.resources.backend import CollectConfigListResource
from monitor_web.collecting.resources.status import UpdateConfigInstanceCountResource
from monitor_web.collecting.resources.toolkit import IsTaskReady
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
)
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)


class FakeWorkflowClient:
    def __init__(self, distributions):
        self.distributions = distributions
        self.calls = []

    def list_operation_instance_status_distribution(self, payload, *, context):
        self.calls.append((payload, context))
        return {
            "items": {
                trigger_id: self.distributions[trigger_id]
                for trigger_id in payload["trigger_id"]
                if trigger_id in self.distributions
            }
        }


class FailingWorkflowClient:
    def list_operation_instance_status_distribution(self, payload, *, context):
        raise NodeManV3TransportError("unavailable")


def _config(config_id, *, tenant="tenant-a", bk_biz_id=2):
    return SimpleNamespace(pk=config_id, bk_tenant_id=tenant, bk_biz_id=bk_biz_id)


def _binding(config):
    return NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key=str(config.pk),
        owner_bk_tenant_id=config.bk_tenant_id,
        execution_bk_tenant_id=config.bk_tenant_id,
        bk_biz_id=config.bk_biz_id,
    )


def _operation(binding, trigger_id, *, status=NodeManOperationStatus.RUNNING):
    operation = MonitorNodeManOperation.objects.create(
        binding=binding,
        config_meta_id=int(binding.resource_key),
        operation_type=NodeManOperationType.RECONCILE,
        generation=binding.generation,
        status=status,
    )
    MonitorNodeManWorkflow.objects.create(
        monitor_operation=operation,
        trigger_id=trigger_id,
        batch_index=0,
        dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
    )
    return operation


@pytest.mark.django_db
def test_fetch_statistics_batches_triggers_by_execution_context():
    first = _config(7)
    second = _config(8)
    _operation(_binding(first), "trigger-7")
    _operation(_binding(second), "trigger-8")
    client = FakeWorkflowClient(
        {
            "trigger-7": {
                "not_inited_count": 1,
                "state_counts": {
                    "init": 2,
                    "launched": 3,
                    "running": 4,
                    "success": 5,
                    "failed": 6,
                    "timeout": 7,
                    "terminated": 8,
                    "future_state": 9,
                },
            },
            "trigger-8": {"not_inited_count": 0, "state_counts": {"success": 2}},
        }
    )

    config_by_key, statistics = NodeManV3CollectStatusService(workflow_client=client).fetch_statistics([first, second])

    assert config_by_key == {7: first, 8: second}
    assert statistics == [
        {
            "key": 7,
            "error_instance_count": 30,
            "total_instance_count": 45,
            "pending_instance_count": 3,
            "running_instance_count": 7,
        },
        {
            "key": 8,
            "error_instance_count": 0,
            "total_instance_count": 2,
            "pending_instance_count": 0,
            "running_instance_count": 0,
        },
    ]
    assert len(client.calls) == 1
    assert client.calls[0][0] == {"trigger_id": ["trigger-7", "trigger-8"]}
    assert client.calls[0][1].bk_tenant_id == "tenant-a"
    assert client.calls[0][1].bk_biz_id == 2


@pytest.mark.django_db
def test_fetch_statistics_separates_execution_contexts_and_ignores_missing_observations():
    first = _config(7, tenant="tenant-a", bk_biz_id=2)
    second = _config(8, tenant="tenant-b", bk_biz_id=3)
    _operation(_binding(first), "trigger-7")
    _operation(_binding(second), "trigger-missing")
    client = FakeWorkflowClient({"trigger-7": {"not_inited_count": 0, "state_counts": {"success": 1}}})

    config_by_key, statistics = NodeManV3CollectStatusService(workflow_client=client).fetch_statistics([first, second])

    assert config_by_key == {7: first}
    assert statistics == [
        {
            "key": 7,
            "error_instance_count": 0,
            "total_instance_count": 1,
            "pending_instance_count": 0,
            "running_instance_count": 0,
        }
    ]
    assert {(call[1].bk_tenant_id, call[1].bk_biz_id) for call in client.calls} == {
        ("tenant-a", 2),
        ("tenant-b", 3),
    }


@pytest.mark.django_db
def test_fetch_statistics_does_not_read_a_stale_generation():
    config = _config(7)
    binding = _binding(config)
    _operation(binding, "trigger-stale")
    binding.advance_generation(expected_generation=1)
    client = FakeWorkflowClient({"trigger-stale": {"not_inited_count": 0, "state_counts": {"success": 1}}})

    config_by_key, statistics = NodeManV3CollectStatusService(workflow_client=client).fetch_statistics([config])

    assert config_by_key == {}
    assert statistics == []
    assert client.calls == []


@pytest.mark.django_db
def test_fetch_statistics_does_not_replace_cache_when_nodeman_read_fails():
    config = _config(7)
    _operation(_binding(config), "trigger-7")

    config_by_key, statistics = NodeManV3CollectStatusService(workflow_client=FailingWorkflowClient()).fetch_statistics(
        [config]
    )

    assert config_by_key == {}
    assert statistics == []


@pytest.mark.django_db
def test_is_task_ready_waits_for_durable_dispatch_and_exposes_terminal_failure():
    config = _config(7)
    service = NodeManV3CollectStatusService(workflow_client=FakeWorkflowClient({}))
    assert service.is_task_ready(config) is True

    binding = _binding(config)
    assert service.is_task_ready(config) is False

    operation = MonitorNodeManOperation.objects.create(
        binding=binding,
        config_meta_id=config.pk,
        operation_type=NodeManOperationType.RECONCILE,
        generation=binding.generation,
        status=NodeManOperationStatus.DISPATCHING,
    )
    workflow = MonitorNodeManWorkflow.objects.create(
        monitor_operation=operation,
        batch_index=0,
        dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
    )
    assert service.is_task_ready(config) is False

    workflow.trigger_id = "trigger-7"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.save(update_fields=("trigger_id", "dispatch_status", "updated_at"))
    assert service.is_task_ready(config) is True

    workflow.trigger_id = None
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
    workflow.save(update_fields=("trigger_id", "dispatch_status", "updated_at"))
    operation.status = NodeManOperationStatus.FAILED
    operation.save(update_fields=("status", "updated_at"))
    assert service.is_task_ready(config) is True


@pytest.fixture
def collection(db):
    plugin = CollectorPluginMeta.objects.create(
        bk_tenant_id="tenant-a",
        plugin_id="test-process",
        plugin_type="Process",
    )
    version = PluginVersionHistory.objects.create(
        bk_tenant_id="tenant-a",
        plugin_id=plugin.plugin_id,
        config=CollectorPluginConfig.objects.create(),
        info=CollectorPluginInfo.objects.create(),
        stage="release",
    )
    deployment = DeploymentConfigVersion.objects.create(
        plugin_version=version,
        config_meta_id=0,
        target_node_type="INSTANCE",
        target_nodes=[{"bk_host_id": 41}],
        params={"collector": {"period": 60}, "plugin": {}},
        subscription_id=0,
    )
    collect_config = CollectConfigMeta.objects.create(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        name="test collection",
        plugin_id=plugin.plugin_id,
        collect_type="Process",
        target_object_type="HOST",
        deployment_config=deployment,
        last_operation="CREATE",
        operation_result=OperationResult.PREPARING,
    )
    deployment.config_meta_id = collect_config.pk
    deployment.save(update_fields=("config_meta_id", "update_time"))
    return collect_config


@pytest.mark.django_db
def test_collection_list_updates_v3_counts_by_collection_key(collection, monkeypatch):
    summary = {
        "key": collection.pk,
        "error_instance_count": 1,
        "total_instance_count": 3,
        "pending_instance_count": 0,
        "running_instance_count": 0,
    }
    monkeypatch.setattr(
        "monitor_web.collecting.resources.backend.fetch_collect_statistics",
        lambda configs: ({collection.pk: collection}, [summary]),
    )
    monkeypatch.setattr(
        "monitor_web.collecting.resources.backend.get_collect_status_key",
        lambda config: config.pk,
    )

    resource = CollectConfigListResource()
    resource.get_realtime_data([collection], "tenant-a")

    collection.refresh_from_db()
    assert resource.realtime_data == {collection.pk: summary}
    assert collection.cache_data == {"error_instance_count": 1, "total_instance_count": 3}
    assert collection.operation_result == OperationResult.WARNING


@pytest.mark.django_db
def test_instance_count_refresh_uses_v3_collection_key(collection, monkeypatch):
    summary = {
        "key": collection.pk,
        "error_instance_count": 2,
        "total_instance_count": 4,
        "pending_instance_count": 0,
        "running_instance_count": 0,
    }
    monkeypatch.setattr(
        "monitor_web.collecting.resources.status.fetch_collect_statistics",
        lambda configs: ({collection.pk: collection}, [summary]),
    )
    monkeypatch.setattr(
        "monitor_web.collecting.resources.status.get_collect_status_key",
        lambda config: config.pk,
    )

    UpdateConfigInstanceCountResource().perform_request({"bk_biz_id": 2, "id": collection.pk})

    collection.refresh_from_db()
    assert collection.cache_data == {"error_instance_count": 2, "total_instance_count": 4}


@pytest.mark.django_db
def test_instance_count_refresh_keeps_last_counts_without_a_v3_observation(collection, monkeypatch):
    collection.cache_data = {"error_instance_count": 1, "total_instance_count": 3}
    collection.save(not_update_user=True, update_fields=("cache_data",))
    monkeypatch.setattr(
        "monitor_web.collecting.resources.status.fetch_collect_statistics",
        lambda configs: ({}, []),
    )

    UpdateConfigInstanceCountResource().perform_request({"bk_biz_id": 2, "id": collection.pk})

    collection.refresh_from_db()
    assert collection.cache_data == {"error_instance_count": 1, "total_instance_count": 3}


@pytest.mark.django_db
def test_is_task_ready_resource_uses_process_bound_facade(collection, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "monitor_web.collecting.resources.toolkit.is_collect_task_ready",
        lambda config: calls.append(config.pk) or False,
    )

    result = IsTaskReady().perform_request({"bk_biz_id": 2, "collect_config_id": collection.pk})

    assert result is False
    assert calls == [collection.pk]
