"""采集结果能力回归：不依赖真实节点管理或数据库。"""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings

from core.drf_resource import api
from core.errors.api import BKAPIError
from monitor_web.collecting import deploy
from monitor_web.collecting.constant import OperationResult, Status, TaskStatus
from monitor_web.collecting.deploy.base import CollectionStatistics
from monitor_web.collecting.deploy.k8s import K8sInstaller
from monitor_web.collecting.deploy.node_man import NodeManInstaller
from monitor_web.collecting.resources import backend, status, toolkit
from monitor_web.plugin.constant import PluginType


def config(config_id=1, tenant="tenant-a", subscription_id=10, plugin_type=PluginType.SCRIPT):
    return SimpleNamespace(
        pk=config_id,
        bk_tenant_id=tenant,
        collect_type=plugin_type,
        plugin_id=f"plugin-{config_id}",
        plugin=SimpleNamespace(plugin_type=plugin_type),
        deployment_config=SimpleNamespace(subscription_id=subscription_id, task_ids=[31]),
        cache_data={"total_instance_count": 4, "error_instance_count": 0},
        operation_result=OperationResult.PREPARING,
        save=mock.Mock(),
    )


@pytest.mark.parametrize("control_url", ["", "https://control.example.com/api"])
def test_control_switch_does_not_change_collection_backend(control_url):
    with override_settings(BKNODEMAN_CONTROL_API_BASE_URL=control_url):
        item = config()
        assert deploy.get_collect_installer_class(item) is NodeManInstaller
        assert isinstance(deploy.get_collect_installer(item), NodeManInstaller)


def test_k8s_does_not_query_nodeman():
    item = config(plugin_type=PluginType.K8S, subscription_id=0)
    with mock.patch.object(api.node_man, "check_task_ready") as ready:
        with mock.patch.object(api.node_man.fetch_subscription_statistic, "bulk_request") as query:
            assert deploy.get_collect_installer_class(item) is K8sInstaller
            assert deploy.get_collect_installer(item).is_task_ready() is True
            assert deploy.fetch_collection_statistics([item]) == {}
            ready.assert_not_called()
            query.assert_not_called()


def test_statistics_isolate_tenants_and_preserve_all_configs():
    items = [config(1), config(2), config(3, tenant="tenant-b")]
    responses = [
        [[{"subscription_id": 10, "instances": 3, "status": [{"status": "FAILED", "count": 1}]}]],
        [[{"subscription_id": 10, "instances": 8, "status": [{"status": "RUNNING", "count": 2}]}]],
    ]
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "bulk_request", side_effect=responses) as query:
        assert deploy.fetch_collection_statistics(items) == {
            1: CollectionStatistics(total=3, failed=1),
            2: CollectionStatistics(total=3, failed=1),
            3: CollectionStatistics(total=8, running=2),
        }
        assert query.call_args_list == [
            mock.call([{"bk_tenant_id": "tenant-a", "subscription_id_list": [10]}], ignore_exceptions=True),
            mock.call([{"bk_tenant_id": "tenant-b", "subscription_id_list": [10]}], ignore_exceptions=True),
        ]


def test_statistics_batches_and_partial_failure():
    items = [config(i, subscription_id=i) for i in range(1, 42)]

    def response(request_data):
        ids = request_data["subscription_id_list"]
        if ids[0] == 21:
            raise BKAPIError()
        return [{"subscription_id": i, "instances": 2, "status": []} for i in ids]

    # 使用真实 bulk_request，验证失败批次返回 None 不影响其他批次。
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "request", side_effect=response) as query:
        result = deploy.fetch_collection_statistics(items)
        assert set(result) == {*range(1, 21), 41}
        assert all(item == CollectionStatistics(total=2) for item in result.values())
        assert sorted(len(call.args[0]["subscription_id_list"]) for call in query.call_args_list) == [1, 20, 20]


def test_statistics_all_failed_still_raises():
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "request", side_effect=BKAPIError()):
        with pytest.raises(BKAPIError):
            deploy.fetch_collection_statistics([config()])


@pytest.mark.parametrize("items", [[], [config(subscription_id=0)]])
def test_statistics_without_subscription_does_not_query(items):
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "bulk_request") as query:
        assert deploy.fetch_collection_statistics(items) == {}
        query.assert_not_called()


def test_statistics_ignore_unrequested_subscription():
    with mock.patch.object(
        api.node_man.fetch_subscription_statistic,
        "bulk_request",
        return_value=[[{"subscription_id": 99, "instances": 1}]],
    ):
        assert deploy.fetch_collection_statistics([config()]) == {}


def test_statistics_only_routes_nodeman_configs():
    with mock.patch.object(NodeManInstaller, "statistics", return_value={}) as query:
        item = config()
        deploy.fetch_collection_statistics([item, config(2, plugin_type=PluginType.K8S, subscription_id=0)])
        query.assert_called_once_with([item])


def test_future_installer_does_not_need_v2_identity(monkeypatch):
    item = config()
    del item.deployment_config.subscription_id

    class FutureInstaller:
        @classmethod
        def statistics(cls, configs):
            return {entry.pk: CollectionStatistics(total=2, pending=1) for entry in configs}

    monkeypatch.setattr(deploy, "get_collect_installer_class", lambda config: FutureInstaller)
    assert deploy.fetch_collection_statistics([item]) == {1: CollectionStatistics(total=2, pending=1)}


@pytest.mark.parametrize("ready", [True, False])
def test_readiness_preserves_result_tenant_and_task_ids(ready):
    with mock.patch.object(api.node_man, "check_task_ready", return_value=ready) as query:
        assert NodeManInstaller(config()).is_task_ready() is ready
        query.assert_called_once_with(bk_tenant_id="tenant-a", subscription_id=10, task_id_list=[31])


def test_readiness_without_subscription():
    with mock.patch.object(api.node_man, "check_task_ready") as query:
        assert NodeManInstaller(config(subscription_id=0)).is_task_ready() is True
        query.assert_not_called()


def test_readiness_keeps_v2_legacy_api_error_fallback():
    with mock.patch.object(api.node_man, "check_task_ready", side_effect=BKAPIError()):
        assert NodeManInstaller(config()).is_task_ready() is True


def test_readiness_does_not_swallow_other_errors():
    with mock.patch.object(api.node_man, "check_task_ready", side_effect=ValueError("invalid response")):
        with pytest.raises(ValueError):
            NodeManInstaller(config()).is_task_ready()


def test_readiness_resource_delegates_without_checking_subscription():
    item = config(subscription_id=0)
    with (
        mock.patch.object(toolkit.CollectConfigMeta.objects, "select_related") as select,
        mock.patch.object(toolkit, "get_collect_installer") as factory,
    ):
        select.return_value.get.return_value = item
        factory.return_value.is_task_ready.return_value = False
        assert toolkit.IsTaskReady().perform_request({"collect_config_id": 1, "bk_biz_id": 2}) is False
        factory.assert_called_once_with(item)
        select.return_value.get.assert_called_once_with(id=1, bk_biz_id=2)


@pytest.mark.parametrize("result", [{}, {1: CollectionStatistics(total=8, failed=2)}, {1: CollectionStatistics()}])
def test_instance_count_uses_normalized_result_and_keeps_cache_if_missing(result):
    item = config()
    with (
        mock.patch.object(status.CollectConfigMeta.objects, "select_related") as select,
        mock.patch.object(status, "fetch_collection_statistics", return_value=result),
    ):
        select.return_value.get.return_value = item
        status.UpdateConfigInstanceCountResource().perform_request({"id": 1, "bk_biz_id": 2})
        if not result:
            assert item.cache_data == {"total_instance_count": 4, "error_instance_count": 0}
            item.save.assert_not_called()
        else:
            assert item.cache_data == {
                "total_instance_count": result[1].total,
                "error_instance_count": result[1].failed,
            }
            item.save.assert_called_once_with(not_update_user=True, update_fields=["cache_data"])


@pytest.mark.parametrize(
    ("statistics", "expected"),
    [
        (CollectionStatistics(total=4, running=1), OperationResult.DEPLOYING),
        (CollectionStatistics(total=4, pending=1), OperationResult.DEPLOYING),
        (CollectionStatistics(total=4), OperationResult.SUCCESS),
        (CollectionStatistics(total=4, failed=4), OperationResult.FAILED),
        (CollectionStatistics(total=4, failed=1), OperationResult.WARNING),
        (CollectionStatistics(), OperationResult.SUCCESS),
        (None, OperationResult.PREPARING),
    ],
)
def test_list_status_and_cache(statistics, expected):
    item = config()
    results = {} if statistics is None else {item.pk: statistics}
    with (
        mock.patch.object(backend, "fetch_collection_statistics", return_value=results),
        mock.patch.object(backend.CollectorPluginMeta.objects, "filter") as plugins,
        mock.patch.object(backend.CollectConfigMeta.objects, "bulk_update") as update,
    ):
        plugins.return_value.values.return_value = [{"plugin_id": item.plugin_id, "plugin_type": PluginType.SCRIPT}]
        resource = backend.CollectConfigListResource()
        resource.get_realtime_data([item], "tenant-a")
        assert item.operation_result == expected
        if statistics is None:
            assert resource.realtime_data == {}
            assert item.cache_data == {"total_instance_count": 4, "error_instance_count": 0}
            update.assert_called_once_with([], ["cache_data", "operation_result"])
        else:
            assert set(resource.realtime_data) == {item.pk}
            assert item.cache_data == {
                "total_instance_count": statistics.total,
                "error_instance_count": statistics.failed,
            }


def test_list_cache_and_auto_deploy_status_use_collection_identity():
    item = config()
    item.config_status = Status.STARTED
    item.task_status = TaskStatus.SUCCESS
    resource = backend.CollectConfigListResource()
    resource.realtime_data = {
        1: {"total_instance_count": 8, "error_instance_count": 2, "is_auto_deploying": True, "auto_running_tasks": [31]}
    }
    resource.update_cache_data(item)
    assert item.cache_data == {"total_instance_count": 8, "error_instance_count": 2}
    item.save.assert_called_once()
    assert resource.get_status(item) == {
        "config_status": Status.AUTO_DEPLOYING,
        "task_status": TaskStatus.AUTO_DEPLOYING,
        "running_tasks": [31],
    }


def test_v2_statistics_to_list_integration():
    """Resource → 工厂 → V2 API → 统计值 → 缓存和页面状态。"""
    items = [config(1, subscription_id=10), config(2, subscription_id=20)]
    response = [
        {"subscription_id": 10, "instances": 4, "status": [{"status": "FAILED", "count": 1}]},
        {"subscription_id": 20, "instances": 2, "status": [{"status": "RUNNING", "count": 2}]},
    ]
    with (
        mock.patch.object(api.node_man.fetch_subscription_statistic, "request", return_value=response) as query,
        mock.patch.object(backend.CollectorPluginMeta.objects, "filter") as plugins,
        mock.patch.object(backend.CollectConfigMeta.objects, "bulk_update") as update,
        override_settings(BKNODEMAN_CONTROL_API_BASE_URL="https://control.example.com/api"),
    ):
        plugins.return_value.values.return_value = []
        resource = backend.CollectConfigListResource()
        resource.get_realtime_data(items, "tenant-a")
        query.assert_called_once_with({"bk_tenant_id": "tenant-a", "subscription_id_list": [10, 20]})
        assert items[0].operation_result == OperationResult.WARNING
        assert items[1].operation_result == OperationResult.DEPLOYING
        assert items[0].cache_data == {"total_instance_count": 4, "error_instance_count": 1}
        assert items[1].cache_data == {"total_instance_count": 2, "error_instance_count": 0}
        assert set(resource.realtime_data) == {1, 2}
        update.assert_called_once_with(items, ["cache_data", "operation_result"])
