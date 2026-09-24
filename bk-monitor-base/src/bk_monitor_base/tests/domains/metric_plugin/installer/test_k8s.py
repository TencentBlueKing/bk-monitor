"""
测试 K8sInstaller

验证 K8S 安装器的核心行为：
1. install / uninstall / start / stop / retry / revoke / status 全套方法
2. _create_or_update_dynamic_resource 幂等性（MD5 对比）
3. _get_context 上下文构建
4. K8S API 异常容错
"""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from kubernetes import client as k8s_client

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.installer.k8s import (
    K8sInstaller,
    _jinja_render,
)
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)

BK_TENANT_ID = "test_tenant_k8s_inst"
BK_BIZ_ID = 200
OPERATOR = "admin"
PLUGIN_ID = "qcloud-exporter-200"
CLUSTER_ID = "BCS-K8S-00001"
NAMESPACE = "bk-monitor-plugin"


@pytest.fixture
def k8s_plugin() -> MetricPlugin:
    """创建 K8S 测试插件"""
    return MetricPlugin(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        id=PLUGIN_ID,
        type="k8s",
        name="腾讯云指标采集",
        label="os",
        define={
            "template": ("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ release_name }}\n"),
            "values": {"replicas": 1},
        },
        params=[],
        version=VersionTuple(1, 0),
        status=MetricPluginStatus.RELEASE,
        created_by=OPERATOR,
        updated_by=OPERATOR,
        related_params={"data_id": 50001},
    )


@pytest.fixture
def k8s_deployment() -> MetricPluginDeployment:
    """创建 K8S 测试部署项"""
    return MetricPluginDeployment(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        id=300,
        name="K8S采集部署",
        plugin_id=PLUGIN_ID,
        status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        related_params={},
    )


@pytest.fixture
def k8s_deployment_version(k8s_deployment: MetricPluginDeployment) -> MetricPluginDeploymentVersion:
    """创建 K8S 测试部署版本"""
    return MetricPluginDeploymentVersion(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        deployment_id=k8s_deployment.id,
        plugin_version=VersionTuple(1, 0),
        version=1,
        target_scope=MetricPluginDeploymentScope(
            node_type="bcs_cluster",
            nodes=[{"bcs_cluster_id": CLUSTER_ID, "namespace": NAMESPACE}],
        ),
        remote_scope=None,
        params={
            "collector": {"period": 60, "timeout": 30},
            "plugin": {"replicas": 2},
        },
    )


@pytest.fixture
def mock_k8s_config():
    """Mock K8S 配置和 get_config"""
    config_mock = MagicMock()
    bcs_config = config_mock.blueking.bcs
    bcs_config.api_gateway_host = "bcs.example.com"
    bcs_config.api_gateway_port = 443
    bcs_config.api_gateway_schema = "https"
    bcs_config.api_gateway_token = "test-token"
    bcs_config.cluster_bk_env_label = ""

    with patch(
        "bk_monitor_base.domains.metric_plugin.installer.k8s.get_config",
        return_value=config_mock,
    ):
        yield config_mock


@pytest.fixture
def mock_k8s_clients():
    """Mock kubernetes client 和 dynamic client"""
    with (
        patch("bk_monitor_base.domains.metric_plugin.installer.k8s.k8s_client") as mock_client,
        patch("bk_monitor_base.domains.metric_plugin.installer.k8s.k8s_dynamic") as mock_dynamic,
    ):
        api_client_ctx = MagicMock()
        api_client_instance = MagicMock()
        api_client_ctx.__enter__ = Mock(return_value=api_client_instance)
        api_client_ctx.__exit__ = Mock(return_value=False)
        mock_client.ApiClient.return_value = api_client_ctx

        core_v1 = MagicMock()
        mock_client.CoreV1Api.return_value = core_v1

        mock_client.Configuration = k8s_client.Configuration
        mock_client.exceptions = k8s_client.exceptions

        dynamic_client = MagicMock()
        mock_dynamic.DynamicClient.return_value = dynamic_client

        resource_client = MagicMock()
        dynamic_client.resources.get.return_value = resource_client

        not_found = k8s_client.exceptions.ApiException(status=404)
        resource_client.get.side_effect = not_found

        yield {
            "client_module": mock_client,
            "dynamic_module": mock_dynamic,
            "api_client": api_client_instance,
            "core_v1": core_v1,
            "dynamic_client": dynamic_client,
            "resource_client": resource_client,
        }


@pytest.mark.django_db(databases=["default"])
class TestK8sInstaller:
    """测试 K8sInstaller"""

    @pytest.fixture(autouse=True)
    def setup(
        self,
        k8s_plugin: MetricPlugin,
        k8s_deployment: MetricPluginDeployment,
        k8s_deployment_version: MetricPluginDeploymentVersion,
        mock_k8s_config: MagicMock,
        mock_k8s_clients: dict[str, Any],
    ):
        """创建数据库记录和安装器实例"""
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=k8s_plugin.bk_tenant_id,
            bk_biz_id=k8s_plugin.bk_biz_id,
            plugin_id=k8s_plugin.id,
            type=k8s_plugin.type,
            label=k8s_plugin.label,
            created_by=k8s_plugin.created_by,
            related_params=k8s_plugin.related_params,
        )
        self.version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id=k8s_plugin.bk_tenant_id,
            bk_biz_id=k8s_plugin.bk_biz_id,
            plugin=self.plugin_model,
            name=k8s_plugin.name,
            params=[],
            define=k8s_plugin.define,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )
        self.deployment_model = MetricPluginDeploymentModel.objects.create(
            id=k8s_deployment.id,
            bk_tenant_id=k8s_deployment.bk_tenant_id,
            bk_biz_id=k8s_deployment.bk_biz_id,
            plugin=self.plugin_model,
            name=k8s_deployment.name,
            status=k8s_deployment.status,
            related_params=k8s_deployment.related_params,
        )

        self.k8s_plugin = k8s_plugin
        self.k8s_deployment = k8s_deployment
        self.k8s_deployment_version = k8s_deployment_version
        self.mock_k8s_clients = mock_k8s_clients

        self.installer = K8sInstaller(deployment=k8s_deployment, operator=OPERATOR)

    def test_install_creates_version_and_deploys(self):
        """install 应保存部署版本记录并部署 K8S 资源"""
        result = self.installer.install(self.k8s_deployment_version)

        assert result is not None

        version_count = MetricPluginDeploymentVersionModel.objects.filter(deployment=self.deployment_model).count()
        assert version_count == 1

        current = MetricPluginDeploymentVersionModel.objects.get(deployment=self.deployment_model, is_current=True)
        assert current.version == 1

        self.mock_k8s_clients["resource_client"].create.assert_called()

    def test_install_updates_deployment_status(self):
        """install 成功后部署状态应为 RUNNING"""
        self.installer.install(self.k8s_deployment_version)

        deployment = MetricPluginDeploymentModel.objects.get(id=self.k8s_deployment.id)
        assert deployment.status == MetricPluginDeploymentStatusEnum.RUNNING.value

    def test_install_failure_sets_failed_status(self):
        """install 部署失败时状态应为 FAILED"""
        self.mock_k8s_clients["resource_client"].create.side_effect = k8s_client.exceptions.ApiException(
            status=500, reason="Internal Server Error"
        )

        self.installer.install(self.k8s_deployment_version)

        deployment = MetricPluginDeploymentModel.objects.get(id=self.k8s_deployment.id)
        assert deployment.status == MetricPluginDeploymentStatusEnum.FAILED.value

    def test_uninstall_deletes_resources(self):
        """uninstall 应删除 K8S 资源和部署版本记录"""
        self.installer.install(self.k8s_deployment_version)

        self.installer.uninstall()

        version_count = MetricPluginDeploymentVersionModel.objects.filter(deployment=self.deployment_model).count()
        assert version_count == 0

    def test_stop_undeploys_resources(self):
        """stop 应卸载 K8S 资源并更新状态为 STOPPED"""
        self.installer.install(self.k8s_deployment_version)

        self.installer.stop()

        deployment = MetricPluginDeploymentModel.objects.get(id=self.k8s_deployment.id)
        assert deployment.status == MetricPluginDeploymentStatusEnum.STOPPED.value

    def test_start_redeploys_resources(self):
        """start 应重新部署 K8S 资源并更新状态为 RUNNING"""
        self.installer.install(self.k8s_deployment_version)
        self.installer.stop()

        self.installer.start()

        deployment = MetricPluginDeploymentModel.objects.get(id=self.k8s_deployment.id)
        assert deployment.status == MetricPluginDeploymentStatusEnum.RUNNING.value

    def test_retry_redeploys_resources(self):
        """retry 应重新部署当前版本"""
        self.installer.install(self.k8s_deployment_version)

        self.installer.retry()

        deployment = MetricPluginDeploymentModel.objects.get(id=self.k8s_deployment.id)
        assert deployment.status == MetricPluginDeploymentStatusEnum.RUNNING.value

    def test_revoke_is_noop(self):
        """revoke 对 K8S 类型应为空操作"""
        result = self.installer.revoke()
        assert result is None

    def test_status_returns_status_dict(self):
        """status 应返回包含 deployment_status 的字典"""
        self.installer.install(self.k8s_deployment_version)

        result = self.installer.status()

        assert "deployment_status" in result
        assert "instance_count" in result
        assert "instance_status" in result
        assert result["instance_count"] == 1

    def test_status_stopped_deployment(self):
        """已停止的部署 status 应返回 stopped 实例状态"""
        self.installer.install(self.k8s_deployment_version)
        self.installer.stop()

        result = self.installer.status()

        assert result["instance_status"]["default"]["status"] == "stopped"

    def test_status_no_current_version(self):
        """无当前版本时 status 应返回空实例"""
        result = self.installer.status()

        assert result["instance_count"] == 0
        assert result["instance_status"] == {}


@pytest.mark.django_db(databases=["default"])
class TestK8sInstallerContext:
    """测试 K8sInstaller._get_context"""

    @pytest.fixture(autouse=True)
    def setup(
        self,
        k8s_plugin: MetricPlugin,
        k8s_deployment: MetricPluginDeployment,
        k8s_deployment_version: MetricPluginDeploymentVersion,
        mock_k8s_config: MagicMock,
    ):
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=k8s_plugin.bk_tenant_id,
            bk_biz_id=k8s_plugin.bk_biz_id,
            plugin_id=k8s_plugin.id,
            type=k8s_plugin.type,
            label=k8s_plugin.label,
            created_by=k8s_plugin.created_by,
            related_params=k8s_plugin.related_params,
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=k8s_plugin.bk_tenant_id,
            bk_biz_id=k8s_plugin.bk_biz_id,
            plugin=self.plugin_model,
            name=k8s_plugin.name,
            params=[],
            define=k8s_plugin.define,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )
        MetricPluginDeploymentModel.objects.create(
            id=k8s_deployment.id,
            bk_tenant_id=k8s_deployment.bk_tenant_id,
            bk_biz_id=k8s_deployment.bk_biz_id,
            plugin=self.plugin_model,
            name=k8s_deployment.name,
            status=k8s_deployment.status,
            related_params=k8s_deployment.related_params,
        )

        self.installer = K8sInstaller(deployment=k8s_deployment, operator=OPERATOR)
        self.deployment_version = k8s_deployment_version
        self.mock_k8s_config = mock_k8s_config

    def test_context_basic_fields(self):
        """验证上下文基本字段"""
        context = self.installer._get_context(self.deployment_version)

        assert context["bk_biz_id"] == BK_BIZ_ID
        assert context["cluster_id"] == CLUSTER_ID
        assert context["namespace"] == NAMESPACE
        assert context["plugin"]["id"] == PLUGIN_ID
        assert context["plugin"]["data_id"] == 50001
        assert context["collect"]["period"] == 60
        assert context["collect"]["timeout"] == 30

    def test_context_release_name_without_env(self):
        """无 bk_env 时 release_name 不含环境后缀"""
        context = self.installer._get_context(self.deployment_version)

        expected_plugin_id = PLUGIN_ID.replace("_", "-")
        assert context["release_name"] == "bk-monitor-collector-300"
        assert context["plugin_release_name"] == f"bk-monitor-plugin-{expected_plugin_id}"
        assert context["bk_env"] == ""

    def test_context_release_name_with_env(self):
        """有 bk_env 时 release_name 包含环境后缀"""
        self.mock_k8s_config.blueking.bcs.cluster_bk_env_label = "prod"

        context = self.installer._get_context(self.deployment_version)

        expected_plugin_id = PLUGIN_ID.replace("_", "-")
        assert context["release_name"] == "bk-monitor-collector-300-prod"
        assert context["plugin_release_name"] == f"bk-monitor-plugin-{expected_plugin_id}-prod"
        assert context["bk_env"] == "prod"

    def test_context_merges_plugin_params_to_values(self):
        """采集参数中 plugin 字段应合并到 values"""
        context = self.installer._get_context(self.deployment_version)

        assert context["values"]["replicas"] == 2


class TestK8sInstallerCompareMd5:
    """测试 K8sInstaller._compare_md5"""

    def test_no_existing_config(self):
        """无已存在配置时应返回有差异"""
        diff, md5 = K8sInstaller._compare_md5({"key": "value"}, None)
        assert diff is True
        assert md5 != ""

    def test_same_config(self):
        """相同配置应返回无差异"""
        import hashlib
        import json

        config = {"key": "value"}
        md5 = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()
        exists = {"metadata": {"annotations": {"app.kubernetes.io/config-md5": md5}}}

        diff, new_md5 = K8sInstaller._compare_md5(config, exists)
        assert diff is False
        assert new_md5 == md5

    def test_different_config(self):
        """不同配置应返回有差异"""
        config = {"key": "new_value"}
        exists = {"metadata": {"annotations": {"app.kubernetes.io/config-md5": "old_md5"}}}

        diff, _ = K8sInstaller._compare_md5(config, exists)
        assert diff is True


class TestJinjaRender:
    """测试 _jinja_render 辅助函数"""

    def test_basic_render(self):
        """基本模板渲染"""
        result = _jinja_render("Hello {{ name }}", {"name": "World"})
        assert result == "Hello World"

    def test_conditional_render(self):
        """条件渲染"""
        template = "{%- if show %}visible{%- endif %}"
        assert _jinja_render(template, {"show": True}) == "visible"
        assert _jinja_render(template, {"show": False}) == ""


@pytest.mark.django_db(databases=["default"])
class TestK8sInstallerRegistration:
    """测试 K8sInstaller 在安装器映射中的注册"""

    def test_registered_in_installers(self):
        """K8sInstaller 应注册在 INSTALLERS 映射中"""
        from bk_monitor_base.domains.metric_plugin.installer.tools import INSTALLERS

        assert "k8s" in INSTALLERS
        assert INSTALLERS["k8s"] is K8sInstaller
