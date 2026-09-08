"""测试 NodemanInstaller 的订阅相关逻辑。"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.metric_plugin.constants import TargetNodeType
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginDeploymentOperationError
from bk_monitor_base.domains.metric_plugin.installer.nodeman import NodemanInstaller


def _build_installer(label: str = "os") -> tuple[NodemanInstaller, MagicMock]:
    """构造可用于单元测试的 NodemanInstaller 实例。"""
    deployment = SimpleNamespace(
        id=1,
        plugin_id="test_plugin",
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        related_params={},
        status="initializing",
    )
    plugin = SimpleNamespace(id="test_plugin", label=label)
    plugin_manager = MagicMock()

    def _fake_base_installer_init(self: NodemanInstaller, deployment: Any, operator: str) -> None:
        self.operator = operator
        self.deployment = deployment
        self.deployment_version = None
        self.plugin = plugin

    with patch(
        "bk_monitor_base.domains.metric_plugin.installer.base.BaseInstaller.__init__",
        new=_fake_base_installer_init,
    ), patch(
        "bk_monitor_base.domains.metric_plugin.installer.nodeman.get_nodeman_deploy_plugin_manager",
        return_value=plugin_manager,
    ):
        installer = NodemanInstaller(deployment=deployment, operator="tester")

    return installer, plugin_manager


def _build_deployment_version(node_type: str = TargetNodeType.HOST.value) -> SimpleNamespace:
    """构造测试用部署版本。"""
    return SimpleNamespace(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        deployment_id=1,
        version="1.0.0",
        plugin_version=SimpleNamespace(major=1, minor=0),
        created_by="tester",
        params={"collector": {"period": 60}, "plugin": {"foo": "bar"}},
        target_scope=SimpleNamespace(node_type=node_type, nodes=[{"bk_host_id": 1, "ip": "127.0.0.1"}]),
        remote_scope=None,
    )


class TestNodemanInstaller:
    """测试 NodemanInstaller 的订阅私有方法。"""

    @pytest.mark.parametrize(
        ("label", "node_type", "expected_object_type", "expected_node_type"),
        [
            ("os", TargetNodeType.HOST.value, "HOST", "INSTANCE"),
            ("component", TargetNodeType.TOPO.value, "SERVICE", TargetNodeType.TOPO.value),
        ],
    )
    def test_get_subscription_scope(
        self,
        label: str,
        node_type: str,
        expected_object_type: str,
        expected_node_type: str,
    ) -> None:
        """测试订阅范围参数构建逻辑。"""
        installer, _ = _build_installer(label=label)
        deployment_version = _build_deployment_version(node_type=node_type)

        scope = installer._get_subscription_scope(deployment_version)

        assert scope == {
            "bk_biz_id": 2,
            "object_type": expected_object_type,
            "node_type": expected_node_type,
            "nodes": [{"bk_host_id": 1, "ip": "127.0.0.1"}],
        }

    def test_create_subscription(self) -> None:
        """测试创建订阅时仅调用节点管理并返回结果。"""
        installer, _ = _build_installer()
        deployment_version = _build_deployment_version()
        expected_params: dict[str, Any] = {
            "steps": [{"id": "test_plugin"}],
            "run_immediately": True,
            "scope": {"bk_biz_id": 2},
        }

        with patch.object(installer, "_get_deploy_params", return_value=expected_params) as mock_get_params, patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.create_subscription",
            return_value={"subscription_id": 9527, "task_id": 1001},
        ) as mock_create:
            result = installer._create_subscription(deployment_version)

        mock_get_params.assert_called_once_with(deployment_version)
        mock_create.assert_called_once_with(bk_tenant_id="test_tenant", params=expected_params)
        assert result == {"subscription_id": 9527, "task_id": 1001}
        assert installer.subscription_id is None
        assert installer.deployment.related_params == {}

    def test_update_subscription(self) -> None:
        """测试更新订阅时会生成预期参数并返回结果。"""
        installer, plugin_manager = _build_installer()
        installer.subscription_id = 9527
        deployment_version = _build_deployment_version()
        plugin_manager.get_deploy_steps_params.return_value = [{"id": "test_plugin"}, {"id": "bkmonitorbeat"}]

        with patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.update_subscription",
            return_value={"task_id": 1002},
        ) as mock_update:
            result = installer._update_subscription(deployment_version)

        plugin_manager.get_deploy_steps_params.assert_called_once_with(
            bk_biz_id=2,
            collect_task_id=1,
            bk_data_ids=installer.get_data_ids(),
            collect_params={"period": 60},
            plugin_params={"foo": "bar"},
            target_nodes=[{"bk_host_id": 1, "ip": "127.0.0.1"}],
        )
        mock_update.assert_called_once_with(
            bk_tenant_id="test_tenant",
            params={
                "subscription_id": 9527,
                "steps": [{"id": "test_plugin"}, {"id": "bkmonitorbeat"}],
                "run_immediately": True,
                "scope": {
                    "bk_biz_id": 2,
                    "object_type": "HOST",
                    "node_type": "INSTANCE",
                    "nodes": [{"bk_host_id": 1, "ip": "127.0.0.1"}],
                },
            },
        )
        assert result == {"task_id": 1002}
        assert installer.deployment.related_params == {
            "subscription_id": 9527,
            "subscription_id_history": [9527],
        }

    def test_update_subscription_without_subscription_id(self) -> None:
        """测试更新订阅前必须存在订阅 ID。"""
        installer, _ = _build_installer()

        with pytest.raises(MetricPluginDeploymentOperationError, match="订阅ID不存在"):
            installer._update_subscription(_build_deployment_version())

    def test_install_create_subscription_updates_deployment_explicitly(self) -> None:
        """测试 install 在创建订阅分支显式回填 deployment 信息。"""
        installer, _ = _build_installer()
        deployment_version = _build_deployment_version()
        deployment_model = SimpleNamespace(bk_tenant_id="test_tenant", bk_biz_id=2)
        filter_result = MagicMock()
        filter_result.exclude.return_value.update.return_value = None

        with patch.object(installer, "_get_current_deployment_version", return_value=None), patch.object(
            installer, "get_version_diff", return_value=(True, {"changed": True})
        ), patch.object(
            installer, "_create_subscription", return_value={"subscription_id": 9527, "task_id": 1001}
        ) as mock_create, patch.object(
            installer, "_update_subscription"
        ) as mock_update, patch.object(
            installer, "_save"
        ) as mock_save, patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentModel.objects.get",
            return_value=deployment_model,
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.update_or_create"
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.filter",
            return_value=filter_result,
        ):
            result = installer.install(deployment_version)

        mock_create.assert_called_once_with(deployment_version)
        mock_update.assert_not_called()
        mock_save.assert_called_once_with()
        assert installer.subscription_id == 9527
        assert installer.deployment.related_params["subscription_task_id"] == 1001
        assert installer.deployment.related_params["subscription_id_history"] == [9527]
        assert installer.deployment.status == "deploying"
        assert installer.deployment_version is deployment_version
        assert result == {
            "deployment_id": 1,
            "subscription_task_id": 1001,
            "subscription_id": 9527,
            "diff_result": {"changed": True},
        }

    def test_install_update_subscription_updates_task_id_explicitly(self) -> None:
        """测试 install 在更新订阅分支显式回填任务 ID。"""
        installer, _ = _build_installer()
        current_version = _build_deployment_version()
        deployment_version = _build_deployment_version()
        deployment_model = SimpleNamespace(bk_tenant_id="test_tenant", bk_biz_id=2)
        filter_result = MagicMock()
        filter_result.exclude.return_value.update.return_value = None
        installer.subscription_id = 9527

        with patch.object(installer, "_get_current_deployment_version", return_value=current_version), patch.object(
            installer, "get_version_diff", return_value=(True, {"changed": True})
        ), patch.object(
            installer, "_create_subscription"
        ) as mock_create, patch.object(
            installer, "_update_subscription", return_value={"task_id": 1002}
        ) as mock_update, patch.object(
            installer, "_save"
        ) as mock_save, patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentModel.objects.get",
            return_value=deployment_model,
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.update_or_create"
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.filter",
            return_value=filter_result,
        ):
            result = installer.install(deployment_version)

        mock_create.assert_not_called()
        mock_update.assert_called_once_with(deployment_version)
        mock_save.assert_called_once_with()
        assert installer.subscription_id == 9527
        assert installer.deployment.related_params == {
            "subscription_id": 9527,
            "subscription_id_history": [9527],
            "subscription_task_id": 1002,
        }
        assert installer.deployment.status == "deploying"
        assert installer.deployment_version is deployment_version
        assert result == {
            "deployment_id": 1,
            "subscription_task_id": 1002,
            "subscription_id": 9527,
            "diff_result": {"changed": True},
        }

    def test_install_create_subscription_requires_task_id(self) -> None:
        """测试 install 在创建订阅时仍然要求节点管理返回 task_id。"""
        installer, _ = _build_installer()
        deployment_version = _build_deployment_version()
        deployment_model = SimpleNamespace(bk_tenant_id="test_tenant", bk_biz_id=2)
        filter_result = MagicMock()
        filter_result.exclude.return_value.update.return_value = None

        with patch.object(installer, "_get_current_deployment_version", return_value=None), patch.object(
            installer, "get_version_diff", return_value=(True, {"changed": True})
        ), patch.object(
            installer, "_create_subscription", return_value={"subscription_id": 9527}
        ), patch.object(
            installer, "_save"
        ) as mock_save, patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentModel.objects.get",
            return_value=deployment_model,
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.update_or_create"
        ), patch(
            "bk_monitor_base.domains.metric_plugin.installer.nodeman.MetricPluginDeploymentVersionModel.objects.filter",
            return_value=filter_result,
        ):
            with pytest.raises(KeyError, match="task_id"):
                installer.install(deployment_version)

        filter_result.exclude.assert_called_once_with(version=deployment_version.version)
        filter_result.exclude.return_value.update.assert_called_once_with(is_current=False)
        mock_save.assert_not_called()
