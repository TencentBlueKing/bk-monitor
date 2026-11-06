"""
测试 K8sPluginManager

验证 K8S 插件管理器的核心行为：
1. 创建插件时直接进入 RELEASE 状态并申请数据链路
2. 创建版本后自动发布
3. apply_data_link / delete_data_link 数据链路管理
4. 不支持的操作抛出 NotImplementedError
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPluginMetricGroup,
    MetricPluginParams,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.k8s import K8sPluginDataLinker, K8sPluginManager
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginModel,
    MetricPluginVersionModel,
)
from bk_monitor_base.infras.third_party_api.errors import BkApiError

BK_TENANT_ID = "test_tenant_k8s"
BK_BIZ_ID = 100
OPERATOR = "admin"
DEFAULT_DATA_LABEL = "qcloud_exporter"
DEFAULT_RELATED_PARAMS: dict[str, Any] = {"data_label": DEFAULT_DATA_LABEL}


def _create_k8s_plugin(
    plugin_id: str = "qcloud_exporter_100",
    related_params: dict[str, Any] | None = None,
    **create_overrides: Any,
) -> K8sPluginManager:
    """创建 K8S 插件的测试辅助函数

    自动调用 create_plugin + set_related_params，模拟真实调用方行为。
    """
    params = _make_create_params(plugin_id=plugin_id, **create_overrides)
    manager = K8sPluginManager.create_plugin(
        bk_tenant_id=BK_TENANT_ID,
        bk_biz_id=BK_BIZ_ID,
        params=params,
        operator=OPERATOR,
    )
    manager.set_related_params(related_params or DEFAULT_RELATED_PARAMS)
    return manager


_NOT_FOUND_ERROR = BkApiError(
    module="metadata",
    action="get_data_source",
    method="GET",
    url="/api/v1/data_source",
    message="DataSource matching query does not exist",
)


def _get_data_source_side_effect(**kwargs: Any) -> dict[str, Any]:
    """模拟 get_data_source 行为：按 bk_data_id 查询成功，按 data_name 查询抛异常"""
    if "bk_data_id" in kwargs:
        return {
            "bk_data_id": kwargs["bk_data_id"],
            "data_name": "k8s_test_plugin",
            "is_platform_data_id": False,
            "data_description": "plugin_type: k8s, plugin_id: test",
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
        }
    raise _NOT_FOUND_ERROR


@pytest.fixture
def mock_metadata_api():
    """Mock metadata API 调用，避免测试中发起真实网络请求

    默认行为：
    - get_data_source(bk_data_id=xxx): 返回数据源信息
    - get_data_source(data_name=xxx): 抛出 BkApiError（模拟未找到旧数据源）
    - create_data_source: 返回 50001
    - query_time_series_group: 返回空列表
    """
    with patch("bk_monitor_base.domains.metric_plugin.manager.k8s.api.metadata") as mock_api:
        mock_api.create_data_source.return_value = 50001
        mock_api.get_data_source.side_effect = _get_data_source_side_effect
        mock_api.query_time_series_group.return_value = []
        mock_api.create_time_series_group.return_value = {"time_series_group_id": 1}
        mock_api.modify_data_source.return_value = None
        mock_api.modify_time_series_group.return_value = None
        yield mock_api


def _make_create_params(plugin_id: str = "qcloud_exporter_100", **overrides: Any) -> CreatePluginParams:
    """构造创建插件参数"""
    defaults: dict[str, Any] = {
        "id": plugin_id,
        "type": "k8s",
        "name": "腾讯云指标采集",
        "description_md": "K8S 指标采集插件",
        "label": "os",
        "logo": "",
        "metrics": [],
        "params": [],
        "define": {"template": "apiVersion: apps/v1\nkind: Deployment\n", "values": {}},
        "is_support_remote": False,
        "version": VersionTuple(major=1, minor=0),
        "version_log": "初始版本",
    }
    defaults.update(overrides)
    return CreatePluginParams(**defaults)


def _make_version_params(**overrides: Any) -> CreatePluginVersionParams:
    """构造创建版本参数"""
    defaults: dict[str, Any] = {
        "name": "腾讯云指标采集",
        "description_md": "K8S 指标采集插件",
        "label": "os",
        "logo": "",
        "metrics": [],
        "params": [],
        "define": {"template": "apiVersion: apps/v1\nkind: Deployment\n", "values": {}},
        "is_support_remote": False,
        "version_log": "版本更新",
    }
    defaults.update(overrides)
    return CreatePluginVersionParams(**defaults)


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginManagerCreatePlugin:
    """测试 K8sPluginManager.create_plugin"""

    def test_create_plugin_auto_release(self, mock_metadata_api: MagicMock):
        """创建 K8S 插件后状态应直接为 RELEASE"""
        manager = _create_k8s_plugin(plugin_id="k8s_test_create_release")

        assert manager.plugin.status == MetricPluginStatus.RELEASE
        assert manager.plugin.id == "k8s_test_create_release"
        assert manager.plugin.type == "k8s"
        assert manager.plugin.version == VersionTuple(major=1, minor=0)

        version_model = MetricPluginVersionModel.objects.get(
            bk_tenant_id=BK_TENANT_ID,
            plugin__plugin_id="k8s_test_create_release",
        )
        assert version_model.status == MetricPluginStatus.RELEASE.value

    def test_create_plugin_saves_related_params(self, mock_metadata_api: MagicMock):
        """set_related_params 应将 data_label 持久化到数据库"""
        manager = _create_k8s_plugin(plugin_id="k8s_test_datalink_params")

        assert manager.plugin.related_params["data_label"] == DEFAULT_DATA_LABEL

        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_datalink_params")
        assert plugin_model.related_params["data_label"] == DEFAULT_DATA_LABEL

    def test_create_plugin_ignores_debug_status_param(self, mock_metadata_api: MagicMock):
        """即使传入 DEBUG 状态，K8S 插件创建后也应为 RELEASE"""
        manager = _create_k8s_plugin(
            plugin_id="k8s_test_ignore_debug",
            status=MetricPluginStatus.DEBUG,
        )

        assert manager.plugin.status == MetricPluginStatus.RELEASE

    def test_create_plugin_preserves_fields(self, mock_metadata_api: MagicMock):
        """验证创建插件时各字段正确保存"""
        manager = _create_k8s_plugin(
            plugin_id="k8s_test_fields",
            name="自定义名称",
            description_md="# 自定义描述",
            label="component",
        )

        assert manager.plugin.name == "自定义名称"
        assert manager.plugin.description_md == "# 自定义描述"
        assert manager.plugin.label == "component"
        assert manager.plugin.bk_biz_id == BK_BIZ_ID


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginManagerCreateVersion:
    """测试 K8sPluginManager.create_plugin_version"""

    @pytest.fixture(autouse=True)
    def setup_plugin(self, mock_metadata_api: MagicMock):
        """创建基础插件用于版本测试"""
        self.mock_metadata_api = mock_metadata_api
        self.plugin_id = "k8s_test_version"
        self.manager = _create_k8s_plugin(plugin_id=self.plugin_id)

    def test_create_version_auto_release(self):
        """创建新版本后应自动发布为 RELEASE 状态"""
        version_params = _make_version_params(
            define={"template": "new_template", "values": {"key": "value"}},
        )

        version_changed, version = self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        assert version_changed is True
        assert version == VersionTuple(major=2, minor=0)
        assert self.manager.plugin.status == MetricPluginStatus.RELEASE

        version_model = MetricPluginVersionModel.objects.filter(
            bk_tenant_id=BK_TENANT_ID,
            plugin__plugin_id=self.plugin_id,
        ).first()
        assert version_model is not None
        assert version_model.status == MetricPluginStatus.RELEASE.value

    def test_create_version_no_change(self):
        """配置完全未变更时版本号不变"""
        version_params = _make_version_params()

        version_changed, version = self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        assert version_changed is False
        assert version == VersionTuple(major=1, minor=0)

    def test_create_version_skips_data_link_when_exists(self):
        """已有数据链路时更新版本不应重复申请"""
        self.manager.set_related_params({"bk_data_id": 50001, "data_name": "k8s_k8s_test_version"})
        self.mock_metadata_api.reset_mock()

        version_params = _make_version_params(
            define={"template": "new_template", "values": {}},
        )

        self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        self.mock_metadata_api.create_data_source.assert_not_called()

    def test_create_version_minor_change(self):
        """次要配置变更时次版本号递增并自动发布"""
        version_params = _make_version_params(name="更新后的名称")

        version_changed, version = self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        assert version_changed is True
        assert version == VersionTuple(major=1, minor=1)
        assert self.manager.plugin.status == MetricPluginStatus.RELEASE

    def test_create_version_major_change(self):
        """主要配置变更时主版本号递增并自动发布"""
        version_params = _make_version_params(
            params=[MetricPluginParams(name="new_param", type="string")],
        )

        version_changed, version = self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        assert version_changed is True
        assert version == VersionTuple(major=2, minor=0)
        assert self.manager.plugin.status == MetricPluginStatus.RELEASE

    def test_create_version_with_metrics(self):
        """带指标配置变更的版本创建"""
        version_params = _make_version_params(
            metrics=[
                MetricPluginMetricGroup(
                    table_name="cpu",
                    table_desc="CPU指标",
                    fields=[],
                )
            ],
        )

        version_changed, version = self.manager.create_plugin_version(params=version_params, operator=OPERATOR)

        assert version_changed is True
        assert self.manager.plugin.status == MetricPluginStatus.RELEASE
        assert len(self.manager.plugin.metrics) == 1
        assert self.manager.plugin.metrics[0].table_name == "cpu"


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginManagerDataLink:
    """测试 K8sPluginManager 数据链路方法"""

    @pytest.fixture(autouse=True)
    def setup_plugin(self, mock_metadata_api: MagicMock):
        """创建基础插件"""
        self.mock_metadata_api = mock_metadata_api
        self.manager = _create_k8s_plugin(plugin_id="k8s_test_datalink")

    def test_apply_data_link_is_idempotent(self):
        """apply_data_link 可重复调用不报错（已有 data_id 时不重复创建）"""
        self.manager.set_related_params({"bk_data_id": 50001, "data_name": "k8s_k8s_test_datalink"})
        self.mock_metadata_api.reset_mock()

        def side_effect(**kwargs: Any) -> dict[str, Any]:
            if "bk_data_id" in kwargs:
                return {
                    "bk_data_id": kwargs["bk_data_id"],
                    "data_name": "k8s_k8s_test_datalink",
                    "is_platform_data_id": False,
                    "data_description": "k8s_k8s_test_datalink",
                    "option": {
                        "inject_local_time": True,
                        "allow_dimensions_missing": True,
                        "is_split_measurement": True,
                    },
                }
            raise _NOT_FOUND_ERROR

        self.mock_metadata_api.get_data_source.side_effect = side_effect
        self.mock_metadata_api.query_time_series_group.return_value = [{"time_series_group_id": 1}]

        result = self.manager.apply_data_link(operator=OPERATOR)

        assert "bk_data_id" in result
        self.mock_metadata_api.create_data_source.assert_not_called()
        self.mock_metadata_api.modify_time_series_group.assert_called_once()

    def test_delete_data_link(self):
        """delete_data_link 调用不报错"""
        result = self.manager.delete_data_link(operator=OPERATOR)
        assert result is None

    def test_apply_data_link_with_deployment_returns_none(self):
        """K8S 数据链路基于插件级别，deployment 级别返回 None"""
        from bk_monitor_base.domains.metric_plugin.define import (
            MetricPluginDeployment,
            MetricPluginDeploymentStatusEnum,
        )

        deployment = MetricPluginDeployment(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=BK_BIZ_ID,
            id=1,
            name="test",
            plugin_id="k8s_test_datalink",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING,
        )
        result = self.manager.apply_data_link_with_deployment(deployment, operator=OPERATOR)
        assert result is None

    def test_apply_data_link_creates_data_source_with_correct_etl(self):
        """验证创建数据源时使用 bk_standard_v2_time_series ETL 配置"""
        self.mock_metadata_api.reset_mock()

        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_datalink")
        plugin_model.related_params = {"data_label": DEFAULT_DATA_LABEL}
        plugin_model.save(update_fields=["related_params"])
        self.manager.plugin.related_params = {"data_label": DEFAULT_DATA_LABEL}

        self.manager.apply_data_link(operator=OPERATOR)

        self.mock_metadata_api.create_data_source.assert_called_once()
        call_args = self.mock_metadata_api.create_data_source.call_args
        assert call_args.kwargs.get("etl_config") == "bk_standard_v2_time_series"

    def test_apply_data_link_data_name_consistent_with_old(self):
        """验证 data_name 格式与旧 PluginDataAccessor 一致：k8s_{plugin_id} 无随机后缀"""
        self.mock_metadata_api.reset_mock()

        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_datalink")
        plugin_model.related_params = {"data_label": DEFAULT_DATA_LABEL}
        plugin_model.save(update_fields=["related_params"])
        self.manager.plugin.related_params = {"data_label": DEFAULT_DATA_LABEL}

        self.manager.apply_data_link(operator=OPERATOR)

        call_args = self.mock_metadata_api.create_data_source.call_args
        data_name = call_args.kwargs.get("data_name")
        assert data_name == "k8s_k8s_test_datalink"

    def test_apply_data_link_table_id_consistent_with_old(self):
        """验证 table_id 格式与旧 PluginDataAccessor 一致：k8s_{plugin_id}.__default__"""
        self.mock_metadata_api.reset_mock()

        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_datalink")
        plugin_model.related_params = {
            "bk_data_id": 50001,
            "data_name": "k8s_k8s_test_datalink",
            "data_label": DEFAULT_DATA_LABEL,
        }
        plugin_model.save(update_fields=["related_params"])
        self.manager.plugin.related_params = plugin_model.related_params.copy()

        self.mock_metadata_api.query_time_series_group.return_value = []
        self.manager.apply_data_link(operator=OPERATOR)

        call_args = self.mock_metadata_api.create_time_series_group.call_args
        assert call_args.kwargs.get("table_id") == "k8s_k8s_test_datalink.__default__"
        assert call_args.kwargs.get("time_series_group_name") == "k8s_k8s_test_datalink"
        assert call_args.kwargs.get("data_label") == DEFAULT_DATA_LABEL

    def test_apply_data_link_creates_time_series_group_with_blacklist(self):
        """验证创建时序分组时开启字段黑名单"""
        self.mock_metadata_api.reset_mock()

        plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_datalink")
        plugin_model.related_params = {
            "bk_data_id": 50001,
            "data_name": "k8s_test",
            "data_label": DEFAULT_DATA_LABEL,
        }
        plugin_model.save(update_fields=["related_params"])
        self.manager.plugin.related_params = plugin_model.related_params.copy()

        self.mock_metadata_api.query_time_series_group.return_value = []

        self.manager.apply_data_link(operator=OPERATOR)

        call_kwargs = self.mock_metadata_api.create_time_series_group.call_args
        assert call_kwargs is not None
        additional_options = call_kwargs.kwargs.get("additional_options", {})
        assert additional_options.get("enable_field_black_list") is True


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginManagerMiscMethods:
    """测试 K8sPluginManager 辅助方法"""

    @pytest.fixture(autouse=True)
    def setup_plugin(self, mock_metadata_api: MagicMock):
        """创建基础插件"""
        self.manager = _create_k8s_plugin(plugin_id="k8s_test_misc")

    def test_get_supported_os_types_returns_empty(self):
        """K8S 插件不依赖操作系统类型"""
        assert self.manager.get_supported_os_types() == []

    def test_register_returns_empty(self):
        """K8S 插件不需要注册"""
        assert self.manager.register(operator=OPERATOR) == []

    def test_export_package_raises(self):
        """K8S 插件不支持导出插件包"""
        with pytest.raises(NotImplementedError, match="K8S"):
            self.manager.export_package(operator=OPERATOR)

    def test_parse_define_raises(self):
        """K8S 插件不支持从插件包导入"""
        with pytest.raises(NotImplementedError, match="K8S"):
            K8sPluginManager._parse_define(
                bk_tenant_id=BK_TENANT_ID,
                operator=OPERATOR,
                extract_dir=Path("/tmp"),
                plugin_id="test",
                meta_data={},
            )

    def test_type_is_k8s(self):
        """验证管理器类型为 k8s"""
        assert K8sPluginManager.type == "k8s"


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginManagerRegistration:
    """测试 K8sPluginManager 在管理器映射中的注册"""

    def test_registered_in_plugin_managers(self):
        """K8sPluginManager 应注册在 PLUGIN_MANAGERS 映射中"""
        from bk_monitor_base.domains.metric_plugin.manager.tools import PLUGIN_MANAGERS

        assert "k8s" in PLUGIN_MANAGERS
        assert PLUGIN_MANAGERS["k8s"] is K8sPluginManager

    def test_get_plugin_manager_class(self):
        """通过 get_plugin_manager_class 能获取到 K8sPluginManager"""
        from bk_monitor_base.domains.metric_plugin.manager.tools import get_plugin_manager_class

        assert get_plugin_manager_class("k8s") is K8sPluginManager

    def test_get_plugin_manager(self, mock_metadata_api: MagicMock):
        """通过 get_plugin_manager 能获取到 K8sPluginManager 实例"""
        _create_k8s_plugin(plugin_id="k8s_test_get_manager")

        from bk_monitor_base.domains.metric_plugin.manager.tools import get_plugin_manager

        manager = get_plugin_manager(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_get_manager")
        assert isinstance(manager, K8sPluginManager)


@pytest.mark.django_db(databases=["default"])
class TestK8sPluginDataLinker:
    """测试 K8sPluginDataLinker"""

    @pytest.fixture(autouse=True)
    def setup_plugin(self, mock_metadata_api: MagicMock):
        """创建测试插件和数据链路器"""
        self.mock_metadata_api = mock_metadata_api
        manager = _create_k8s_plugin(plugin_id="k8s_test_linker")
        self.plugin = manager.plugin
        self.plugin_model = MetricPluginModel.objects.get(bk_tenant_id=BK_TENANT_ID, plugin_id="k8s_test_linker")

    def test_apply_data_ids_creates_new(self):
        """没有已有数据 ID 时应创建新数据源"""
        self.mock_metadata_api.reset_mock()
        self.plugin.related_params = {}
        self.plugin_model.related_params = {}
        self.plugin_model.save(update_fields=["related_params"])

        linker = K8sPluginDataLinker(self.plugin, self.plugin_model)
        linker.apply_data_ids(operator=OPERATOR)

        self.mock_metadata_api.create_data_source.assert_called_once()
        assert "bk_data_id" in self.plugin.related_params

    def test_apply_data_ids_reuses_existing(self):
        """已有数据 ID 时应校准而不重新创建"""
        self.plugin.related_params.update({"bk_data_id": 50001, "data_name": "k8s_k8s_test_linker"})
        self.plugin_model.related_params = self.plugin.related_params.copy()
        self.plugin_model.save(update_fields=["related_params"])
        self.mock_metadata_api.reset_mock()

        def side_effect(**kwargs: Any) -> dict[str, Any]:
            if "bk_data_id" in kwargs:
                return {
                    "bk_data_id": kwargs["bk_data_id"],
                    "data_name": "k8s_k8s_test_linker",
                    "is_platform_data_id": False,
                    "data_description": "k8s_k8s_test_linker",
                    "option": {
                        "inject_local_time": True,
                        "allow_dimensions_missing": True,
                        "is_split_measurement": True,
                    },
                }
            raise _NOT_FOUND_ERROR

        self.mock_metadata_api.get_data_source.side_effect = side_effect

        linker = K8sPluginDataLinker(self.plugin, self.plugin_model)
        linker.apply_data_ids(operator=OPERATOR)

        self.mock_metadata_api.create_data_source.assert_not_called()

    def test_apply_result_tables_creates_group(self):
        """apply_result_tables 应创建 time_series_group"""
        self.plugin.related_params.update({"bk_data_id": 50001, "data_name": "k8s_k8s_test_linker"})
        self.plugin_model.related_params = self.plugin.related_params.copy()
        self.plugin_model.save(update_fields=["related_params"])
        self.mock_metadata_api.reset_mock()
        self.mock_metadata_api.query_time_series_group.return_value = []

        linker = K8sPluginDataLinker(self.plugin, self.plugin_model)
        linker.apply_result_tables(operator=OPERATOR)

        self.mock_metadata_api.create_time_series_group.assert_called_once()

    def test_apply_result_tables_modifies_existing_group(self):
        """已有 time_series_group 时应更新而不创建"""
        self.plugin.related_params.update({"bk_data_id": 50001, "data_name": "k8s_k8s_test_linker"})
        self.plugin_model.related_params = self.plugin.related_params.copy()
        self.plugin_model.save(update_fields=["related_params"])
        self.mock_metadata_api.reset_mock()
        self.mock_metadata_api.query_time_series_group.return_value = [{"time_series_group_id": 1}]

        linker = K8sPluginDataLinker(self.plugin, self.plugin_model)
        linker.apply_result_tables(operator=OPERATOR)

        self.mock_metadata_api.create_time_series_group.assert_not_called()
        self.mock_metadata_api.modify_time_series_group.assert_called_once()

    def test_apply_result_tables_raises_without_data_id(self):
        """没有 bk_data_id 时应抛出 ValueError"""
        self.plugin.related_params = {}
        self.plugin_model.related_params = {}
        self.plugin_model.save(update_fields=["related_params"])

        linker = K8sPluginDataLinker(self.plugin, self.plugin_model)

        with pytest.raises(ValueError, match="bk_data_id"):
            linker.apply_result_tables(operator=OPERATOR)
