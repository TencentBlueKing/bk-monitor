from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bkmonitor.nodeman_integration.exceptions import NodeManV3CapabilityBlocked
from bkmonitor.nodeman_integration.resources import NodeManResourceType
from bkmonitor.nodeman_integration.v3.backend import node_man_v3_backend
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManWorkflowDispatchStatus,
)
from monitor_web.nodeman_integration.v3.policy import (
    DeployPolicySubmission,
    SubscriptionDeployPolicyPayloadBuilder,
)

from bk_monitor_base.domains.uptime_check.collector import UptimeCheckCollector
from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskSubscription
from bk_monitor_base.domains.uptime_check.services.nodeman_v3 import UptimeCheckNodeManV3Service
from bk_monitor_base.domains.uptime_check.services.task_manager import TaskManager


@pytest.fixture
def subscription_config():
    return {
        "scope": {
            "bk_biz_id": 2,
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": 123}],
        },
        "steps": [
            {
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_http.conf", "version": "latest"}],
                },
                "params": {"context": {"data_id": 1001, "tasks": [{"url": "https://example.com"}]}},
            }
        ],
    }


class RecordingPolicyService:
    payload_builder = SubscriptionDeployPolicyPayloadBuilder()

    def __init__(self):
        self.calls = []

    def ensure(self, **kwargs):
        self.calls.append(kwargs)
        binding = NodeManIntegrationBinding.objects.create(
            resource_type=kwargs["resource_type"],
            resource_key=kwargs["resource_key"],
            owner_bk_tenant_id=kwargs["owner_bk_tenant_id"],
            execution_bk_tenant_id=kwargs["execution_bk_tenant_id"],
            bk_biz_id=kwargs["bk_biz_id"],
            node_man_deploy_policy_id=901,
            node_man_policy_fingerprint="f" * 64,
        )
        operation = MonitorNodeManOperation.objects.create(
            binding=binding,
            operation_type=NodeManOperationType.RECONCILE,
            generation=binding.generation,
            request_summary={},
            status=NodeManOperationStatus.RUNNING,
        )
        MonitorNodeManWorkflow.objects.create(
            monitor_operation=operation,
            batch_index=0,
            trigger_id="trigger-1",
            target_summary={},
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
        )
        return DeployPolicySubmission(binding_id=binding.pk, operation_id=str(operation.pk), prepared=True)


def test_uptime_policy_uses_shared_v3_control_plane(create_task, subscription_config, mocker):
    task = create_task(status="new_draft")
    policy_service = RecordingPolicyService()
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.nodeman_v3.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )

    relation = UptimeCheckNodeManV3Service(policy_service=policy_service).ensure(task, subscription_config)

    assert policy_service.calls[0]["resource_type"] == NodeManResourceType.UPTIME_CHECK
    assert policy_service.calls[0]["resource_key"] == str(task.pk)
    assert policy_service.calls[0]["steps"] == subscription_config["steps"]
    assert relation.subscription_id == NodeManIntegrationBinding.objects.get().pk
    assert relation.node_man_trigger_id == "trigger-1"
    assert relation.node_man_operation_status == NodeManOperationStatus.RUNNING
    assert relation.node_man_policy_fingerprint == "f" * 64


def test_uptime_preflight_rejects_old_direct_policy_identifier(create_task, subscription_config, mocker):
    task = create_task(status="new_draft")
    UptimeCheckTaskSubscription.objects.create(
        uptimecheck_id=task.pk,
        subscription_id=901,
        bk_biz_id=2,
        node_man_backend="v3",
    )
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.nodeman_v3.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )

    with pytest.raises(NodeManV3PayloadError, match="unexpected V3 binding"):
        UptimeCheckNodeManV3Service(policy_service=RecordingPolicyService()).preflight_deploy(
            task, [subscription_config]
        )


def test_task_manager_v3_deploy_never_calls_v2_subscription_api(create_task, create_node, subscription_config, mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )
    task = create_task(status="new_draft")
    task.nodes.add(create_node(bk_host_id=123))
    service = Mock()
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.nodeman_v3.UptimeCheckNodeManV3Service",
        return_value=service,
    )
    manager = TaskManager(task)
    manager.data_access_service.get_or_create_data_id = Mock(return_value=(False, 1001))
    manager.subscription_service.generate_subscription_config = Mock(return_value=[subscription_config])
    create_v2 = mocker.patch.object(manager, "_handle_create_subscriptions")
    update_v2 = mocker.patch.object(manager, "_handle_update_subscriptions")

    assert manager.deploy() == "success"

    service.preflight_deploy.assert_called_once_with(task, [subscription_config])
    service.ensure.assert_called_once_with(task, subscription_config, force=False)
    create_v2.assert_not_called()
    update_v2.assert_not_called()


def test_task_test_uses_v3_process_status_instead_of_plugin_search(create_task, create_node, mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )
    task = create_task(status="new_draft")
    task.nodes.add(create_node(bk_host_id=123))
    mocker.patch("bk_monitor_base.domains.uptime_check.services.nodeman_v3.UptimeCheckNodeManV3Service")
    status = mocker.patch.object(
        node_man_v3_backend,
        "plugin_search_host_status",
        return_value=[
            {
                "bk_host_id": 123,
                "inner_ip": "127.0.0.1",
                "inner_ipv6": "",
                "bk_cloud_id": 0,
                "plugin_status": [{"name": "bkmonitorbeat", "version": "3.5.0"}],
            }
        ],
    )
    legacy_search = mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.plugin_search"
    )
    mocker.patch.object(
        UptimeCheckCollector,
        "test",
        return_value={
            "success": [{"bk_host_id": 123, "ip": "127.0.0.1", "log_content": '{"error_code": 0}'}],
            "failed": [],
        },
    )

    assert TaskManager(task).test() == "正常"

    status.assert_called_once_with(
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_host_ids=[123],
        plugin_names=["bkmonitorbeat"],
    )
    legacy_search.assert_not_called()


def test_collector_v3_reads_setup_path_from_process_status(mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.collector.get_host_by_ip",
        return_value=[
            SimpleNamespace(
                bk_host_id=123,
                bk_host_innerip="127.0.0.1",
                bk_host_innerip_v6="",
                bk_cloud_id=0,
                bk_os_type="1",
                bk_os_type_name="",
            )
        ],
    )
    status = mocker.patch.object(
        node_man_v3_backend,
        "plugin_search_host_status",
        return_value=[
            {
                "bk_host_id": 123,
                "inner_ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "plugin_status": [{"name": "bkmonitorbeat", "version": "3.5.0", "setup_path": "/usr/local/gse"}],
            }
        ],
    )
    legacy_search = mocker.patch("bk_monitor_base.domains.uptime_check.collector.node_man_v2_api.plugin_search")

    groups, errors = UptimeCheckCollector(bk_biz_id=2)._separate_hosts_by_system_and_path(
        bk_tenant_id="system",
        hosts=[{"bk_host_id": 123}],
    )

    assert errors == []
    assert groups[0]["setup_path"] == "/usr/local/gse"
    status.assert_called_once()
    legacy_search.assert_not_called()


def test_legacy_uptime_status_poll_fails_closed_in_v3(mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    legacy_query = mocker.patch(
        "bk_monitor_base.domains.uptime_check.tasks.node_man_v2_api.batch_get_subscription_task_result"
    )

    from bk_monitor_base.domains.uptime_check.tasks import check_single_task_status

    with pytest.raises(NodeManV3CapabilityBlocked, match="cannot interpret a NodeMan V3 binding"):
        check_single_task_status("system", 901)

    legacy_query.assert_not_called()


def test_uptime_v3_start_forces_forward_reconciliation(create_task, mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )
    task = create_task(status="stoped")
    UptimeCheckTaskSubscription.objects.create(
        uptimecheck_id=task.pk,
        subscription_id=901,
        bk_biz_id=2,
        node_man_backend="v3",
    )
    mocker.patch("bk_monitor_base.domains.uptime_check.services.nodeman_v3.UptimeCheckNodeManV3Service")
    manager = TaskManager(task)
    deploy = mocker.patch.object(manager, "deploy", return_value="success")

    assert manager.start("admin") == "success"

    deploy.assert_called_once_with(force_nodeman_v3=True)
    task.refresh_from_db()
    assert task.update_user == "admin"


def test_uptime_v3_stop_and_delete_remain_fail_closed(create_task, mocker):
    mocker.patch("bkmonitor.nodeman_integration.mode.get_nodeman_integration_mode", return_value="v3_fresh")
    mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.bk_biz_id_to_bk_tenant_id",
        return_value="system",
    )
    task = create_task(status="running")
    mocker.patch("bk_monitor_base.domains.uptime_check.services.nodeman_v3.UptimeCheckNodeManV3Service")
    manager = TaskManager(task)
    switch_v2 = mocker.patch(
        "bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription"
    )
    run_v2 = mocker.patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.run_subscription")

    with pytest.raises(NodeManV3CapabilityBlocked, match="reverse field"):
        manager.stop("admin")
    with pytest.raises(NodeManV3CapabilityBlocked, match="only detaches management"):
        manager.delete("admin")

    switch_v2.assert_not_called()
    run_v2.assert_not_called()
