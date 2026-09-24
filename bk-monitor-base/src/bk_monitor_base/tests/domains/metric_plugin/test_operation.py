"""
测试 metric_plugin.operation 模块
"""

from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.define import (
    CreateOrUpdateDeploymentParams,
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPlugin,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginStatus,
    UpdatePluginVersionParams,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.errors import (
    MetricPluginDeploymentNotFoundError,
    MetricPluginDeploymentOperationError,
    MetricPluginDeploymentStatusError,
    MetricPluginManagerNotFoundError,
    MetricPluginNotFoundError,
    MetricPluginVersionNotFoundError,
    PluginIDExistsError,
)
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metric_plugin import (
    apply_metric_plugin_data_link,
    count_metric_plugin_type,
    create_metric_plugin,
    create_metric_plugin_version,
    debug_job_plugin,
    debug_nodeman_plugin,
    delete_metric_plugin,
    delete_metric_plugin_deployment,
    export_metric_plugin_package,
    get_job_plugin_debug_log,
    get_metric_plugin,
    get_metric_plugin_deployment,
    get_metric_plugin_deployment_status,
    get_metric_plugin_supported_os_types,
    get_metric_plugin_versions,
    get_nodeman_plugin_debug_log,
    list_metric_plugin_deployments,
    list_metric_plugins,
    parse_metric_plugin_package,
    refresh_metric_plugin_metrics,
    release_metric_plugin_version,
    save_and_install_metric_plugin_deployment,
    start_metric_plugin_deployment,
    stop_job_plugin_debug,
    stop_metric_plugin_deployment,
    stop_nodeman_plugin_debug,
    update_metric_plugin_version,
)


@pytest.fixture(autouse=True)
def plugin_model():
    """设置测试数据"""
    return MetricPluginModel.objects.create(
        bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="test_plugin", type="script", created_by="admin"
    )


@pytest.fixture(autouse=True)
def version_model(plugin_model):
    """设置测试数据"""
    return MetricPluginVersionModel.objects.create(
        bk_tenant_id="test_tenant",
        bk_biz_id=1,
        plugin=plugin_model,
        name="测试插件",
        description_md="# 测试插件",
        params=[],
        define={"script": "echo 'test'"},
        version="000001.000000",
        version_log="初始版本",
        status=MetricPluginStatus.DEBUG,
        updated_by="admin",
    )


class TestParseMetricPluginPackage:
    """测试插件包解析入口函数。"""

    def test_parse_metric_plugin_package_supports_directory(self, tmp_path: Path, mocker: MockerFixture):
        """测试目录输入会被原样传递给对应插件管理器。

        这里不重复验证底层解析细节，只校验 operation 层会正确识别类型并把目录路径透传。
        """
        # Arrange
        package_dir = tmp_path / "plugin_package"
        package_dir.mkdir()
        expected_result = CreatePluginParams(
            id="test_plugin",
            type="script",
            name="测试插件",
            description_md="# 测试插件",
            label="component",
            params=[],
            define={"script": "echo test"},
            version=VersionTuple(major=1, minor=0),
            version_log="初始化版本",
            status=MetricPluginStatus.DEBUG,
        )
        mock_get_plugin_type = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_type_from_package",
            return_value="script",
        )
        mock_plugin_manager = mocker.Mock()
        mock_plugin_manager.parse_package.return_value = expected_result
        mock_get_manager_class = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager_class",
            return_value=mock_plugin_manager,
        )

        # Act
        result = parse_metric_plugin_package("test_tenant", package_dir, "admin")

        # Assert
        mock_get_plugin_type.assert_called_once_with(package_file=package_dir)
        mock_get_manager_class.assert_called_once_with(plugin_type="script")
        mock_plugin_manager.parse_package.assert_called_once_with(
            bk_tenant_id="test_tenant",
            package_file=package_dir,
            operator="admin",
        )
        assert result == expected_result

    def test_parse_metric_plugin_package_supports_job_plugin_directory(self, tmp_path: Path, mocker: MockerFixture):
        """测试导入入口可以从 job_plugins 目录识别作业平台插件类型。"""
        package_dir = tmp_path / "plugin_package"
        meta_file = package_dir / "job_plugins_linux_x86_64" / "bkplugin_mysql" / "info" / "meta.yaml"
        meta_file.parent.mkdir(parents=True)
        meta_file.write_text("plugin_type: job_mysql\n", encoding="utf-8")
        expected_result = CreatePluginParams(
            id="bkplugin_mysql",
            type="job_mysql",
            name="MySQL 作业插件",
            description_md="# MySQL 作业插件",
            label="component",
            params=[],
            define={},
            version=VersionTuple(major=1, minor=0),
            version_log="初始化版本",
            status=MetricPluginStatus.DEBUG,
        )
        mock_plugin_manager = mocker.Mock()
        mock_plugin_manager.parse_package.return_value = expected_result
        mock_get_manager_class = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager_class",
            return_value=mock_plugin_manager,
        )

        result = parse_metric_plugin_package("test_tenant", package_dir, "admin")

        mock_get_manager_class.assert_called_once_with(plugin_type="job_mysql")
        mock_plugin_manager.parse_package.assert_called_once_with(
            bk_tenant_id="test_tenant",
            package_file=package_dir,
            operator="admin",
        )
        assert result == expected_result


@pytest.mark.django_db(databases=["default"])
class TestListPlugins:
    """测试 list_plugins 函数"""

    def setUp(self):
        """设置测试数据"""
        # 创建插件模型
        self.plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="test_plugin", type="script", created_by="admin"
        )

        # 创建版本模型
        self.version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试插件",
            description_md="# 测试插件",
            params=[],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

    def test_list_plugins_basic(self):
        """测试基本插件列表"""
        plugins, total = list_metric_plugins()
        assert total == 1
        assert len(plugins) == 1
        plugin = plugins[0]
        assert plugin["id"] == "test_plugin"
        assert plugin["name"] == "测试插件"
        assert plugin["type"] == "script"
        # 默认不统计部署项数量：deployment_count 应为 None，避免误解为 0
        assert plugin["deployment_count"] is None

    def test_list_plugins_with_deployment_count_basic(self, plugin_model):
        """测试开启 with_deployment_count 时能返回正确的部署项数量。"""
        # Arrange: 创建两个部署项
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id=plugin_model.bk_tenant_id,
            bk_biz_id=plugin_model.bk_biz_id,
            plugin=plugin_model,
            name="deployment_1",
            created_by="admin",
        )
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id=plugin_model.bk_tenant_id,
            bk_biz_id=plugin_model.bk_biz_id,
            plugin=plugin_model,
            name="deployment_2",
            created_by="admin",
        )

        # Act
        plugins, total = list_metric_plugins(with_deployment_count=True)

        # Assert
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["deployment_count"] == 2

    def test_list_plugins_with_deployment_count_multi_tenant_same_plugin_id(self, plugin_model):
        """测试多租户同名 plugin_id 时，deployment_count 不应跨租户聚合串账。"""
        # Arrange: 创建另一个租户的同名插件（plugin_id 相同，但 bk_tenant_id 不同）
        other_plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id="other_tenant",
            bk_biz_id=1,
            plugin_id=plugin_model.plugin_id,
            type="script",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="other_tenant",
            bk_biz_id=1,
            plugin=other_plugin_model,
            name="其他租户插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # 当前租户：1 个部署项；其他租户：2 个部署项
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id=plugin_model.bk_tenant_id,
            bk_biz_id=plugin_model.bk_biz_id,
            plugin=plugin_model,
            name="tenant_deployment_1",
            created_by="admin",
        )
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id=other_plugin_model.bk_tenant_id,
            bk_biz_id=other_plugin_model.bk_biz_id,
            plugin=other_plugin_model,
            name="other_deployment_1",
            created_by="admin",
        )
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id=other_plugin_model.bk_tenant_id,
            bk_biz_id=other_plugin_model.bk_biz_id,
            plugin=other_plugin_model,
            name="other_deployment_2",
            created_by="admin",
        )

        # Act: 仅按 plugin_id 过滤，命中两个租户的同名插件
        plugins, total = list_metric_plugins(plugin_ids=[plugin_model.plugin_id], with_deployment_count=True)

        # Assert
        assert total == 2
        assert len(plugins) == 2
        deployment_count_by_tenant = {p["bk_tenant_id"]: p["deployment_count"] for p in plugins}
        assert deployment_count_by_tenant["test_tenant"] == 1
        assert deployment_count_by_tenant["other_tenant"] == 2

    def test_list_plugins_filter_tenant(self):
        """测试按租户过滤"""
        plugins, total = list_metric_plugins(bk_tenant_id="test_tenant")
        assert total == 1
        assert len(plugins) == 1

        plugins, total = list_metric_plugins(bk_tenant_id="other_tenant")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_filter_biz_ids(self):
        """测试按业务ID过滤"""
        plugins, total = list_metric_plugins(bk_biz_ids=[1])
        assert total == 1
        assert len(plugins) == 1

        plugins, total = list_metric_plugins(bk_biz_ids=[2])
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_filter_global(self):
        """测试按全局插件过滤"""
        # 创建全局插件
        global_plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="global_plugin",
            type="script",
            is_global=True,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=global_plugin_model,
            name="全局插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        plugins, total = list_metric_plugins(is_global=True)
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "global_plugin"

    def test_list_plugins_filter_internal(self):
        """测试按内置插件过滤"""
        # 创建内置插件
        internal_plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="internal_plugin",
            type="script",
            is_internal=True,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=internal_plugin_model,
            name="内置插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        plugins, total = list_metric_plugins(is_internal=True)
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "internal_plugin"

    def test_list_plugins_filter_plugin_ids(self):
        """测试按插件ID过滤"""
        plugins, total = list_metric_plugins(plugin_ids=["test_plugin"])
        assert total == 1
        assert len(plugins) == 1

        plugins, total = list_metric_plugins(plugin_ids=["nonexistent_plugin"])
        assert total == 0
        assert len(plugins) == 0

        plugins, total = list_metric_plugins(plugin_ids=[])
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_filter_plugin_types(self):
        """测试按插件类型过滤"""
        plugins, total = list_metric_plugins(plugin_types=["script"])
        assert total == 1
        assert len(plugins) == 1

        plugins, total = list_metric_plugins(plugin_types=["exporter"])
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_by_name(self):
        """测试按插件名称搜索"""
        plugins, total = list_metric_plugins(search="测试插件")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "测试插件"

        plugins, total = list_metric_plugins(search="其他插件")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_by_name_partial(self):
        """测试按插件名称部分匹配搜索"""
        plugins, total = list_metric_plugins(search="测试")
        assert total == 1
        assert len(plugins) == 1
        assert "测试" in plugins[0]["name"]

        plugins, total = list_metric_plugins(search="其他")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_by_plugin_id(self):
        """测试按插件ID搜索"""
        plugins, total = list_metric_plugins(search="test_plugin")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "test_plugin"

        plugins, total = list_metric_plugins(search="nonexistent")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_case_insensitive(self):
        """测试搜索不区分大小写"""
        plugins, total = list_metric_plugins(search="TEST_PLUGIN")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "test_plugin"

        plugins, total = list_metric_plugins(search="测试")
        assert total == 1
        assert len(plugins) == 1

    def test_list_plugins_search_with_other_filters(self):
        """测试搜索与其他过滤条件的组合"""
        # 创建第二个插件用于测试
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            plugin_id="another_plugin",
            type="exporter",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            plugin=plugin_model2,
            name="另一个测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索 + 业务ID过滤
        plugins, total = list_metric_plugins(search="测试", bk_biz_ids=[1])
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "test_plugin"

        # 搜索 + 插件类型过滤
        plugins, total = list_metric_plugins(search="测试", plugin_types=["script"])
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["type"] == "script"

    def test_list_plugins_search_latest_version_name(self):
        """测试搜索使用最新版本的名称（debug版本）"""
        # 创建插件并添加多个版本
        plugin_model = MetricPluginModel.objects.get(plugin_id="test_plugin")
        # 创建新版本，名称不同
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="新版本名称",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索应该匹配最新版本的名称
        plugins, total = list_metric_plugins(search="新版本")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "新版本名称"

        # 旧版本名称不应该匹配（因为不是最新版本）
        plugins, total = list_metric_plugins(search="测试插件")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_release_version_priority(self):
        """测试搜索优先使用release版本的最新版本名称"""
        # 创建插件并添加多个版本
        plugin_model = MetricPluginModel.objects.get(plugin_id="test_plugin")
        # 创建 release 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="Release版本名称",
            params=[],
            define={},
            version="000001.000001",
            status=MetricPluginStatus.RELEASE,
        )
        # 创建更新的 debug 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="Debug版本名称",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索应该匹配 release 版本的最新版本名称（优先 release）
        plugins, total = list_metric_plugins(search="Release")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "Release版本名称"

        # Debug 版本名称不应该匹配（因为有 release 版本）
        plugins, total = list_metric_plugins(search="Debug")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_release_latest_version(self):
        """测试搜索release版本时只搜索最新版本"""
        # 创建插件并添加多个 release 版本
        plugin_model = MetricPluginModel.objects.get(plugin_id="test_plugin")
        # 创建第一个 release 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧Release版本",
            params=[],
            define={},
            version="000001.000001",
            status=MetricPluginStatus.RELEASE,
        )
        # 创建更新的 release 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="新Release版本",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.RELEASE,
        )

        # 搜索应该匹配最新 release 版本的名称
        plugins, total = list_metric_plugins(search="新Release")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "新Release版本"

        # 旧 release 版本名称不应该匹配（因为不是最新版本）
        plugins, total = list_metric_plugins(search="旧Release")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_debug_when_no_release(self):
        """测试当没有release版本时，搜索debug版本的最新版本"""
        # 创建新插件，只有 debug 版本
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="debug_only_plugin",
            type="script",
            created_by="admin",
        )
        # 创建第一个 debug 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="旧Debug版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )
        # 创建更新的 debug 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="新Debug版本",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索应该匹配最新 debug 版本的名称
        plugins, total = list_metric_plugins(search="新Debug")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "新Debug版本"

        # 旧 debug 版本名称不应该匹配（因为不是最新版本）
        plugins, total = list_metric_plugins(search="旧Debug")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_search_multiple_plugins_with_different_versions(self):
        """测试多个插件，每个插件有不同版本类型的搜索"""
        # 创建插件1：有 release 版本
        plugin_model1 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="plugin_with_release",
            type="script",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model1,
            name="Release插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        # 创建插件2：只有 debug 版本
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="plugin_with_debug",
            type="script",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="Debug插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索 release 插件
        plugins, total = list_metric_plugins(search="Release")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "plugin_with_release"

        # 搜索 debug 插件
        plugins, total = list_metric_plugins(search="Debug")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["id"] == "plugin_with_debug"

    def test_list_plugins_search_version_major_minor_ordering(self):
        """测试版本号排序：确保搜索使用正确的版本（按major和minor排序）"""
        plugin_model = MetricPluginModel.objects.get(plugin_id="test_plugin")
        # 创建版本 1.1
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="版本1.1",
            params=[],
            define={},
            version="000001.000001",
            status=MetricPluginStatus.DEBUG,
        )
        # 创建版本 1.2（应该是最新版本）
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="版本1.2",
            params=[],
            define={},
            version="000001.000002",
            status=MetricPluginStatus.DEBUG,
        )
        # 创建版本 2.0（应该是最新版本）
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="版本2.0",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 搜索应该匹配最新版本 2.0
        plugins, total = list_metric_plugins(search="版本2.0")
        assert total == 1
        assert len(plugins) == 1
        assert plugins[0]["name"] == "版本2.0"

        # 旧版本不应该匹配
        plugins, total = list_metric_plugins(search="版本1.1")
        assert total == 0
        assert len(plugins) == 0

        plugins, total = list_metric_plugins(search="版本1.2")
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_pagination(self):
        """测试分页"""
        # 创建第二个插件
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="test_plugin2", type="script", created_by="admin"
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="测试插件2",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        plugins, total = list_metric_plugins(limit=1)
        assert total == 2  # 总共有2个插件
        assert len(plugins) == 1

        plugins, total = list_metric_plugins(offset=1, limit=1)
        assert total == 2  # 总共有2个插件
        assert len(plugins) == 1

    def test_list_plugins_order_by_updated_at(self):
        """测试按 updated_at 排序。"""
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="test_plugin2",
            type="script",
            created_by="admin",
        )
        version_model2 = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="测试插件2",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # 手动调整更新时间：test_plugin2 更新更晚
        old_time = timezone.now() - timedelta(days=1)
        now_time = timezone.now()
        MetricPluginVersionModel.objects.filter(plugin__plugin_id="test_plugin").update(updated_at=old_time)
        MetricPluginVersionModel.objects.filter(pk=version_model2.pk).update(updated_at=now_time)

        plugins, _ = list_metric_plugins(order="-updated_at")
        assert [plugin["id"] for plugin in plugins][:2] == ["test_plugin2", "test_plugin"]

    def test_list_plugins_order_by_status(self):
        """测试按状态排序：draft 在 normal 前。"""
        plugin_model2 = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="release_plugin",
            type="script",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model2,
            name="发布插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
            updated_by="admin",
        )

        plugins, _ = list_metric_plugins(order="status")
        assert [plugin["id"] for plugin in plugins][:2] == ["test_plugin", "release_plugin"]

    def test_list_plugins_version_not_found(self, version_model):
        """测试版本不存在的情况"""
        # 删除版本模型
        version_model.delete()

        plugins, total = list_metric_plugins()
        assert total == 0
        assert len(plugins) == 0

    def test_list_plugins_query_count_constant(self, django_assert_num_queries):
        """测试查询次数为常量级，避免 N+1 查询回归。

        关注点：
        - list_metric_plugins() 分页后不应对每个插件循环查询 release/debug 版本。
        - search 分支也应复用注解字段，在 DB 侧完成过滤，查询次数不随插件数量增长。
        """
        for i in range(20):
            plugin_model = MetricPluginModel.objects.create(
                bk_tenant_id="test_tenant",
                bk_biz_id=1,
                plugin_id=f"test_plugin_{i}",
                type="script",
                created_by="admin",
            )
            MetricPluginVersionModel.objects.create(
                bk_tenant_id="test_tenant",
                bk_biz_id=1,
                plugin=plugin_model,
                name=f"Debug{i}",
                params=[],
                define={},
                version="000001.000000",
                status=MetricPluginStatus.DEBUG,
                updated_by="admin",
            )
            # 偶数插件额外创建 release 版本，用于覆盖“release 优先”的路径
            if i % 2 == 0:
                MetricPluginVersionModel.objects.create(
                    bk_tenant_id="test_tenant",
                    bk_biz_id=1,
                    plugin=plugin_model,
                    name=f"Release{i}",
                    params=[],
                    define={},
                    version="000001.000001",
                    status=MetricPluginStatus.RELEASE,
                    updated_by="admin",
                )

        # 预期：count + list + 批量版本查询 = 3 次，且不随插件数量增长。
        with django_assert_num_queries(3):
            list_metric_plugins()

        with django_assert_num_queries(3):
            list_metric_plugins(search="Release")

        # 开启 with_deployment_count 会额外触发一次部署项聚合查询：count + list + versions + deployment_count = 4 次
        with django_assert_num_queries(4):
            list_metric_plugins(with_deployment_count=True)


@pytest.mark.django_db(databases=["default"])
class TestCountMetricPluginType:
    """测试 count_metric_plugin_type 函数"""

    def test_count_metric_plugin_type_basic(self):
        """测试基础统计：默认仅统计有版本插件。"""
        result = count_metric_plugin_type()
        assert result == {"script": 1}

    def test_count_metric_plugin_type_with_filters(self):
        """测试组合过滤：业务 + 含全局 + 标签 + 搜索。"""
        global_plugin = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=999,
            plugin_id="global_exporter",
            type="exporter",
            is_global=True,
            label="system",
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=999,
            plugin=global_plugin,
            name="全局导出插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        result = count_metric_plugin_type(
            bk_tenant_id="test_tenant",
            bk_biz_ids=[1],
            bk_biz_id_with_global=True,
            labels=["system"],
            search="导出",
        )
        assert result == {"exporter": 1}

    def test_count_metric_plugin_type_plugin_types_empty(self):
        """测试 plugin_types 为空列表时直接返回空统计。"""
        result = count_metric_plugin_type(plugin_types=[])
        assert result == {}

    def test_count_metric_plugin_type_exclude_plugin_without_version(self):
        """测试无版本插件不会进入统计。"""
        MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin_id="no_version_plugin",
            type="exporter",
            created_by="admin",
        )

        result = count_metric_plugin_type()
        assert result == {"script": 1}


@pytest.mark.django_db(databases=["default"])
class TestGetPlugin:
    """测试 get_metric_plugin 函数"""

    def test_get_plugin_success(self):
        """测试获取插件成功"""
        plugin = get_metric_plugin("test_tenant", "test_plugin")
        assert plugin.id == "test_plugin"
        assert plugin.name == "测试插件"
        assert plugin.type == "script"
        assert plugin.version == VersionTuple(major=1, minor=0)

    def test_get_plugin_with_version(self):
        """测试获取指定版本插件"""
        plugin = get_metric_plugin("test_tenant", "test_plugin", version=VersionTuple(major=1, minor=0))
        assert plugin.version == VersionTuple(major=1, minor=0)

    def test_get_plugin_with_status(self):
        """测试获取指定状态插件"""
        plugin = get_metric_plugin("test_tenant", "test_plugin", status=MetricPluginStatus.DEBUG)
        assert plugin.status == MetricPluginStatus.DEBUG

    def test_get_plugin_not_found(self):
        """测试插件不存在"""
        with pytest.raises(MetricPluginNotFoundError):
            get_metric_plugin("test_tenant", "nonexistent_plugin")

    def test_get_plugin_version_not_found(self, version_model):
        """测试插件版本不存在"""
        with pytest.raises(MetricPluginVersionNotFoundError):
            get_metric_plugin("test_tenant", "test_plugin", version=VersionTuple(major=2, minor=0))


@pytest.mark.django_db(databases=["default"])
class TestJobPluginDebugOperation:
    """测试 Job 插件调试 operation。"""

    def test_debug_job_plugin(self, mocker: MockerFixture):
        mock_plugin = mocker.MagicMock()
        mock_manager = mocker.MagicMock()
        mock_manager.start_debug.return_value = 1001

        mocker.patch("bk_monitor_base.domains.metric_plugin.operation.get_metric_plugin", return_value=mock_plugin)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_job_plugin_manager", return_value=mock_manager
        )

        result = debug_job_plugin(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            collect_params={"period": 60},
            plugin_params={"host": "127.0.0.1"},
            collect_host={"bk_host_id": 1},
            operator="admin",
        )

        assert result == {"task_id": 1001}
        mock_manager.start_debug.assert_called_once()

    def test_get_job_plugin_debug_log(self, mocker: MockerFixture):
        from bk_monitor_base.domains.metric_plugin.manager.job.define import JobStatus

        mock_plugin = mocker.MagicMock()
        mock_manager = mocker.MagicMock()
        task_log = [{"step": "START_DEBUG_METRICS", "job_instance_id": 12345, "messages": "log content"}]
        mock_manager.get_debug_log.return_value = (task_log, JobStatus.SUCCESS, [{"metric_name": "m1"}])

        mocker.patch("bk_monitor_base.domains.metric_plugin.operation.get_metric_plugin", return_value=mock_plugin)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_job_plugin_manager", return_value=mock_manager
        )

        result = get_job_plugin_debug_log(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            task_id=1001,
        )

        assert result["task_log"] == task_log
        assert result["debug_status"] == JobStatus.SUCCESS
        assert result["metric_json"] == [{"metric_name": "m1"}]
        mock_manager.get_debug_log.assert_called_once_with(task_id=1001)

    def test_stop_job_plugin_debug(self, mocker: MockerFixture):
        mock_plugin = mocker.MagicMock()
        mock_manager = mocker.MagicMock()

        mocker.patch("bk_monitor_base.domains.metric_plugin.operation.get_metric_plugin", return_value=mock_plugin)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_job_plugin_manager", return_value=mock_manager
        )

        stop_job_plugin_debug(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            task_id=1001,
            operator="admin",
        )

        mock_manager.stop_debug.assert_called_once_with(task_id=1001, operator="admin")


@pytest.mark.django_db(databases=["default"])
class TestListVersionLog:
    """测试 get_metric_plugin_versions 函数"""

    @pytest.fixture(autouse=True)
    def version_model2(self, plugin_model):
        return MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000001",
            version_log="版本2",
            status=MetricPluginStatus.RELEASE,
            updated_by="admin",
        )

    def test_get_plugin_versions_all(self, version_model, version_model2):
        """测试获取所有版本日志"""
        logs = get_metric_plugin_versions("test_tenant", "test_plugin")
        assert len(logs) == 1  # 只返回已发布的版本
        assert logs[0]["version"] == VersionTuple(major=1, minor=1)
        assert logs[0]["version_log"] == "版本2"
        assert logs[0]["status"] == MetricPluginStatus.RELEASE

    def test_get_plugin_versions_with_status(self):
        """测试按状态获取版本日志"""
        logs = get_metric_plugin_versions("test_tenant", "test_plugin", status=MetricPluginStatus.DEBUG)
        assert len(logs) == 1
        assert logs[0]["status"] == MetricPluginStatus.DEBUG

    def test_get_plugin_versions_no_versions(self):
        """测试无版本日志"""
        with pytest.raises(MetricPluginNotFoundError):
            get_metric_plugin_versions("test_tenant", "nonexistent_plugin")


@pytest.mark.django_db(databases=["default"])
class TestListPluginDeployments:
    """测试 list_metric_plugin_deployments 函数"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.get_or_create(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            defaults={
                "bk_biz_id": 1,
                "type": "script",
                "created_by": "admin",
            },
        )[0]
        self.deployment1 = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="部署1",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )
        self.deployment2 = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=2,
            plugin=self.plugin_model,
            name="部署2",
            status=MetricPluginDeploymentStatusEnum.RUNNING.value,
        )

    def test_list_plugin_deployments_basic(self):
        """测试基本部署列表"""
        deployments, total = list_metric_plugin_deployments(bk_tenant_id="test_tenant", bk_biz_ids=None)
        assert len(deployments) == 2
        assert total == 2

    def test_list_plugin_deployments_filter_biz_ids(self):
        """测试按业务ID过滤"""
        deployments, total = list_metric_plugin_deployments(bk_tenant_id="test_tenant", bk_biz_ids=[1])
        assert len(deployments) == 1
        assert deployments[0].bk_biz_id == 1
        assert total == 1

    def test_list_plugin_deployments_filter_plugin_types(self):
        """测试按插件类型过滤"""
        # 创建另一个类型的插件
        exporter_plugin = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="exporter_plugin", type="exporter", created_by="admin"
        )
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=exporter_plugin,
            name="Exporter部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id="test_tenant", bk_biz_ids=None, plugin_types=["script"]
        )
        assert len(deployments) == 2
        assert total == 2
        assert all(d.plugin_id == "test_plugin" for d in deployments)

    def test_list_plugin_deployments_filter_plugin_ids(self):
        """测试按插件ID过滤"""
        # 创建另一个插件
        other_plugin = MetricPluginModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="other_plugin", type="script", created_by="admin"
        )
        MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=other_plugin,
            name="其他部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id="test_tenant", bk_biz_ids=None, plugin_ids=["test_plugin"]
        )
        assert len(deployments) == 2
        assert total == 2
        assert all(d.plugin_id == "test_plugin" for d in deployments)

    def test_list_plugin_deployments_pagination(self):
        """测试分页"""
        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id="test_tenant", bk_biz_ids=None, limit=1, offset=0
        )
        assert len(deployments) == 1
        assert total == 2

        deployments, total = list_metric_plugin_deployments(
            bk_tenant_id="test_tenant", bk_biz_ids=None, limit=1, offset=1
        )
        assert len(deployments) == 1
        assert total == 2


@pytest.mark.django_db(databases=["default"])
class TestGetPluginDeployment:
    """测试 get_plugin_deployment 函数"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.get_or_create(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            defaults={
                "bk_biz_id": 1,
                "type": "script",
                "created_by": "admin",
            },
        )[0]
        self.deployment = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )
        self.version = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )

    def test_get_plugin_deployment_success(self):
        """测试获取部署项成功"""
        deployment, version = get_metric_plugin_deployment(
            bk_tenant_id="test_tenant",
            deployment_id=self.deployment.pk,
            bk_biz_id=1,
        )
        assert deployment.id == self.deployment.pk
        assert deployment.name == "测试部署"
        assert version is not None
        assert version.version == 1

    def test_get_plugin_deployment_no_version(self):
        """测试获取部署项 - 无版本"""
        # 删除版本
        MetricPluginDeploymentVersionModel.objects.filter(deployment=self.deployment).delete()

        deployment, version = get_metric_plugin_deployment(
            bk_tenant_id="test_tenant",
            deployment_id=self.deployment.pk,
            bk_biz_id=1,
        )
        assert deployment.id == self.deployment.pk
        assert version is None

    def test_get_plugin_deployment_not_found(self):
        """测试获取部署项 - 不存在"""
        with pytest.raises(MetricPluginDeploymentNotFoundError):
            get_metric_plugin_deployment(
                bk_tenant_id="test_tenant",
                deployment_id=99999,
                bk_biz_id=1,
            )


@pytest.mark.django_db(databases=["default"])
class TestSaveAndInstallMetricPluginDeployment:
    """测试 save_and_install_metric_plugin_deployment 函数"""

    @pytest.fixture(autouse=True)
    def setup(self, mocker: MockerFixture):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.get_or_create(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            defaults={
                "bk_biz_id": 1,
                "type": "script",
                "created_by": "admin",
            },
        )[0]
        # Mock get_installer
        self.mock_installer = mocker.MagicMock()
        self.mock_get_installer = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_installer", return_value=self.mock_installer
        )

    def test_save_and_install_metric_plugin_deployment_create(self):
        """测试创建部署项"""
        params = CreateOrUpdateDeploymentParams(
            plugin_id="test_plugin",
            name="新部署",
            plugin_version=VersionTuple(major=1, minor=0),
            params={"test": "param"},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
        )

        # 验证部署项已创建
        deployment_model = MetricPluginDeploymentModel.objects.get(
            bk_tenant_id="test_tenant", bk_biz_id=1, name="新部署"
        )
        assert deployment_model.plugin == self.plugin_model
        assert deployment_model.status == MetricPluginDeploymentStatusEnum.INITIALIZING.value
        assert deployment_model.created_by == "admin"

        # 验证 installer.install 被调用，并且传入正确的 deployment_version
        self.mock_installer.install.assert_called_once()
        call_args = self.mock_installer.install.call_args
        deployment_version_arg = call_args[0][0]
        assert deployment_version_arg.version == 1
        assert deployment_version_arg.params == {"test": "param"}
        assert deployment_version_arg.bk_tenant_id == "test_tenant"
        assert deployment_version_arg.bk_biz_id == 1
        assert deployment_version_arg.deployment_id == deployment_model.pk

    def test_save_and_install_metric_plugin_deployment_update(self):
        """测试更新部署项"""
        # 创建现有部署项
        existing_deployment = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="原部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
            created_by="admin",
        )

        # 更新部署项
        params = CreateOrUpdateDeploymentParams(
            id=existing_deployment.pk,
            plugin_id="test_plugin",
            name="更新后的部署",
            plugin_version=VersionTuple(major=1, minor=0),
            params={"test": "new_param"},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="operator", params=params
        )

        # 验证部署项已更新
        existing_deployment.refresh_from_db()
        assert existing_deployment.name == "更新后的部署"
        assert existing_deployment.updated_by == "operator"

        # 验证 installer.install 被调用，并且传入正确的 deployment_version
        self.mock_installer.install.assert_called_once()
        call_args = self.mock_installer.install.call_args
        deployment_version_arg = call_args[0][0]
        assert deployment_version_arg.version == 1
        assert deployment_version_arg.params == {"test": "new_param"}

    def test_save_and_install_metric_plugin_deployment_plugin_not_found(self):
        """测试保存部署项 - 插件不存在"""
        params = CreateOrUpdateDeploymentParams(
            plugin_id="nonexistent_plugin",
            name="新部署",
            plugin_version=VersionTuple(major=1, minor=0),
            params={},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        with pytest.raises(MetricPluginNotFoundError):
            save_and_install_metric_plugin_deployment(
                bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
            )

    def test_save_and_install_metric_plugin_deployment_not_found(self):
        """测试更新部署项 - 部署项不存在"""
        params = CreateOrUpdateDeploymentParams(
            id=99999,  # 不存在的ID
            plugin_id="test_plugin",
            name="更新后的部署",
            plugin_version=VersionTuple(major=1, minor=0),
            params={},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        with pytest.raises(MetricPluginDeploymentNotFoundError):
            save_and_install_metric_plugin_deployment(
                bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
            )

    def test_save_and_install_metric_plugin_deployment_new_version(self):
        """测试配置变更产生新版本"""
        # 创建现有部署项和版本
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin=self.plugin_model, name="部署1"
        )
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=deployment_model,
            version=1,
            is_current=True,
            plugin_version="1.0",
            params={"v": 1},
        )

        # 变更参数
        params = CreateOrUpdateDeploymentParams(
            id=deployment_model.id,
            plugin_id="test_plugin",
            name="部署1",
            plugin_version=VersionTuple(major=1, minor=0),
            params={"v": 2},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        # Mock installer.get_version_diff 返回有变化
        self.mock_installer.get_version_diff.return_value = (True, {})

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
        )

        # 验证 installer.install 被调用，并且 deployment_version 的版本号为 2
        self.mock_installer.install.assert_called_once()
        call_args = self.mock_installer.install.call_args
        deployment_version_arg = call_args[0][0]
        assert deployment_version_arg.version == 2
        assert deployment_version_arg.params == {"v": 2}

    def test_save_and_install_metric_plugin_deployment_reuse_version(self):
        """测试配置无变更复用版本"""
        # 创建现有部署项和版本
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin=self.plugin_model, name="部署1"
        )
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=deployment_model,
            version=1,
            is_current=True,
            plugin_version="1.0",
            params={"v": 1},
        )

        # 参数无变化
        params = CreateOrUpdateDeploymentParams(
            id=deployment_model.id,
            plugin_id="test_plugin",
            name="部署1",
            plugin_version=VersionTuple(major=1, minor=0),
            params={"v": 1},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        # Mock installer.get_version_diff 返回无变化
        self.mock_installer.get_version_diff.return_value = (False, {})

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
        )

        # 验证版本未增加
        assert MetricPluginDeploymentVersionModel.objects.filter(deployment=deployment_model).count() == 1
        version = MetricPluginDeploymentVersionModel.objects.get(deployment=deployment_model)
        assert version.version == 1

    def test_save_and_install_metric_plugin_deployment_is_current_logic(self):
        """测试 is_current 标识维护逻辑"""
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant", bk_biz_id=1, plugin=self.plugin_model, name="部署1"
        )
        _v1 = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=deployment_model,
            version=1,
            is_current=True,
            plugin_version="1.0",
        )

        params = CreateOrUpdateDeploymentParams(
            id=deployment_model.id,
            plugin_id="test_plugin",
            name="部署1",
            plugin_version=VersionTuple(major=1, minor=1),
            params={},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )
        self.mock_installer.get_version_diff.return_value = (True, {})

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
        )

        # 验证 installer.install 被调用，并且 deployment_version 的版本号为 2
        self.mock_installer.install.assert_called_once()
        call_args = self.mock_installer.install.call_args
        deployment_version_arg = call_args[0][0]
        assert deployment_version_arg.version == 2
        # is_current 逻辑现在在 installer.install 中处理，此处仅验证传入的版本号正确

    def test_save_and_install_metric_plugin_deployment_installer_called(self):
        """测试 installer.install 在数据库变更后被调用"""
        params = CreateOrUpdateDeploymentParams(
            plugin_id="test_plugin",
            name="新部署",
            plugin_version=VersionTuple(major=1, minor=0),
            params={},
            target_scope=MetricPluginDeploymentScope(node_type="host", nodes=[]),
        )

        save_and_install_metric_plugin_deployment(
            bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params
        )

        # 验证部署项已保存
        assert MetricPluginDeploymentModel.objects.filter(name="新部署").exists()

        # 验证 install 被调用，并且传入的 deployment_version 正确
        self.mock_installer.install.assert_called_once()
        call_args = self.mock_installer.install.call_args
        deployment_version_arg = call_args[0][0]
        assert deployment_version_arg.version == 1


@pytest.mark.django_db(databases=["default"])
class TestDeletePluginDeployment:
    """测试 delete_metric_plugin_deployment 函数"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.get_or_create(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            defaults={
                "bk_biz_id": 1,
                "type": "script",
                "created_by": "admin",
            },
        )[0]
        self.stopped_deployment = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="已停止部署",
            status=MetricPluginDeploymentStatusEnum.STOPPED.value,
        )
        self.running_deployment = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="运行中部署",
            status=MetricPluginDeploymentStatusEnum.RUNNING.value,
        )

    def test_delete_plugin_deployment_success(self):
        """测试删除部署项 - 成功（stopped状态）"""
        # 创建版本
        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.stopped_deployment,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={},
            target_node_type="host",
            target_nodes=[],
        )

        delete_metric_plugin_deployment("test_tenant", 1, self.stopped_deployment.pk)

        # 验证部署项已删除
        assert not MetricPluginDeploymentModel.objects.filter(pk=self.stopped_deployment.pk).exists()
        assert not MetricPluginDeploymentVersionModel.objects.filter(deployment=self.stopped_deployment).exists()

    def test_delete_plugin_deployment_status_error(self):
        """测试删除部署项 - 状态错误（非stopped状态）"""
        with pytest.raises(MetricPluginDeploymentStatusError, match="部署项状态不为stopped"):
            delete_metric_plugin_deployment("test_tenant", 1, self.running_deployment.pk)

    def test_delete_plugin_deployment_not_found(self):
        """测试删除部署项 - 不存在"""
        with pytest.raises(MetricPluginDeploymentNotFoundError):
            delete_metric_plugin_deployment("test_tenant", 1, 99999)


@pytest.mark.django_db(databases=["default"])
class TestCreatePlugin:
    """测试 create_metric_plugin 函数"""

    def test_create_plugin_success(self, mocker: MockerFixture):
        """测试成功创建插件"""

        def raise_plugin_not_found(**kwargs):
            """模拟节点管理中不存在同名插件，允许本地继续创建。"""
            error = BkApiError(
                module="nodeman",
                action="get_plugin_info",
                method="GET",
                url="/api/c/compapi/v2/nodeman/plugin_info/",
                message="plugin not found",
                third_api_error_code="3800100",
            )
            raise error

        # 准备测试数据
        bk_tenant_id = "test_tenant"
        bk_biz_id = 1
        operator = "admin"
        params = CreatePluginParams(
            id="new_plugin",
            type="script",
            name="新插件",
            description_md="# 新插件",
            label="test",
            params=[],
            define={"script": "echo 'test'"},
            metrics=[],
            version=VersionTuple(major=1, minor=0),
            status=MetricPluginStatus.DEBUG,
        )

        # 创建预期的插件对象
        expected_plugin = MetricPlugin(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            id="new_plugin",
            type="script",
            name="新插件",
            description_md="# 新插件",
            label="test",
            version=VersionTuple(major=1, minor=0),
            status=MetricPluginStatus.DEBUG,
            created_by=operator,
            updated_by=operator,
        )

        # Mock 插件管理器类
        mock_manager_class = mocker.MagicMock()
        mock_manager_instance = mocker.MagicMock()
        mock_manager_instance.plugin = expected_plugin
        mock_manager_class.create_plugin.return_value = mock_manager_instance

        # Mock get_plugin_manager_class
        mock_get_manager_class = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager_class",
            return_value=mock_manager_class,
        )
        mock_get_plugin_info = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.nodeman_api.get_plugin_info",
            side_effect=raise_plugin_not_found,
        )

        # 调用函数
        result = create_metric_plugin(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, operator=operator, params=params)

        # 验证结果
        assert result == expected_plugin
        mock_get_plugin_info.assert_called_once_with(bk_tenant_id=bk_tenant_id, name=params.id)
        mock_get_manager_class.assert_called_once_with(plugin_type="script")
        mock_manager_class.create_plugin.assert_called_once_with(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, operator=operator, params=params
        )

    def test_create_plugin_duplicate_id(self):
        """测试插件ID已存在的情况"""
        # 使用已有的插件ID
        bk_tenant_id = "test_tenant"
        bk_biz_id = 1
        operator = "admin"
        params = CreatePluginParams(
            id="test_plugin",  # 使用已存在的插件ID
            type="script",
            name="重复插件",
            description_md="# 重复插件",
            label="test",
            params=[],
            define={},
            metrics=[],
            version=VersionTuple(major=1, minor=0),
            status=MetricPluginStatus.DEBUG,
        )

        # 验证抛出 PluginIDExistsError
        with pytest.raises(PluginIDExistsError, match="插件ID已存在: test_tenant/test_plugin"):
            create_metric_plugin(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, operator=operator, params=params)


@pytest.mark.django_db(databases=["default"])
class TestCreatePluginVersion:
    """测试 create_metric_plugin_version 函数"""

    def test_create_plugin_version_success(self, mocker: MockerFixture):
        """测试成功创建插件版本"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        operator = "admin"
        params = CreatePluginVersionParams(
            name="测试插件",
            description_md="# 测试插件",
            label="test",
            params=[],
            define={"script": "echo 'test'"},
            metrics=[],
            version=VersionTuple(major=1, minor=1),
            status=MetricPluginStatus.DEBUG,
        )
        expected_version = VersionTuple(major=1, minor=1)
        expected_version_changed = True

        # Mock 插件管理器
        mock_manager = mocker.MagicMock()
        mock_manager.create_plugin_version.return_value = (expected_version_changed, expected_version)

        # Mock get_plugin_manager
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        # 调用函数
        version_changed, version = create_metric_plugin_version(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, operator=operator, params=params
        )

        # 验证结果
        assert version_changed == expected_version_changed
        assert version == expected_version
        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        mock_manager.create_plugin_version.assert_called_once_with(params=params, operator=operator)

    def test_create_plugin_version_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在的情况"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        operator = "admin"
        params = CreatePluginVersionParams(
            name="测试插件",
            description_md="# 测试插件",
            label="test",
            params=[],
            define={},
            metrics=[],
            status=MetricPluginStatus.DEBUG,
        )

        # Mock get_plugin_manager 抛出异常
        from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        # 验证抛出 MetricPluginNotFoundError
        with pytest.raises(MetricPluginNotFoundError):
            create_metric_plugin_version(
                bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, operator=operator, params=params
            )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)


@pytest.mark.django_db(databases=["default"])
class TestUpdatePluginVersion:
    """测试 update_plugin_version 函数"""

    def test_update_plugin_version_success(self, mocker: MockerFixture):
        """测试成功更新插件版本"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"
        params = UpdatePluginVersionParams(
            name="更新后的插件",
            description_md="# 更新后的插件",
            label="updated",
            metrics=[],
            version_log="更新日志",
        )

        # Mock 插件管理器
        mock_manager = mocker.MagicMock()

        # Mock get_plugin_manager
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        # 调用函数
        update_metric_plugin_version(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version, operator=operator, params=params
        )

        # 验证结果
        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        mock_manager.update_plugin_version.assert_called_once_with(params=params, operator=operator)

    def test_update_plugin_version_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在的情况"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"
        params = UpdatePluginVersionParams(
            name="更新后的插件",
            description_md="# 更新后的插件",
            label="updated",
            metrics=[],
        )

        # Mock get_plugin_manager 抛出异常
        from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        # 验证抛出 MetricPluginNotFoundError
        with pytest.raises(MetricPluginNotFoundError):
            update_metric_plugin_version(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                operator=operator,
                params=params,
            )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)


@pytest.mark.django_db(databases=["default"])
class TestReleasePluginVersion:
    """测试 release_plugin_version 函数"""

    def test_release_plugin_version_success(self, mocker: MockerFixture):
        """测试成功发布插件版本"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        # Mock 插件管理器
        mock_manager = mocker.MagicMock()

        # Mock get_plugin_manager
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        # 调用函数
        release_metric_plugin_version(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version, operator=operator
        )

        # 验证结果
        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        mock_manager.release_plugin_version.assert_called_once_with(
            operator=operator,
            apply_data_link=True,
            md5_list=None,
        )

    def test_release_plugin_version_without_apply_data_link(self, mocker: MockerFixture):
        """测试发布插件版本时可显式跳过申请数据链路"""
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        mock_manager = mocker.MagicMock()
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        release_metric_plugin_version(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            operator=operator,
            apply_data_link=False,
        )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        mock_manager.release_plugin_version.assert_called_once_with(
            operator=operator,
            apply_data_link=False,
            md5_list=None,
        )

    def test_release_plugin_version_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在的情况"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        # Mock get_plugin_manager 抛出异常
        from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        # 验证抛出 MetricPluginNotFoundError
        with pytest.raises(MetricPluginNotFoundError):
            release_metric_plugin_version(
                bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version, operator=operator
            )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)


@pytest.mark.django_db(databases=["default"])
class TestExportMetricPluginPackage:
    """测试 export_metric_plugin_package 函数"""

    def test_export_metric_plugin_package_uses_latest_release_when_version_missing(self, mocker: MockerFixture):
        """测试未显式指定版本时，导出已发布版本"""
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        operator = "admin"

        mock_plugin = mocker.MagicMock()
        mock_plugin_model = mocker.MagicMock()
        mock_plugin_model.type = "script"
        mock_plugin_model.to_plugin.return_value = mock_plugin

        mock_filter = mocker.patch("bk_monitor_base.domains.metric_plugin.operation.MetricPluginModel.objects.filter")
        mock_filter.return_value.first.return_value = mock_plugin_model

        mock_manager = mocker.MagicMock()
        mock_manager.export_package.return_value = "https://example.com/plugin.tgz"
        mock_manager_class = mocker.MagicMock(return_value=mock_manager)
        mock_get_manager_class = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager_class",
            return_value=mock_manager_class,
        )
        mock_get_manager = mocker.patch("bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager")

        result = export_metric_plugin_package(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            operator=operator,
        )

        assert result == "https://example.com/plugin.tgz"
        mock_filter.assert_called_once_with(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            is_deleted=False,
        )
        mock_get_manager_class.assert_called_once_with("script")
        mock_plugin_model.to_plugin.assert_called_once_with(status=MetricPluginStatus.RELEASE)
        mock_manager_class.assert_called_once_with(plugin=mock_plugin, plugin_model=mock_plugin_model)
        mock_manager.export_package.assert_called_once_with(operator=operator)
        mock_get_manager.assert_not_called()

    def test_export_metric_plugin_package_respects_explicit_version(self, mocker: MockerFixture):
        """测试显式传版本时仍使用指定版本获取管理器"""
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        operator = "admin"
        version = VersionTuple(major=2, minor=1)

        mock_manager = mocker.MagicMock()
        mock_manager.export_package.return_value = "https://example.com/plugin-2.1.tgz"
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )
        mock_filter = mocker.patch("bk_monitor_base.domains.metric_plugin.operation.MetricPluginModel.objects.filter")

        result = export_metric_plugin_package(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            operator=operator,
            version=version,
        )

        assert result == "https://example.com/plugin-2.1.tgz"
        mock_get_manager.assert_called_once_with(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
        )
        mock_manager.export_package.assert_called_once_with(operator=operator)
        mock_filter.assert_not_called()


@pytest.mark.django_db(databases=["default"])
class TestApplyMetricPluginDataLink:
    """测试 apply_metric_plugin_data_link 函数"""

    def test_apply_metric_plugin_data_link_success(self, mocker: MockerFixture):
        """测试成功申请插件数据链路"""
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        mock_manager = mocker.MagicMock()
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        apply_metric_plugin_data_link(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            operator=operator,
        )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        mock_manager.apply_data_link.assert_called_once_with(operator=operator)

    def test_apply_metric_plugin_data_link_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在时抛出异常"""
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        with pytest.raises(MetricPluginNotFoundError):
            apply_metric_plugin_data_link(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                operator=operator,
            )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)


@pytest.mark.django_db(databases=["default"])
class TestRefreshMetricPluginMetrics:
    """测试 refresh_metric_plugin_metrics 函数。"""

    def test_refresh_metric_plugin_metrics_success(self, mocker: MockerFixture):
        """测试成功刷新插件指标配置。"""
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        mock_manager = mocker.MagicMock()
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        refresh_metric_plugin_metrics(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            operator=operator,
        )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        mock_manager.refresh_metrics.assert_called_once_with(operator=operator)

    def test_refresh_metric_plugin_metrics_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在时抛出异常。"""
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        version = VersionTuple(major=1, minor=0)
        operator = "admin"

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        with pytest.raises(MetricPluginNotFoundError):
            refresh_metric_plugin_metrics(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                operator=operator,
            )

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)


@pytest.mark.django_db(databases=["default"])
class TestDeletePlugin:
    """测试 delete_plugin 函数"""

    def test_delete_plugin_success(self, mocker: MockerFixture):
        """测试成功删除插件（软删除）"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        operator = "admin"

        # 确保插件存在且未被删除
        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        assert plugin_model.is_deleted is False

        # Mock 插件管理器
        mock_manager = mocker.MagicMock()

        # Mock get_plugin_manager
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        # 调用函数
        delete_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, operator=operator)

        # 验证结果
        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        mock_manager.delete_plugin.assert_called_once()

        # 验证插件管理器调用了 delete_plugin 方法后，插件被软删除
        # 注意：实际的软删除是在插件管理器的 delete_plugin 方法中执行的
        # 这里我们验证方法被调用了

    def test_delete_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在的情况"""
        # 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"
        operator = "admin"

        # Mock get_plugin_manager 抛出异常
        from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError

        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        # 验证抛出 MetricPluginNotFoundError
        with pytest.raises(MetricPluginNotFoundError):
            delete_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, operator=operator)

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)


@pytest.mark.django_db(databases=["default"])
class TestDeploymentActions:
    """测试 start/stop/status 操作"""

    @pytest.fixture(autouse=True)
    def setup(self, mocker: MockerFixture):
        """设置测试数据"""
        self.plugin_model = MetricPluginModel.objects.get_or_create(
            bk_tenant_id="test_tenant",
            plugin_id="test_plugin",
            defaults={
                "bk_biz_id": 1,
                "type": "script",
                "created_by": "admin",
            },
        )[0]
        self.deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.STOPPED.value,
        )
        # Mock installer
        self.mock_installer = mocker.MagicMock()
        self.mock_get_installer = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_installer", return_value=self.mock_installer
        )

    def test_start_metric_plugin_deployment_success(self):
        """测试启动部署项成功"""
        start_metric_plugin_deployment("test_tenant", 1, self.deployment_model.pk, "admin")

        # 验证状态变更为 STARTING
        self.deployment_model.refresh_from_db()
        assert self.deployment_model.status == MetricPluginDeploymentStatusEnum.STARTING.value
        # 验证 installer 被调用
        self.mock_installer.start.assert_called_once()

    def test_start_metric_plugin_deployment_status_error(self):
        """测试启动部署项状态错误"""
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        self.deployment_model.save()

        with pytest.raises(MetricPluginDeploymentOperationError, match="无法启动"):
            start_metric_plugin_deployment("test_tenant", 1, self.deployment_model.pk, "admin")

    def test_stop_metric_plugin_deployment_success(self):
        """测试停止部署项成功"""
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        self.deployment_model.save()

        stop_metric_plugin_deployment("test_tenant", 1, self.deployment_model.pk, "admin")

        # 验证状态变更为 STOPPING
        self.deployment_model.refresh_from_db()
        assert self.deployment_model.status == MetricPluginDeploymentStatusEnum.STOPPING.value
        # 验证 installer 被调用
        self.mock_installer.stop.assert_called_once()

    def test_stop_metric_plugin_deployment_status_error(self):
        """测试停止部署项状态错误"""
        self.deployment_model.status = MetricPluginDeploymentStatusEnum.STOPPED.value
        self.deployment_model.save()

        with pytest.raises(MetricPluginDeploymentOperationError, match="无法停止"):
            stop_metric_plugin_deployment(
                bk_tenant_id="test_tenant", bk_biz_id=1, deployment_id=self.deployment_model.pk, operator="admin"
            )

    def test_get_metric_plugin_deployment_status(self):
        """测试获取部署项状态"""
        self.mock_installer.status.return_value = {"status": "SUCCESS"}

        result = get_metric_plugin_deployment_status(
            bk_tenant_id="test_tenant", bk_biz_id=1, deployment_id=self.deployment_model.pk
        )

        assert result == {"status": "SUCCESS"}
        self.mock_installer.status.assert_called_once_with()


@pytest.mark.django_db(databases=["default"])
class TestGetMetricPluginSupportedOsTypes:
    """测试 get_metric_plugin_supported_os_types 函数

    该测试类覆盖以下场景：
    1. 成功获取插件支持的操作系统类型
    2. 插件不存在时抛出 MetricPluginNotFoundError
    3. 插件管理器不存在时抛出 MetricPluginManagerNotFoundError
    """

    # 表驱动测试：成功场景的测试用例
    SUCCESS_TEST_CASES = [
        {
            "id": "single_os_type",
            "description": "插件仅支持单个操作系统类型（Linux）",
            "os_types": ["linux"],
        },
        {
            "id": "multiple_os_types",
            "description": "插件支持多个操作系统类型",
            "os_types": ["linux", "windows", "aix"],
        },
        {
            "id": "empty_os_types",
            "description": "插件不支持任何操作系统类型",
            "os_types": [],
        },
        {
            "id": "all_os_types",
            "description": "插件支持所有操作系统类型",
            "os_types": ["linux", "linux_aarch64", "windows", "aix"],
        },
    ]

    @pytest.mark.parametrize(
        "test_case",
        SUCCESS_TEST_CASES,
        ids=[case["id"] for case in SUCCESS_TEST_CASES],
    )
    def test_get_supported_os_types_success(self, mocker: MockerFixture, test_case: dict):
        """测试成功获取插件支持的操作系统类型

        使用表驱动测试验证不同的操作系统类型组合：
        - 单个操作系统类型
        - 多个操作系统类型
        - 空列表
        - 所有支持的操作系统类型

        Args:
            mocker: pytest-mock 提供的 mocker fixture
            test_case: 包含测试用例配置的字典
        """
        # Arrange: 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        expected_os_types = test_case["os_types"]

        # 创建模拟的 OSType 枚举对象
        from enum import Enum

        class MockOSType(Enum):
            LINUX = "linux"
            LINUX_AARCH64 = "linux_aarch64"
            WINDOWS = "windows"
            AIX = "aix"

        # 将字符串转换为模拟的枚举对象
        mock_os_type_objects = [MockOSType(os_type) for os_type in expected_os_types]

        # Mock 插件管理器
        mock_manager = mocker.MagicMock()
        mock_manager.get_supported_os_types.return_value = mock_os_type_objects

        # Mock get_plugin_manager
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            return_value=mock_manager,
        )

        # Act: 调用被测函数
        result = get_metric_plugin_supported_os_types(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)

        # Assert: 验证结果
        assert result == expected_os_types, f"期望 {expected_os_types}，实际 {result}"
        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        mock_manager.get_supported_os_types.assert_called_once()

    def test_get_supported_os_types_plugin_not_found(self, mocker: MockerFixture):
        """测试插件不存在时抛出 MetricPluginNotFoundError

        当调用 get_plugin_manager 时，如果插件不存在，
        应该抛出 MetricPluginNotFoundError 异常。

        Args:
            mocker: pytest-mock 提供的 mocker fixture
        """
        # Arrange: 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "nonexistent_plugin"

        # Mock get_plugin_manager 抛出 MetricPluginNotFoundError
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginNotFoundError(f"插件不存在: {bk_tenant_id}/{plugin_id}"),
        )

        # Act & Assert: 验证抛出 MetricPluginNotFoundError
        with pytest.raises(MetricPluginNotFoundError, match="插件不存在"):
            get_metric_plugin_supported_os_types(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)

    def test_get_supported_os_types_manager_not_found(self, mocker: MockerFixture):
        """测试插件管理器不存在时抛出 MetricPluginManagerNotFoundError

        当调用 get_plugin_manager 时，如果找不到对应类型的插件管理器，
        应该抛出 MetricPluginManagerNotFoundError 异常。

        Args:
            mocker: pytest-mock 提供的 mocker fixture
        """
        # Arrange: 准备测试数据
        bk_tenant_id = "test_tenant"
        plugin_id = "test_plugin"
        plugin_type = "unknown_type"

        # Mock get_plugin_manager 抛出 MetricPluginManagerNotFoundError
        mock_get_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_plugin_manager",
            side_effect=MetricPluginManagerNotFoundError(f"插件管理器不存在: {plugin_type}"),
        )

        # Act & Assert: 验证抛出 MetricPluginManagerNotFoundError
        with pytest.raises(MetricPluginManagerNotFoundError, match="插件管理器不存在"):
            get_metric_plugin_supported_os_types(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)

        mock_get_manager.assert_called_once_with(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)


class TestDebugNodemanPlugin:
    """debug_nodeman_plugin 函数的测试用例

    测试目标：
    1. 验证对不同 nodeman 类型插件（script、exporter、jmx、datadog、pushgateway）的管理器选择
    2. 验证返回形状 {"task_id": int}
    3. 验证插件不存在时抛出 MetricPluginNotFoundError
    4. 验证非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError
    """

    NODEMAN_PLUGIN_TYPES = [
        pytest.param("script", id="script类型"),
        pytest.param("exporter", id="exporter类型"),
        pytest.param("jmx", id="jmx类型"),
        pytest.param("datadog", id="datadog类型"),
        pytest.param("pushgateway", id="pushgateway类型"),
    ]

    NON_NODEMAN_PLUGIN_TYPES = [
        pytest.param("job_mysql", id="job_mysql类型"),
        pytest.param("job_oracle", id="job_oracle类型"),
        pytest.param("job_db2", id="job_db2类型"),
        pytest.param("job_mssql", id="job_mssql类型"),
    ]

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NODEMAN_PLUGIN_TYPES)
    def test_debug_nodeman_plugin_success(self, mocker: MockerFixture, plugin_type: str):
        """测试 debug_nodeman_plugin 成功调用并返回 task_id"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        collect_params = {"period": 60}
        plugin_params = {"param1": "value1"}
        collect_host = {"bk_host_id": 1}
        target_nodes = [{"bk_host_id": 1}]
        operator = "admin"
        expected_task_id = 12345

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        mock_manager = mocker.MagicMock()
        mock_manager.start_debug.return_value = expected_task_id
        mock_get_nodeman_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_nodeman_plugin_manager",
            return_value=mock_manager,
        )

        # Act
        result = debug_nodeman_plugin(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            collect_params=collect_params,
            plugin_params=plugin_params,
            collect_host=collect_host,
            target_nodes=target_nodes,
            operator=operator,
        )

        # Assert
        assert result == {"task_id": expected_task_id}
        mock_get_nodeman_manager.assert_called_once()
        mock_manager.start_debug.assert_called_once_with(
            collect_params=collect_params,
            plugin_params=plugin_params,
            collect_host=collect_host,
            target_nodes=target_nodes,
            operator=operator,
        )

    @pytest.mark.django_db(databases=["default"])
    def test_debug_nodeman_plugin_not_found(self, mocker: MockerFixture):
        """测试 debug_nodeman_plugin 在插件不存在时抛出 MetricPluginNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = "non_existent_plugin"
        version = VersionTuple(major=1, minor=0)
        collect_params = {"period": 60}
        plugin_params = {}
        collect_host = {"bk_host_id": 1}
        target_nodes = [{"bk_host_id": 1}]
        operator = "admin"

        # Act & Assert
        with pytest.raises(MetricPluginNotFoundError):
            debug_nodeman_plugin(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                collect_params=collect_params,
                plugin_params=plugin_params,
                collect_host=collect_host,
                target_nodes=target_nodes,
                operator=operator,
            )

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NON_NODEMAN_PLUGIN_TYPES)
    def test_debug_nodeman_plugin_non_nodeman_type(self, mocker: MockerFixture, plugin_type: str):
        """测试 debug_nodeman_plugin 对非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        collect_params = {"period": 60}
        plugin_params = {}
        collect_host = {"bk_host_id": 1}
        target_nodes = [{"bk_host_id": 1}]
        operator = "admin"

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # Act & Assert
        with pytest.raises(MetricPluginManagerNotFoundError):
            debug_nodeman_plugin(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                collect_params=collect_params,
                plugin_params=plugin_params,
                collect_host=collect_host,
                target_nodes=target_nodes,
                operator=operator,
            )


class TestGetNodemanPluginDebugLog:
    """get_nodeman_plugin_debug_log 函数的测试用例

    测试目标：
    1. 验证对不同 nodeman 类型插件的管理器选择
    2. 验证返回形状 {"status", "metric_json", "last_time", "error_message", "log"}
    3. 验证插件不存在时抛出 MetricPluginNotFoundError
    4. 验证非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError
    """

    NODEMAN_PLUGIN_TYPES = [
        pytest.param("script", id="script类型"),
        pytest.param("exporter", id="exporter类型"),
        pytest.param("jmx", id="jmx类型"),
        pytest.param("datadog", id="datadog类型"),
        pytest.param("pushgateway", id="pushgateway类型"),
    ]

    NON_NODEMAN_PLUGIN_TYPES = [
        pytest.param("job_mysql", id="job_mysql类型"),
        pytest.param("job_oracle", id="job_oracle类型"),
        pytest.param("job_db2", id="job_db2类型"),
        pytest.param("job_mssql", id="job_mssql类型"),
    ]

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NODEMAN_PLUGIN_TYPES)
    def test_get_nodeman_plugin_debug_log_success(self, mocker: MockerFixture, plugin_type: str):
        """测试 get_nodeman_plugin_debug_log 成功调用并返回正确的日志结构"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_log_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"
        expected_log_result = {
            "status": "SUCCESS",
            "metric_json": [{"metric_name": "cpu", "metric_value": 0.5, "dimensions": []}],
            "last_time": "2024-01-01 12:00:00",
            "error_message": "",
            "log": "Debug completed successfully",
        }

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        mock_manager = mocker.MagicMock()
        mock_manager.get_debug_log.return_value = expected_log_result
        mock_get_nodeman_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_nodeman_plugin_manager",
            return_value=mock_manager,
        )

        # Act
        result = get_nodeman_plugin_debug_log(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            task_id=task_id,
            operator=operator,
        )

        # Assert
        assert result == expected_log_result
        assert "status" in result
        assert "metric_json" in result
        assert "last_time" in result
        assert "error_message" in result
        assert "log" in result
        mock_get_nodeman_manager.assert_called_once()
        mock_manager.get_debug_log.assert_called_once_with(task_id=task_id, operator=operator)

    @pytest.mark.django_db(databases=["default"])
    def test_get_nodeman_plugin_debug_log_not_found(self, mocker: MockerFixture):
        """测试 get_nodeman_plugin_debug_log 在插件不存在时抛出 MetricPluginNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = "non_existent_plugin_log"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"

        # Act & Assert
        with pytest.raises(MetricPluginNotFoundError):
            get_nodeman_plugin_debug_log(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                task_id=task_id,
                operator=operator,
            )

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NON_NODEMAN_PLUGIN_TYPES)
    def test_get_nodeman_plugin_debug_log_non_nodeman_type(self, mocker: MockerFixture, plugin_type: str):
        """测试 get_nodeman_plugin_debug_log 对非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_log_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # Act & Assert
        with pytest.raises(MetricPluginManagerNotFoundError):
            get_nodeman_plugin_debug_log(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                task_id=task_id,
                operator=operator,
            )


class TestStopNodemanPluginDebug:
    """stop_nodeman_plugin_debug 函数的测试用例

    测试目标：
    1. 验证对不同 nodeman 类型插件的管理器选择
    2. 验证成功调用返回 None
    3. 验证插件不存在时抛出 MetricPluginNotFoundError
    4. 验证非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError
    """

    NODEMAN_PLUGIN_TYPES = [
        pytest.param("script", id="script类型"),
        pytest.param("exporter", id="exporter类型"),
        pytest.param("jmx", id="jmx类型"),
        pytest.param("datadog", id="datadog类型"),
        pytest.param("pushgateway", id="pushgateway类型"),
    ]

    NON_NODEMAN_PLUGIN_TYPES = [
        pytest.param("job_mysql", id="job_mysql类型"),
        pytest.param("job_oracle", id="job_oracle类型"),
        pytest.param("job_db2", id="job_db2类型"),
        pytest.param("job_mssql", id="job_mssql类型"),
    ]

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NODEMAN_PLUGIN_TYPES)
    def test_stop_nodeman_plugin_debug_success(self, mocker: MockerFixture, plugin_type: str):
        """测试 stop_nodeman_plugin_debug 成功调用并返回 None"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_stop_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        mock_manager = mocker.MagicMock()
        mock_manager.stop_debug.return_value = None
        mock_get_nodeman_manager = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.operation.get_nodeman_plugin_manager",
            return_value=mock_manager,
        )

        # Act
        result = stop_nodeman_plugin_debug(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=version,
            task_id=task_id,
            operator=operator,
        )

        # Assert
        assert result is None
        mock_get_nodeman_manager.assert_called_once()
        mock_manager.stop_debug.assert_called_once_with(task_id=task_id, operator=operator)

    @pytest.mark.django_db(databases=["default"])
    def test_stop_nodeman_plugin_debug_not_found(self, mocker: MockerFixture):
        """测试 stop_nodeman_plugin_debug 在插件不存在时抛出 MetricPluginNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = "non_existent_plugin_stop"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"

        # Act & Assert
        with pytest.raises(MetricPluginNotFoundError):
            stop_nodeman_plugin_debug(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                task_id=task_id,
                operator=operator,
            )

    @pytest.mark.django_db(databases=["default"])
    @pytest.mark.parametrize("plugin_type", NON_NODEMAN_PLUGIN_TYPES)
    def test_stop_nodeman_plugin_debug_non_nodeman_type(self, mocker: MockerFixture, plugin_type: str):
        """测试 stop_nodeman_plugin_debug 对非 nodeman 类型插件抛出 MetricPluginManagerNotFoundError"""
        # Arrange
        bk_tenant_id = "test_tenant"
        plugin_id = f"test_plugin_stop_{plugin_type}"
        version = VersionTuple(major=1, minor=0)
        task_id = 12345
        operator = "admin"

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin_id=plugin_id,
            type=plugin_type,
            created_by="admin",
        )
        MetricPluginVersionModel.objects.create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=2,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            params=[],
            define={},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # Act & Assert
        with pytest.raises(MetricPluginManagerNotFoundError):
            stop_nodeman_plugin_debug(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                task_id=task_id,
                operator=operator,
            )
