"""集成能力边界的无数据库测试，覆盖安装器选择与兼容控制入口。"""

from types import SimpleNamespace
from unittest import mock

import pytest

from bk_monitor_base.domains.metric_plugin.errors import MetricPluginManagerNotFoundError
from bk_monitor_base.domains.metric_plugin.installer import nodeman, tools
from bk_monitor_base.domains.metric_plugin.installer.base import BaseInstaller
from bk_monitor_base.domains.metric_plugin.manager import tools as managers
from bk_monitor_base.infras.nodeman_control import host_queries, official_plugins
from bk_monitor_base.infras.third_party_api.nodeman import api


def make_installer(deployment_params: dict):
    """隔离 ORM，只验证实际安装器初始化与调用，不替换其路由判断。"""
    deployment = SimpleNamespace(related_params=deployment_params, bk_tenant_id="tenant-a")

    def initialize(self, deployment, operator):
        self.deployment = deployment
        self.plugin = SimpleNamespace(related_params={})

    with (
        mock.patch.object(BaseInstaller, "__init__", initialize),
        mock.patch.object(nodeman, "get_nodeman_deploy_plugin_manager"),
    ):
        return nodeman.NodemanInstaller(deployment, "tester")


@pytest.mark.parametrize("params", [{}, {"subscription_id": 12, "subscription_task_id": 31}])
def test_installer_does_not_add_persistent_metadata(params):
    """构造安装器不改变既有部署记录，无需补充后端标记。"""
    installer = make_installer(params.copy())
    assert installer.deployment.related_params == params


def test_installer_factory_uses_type_and_tenant():
    """工厂按租户查插件，沿用插件类型选择安装器，不依赖新增字段。"""
    deployment = SimpleNamespace(plugin_id="example", bk_tenant_id="tenant-a", related_params={})
    installer = mock.Mock()
    with (
        mock.patch.object(tools.MetricPluginModel.objects, "filter") as query,
        mock.patch.dict(tools.INSTALLERS, {"exporter": installer}),
    ):
        query.return_value.first.return_value = SimpleNamespace(type="exporter")
        assert tools.get_installer(deployment, "tester") is installer.return_value
        installer.assert_called_once_with(deployment=deployment, operator="tester")
        query.assert_called_once_with(bk_tenant_id="tenant-a", plugin_id="example")


def test_plugin_manager_registry_has_no_unknown_fallback():
    """插件类型映射保持有效，未知类型不隐式回退。"""
    with pytest.raises(MetricPluginManagerNotFoundError):
        managers.get_plugin_manager_class("unknown")
    assert managers.get_plugin_manager_class("exporter") is managers.ExporterPluginManager


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
