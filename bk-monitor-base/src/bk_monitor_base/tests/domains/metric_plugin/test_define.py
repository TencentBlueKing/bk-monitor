"""
测试 metric_plugin.define 模块
"""

import pytest
from pydantic import ValidationError

from bk_monitor_base.metric_plugin import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
)


class TestMetricPluginStatus:
    """测试 MetricPluginStatus 枚举"""

    def test_enum_values(self):
        """测试枚举值"""
        assert MetricPluginStatus.DEBUG == "debug"
        assert MetricPluginStatus.RELEASE == "release"

    def test_enum_membership(self):
        """测试枚举成员"""
        # 检查枚举值
        assert MetricPluginStatus.DEBUG.value == "debug"
        assert MetricPluginStatus.RELEASE.value == "release"

        # 检查枚举成员
        assert MetricPluginStatus.DEBUG in MetricPluginStatus
        assert MetricPluginStatus.RELEASE in MetricPluginStatus


class TestMetricPluginMetricField:
    """测试 MetricPluginMetricField 模型"""

    def test_valid_field_with_string_type(self):
        """测试有效的字符串类型字段"""
        field = MetricPluginMetricField(name="dimension1", type="string", monitor_type="dimension")
        assert field.name == "dimension1"
        assert field.type == "string"
        assert field.monitor_type == "dimension"
        assert field.is_diff_metric is False

    def test_valid_field_with_double_type(self):
        """测试有效的 double 类型字段"""
        field = MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")
        assert field.name == "metric1"
        assert field.type == "double"
        assert field.monitor_type == "metric"

    def test_default_type_is_string(self):
        """测试默认类型为 string"""
        field = MetricPluginMetricField(name="field1", monitor_type="dimension")
        assert field.type == "string"
        assert field.is_diff_metric is False

    def test_normalize_type_int_to_double(self):
        """测试 int 类型自动转换为 double（兼容处理）

        验证 normalize_type 验证器能够将 type="int" 自动转换为 "double"，
        以兼容历史数据或外部系统传入的 int 类型。
        """
        field = MetricPluginMetricField(name="metric1", type="int", monitor_type="metric")
        assert field.type == "double"

    def test_normalize_type_preserves_double(self):
        """测试 double 类型保持不变"""
        field = MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")
        assert field.type == "double"

    def test_normalize_type_preserves_string(self):
        """测试 string 类型保持不变"""
        field = MetricPluginMetricField(name="dim1", type="string", monitor_type="dimension")
        assert field.type == "string"

    def test_invalid_type_raises_error(self):
        """测试无效类型抛出验证错误"""
        with pytest.raises(ValidationError):
            MetricPluginMetricField(name="field1", type="invalid", monitor_type="dimension")


class TestMetricPluginMetricGroup:
    """测试 MetricPluginMetricGroup 模型"""

    def test_valid_metric_group(self):
        """测试有效的指标组"""
        group = MetricPluginMetricGroup(
            table_name="test_table",
            table_desc="测试表",
            fields=[
                MetricPluginMetricField(name="metric1", type="double", monitor_type="metric"),
                MetricPluginMetricField(name="dim1", type="string", monitor_type="dimension"),
            ],
            rules=["rule1", "rule2"],
        )
        assert group.table_name == "test_table"
        assert group.table_desc == "测试表"
        assert len(group.fields) == 2
        assert group.rules == ["rule1", "rule2"]

    def test_minimal_metric_group(self):
        """测试最小参数的指标组"""
        group = MetricPluginMetricGroup(table_name="test_table")
        assert group.table_name == "test_table"
        assert group.table_desc == ""
        assert group.fields == []
        assert group.rules == []

    def test_nested_field_normalize_type_int_to_double(self):
        """测试嵌套字段的 int 类型自动转换为 double

        验证通过 dict 方式创建 MetricPluginMetricGroup 时，
        嵌套的 MetricPluginMetricField 中 type="int" 也能正确转换为 "double"。
        """
        group = MetricPluginMetricGroup(
            table_name="test_table",
            fields=[{"name": "metric1", "type": "int", "monitor_type": "metric"}],
        )
        assert group.fields[0].type == "double"


class TestMetricPluginParams:
    """测试 MetricPluginParams 模型"""

    def test_valid_params(self):
        """测试有效参数"""
        params = MetricPluginParams(
            name="test_param",
            description="测试参数",
            type="string",
            required=True,
            default="default_value",
            alias="test",
            mode="input",
        )
        assert params.name == "test_param"
        assert params.description == "测试参数"
        assert params.type == "string"
        assert params.required is True
        assert params.default == "default_value"
        assert params.alias == "test"
        assert params.mode == "input"

    def test_minimal_params(self):
        """测试最小参数"""
        params = MetricPluginParams(name="test", type="string")
        assert params.name == "test"
        assert params.type == "string"
        assert params.description == ""
        assert params.required is False
        assert params.default is None
        assert params.alias == ""
        assert params.mode == ""
        assert params.file_base64 == ""

    def test_invalid_name_empty(self):
        """测试无效的空名称"""
        with pytest.raises(ValidationError):
            MetricPluginParams(name="", type="string")

    def test_invalid_name_too_long(self):
        """测试名称过长"""
        with pytest.raises(ValidationError):
            MetricPluginParams(name="a" * 256, type="string")

    def test_invalid_type_empty(self):
        """测试无效的空类型"""
        with pytest.raises(ValidationError):
            MetricPluginParams(name="test", type="")

    def test_invalid_type_too_long(self):
        """测试类型过长"""
        with pytest.raises(ValidationError):
            MetricPluginParams(name="test", type="a" * 33)


class TestMetricPlugin:
    """测试 MetricPlugin 模型"""

    def test_valid_plugin(self):
        """测试有效插件"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            description_md="# 测试插件",
            logo="logo.png",
            created_by="admin",
            updated_by="admin",
            metrics=[
                MetricPluginMetricGroup(
                    table_name="test_metric",
                    fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
                )
            ],
            enable_metric_discovery=True,
            params=[MetricPluginParams(name="param1", type="string")],
            define={"script": "echo 'test'"},
            version=(1, 0),
            version_log="初始版本",
            status=MetricPluginStatus.DEBUG,
        )
        assert plugin.bk_tenant_id == "test_tenant"
        assert plugin.bk_biz_id == 1
        assert plugin.id == "test_plugin"
        assert plugin.type == "script"
        assert plugin.name == "测试插件"
        assert plugin.description_md == "# 测试插件"
        assert plugin.logo == "logo.png"
        assert plugin.created_by == "admin"
        assert plugin.updated_by == "admin"
        assert plugin.metrics == [
            MetricPluginMetricGroup(
                table_name="test_metric",
                fields=[MetricPluginMetricField(name="metric1", type="double", monitor_type="metric")],
            )
        ]
        assert plugin.enable_metric_discovery is True
        assert len(plugin.params) == 1
        assert plugin.params[0].name == "param1"
        assert plugin.define == {"script": "echo 'test'"}
        assert plugin.version == (1, 0)
        assert plugin.version_log == "初始版本"
        assert plugin.status == MetricPluginStatus.DEBUG

    def test_minimal_plugin(self):
        """测试最小插件"""
        plugin = MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="script", name="测试插件")
        assert plugin.bk_tenant_id == "test_tenant"
        assert plugin.bk_biz_id == 1
        assert plugin.id == "test_plugin"
        assert plugin.type == "script"
        assert plugin.name == "测试插件"
        assert plugin.description_md == ""
        assert plugin.logo == ""
        assert plugin.created_by == ""
        assert plugin.updated_by == ""
        assert plugin.metrics == []
        assert plugin.enable_metric_discovery is False
        assert plugin.params == []
        assert plugin.define == {}
        assert plugin.version == (1, 0)
        assert plugin.status == MetricPluginStatus.DEBUG

    def test_invalid_tenant_id_empty(self):
        """测试无效的空租户ID"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="", bk_biz_id=1, id="test_plugin", type="script", name="测试插件")

    def test_invalid_tenant_id_too_long(self):
        """测试租户ID过长"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="a" * 65, bk_biz_id=1, id="test_plugin", type="script", name="测试插件")

    def test_invalid_plugin_id_empty(self):
        """测试无效的空插件ID"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="", type="script", name="测试插件")

    def test_invalid_plugin_id_too_long(self):
        """测试插件ID过长"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="a" * 65, type="script", name="测试插件")

    def test_invalid_type_empty(self):
        """测试无效的空类型"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="", name="测试插件")

    def test_invalid_type_too_long(self):
        """测试类型过长"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="a" * 33, name="测试插件")

    def test_invalid_name_empty(self):
        """测试无效的空名称"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="script", name="")

    def test_invalid_name_too_long(self):
        """测试名称过长"""
        with pytest.raises(ValidationError):
            MetricPlugin(bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="script", name="a" * 256)

    def test_plugin_with_params(self):
        """测试带参数的插件"""
        params = [
            MetricPluginParams(name="param1", type="string", required=True),
            MetricPluginParams(name="param2", type="int", default=100),
        ]
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="script", name="测试插件", params=params
        )
        assert len(plugin.params) == 2
        assert plugin.params[0].name == "param1"
        assert plugin.params[0].required is True
        assert plugin.params[1].name == "param2"
        assert plugin.params[1].default == 100

    def test_plugin_global_and_internal(self):
        """测试全局和内置插件"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            is_global=True,
            is_internal=True,
        )
        assert plugin.is_global is True
        assert plugin.is_internal is True

    def test_plugin_version_increment(self):
        """测试插件版本递增"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant", bk_biz_id=1, id="test_plugin", type="script", name="测试插件", version=(2, 1)
        )
        assert plugin.version == (2, 1)

    def test_plugin_status_transition(self):
        """测试插件状态转换"""
        plugin = MetricPlugin(
            bk_tenant_id="test_tenant",
            bk_biz_id=1,
            id="test_plugin",
            type="script",
            name="测试插件",
            status=MetricPluginStatus.RELEASE,
        )
        assert plugin.status == MetricPluginStatus.RELEASE
