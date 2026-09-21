"""验证业务能力边界与资源归属，无需真实节点管理或数据库。"""

from types import SimpleNamespace
from unittest import mock

import pytest
from bk_monitor_base.nodeman import CollectionStatistics, UnsupportedNodeManBackend

from bkmonitor.utils.nodeman import host_queries, official_plugins
from core.drf_resource import api
from monitor_web.collecting import deploy
from monitor_web.collecting.deploy.k8s import K8sInstaller
from monitor_web.collecting.deploy.node_man import NodeManInstaller
from monitor_web.collecting.resources.backend import CollectConfigListResource
from monitor_web.collecting.resources.status import UpdateConfigInstanceCountResource
from monitor_web.collecting.resources.toolkit import IsTaskReady
from monitor_web.collecting.deploy import fetch_collection_statistics
from monitor_web.models import CollectorPluginMeta, DeploymentConfigVersion
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory


def config(config_id=1, backend="v2", tenant="tenant-a", subscription_id=10):
    """模拟持久化部署版本；外部身份相同也不能混淆监控配置和租户。"""
    return SimpleNamespace(
        pk=config_id,
        bk_tenant_id=tenant,
        collect_type=PluginType.SCRIPT,
        plugin=SimpleNamespace(plugin_type=PluginType.SCRIPT, nodeman_backend=backend),
        deployment_config_id=100 + config_id,
        deployment_config=SimpleNamespace(nodeman_backend=backend, subscription_id=subscription_id, task_ids=[31]),
        cache_data={"total_instance_count": 4, "error_instance_count": 0},
        save=mock.Mock(),
    )


def test_legacy_database_defaults_are_v2():
    """增量字段的历史默认值固定为 V2，不取运行时路由开关。"""
    assert CollectorPluginMeta().nodeman_backend == "v2"
    assert DeploymentConfigVersion().nodeman_backend == "v2"


@pytest.mark.parametrize("backend", ["v3", "unknown", ""])
def test_unimplemented_backend_never_falls_back(backend):
    """未实现或损坏的归属不能被默认分支吞掉。"""
    with mock.patch.object(api.node_man, "create_subscription") as create:
        with pytest.raises(UnsupportedNodeManBackend):
            deploy.get_collect_installer(config(backend=backend))
        create.assert_not_called()


def test_plugin_and_deployment_cannot_cross_backends():
    """存量部署仍属于 V2 时，不能混用另一后端的插件包。"""
    item = config()
    item.plugin.nodeman_backend = "v3"
    with pytest.raises(UnsupportedNodeManBackend):
        deploy.get_collect_installer(item)


def test_plugin_factory_rejects_unknown_backend():
    """发布、调试等入口也按插件归属选择实现。"""
    plugin = CollectorPluginMeta(plugin_id="example", plugin_type=PluginType.SCRIPT, nodeman_backend="v3")
    with pytest.raises(UnsupportedNodeManBackend):
        PluginManagerFactory.get_manager(plugin=plugin, operator="tester")


def test_k8s_has_no_nodeman_dependency():
    """K8s 的路由和就绪不受节点管理后端影响。"""
    item = config(backend="not-a-nodeman-backend")
    item.collect_type = PluginType.K8S
    assert deploy.get_collect_installer_class(item) is K8sInstaller
    assert deploy.get_collect_installer(item).is_task_ready() is True
    assert fetch_collection_statistics([item]) == {}


def test_statistics_group_by_tenant_and_normalize_identity():
    """跨租户相同订阅 ID 分开查询，返回业务 ID 而不是订阅 ID。"""
    items = [config(1), config(2, tenant="tenant-b")]
    result = [{"subscription_id": 10, "instances": 3, "status": [{"status": "FAILED", "count": 1}]}]
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "bulk_request", return_value=[result]) as query:
        assert fetch_collection_statistics(items) == {
            1: CollectionStatistics(total=3, failed=1),
            2: CollectionStatistics(total=3, failed=1),
        }
        assert query.call_count == 2
        assert {call.args[0][0]["bk_tenant_id"] for call in query.call_args_list} == {"tenant-a", "tenant-b"}


def test_statistics_keep_batches_and_skip_missing_results():
    """保持每组 20 个订阅；失败或缺失结果不补零，避免虚假成功。"""
    items = [config(i, subscription_id=i) for i in range(1, 42)]
    with mock.patch.object(api.node_man.fetch_subscription_statistic, "bulk_request", return_value=[None, []]) as query:
        assert fetch_collection_statistics(items) == {}
        assert [len(batch["subscription_id_list"]) for batch in query.call_args.args[0]] == [20, 20, 1]


def test_future_backend_can_replace_capability_without_subscription(monkeypatch):
    """测试替身代表未来实现：调用方只消费统一结果，不要求它提供 V2 字段。"""
    item = config(backend="v3")
    del item.deployment_config.subscription_id

    class FutureInstaller:
        @classmethod
        def statistics(cls, configs):
            return {entry.pk: CollectionStatistics(total=2, running=1) for entry in configs}

    monkeypatch.setitem(deploy.NODEMAN_INSTALLERS, "v3", FutureInstaller)
    assert fetch_collection_statistics([item]) == {1: CollectionStatistics(total=2, running=1)}


def test_readiness_uses_bound_execution():
    """任务初始化查询使用部署记录中的 V2 任务 ID 与租户。"""
    with mock.patch.object(api.node_man, "check_task_ready", return_value=False) as query:
        assert NodeManInstaller(config()).is_task_ready() is False
        query.assert_called_once_with(bk_tenant_id="tenant-a", subscription_id=10, task_id_list=[31])


def test_readiness_resource_delegates_to_installer():
    """Resource 层不再因没有 subscription_id 就提前报告就绪。"""
    from monitor_web.collecting.resources import toolkit

    item = config(backend="v3", subscription_id=0)
    with (
        mock.patch.object(toolkit.CollectConfigMeta.objects, "select_related") as select,
        mock.patch.object(toolkit, "get_collect_installer") as factory,
    ):
        select.return_value.get.return_value = item
        factory.return_value.is_task_ready.return_value = False
        assert IsTaskReady().perform_request({"collect_config_id": 1, "bk_biz_id": 2}) is False
        factory.assert_called_once_with(item)


def test_instance_count_does_not_clear_cache_on_missing_result():
    """统计未返回时保留已知状态，不写 None。"""
    from monitor_web.collecting.resources import status

    item = config()
    with (
        mock.patch.object(status.CollectConfigMeta.objects, "select_related") as select,
        mock.patch.object(status, "fetch_collection_statistics", return_value={}),
    ):
        select.return_value.get.return_value = item
        UpdateConfigInstanceCountResource().perform_request({"id": 1, "bk_biz_id": 2})
        item.save.assert_not_called()


def test_list_cache_is_keyed_by_collection_not_subscription():
    """配置 ID 与订阅 ID 不同，页面仍能读取正确统计。"""
    resource = CollectConfigListResource()
    resource.realtime_data = {1: {"total_instance_count": 8, "error_instance_count": 2}}
    # 页面缓存的读取与节点管理版本无关。
    item = config()
    resource.update_cache_data(item)
    assert item.cache_data == {"total_instance_count": 8, "error_instance_count": 2}
    item.save.assert_called_once()


def test_official_plugin_service_hides_job_protocol():
    """业务只描述安装意图，兼容实现负责生成 NodeMan job 参数。"""
    with (
        mock.patch.object(api.node_man, "official_plugin_operate", return_value={"job_id": 7}) as control,
        mock.patch.object(api.node_man, "plugin_operate") as v2,
    ):
        assert official_plugins.install("bkmonitorbeat", "1.0", [1], "tenant-a") == {"job_id": 7}
        control.assert_called_once_with(
            bk_tenant_id="tenant-a",
            plugin_params={"name": "bkmonitorbeat", "version": "1.0"},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=[1],
        )
        v2.assert_not_called()


def test_host_queries_preserve_tenant_and_scope():
    """基础设施查询与采集实例归属分开，租户参数不丢失。"""
    with mock.patch.object(api.node_man, "get_proxies_by_biz", return_value=[]) as query:
        assert host_queries.business_proxies(bk_biz_id=2, bk_tenant_id="tenant-a") == []
        query.assert_called_once_with(bk_biz_id=2, bk_tenant_id="tenant-a")
