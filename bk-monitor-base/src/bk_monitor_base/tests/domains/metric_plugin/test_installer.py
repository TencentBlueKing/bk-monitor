"""
测试 metric_plugin.installer.base 模块
"""

import pytest

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError
from bk_monitor_base.domains.metric_plugin.installer.base import BaseInstaller
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)


class ConcreteInstaller(BaseInstaller):
    """具体安装器实现，用于测试"""

    def install(self, deployment_version: MetricPluginDeploymentVersion):
        """安装特定的部署版本"""
        return {"status": "installed", "version": deployment_version.version}

    def uninstall(self):
        """卸载"""
        return {"status": "uninstalled"}

    def stop(self):
        """停止"""
        return {"status": "stopped"}

    def start(self):
        """启动"""
        return {"status": "started"}

    def run(self, action: str | None = None, scope: MetricPluginDeploymentScope | None = None):
        """主动执行操作"""
        return {"status": "run", "action": action}

    def retry(self, scope: MetricPluginDeploymentScope | None = None):
        """重试"""
        return {"status": "retry"}

    def revoke(self, scope: MetricPluginDeploymentScope | None = None):
        """终止"""
        return {"status": "revoked"}

    def status(self, *args, **kwargs):
        """状态"""
        return {"status": "running"}


@pytest.mark.django_db(databases=["default"])
class TestBaseInstaller:
    """测试 BaseInstaller 基类"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="test_plugin", type="script", created_by="admin"
        )
        self.version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )
        self.deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

    def test_init_success(self):
        """测试初始化 - 成功"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        assert installer.operator == "admin"
        assert installer.deployment == deployment
        assert installer.plugin.id == "test_plugin"
        assert installer.plugin.bk_tenant_id == "test_tenant"

    def test_init_plugin_not_found(self):
        """测试初始化 - 插件不存在"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="nonexistent_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        with pytest.raises(MetricPluginNotFoundError, match="插件不存在"):
            ConcreteInstaller(deployment, operator="admin")

    def test_init_plugin_deleted(self):
        """测试初始化 - 插件已删除"""
        # 标记插件为已删除
        self.plugin_model.is_deleted = True
        self.plugin_model.save()

        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        with pytest.raises(MetricPluginNotFoundError, match="插件不存在"):
            ConcreteInstaller(deployment, operator="admin")

    def test_get_current_version_none(self):
        """测试获取当前部署版本 - 无版本"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        current_version = installer._get_current_deployment_version()
        assert current_version is None

    def test_get_current_version_exists(self):
        """测试获取当前部署版本 - 存在版本"""
        # 创建部署版本
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"key": "value"},
            target_node_type="host",
            target_nodes=[{"ip": "127.0.0.1"}],
            created_by="admin",
        )

        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        current_version = installer._get_current_deployment_version()
        assert current_version is not None
        assert current_version.version == 1
        assert current_version.params == {"key": "value"}
        assert current_version.target_scope.node_type == "host"

    def test_get_current_version_not_current(self):
        """测试获取当前部署版本 - 版本不是当前版本"""
        # 创建非当前版本的部署版本
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=False,  # 不是当前版本
            params={},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )

        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        current_version = installer._get_current_deployment_version()
        assert current_version is None

    def test_get_current_version_multiple_versions(self):
        """测试获取当前部署版本 - 多个版本，获取最新的当前版本"""
        # 创建多个版本
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"version": 1},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=2,
            is_current=True,
            params={"version": 2},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )

        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        current_version = installer._get_current_deployment_version()
        # 应该返回第一个（.first()），由于排序是 ["deployment", "-version"]，.first() 返回的是版本号最新的
        assert current_version is not None
        assert current_version.version == 2
        assert current_version.params == {"version": 2}

    def test_install_method(self):
        """测试安装方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        deployment_version = MetricPluginDeploymentVersion(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment_id=self.deployment_model.pk,
            plugin_version=VersionTuple(1, 0),
            version=1,
            params={},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        result = installer.install(deployment_version)
        assert result["status"] == "installed"
        assert result["version"] == 1

    def test_uninstall_method(self):
        """测试卸载方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.uninstall()
        assert result["status"] == "uninstalled"

    def test_stop_method(self):
        """测试停止方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.stop()
        assert result["status"] == "stopped"

    def test_start_method(self):
        """测试启动方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.start()
        assert result["status"] == "started"

    def test_run_method(self):
        """测试运行方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.run(action="test_action")
        assert result["status"] == "run"
        assert result["action"] == "test_action"

    def test_retry_method(self):
        """测试重试方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.retry()
        assert result["status"] == "retry"

    def test_revoke_method(self):
        """测试终止方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.revoke()
        assert result["status"] == "revoked"

    def test_status_method(self):
        """测试状态方法"""
        deployment = MetricPluginDeployment(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id=self.deployment_model.pk,
            plugin_id="test_plugin",
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )

        installer = ConcreteInstaller(deployment, operator="admin")
        result = installer.status()
        assert result["status"] == "running"
