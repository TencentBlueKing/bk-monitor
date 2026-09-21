"""集成能力边界的无数据库测试，覆盖归属、选择与兼容控制入口。"""

from types import SimpleNamespace
from unittest import mock

import pytest

from bk_monitor_base.domains.metric_plugin.installer import nodeman, tools
from bk_monitor_base.domains.metric_plugin.installer.base import BaseInstaller
from bk_monitor_base.domains.metric_plugin.manager import tools as managers
from bk_monitor_base.infras.nodeman_control import host_queries, official_plugins
from bk_monitor_base.infras.third_party_api.nodeman import api
from bk_monitor_base.nodeman import UnsupportedNodeManBackend


def make_installer(deployment_params: dict, plugin_params: dict | None = None):
    """隔离 ORM，只验证实际安装器初始化与调用，不替换其路由判断。"""
    deployment = SimpleNamespace(related_params=deployment_params, bk_tenant_id="tenant-a")

    def initialize(self, deployment, operator):
        self.deployment = deployment
        self.plugin = SimpleNamespace(related_params=plugin_params or {})

    with (
        mock.patch.object(BaseInstaller, "__init__", initialize),
        mock.patch.object(nodeman, "get_nodeman_deploy_plugin_manager"),
    ):
        return nodeman.NodemanInstaller(deployment, "tester")


@pytest.mark.parametrize("params", [{}, {"nodeman_backend": "v2"}])
def test_legacy_record_is_v2(params):
    """历史无标记记录固定归 V2，内存中的绑定随既有保存动作持久化。"""
    installer = make_installer(params.copy())
    assert installer.deployment.related_params["nodeman_backend"] == "v2"
    installer._record_task(123)
    assert installer.deployment.related_params["subscription_task_id"] == 123
    assert installer.deployment.related_params["execution_backend"] == "v2"


@pytest.mark.parametrize("key", ["nodeman_backend", "execution_backend"])
@pytest.mark.parametrize("backend", ["v3", "unknown", ""])
def test_foreign_resource_or_execution_rejected_before_request(key, backend):
    """部署和执行身份均不能通过 V2 安装器解释，不做失败回退。"""
    with mock.patch.object(nodeman, "create_subscription") as create:
        with pytest.raises(UnsupportedNodeManBackend):
            make_installer({key: backend})
        create.assert_not_called()


def test_foreign_plugin_rejected():
    """V2 配置下发不能引用另一控制面的插件包。"""
    with pytest.raises(UnsupportedNodeManBackend):
        make_installer({}, {"nodeman_backend": "v3"})


def test_installer_factory_uses_record_and_tenant():
    """工厂先按租户查插件，再按部署记录选择后端。"""
    deployment = SimpleNamespace(plugin_id="example", bk_tenant_id="tenant-a", related_params={"nodeman_backend": "v3"})
    with mock.patch.object(tools.MetricPluginModel.objects, "filter") as query:
        query.return_value.first.return_value = SimpleNamespace(type="exporter")
        with pytest.raises(UnsupportedNodeManBackend):
            tools.get_installer(deployment, "tester")
        query.assert_called_once_with(bk_tenant_id="tenant-a", plugin_id="example")


def test_plugin_manager_registry_has_no_unknown_fallback():
    """尚未接入的插件后端必须明确失败。"""
    with pytest.raises(UnsupportedNodeManBackend):
        managers.get_plugin_manager_class("exporter", "v3")
    assert managers.get_plugin_manager_class("exporter", "v2") is managers.ExporterPluginManager


def test_readiness_is_owned_by_installer():
    """就绪检查保留既有 V2 行为并携带租户身份。"""
    installer = make_installer({"subscription_id": 12})
    with mock.patch.object(nodeman, "check_subscription_task_ready", return_value=False) as query:
        assert installer.is_task_ready() is False
        query.assert_called_once_with(bk_tenant_id="tenant-a", subscription_id=12)


def test_official_install_and_host_query_capabilities():
    """业务安装意图被兼容实现转换，普通 V2 安装接口不被调用。"""
    with (
        mock.patch.object(api, "official_plugin_operate", return_value={"job_id": 7}) as control,
        mock.patch.object(api, "plugin_operate") as v2,
        mock.patch.object(api, "get_proxies", return_value=[]) as query,
    ):
        assert official_plugins.install("tenant-a", "bkmonitorbeat", "1.0", [1]) == {"job_id": 7}
        control.assert_called_once_with(
            bk_tenant_id="tenant-a",
            params={
                "plugin_params": {"name": "bkmonitorbeat", "version": "1.0"},
                "job_type": "MAIN_INSTALL_PLUGIN",
                "bk_host_id": [1],
            },
        )
        v2.assert_not_called()
        assert host_queries.proxies("tenant-a", 0) == []
        query.assert_called_once_with(bk_tenant_id="tenant-a", bk_cloud_id=0)
