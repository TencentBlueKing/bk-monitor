"""
测试 metric_plugin.models 模块
"""

import base64

import pytest

from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPluginDeploymentStatusEnum,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    UpdatePluginVersionParams,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.errors import (
    MetricPluginRemoteCollectDisableError,
    MetricPluginVersionNotFoundError,
    PluginVersionLessThanReleasedError,
    PluginVersionReleasedError,
)
from bk_monitor_base.domains.metric_plugin.models import (
    MAX_LOGO_SIZE_BYTES,
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
    _parse_logo_to_base64,
)


@pytest.mark.django_db(databases=["default"])
@pytest.fixture(autouse=True)
def plugin_model():
    """设置测试数据"""
    return MetricPluginModel.objects.create(
        bk_tenant_id="test_tenant", bk_biz_id=1, plugin_id="test_plugin", type="script", created_by="admin"
    )


@pytest.mark.django_db(databases=["default"])
class TestMetricPluginVersionModel:
    """测试 MetricPluginVersionModel 模型"""

    def test_version_model_creation(self, plugin_model):
        """测试版本模型创建"""
        version_model = MetricPluginVersionModel.objects.create(
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
        assert version_model.bk_tenant_id == "test_tenant"
        assert version_model.bk_biz_id == 1
        assert version_model.plugin == plugin_model
        assert version_model.name == "测试插件"
        assert version_model.description_md == "# 测试插件"
        assert version_model.params == []
        assert version_model.define == {"script": "echo 'test'"}
        assert version_model.version_tuple == VersionTuple(major=1, minor=0)
        assert version_model.version_log == "初始版本"
        assert version_model.status == MetricPluginStatus.DEBUG
        assert version_model.updated_by == "admin"

    def test_version_model_str(self, plugin_model):
        """测试版本模型字符串表示"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )
        assert str(version_model) == "test_tenant/1/test_plugin(script) (1.0)"

    def test_version_model_meta(self):
        """测试版本模型元数据"""
        assert MetricPluginVersionModel._meta.db_table == "metric_plugin_version"
        assert MetricPluginVersionModel._meta.verbose_name == "指标插件版本"
        assert MetricPluginVersionModel._meta.verbose_name_plural == "指标插件版本"
        assert MetricPluginVersionModel._meta.ordering == ["-version"]
        assert MetricPluginVersionModel._meta.unique_together == (("bk_tenant_id", "bk_biz_id", "plugin", "version"),)

    def test_status_choices(self):
        """测试状态选择"""
        assert MetricPluginStatus.DEBUG == "debug"
        assert MetricPluginStatus.RELEASE == "release"


@pytest.mark.django_db(databases=["default"])
class TestMetricPluginModel:
    """测试 MetricPluginModel 模型"""

    def test_plugin_model_creation(self, plugin_model):
        """测试插件模型创建"""
        assert plugin_model.bk_tenant_id == "test_tenant"
        assert plugin_model.bk_biz_id == 1
        assert plugin_model.plugin_id == "test_plugin"
        assert plugin_model.type == "script"
        assert plugin_model.created_by == "admin"
        assert plugin_model.is_global is False
        assert plugin_model.is_internal is False

    def test_plugin_model_str(self, plugin_model):
        """测试插件模型字符串表示"""
        assert str(plugin_model) == "test_tenant/1/test_plugin(script)"

    def test_plugin_model_meta(self):
        """测试插件模型元数据"""
        assert MetricPluginModel._meta.db_table == "metric_plugin"
        assert MetricPluginModel._meta.verbose_name == "指标插件"
        assert MetricPluginModel._meta.verbose_name_plural == "指标插件"
        assert MetricPluginModel._meta.ordering == ["-created_at"]
        assert MetricPluginModel._meta.unique_together == (("bk_tenant_id", "plugin_id"),)

    def test_get_version_model_none(self, plugin_model):
        """测试获取版本模型 - 无版本"""
        version_model = plugin_model._get_version_model()
        assert version_model is None

    def test_get_version_model_with_version(self, plugin_model):
        """测试获取版本模型 - 指定版本"""
        # 创建版本模型
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 获取版本模型
        result = plugin_model._get_version_model(version=VersionTuple(major=1, minor=0))
        assert result == version_model

    def test_get_version_model_with_status(self, plugin_model):
        """测试获取版本模型 - 指定状态"""
        # 创建版本模型
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 获取版本模型
        result = plugin_model._get_version_model(status=MetricPluginStatus.DEBUG)
        assert result == version_model

    def test_get_version_model_not_found(self, plugin_model):
        """测试获取版本模型 - 未找到"""
        result = plugin_model._get_version_model(version=VersionTuple(major=2, minor=0))
        assert result is None

    def test_to_plugin_success(self, plugin_model):
        """测试转换为插件对象 - 成功"""
        # 创建版本模型
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试插件",
            params=[{"name": "param1", "type": "string"}],
            define={"script": "echo 'test'"},
            version="000001.000000",
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
            updated_by="admin",
        )

        # 转换为插件对象
        plugin = plugin_model.to_plugin()
        assert plugin.bk_tenant_id == "test_tenant"
        assert plugin.bk_biz_id == 1
        assert plugin.id == "test_plugin"
        assert plugin.type == "script"
        assert plugin.name == "测试插件"
        assert plugin.description_md == "# 测试插件"
        assert plugin.version == VersionTuple(major=1, minor=0)
        assert plugin.version_log == "初始版本"
        assert plugin.status == MetricPluginStatus.DEBUG
        assert len(plugin.params) == 1
        assert plugin.params[0].name == "param1"
        assert plugin.define == {"script": "echo 'test'"}

    def test_to_plugin_version_not_found(self, plugin_model):
        """测试转换为插件对象 - 版本不存在"""
        with pytest.raises(MetricPluginVersionNotFoundError):
            plugin_model.to_plugin(version=VersionTuple(major=2, minor=0))

    def test_create_plugin_new_plugin(self):
        """测试创建插件 - 新插件"""
        params = CreatePluginParams(
            id="new_plugin",
            type="script",
            name="新插件",
            label="test_label",
            description_md="# 新插件",
            params=[MetricPluginParams(name="param1", type="string")],
            define={"script": "echo 'new'"},
            version=VersionTuple(major=1, minor=0),
        )

        MetricPluginModel.create_plugin(bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params)

        # 验证插件已创建
        plugin_model = MetricPluginModel.objects.get(plugin_id="new_plugin")
        assert plugin_model.bk_tenant_id == "test_tenant"
        assert plugin_model.bk_biz_id == 1
        assert plugin_model.type == "script"

        # 验证版本模型已创建
        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model)
        assert version_model.name == "新插件"
        assert version_model.version_tuple == VersionTuple(major=1, minor=0)

    def test_create_plugin_plugin_exists(self):
        """测试创建插件 - 插件已存在"""
        # 先创建一个插件
        params1 = CreatePluginParams(
            id="existing_plugin",
            type="script",
            name="已存在插件",
            label="test_label",
            description_md="# 已存在插件",
            params=[],
            define={},
            version=VersionTuple(major=1, minor=0),
        )
        MetricPluginModel.create_plugin(bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params1)

        # 尝试再次创建相同ID的插件
        params2 = CreatePluginParams(
            id="existing_plugin",
            type="script",
            name="新插件",
            label="test_label2",
            description_md="# 新插件",
            params=[],
            define={},
            version=VersionTuple(major=1, minor=0),
        )

        with pytest.raises(ValueError) as exc_info:
            MetricPluginModel.create_plugin(bk_tenant_id="test_tenant", bk_biz_id=1, operator="admin", params=params2)
        assert "插件已存在" in str(exc_info.value)

    def test_compare_major_config_no_change(self, plugin_model):
        """测试比较主要配置 - 无变化"""
        # 创建旧版本，使用完整的 params 字典（包含所有默认字段）
        old_params_dict = MetricPluginParams(name="param1", type="string").model_dump()
        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[old_params_dict],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        # 创建新参数（与旧版本相同）
        new_params = CreatePluginVersionParams(
            params=[MetricPluginParams(name="param1", type="string")],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        result = plugin_model._compare_major_config(old_version, new_params)
        assert result is False

    def test_compare_major_config_params_changed(self, plugin_model):
        """测试比较主要配置 - params 变化"""
        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[{"name": "param1", "type": "string"}],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            params=[MetricPluginParams(name="param2", type="string")],  # params 不同
            define={"script": "echo 'test'"},
            is_support_remote=False,
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        result = plugin_model._compare_major_config(old_version, new_params)
        assert result is True

    def test_compare_major_config_define_changed(self, plugin_model):
        """测试比较主要配置 - define 变化"""
        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            params=[],
            define={"script": "echo 'new'"},  # define 不同
            is_support_remote=False,
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        result = plugin_model._compare_major_config(old_version, new_params)
        assert result is True

    def test_compare_major_config_is_support_remote_changed(self, plugin_model):
        """测试比较主要配置 - is_support_remote 变化"""
        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            params=[],
            define={},
            is_support_remote=True,  # is_support_remote 不同
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        result = plugin_model._compare_major_config(old_version, new_params)
        assert result is True

    def test_compare_major_config_multiple_changes(self, plugin_model):
        """测试比较主要配置 - 多个字段同时变化"""
        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[{"name": "param1", "type": "string"}],
            define={"script": "echo 'test'"},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            params=[MetricPluginParams(name="param2", type="string")],  # params 不同
            define={"script": "echo 'new'"},  # define 不同
            is_support_remote=True,  # is_support_remote 不同
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        result = plugin_model._compare_major_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_no_change(self, plugin_model):
        """测试比较次要配置 - 无变化"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            metrics=[],
            enable_metric_discovery=False,
            version_log="初始版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="# 测试",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="初始版本",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is False

    def test_compare_minor_config_name_changed(self, plugin_model):
        """测试比较次要配置 - name 变化"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="新插件名称",  # name 不同
            description_md="# 测试",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_description_md_changed(self, plugin_model):
        """测试比较次要配置 - description_md 变化"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="# 新描述",  # description_md 不同
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_label_changed(self, plugin_model):
        """测试比较次要配置 - label 变化"""
        plugin_model.label = "old_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="",
            label="new_label",  # label 不同
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_metrics_changed(self, plugin_model):
        """测试比较次要配置 - metrics 变化"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="",
            metrics=[{"table_name": "table1", "fields": []}],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[
                MetricPluginMetricGroup(table_name="table2", fields=[])  # metrics 不同
            ],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_enable_metric_discovery_changed(self, plugin_model):
        """测试比较次要配置 - enable_metric_discovery 变化"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=True,  # enable_metric_discovery 不同
            version_log="",
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_compare_minor_config_version_log_changed(self, plugin_model):
        """测试比较次要配置 - version_log 变化不应影响 minor_changed"""
        plugin_model.label = "test_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="",
            metrics=[],
            enable_metric_discovery=False,
            version_log="初始版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="测试插件",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="新版本",  # version_log 不同，但不应该影响 minor_changed
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is False  # version_log 变化不应该导致 minor_changed 为 True

    def test_compare_minor_config_multiple_changes(self, plugin_model):
        """测试比较次要配置 - 多个字段同时变化"""
        plugin_model.label = "old_label"
        plugin_model.save()

        old_version = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="# 测试",
            metrics=[],
            enable_metric_discovery=False,
            version_log="初始版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        new_params = CreatePluginVersionParams(
            name="新插件名称",  # name 不同
            description_md="# 新描述",  # description_md 不同
            label="new_label",  # label 不同
            metrics=[],
            enable_metric_discovery=True,  # enable_metric_discovery 不同
            version_log="新版本",  # version_log 不同
            params=[],
            define={},
        )

        result = plugin_model._compare_minor_config(old_version, new_params)
        assert result is True

    def test_create_plugin_version_with_specified_version_new(self, plugin_model):
        """测试创建插件版本 - 指定版本号，版本不存在"""
        params = CreatePluginVersionParams(
            version=VersionTuple(major=1, minor=0),
            name="测试插件",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=0)

        # 验证版本已创建
        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model, version="000001.000000")
        assert version_model.name == "测试插件"
        assert version_model.status == MetricPluginStatus.DEBUG

    def test_create_plugin_version_with_specified_version_exists_debug(self, plugin_model):
        """测试创建插件版本 - 指定版本号，版本已存在且为 DEBUG"""
        # 先创建一个 DEBUG 版本的版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        params = CreatePluginVersionParams(
            version=VersionTuple(major=1, minor=0),
            name="新版本",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=0)

        # 验证旧版本被删除，新版本已创建
        version_models = MetricPluginVersionModel.objects.filter(plugin=plugin_model, version="000001.000000")
        assert version_models.count() == 1
        assert version_models.get().name == "新版本"

    def test_create_plugin_version_with_specified_version_exists_release(self, plugin_model):
        """测试创建插件版本 - 指定版本号，版本已存在且为 RELEASE"""
        # 先创建一个 RELEASE 版本的版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="已发布版本",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=VersionTuple(major=1, minor=0),
            name="新版本",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        with pytest.raises(PluginVersionReleasedError) as exc_info:
            plugin_model.create_plugin_version(params, operator="admin")
        assert "已发布，不允许覆盖" in str(exc_info.value)

    def test_create_plugin_version_with_specified_version_less_than_release(self, plugin_model):
        """测试创建插件版本 - 指定版本号小于已发布的最大版本"""
        # 创建一个已发布的版本 2.0
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="已发布版本",
            params=[],
            define={},
            version="000002.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=VersionTuple(major=1, minor=0),  # 小于 2.0
            name="新版本",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        with pytest.raises(PluginVersionLessThanReleasedError) as exc_info:
            plugin_model.create_plugin_version(params, operator="admin")
        assert "禁止创建小于已发布版本的版本号" in str(exc_info.value)

    def test_create_plugin_version_with_specified_version_label_changed(self, plugin_model):
        """测试创建插件版本 - 指定版本号，label 变化"""
        plugin_model.label = "old_label"
        plugin_model.save()

        params = CreatePluginVersionParams(
            version=VersionTuple(major=1, minor=0),
            name="测试插件",
            description_md="",
            label="new_label",  # label 不同
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        plugin_model.create_plugin_version(params, operator="admin")

        # 验证 label 被更新
        plugin_model.refresh_from_db()
        assert plugin_model.label == "new_label"

    def test_create_plugin_version_auto_no_versions(self, plugin_model):
        """测试创建插件版本 - 未指定版本号，无任何版本"""
        params = CreatePluginVersionParams(
            version=None,  # 未指定版本号
            name="测试插件",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=0)

        # 验证版本已创建
        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model, version="000001.000000")
        assert version_model.name == "测试插件"

    def test_create_plugin_version_auto_major_config_changed(self, plugin_model):
        """测试创建插件版本 - 未指定版本号，主要配置变化"""
        # 创建一个 RELEASE 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧版本",
            params=[{"name": "param1", "type": "string"}],
            define={"script": "echo 'old'"},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="新版本",
            description_md="",
            label="test_label",
            params=[MetricPluginParams(name="param2", type="string")],  # params 不同
            define={"script": "echo 'new'"},  # define 不同
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=2, minor=0)  # 主版本号 +1，次版本号重置为 0

    def test_create_plugin_version_auto_minor_config_changed(self, plugin_model):
        """测试创建插件版本 - 未指定版本号，仅次要配置变化"""
        plugin_model.label = "old_label"
        plugin_model.save()

        # 创建一个 RELEASE 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="新版本",  # name 不同
            description_md="",
            label="new_label",  # label 不同
            params=[],  # params 相同
            define={},  # define 相同
            is_support_remote=False,  # is_support_remote 相同
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=1)  # 次版本号 +1

    def test_create_plugin_version_auto_no_config_changed(self, plugin_model):
        """测试创建插件版本 - 未指定版本号且配置无变化时复用已发布版本"""
        plugin_model.label = "test_label"
        plugin_model.save()

        # 创建一个 RELEASE 版本 1.0
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            description_md="",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="测试插件",  # 所有字段都相同
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="复用已发布版本",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")

        assert version_changed is False
        assert version == VersionTuple(major=1, minor=0)

        release_version = MetricPluginVersionModel.objects.get(plugin=plugin_model, version="000001.000000")
        assert release_version.version_log == "复用已发布版本"
        assert MetricPluginVersionModel.objects.filter(plugin=plugin_model, version="000001.000000").count() == 1

    def test_create_plugin_version_auto_no_release_use_latest(self, plugin_model):
        """测试创建插件版本 - 未指定版本号，无 RELEASE 版本，使用 1.0 版本作为基准"""
        # 创建一个 DEBUG 版本
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="DEBUG版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000002.000000",
            status=MetricPluginStatus.DEBUG,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="新版本",
            description_md="",
            label="test_label",
            params=[MetricPluginParams(name="param1", type="string")],  # params 不同
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=0)  #  当没有 RELEASE 版本时，使用 1.0 版本作为基准

    def test_create_plugin_version_auto_generated_exists_debug(self, plugin_model):
        """测试创建插件版本 - 自动生成的版本号已存在且为 DEBUG"""
        plugin_model.label = "test_label"
        plugin_model.save()

        # 创建一个 RELEASE 版本 1.0
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="RELEASE版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        # 创建一个 DEBUG 版本 1.1（次要配置变化）
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="DEBUG版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000001",
            status=MetricPluginStatus.DEBUG,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="新版本",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")
        assert version_changed is True
        assert version == VersionTuple(major=1, minor=1)  # 自动生成 1.1

        # 验证旧 DEBUG 版本被删除
        version_models = MetricPluginVersionModel.objects.filter(plugin=plugin_model, version="000001.000001")
        assert version_models.count() == 1
        assert version_models.get().name == "新版本"

    def test_create_plugin_version_auto_generated_exists_release(self, plugin_model):
        """测试创建插件版本 - 自动生成命中已发布版本时直接复用该版本"""
        plugin_model.label = "test_label"
        plugin_model.save()

        # 创建一个 RELEASE 版本 1.0
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="RELEASE版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        # 创建一个 RELEASE 版本 1.1（已发布）
        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="已发布版本",
            params=[],
            define={},
            is_support_remote=False,
            version="000001.000001",
            status=MetricPluginStatus.RELEASE,
        )

        # 由于配置没有变化，应该直接复用最新 RELEASE 版本 1.1
        params = CreatePluginVersionParams(
            version=None,
            name="已发布版本",  # 与最新 RELEASE 版本（1.1）的 name 相同
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        version_changed, version = plugin_model.create_plugin_version(params, operator="admin")

        assert version_changed is False
        assert version == VersionTuple(major=1, minor=1)
        assert MetricPluginVersionModel.objects.filter(plugin=plugin_model, version="000001.000001").count() == 1

    def test_create_plugin_version_disable_remote_collect_failed(self, plugin_model):
        """测试创建插件版本 - 已发布远程采集插件不允许直接关闭远程采集"""
        plugin_model.label = "test_label"
        plugin_model.save()

        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="远程采集插件",
            description_md="",
            params=[],
            define={},
            is_support_remote=True,
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
        )

        params = CreatePluginVersionParams(
            version=None,
            name="远程采集插件",
            description_md="",
            label="test_label",
            params=[],
            define={},
            is_support_remote=False,
            metrics=[],
            enable_metric_discovery=False,
            version_log="关闭远程采集",
        )

        with pytest.raises(MetricPluginRemoteCollectDisableError, match="已开启远程采集的插件无法关闭远程采集"):
            plugin_model.create_plugin_version(params, operator="admin")

    def test_update_plugin_version_success(self, plugin_model):
        """测试更新插件版本 - 版本存在且为 DEBUG，更新成功"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧名称",
            description_md="旧描述",
            metrics=[],
            enable_metric_discovery=False,
            version_log="旧日志",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
            updated_by="old_operator",
        )

        plugin_model.label = "old_label"
        plugin_model.save()

        params = UpdatePluginVersionParams(
            name="新名称",
            description_md="新描述",
            label="new_label",
            metrics=[],
            enable_metric_discovery=True,
            version_log="新日志",
        )

        plugin_model.update_plugin_version(VersionTuple(major=1, minor=0), params, operator="new_operator")

        # 验证字段被更新
        version_model.refresh_from_db()
        assert version_model.name == "新名称"
        assert version_model.description_md == "新描述"
        assert version_model.enable_metric_discovery is True
        assert version_model.version_log == "新日志"
        assert version_model.updated_by == "new_operator"

        # 验证 label 被更新
        plugin_model.refresh_from_db()
        assert plugin_model.label == "new_label"

    def test_update_plugin_version_release_status(self, plugin_model):
        """测试更新插件 info 版本 - 版本存在且为 RELEASE"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="已发布版本",
            description_md="旧描述",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
            updated_by="old_operator",
        )

        params = UpdatePluginVersionParams(
            name="新名称",
            description_md="新描述",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="更新日志",
        )

        plugin_model.update_plugin_version(VersionTuple(major=1, minor=0), params, operator="admin")

        # 验证字段被更新
        version_model.refresh_from_db()
        assert version_model.name == "新名称"
        assert version_model.description_md == "新描述"
        assert version_model.version_log == "更新日志"
        assert version_model.updated_by == "admin"

        # 验证版本状态保持为 RELEASE
        assert version_model.status == MetricPluginStatus.RELEASE

    def test_update_plugin_version_not_found(self, plugin_model):
        """测试更新插件版本 - 版本不存在"""
        params = UpdatePluginVersionParams(
            name="新名称",
            description_md="",
            label="test_label",
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        with pytest.raises(MetricPluginVersionNotFoundError) as exc_info:
            plugin_model.update_plugin_version(VersionTuple(major=2, minor=0), params, operator="admin")
        assert "插件版本不存在" in str(exc_info.value)

    def test_update_plugin_version_label_changed(self, plugin_model):
        """测试更新插件版本 - label 变化"""
        plugin_model.label = "old_label"
        plugin_model.save()

        MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        params = UpdatePluginVersionParams(
            name="测试插件",
            description_md="",
            label="new_label",  # label 不同
            metrics=[],
            enable_metric_discovery=False,
            version_log="",
        )

        plugin_model.update_plugin_version(VersionTuple(major=1, minor=0), params, operator="admin")

        # 验证 label 被更新
        plugin_model.refresh_from_db()
        assert plugin_model.label == "new_label"

    def test_update_plugin_version_multiple_fields(self, plugin_model):
        """测试更新插件版本 - 更新多个次要配置字段"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="旧名称",
            description_md="旧描述",
            metrics=[],
            enable_metric_discovery=False,
            version_log="旧日志",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
        )

        params = UpdatePluginVersionParams(
            name="新名称",
            description_md="新描述",
            label="test_label",
            metrics=[MetricPluginMetricGroup(table_name="table1", fields=[])],
            enable_metric_discovery=True,
            version_log="新日志",
        )

        plugin_model.update_plugin_version(VersionTuple(major=1, minor=0), params, operator="admin")

        # 验证所有字段都被更新
        version_model.refresh_from_db()
        assert version_model.name == "新名称"
        assert version_model.description_md == "新描述"
        assert version_model.enable_metric_discovery is True
        assert version_model.version_log == "新日志"
        assert len(version_model.metrics) == 1
        assert version_model.metrics[0]["table_name"] == "table1"

    def test_release_plugin_version_success(self, plugin_model):
        """测试发布插件版本 - 版本存在且为 DEBUG"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.DEBUG,
            updated_by="old_operator",
        )

        plugin_model.release_plugin_version(VersionTuple(major=1, minor=0), operator="new_operator")

        # 验证状态被更新
        version_model.refresh_from_db()
        assert version_model.status == MetricPluginStatus.RELEASE
        assert version_model.updated_by == "new_operator"

    def test_release_plugin_version_already_released(self, plugin_model):
        """测试发布插件版本 - 版本存在且为 RELEASE（幂等性）"""
        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=plugin_model,
            name="测试插件",
            params=[],
            define={},
            version="000001.000000",
            status=MetricPluginStatus.RELEASE,
            updated_by="old_operator",
        )

        plugin_model.release_plugin_version(VersionTuple(major=1, minor=0), operator="new_operator")

        # 验证状态保持为 RELEASE，且 updated_by 不会被更新（因为条件不满足）
        version_model.refresh_from_db()
        assert version_model.status == MetricPluginStatus.RELEASE
        assert version_model.updated_by == "old_operator"  # 保持原值，因为状态不是 DEBUG

    def test_release_plugin_version_not_found(self, plugin_model):
        """测试发布插件版本 - 版本不存在"""
        with pytest.raises(MetricPluginVersionNotFoundError) as exc_info:
            plugin_model.release_plugin_version(VersionTuple(major=2, minor=0), operator="admin")
        assert "插件版本不存在" in str(exc_info.value)


@pytest.mark.django_db(databases=["default"])
class TestMetricPluginDeploymentModel:
    """测试 MetricPluginDeploymentModel 模型"""

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

    def test_deployment_model_creation(self):
        """测试部署模型创建"""
        deployment = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
            created_by="admin",
        )
        assert deployment.bk_tenant_id == "test_tenant"
        assert deployment.bk_biz_id == 1
        assert deployment.plugin == self.plugin_model
        assert deployment.name == "测试部署"
        assert deployment.status == MetricPluginDeploymentStatusEnum.INITIALIZING.value
        assert deployment.created_by == "admin"

    def test_deployment_model_meta(self):
        """测试部署模型元数据"""
        assert MetricPluginDeploymentModel._meta.db_table == "metric_plugin_deployment"
        assert MetricPluginDeploymentModel._meta.verbose_name == "指标插件部署项"
        assert MetricPluginDeploymentModel._meta.verbose_name_plural == "指标插件部署项"
        assert MetricPluginDeploymentModel._meta.ordering == ["-created_at"]
        assert MetricPluginDeploymentModel._meta.unique_together == (("bk_tenant_id", "bk_biz_id", "name"),)

    def test_to_deployment(self):
        """测试转换为部署项定义"""
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.RUNNING.value,
            created_by="admin",
            updated_by="admin",
        )

        deployment = deployment_model.to_deployment()
        assert deployment.bk_tenant_id == "test_tenant"
        assert deployment.bk_biz_id == 1
        assert deployment.id == deployment_model.pk
        assert deployment.plugin_id == "test_plugin"
        assert deployment.name == "测试部署"
        assert deployment.status == MetricPluginDeploymentStatusEnum.RUNNING
        assert deployment.created_by == "admin"
        assert deployment.updated_by == "admin"

    def test_get_current_version_none(self):
        """测试获取当前版本 - 无版本"""
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

        current_version = deployment_model.get_current_version()
        assert current_version is None

    def test_get_current_version_exists(self):
        """测试获取当前版本 - 存在版本"""
        deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

        MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"key": "value"},
            target_node_type="host",
            target_nodes=[{"ip": "127.0.0.1"}],
            created_by="admin",
        )

        current_version = deployment_model.get_current_version()
        assert current_version is not None
        assert current_version.plugin_version == VersionTuple(major=1, minor=0)
        assert current_version.version == 1
        assert current_version.params == {"key": "value"}
        assert current_version.target_scope.node_type == "host"
        assert current_version.target_scope.nodes == [{"ip": "127.0.0.1"}]


@pytest.mark.django_db(databases=["default"])
class TestMetricPluginDeploymentVersionModel:
    """测试 MetricPluginDeploymentVersionModel 模型"""

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
        self.deployment_model = MetricPluginDeploymentModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            plugin=self.plugin_model,
            name="测试部署",
            status=MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        )

    def test_version_model_creation(self):
        """测试版本模型创建"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
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
        assert version_model.bk_tenant_id == "test_tenant"
        assert version_model.bk_biz_id == 1
        assert version_model.deployment == self.deployment_model
        assert version_model.plugin_version == "1.0"
        assert version_model.version == 1
        assert version_model.is_current is True
        assert version_model.params == {"key": "value"}
        assert version_model.target_node_type == "host"
        assert version_model.target_nodes == [{"ip": "127.0.0.1"}]
        assert version_model.created_by == "admin"

    def test_version_model_meta(self):
        """测试版本模型元数据"""
        assert MetricPluginDeploymentVersionModel._meta.db_table == "metric_plugin_deployment_version"
        assert MetricPluginDeploymentVersionModel._meta.verbose_name == "指标插件部署版本"
        assert MetricPluginDeploymentVersionModel._meta.verbose_name_plural == "指标插件部署版本"
        assert MetricPluginDeploymentVersionModel._meta.ordering == ["deployment", "-version"]
        assert MetricPluginDeploymentVersionModel._meta.unique_together == (
            ("bk_tenant_id", "bk_biz_id", "deployment", "version"),
        )

    def test_to_deployment_version_success(self):
        """测试转换为部署版本定义 - 成功"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
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

        deployment_version = version_model.to_deployment_version()
        assert deployment_version.plugin_version == VersionTuple(major=1, minor=0)
        assert deployment_version.version == 1
        assert deployment_version.params == {"key": "value"}
        assert deployment_version.target_scope.node_type == "host"
        assert deployment_version.target_scope.nodes == [{"ip": "127.0.0.1"}]
        assert deployment_version.remote_scope is None
        assert deployment_version.target_instances == []
        assert deployment_version.remote_instances == []
        assert deployment_version.created_by == "admin"

    def test_to_deployment_version_with_remote_scope(self):
        """测试转换为部署版本定义 - 包含远程范围"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"key": "value"},
            target_node_type="host",
            target_nodes=[{"ip": "127.0.0.1"}],
            remote_node_type="proxy",
            remote_nodes=[{"ip": "192.168.1.1"}],
            created_by="admin",
        )

        deployment_version = version_model.to_deployment_version()
        assert deployment_version.plugin_version == VersionTuple(major=1, minor=0)
        assert deployment_version.remote_scope is not None
        assert deployment_version.remote_scope.node_type == "proxy"
        assert deployment_version.remote_scope.nodes == [{"ip": "192.168.1.1"}]

    def test_to_deployment_version_without_remote_nodes(self):
        """测试转换为部署版本定义 - 无远程节点"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"key": "value"},
            target_node_type="host",
            target_nodes=[{"ip": "127.0.0.1"}],
            remote_node_type="proxy",
            remote_nodes=[],  # 空列表
            created_by="admin",
        )

        deployment_version = version_model.to_deployment_version()
        assert deployment_version.remote_scope is None

    def test_to_deployment_version_invalid_format(self):
        """测试转换为部署版本定义 - 无效格式"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="invalid",  # 无效格式
            version=1,
            is_current=True,
            params={},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )

        with pytest.raises(ValueError) as exc_info:
            version_model.to_deployment_version()
        # 检查错误消息包含版本格式相关的提示
        assert "插件版本格式错误" in str(exc_info.value) or "无效的插件版本格式" in str(exc_info.value)

    def test_to_deployment_version_invalid_format_missing_minor(self):
        """测试转换为部署版本定义 - 缺少次版本号"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1",  # 缺少次版本号
            version=1,
            is_current=True,
            params={},
            target_node_type="host",
            target_nodes=[],
            created_by="admin",
        )

        with pytest.raises(ValueError) as exc_info:
            version_model.to_deployment_version()
        # 检查错误消息包含版本格式相关的提示
        assert "插件版本格式错误" in str(exc_info.value) or "无效的插件版本格式" in str(exc_info.value)

    def test_to_deployment_version_with_instances(self):
        """测试转换为部署版本定义 - 包含实例"""
        version_model = MetricPluginDeploymentVersionModel.objects.create(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            deployment=self.deployment_model,
            plugin_version="1.0",
            version=1,
            is_current=True,
            params={"key": "value"},
            target_node_type="host",
            target_nodes=[{"ip": "127.0.0.1"}],
            target_instances=[{"instance_id": "inst1"}],
            remote_instances=[{"instance_id": "inst2"}],
            created_by="admin",
        )

        deployment_version = version_model.to_deployment_version()
        assert deployment_version.target_instances == [{"instance_id": "inst1"}]
        assert deployment_version.remote_instances == [{"instance_id": "inst2"}]


@pytest.mark.django_db(databases=["default"])
class TestParseLogoToBase64:
    """测试 _parse_logo_to_base64 函数"""

    def test_empty_logo(self):
        """测试空 logo 字符串"""
        assert _parse_logo_to_base64("") == ""

    def test_valid_base64_with_data_uri(self):
        """测试有效的 data URI 格式 base64"""
        # 创建一个小的测试图片 (1x1 像素 PNG)
        valid_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        logo = f"data:image/png;base64,{valid_base64}"
        assert _parse_logo_to_base64(logo) == logo

    def test_valid_base64_with_comma_only(self):
        """测试只有逗号分隔符的 base64"""
        valid_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        logo = f"data:image/png,{valid_base64}"
        assert _parse_logo_to_base64(logo) == logo

    def test_invalid_base64_data(self):
        """测试无效的 base64 数据"""
        logo = "data:image/png;base64,invalid!@#$%^&*()base64"
        assert _parse_logo_to_base64(logo) == ""

    def test_malformed_base64_data(self):
        """测试格式错误的 base64 数据"""
        logo = "data:image/png;base64,not_valid_base64!!!"
        assert _parse_logo_to_base64(logo) == ""

    def test_logo_without_separator(self):
        """测试没有分隔符的 logo"""
        logo = "invalidlogo"
        assert _parse_logo_to_base64(logo) == ""

    def test_logo_size_exceeded(self):
        """测试 logo 大小超过限制"""
        # 创建一个超过 2MB 的 base64 字符串
        # 添加 1000 字节额外偏移确保超出限制
        large_data = "A" * (MAX_LOGO_SIZE_BYTES + 1000)
        large_base64 = base64.b64encode(large_data.encode()).decode()
        logo = f"data:image/png;base64,{large_base64}"
        # 大小超过限制应该返回空字符串（被 try-except 捕获）
        assert _parse_logo_to_base64(logo) == ""

    def test_base64_decode_exception(self):
        """测试 base64 解码异常"""
        # 使用不符合 base64 编码规范的字符串
        logo = "data:image/png;base64,===invalid==="
        assert _parse_logo_to_base64(logo) == ""

    def test_empty_base64_data_after_split(self):
        """测试分割后为空的 base64 数据"""
        logo = "data:image/png;base64,"
        # 空的 base64 数据会导致解码失败
        assert _parse_logo_to_base64(logo) == ""
