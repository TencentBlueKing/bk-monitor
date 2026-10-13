"""测试 metric_plugin.manager.tools 模块。"""

from types import SimpleNamespace
from unittest.mock import patch

from bk_monitor_base.domains.metric_plugin.define import MetricPlugin, VersionTuple
from bk_monitor_base.domains.metric_plugin.installer.nodeman import NodemanInstaller
from bk_monitor_base.domains.metric_plugin.manager.node_man.log import LogPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.process import ProcessPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.snmp_trap import SNMPTrapPluginManager
from bk_monitor_base.domains.metric_plugin.manager.tools import (
    PLUGIN_MANAGERS,
    get_nodeman_deploy_plugin_manager,
    get_plugin_manager_class,
)


def _build_plugin(plugin_type: str, plugin_id: str = "test_plugin") -> MetricPlugin:
    """构造测试用插件对象。"""
    return MetricPlugin(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        id=plugin_id,
        type=plugin_type,
        name="测试插件",
        label="os",
        version=VersionTuple(major=1, minor=0),
        related_params={},
        params=[],
        metrics=[],
        define={},
        description_md="",
        logo="",
        version_log="",
        is_internal=True,
        is_global=False,
        is_support_remote=False,
        created_by="tester",
        updated_by="tester",
        status="release",
    )


class TestPluginManagerTools:
    """测试插件管理器工具函数。"""

    def test_should_register_built_in_plugins_in_general_manager_mapping(self) -> None:
        """内置插件类型应纳入通用管理器映射。"""
        assert PLUGIN_MANAGERS["process"] is ProcessPluginManager
        assert PLUGIN_MANAGERS["log"] is LogPluginManager
        assert PLUGIN_MANAGERS["snmp_trap"] is SNMPTrapPluginManager

    def test_should_return_built_in_manager_class_from_general_lookup(self) -> None:
        """通用查找入口应能返回内置插件管理器类。"""
        assert get_plugin_manager_class("process") is ProcessPluginManager
        assert get_plugin_manager_class("log") is LogPluginManager
        assert get_plugin_manager_class("snmp_trap") is SNMPTrapPluginManager

    def test_should_return_built_in_manager_from_nodeman_deploy_lookup(self) -> None:
        """节点管理部署入口应支持返回内置插件管理器实例。"""
        plugin = _build_plugin("process")

        manager = get_nodeman_deploy_plugin_manager(plugin)

        assert isinstance(manager, ProcessPluginManager)

    def test_should_use_built_in_manager_when_initializing_nodeman_installer(self) -> None:
        """NodemanInstaller 初始化时应接受内置插件管理器。"""
        plugin = _build_plugin("process", plugin_id="bkprocessbeat")
        deployment = SimpleNamespace(
            plugin_id="bkprocessbeat",
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            related_params={},
            status="initializing",
        )

        def _fake_base_installer_init(self, deployment, operator) -> None:
            self.operator = operator
            self.deployment = deployment
            self.deployment_version = None
            self.plugin = plugin

        with patch(
            "bk_monitor_base.domains.metric_plugin.installer.base.BaseInstaller.__init__",
            new=_fake_base_installer_init,
        ):
            installer = NodemanInstaller(deployment=deployment, operator="tester")

        assert isinstance(installer.plugin_manager, ProcessPluginManager)
