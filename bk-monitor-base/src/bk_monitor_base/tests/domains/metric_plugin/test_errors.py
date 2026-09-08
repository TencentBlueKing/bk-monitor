"""
测试 metric_plugin.errors 模块
"""

from bk_monitor_base.domains.metric_plugin.errors import (
    MetricPluginNotFoundError,
    MetricPluginVersionNotFoundError,
)


class TestMetricPluginNotFoundError:
    """测试 MetricPluginNotFoundError 异常"""

    def test_exception_creation(self):
        """测试异常创建"""
        error = MetricPluginNotFoundError("插件不存在")
        assert str(error) == "插件不存在"

    def test_exception_inheritance(self):
        """测试异常继承关系"""
        error = MetricPluginNotFoundError("测试错误")
        assert isinstance(error, Exception)
        assert isinstance(error, MetricPluginNotFoundError)


class TestMetricPluginVersionNotFoundError:
    """测试 MetricPluginVersionNotFoundError 异常"""

    def test_exception_creation(self):
        """测试异常创建"""
        error = MetricPluginVersionNotFoundError("插件版本不存在")
        assert str(error) == "插件版本不存在"

    def test_exception_inheritance(self):
        """测试异常继承关系"""
        error = MetricPluginVersionNotFoundError("测试错误")
        assert isinstance(error, Exception)
        assert isinstance(error, MetricPluginVersionNotFoundError)

    def test_exception_with_plugin_id(self):
        """测试异常包含插件ID"""
        plugin_id = "test_plugin"
        version = (1, 0)
        error = MetricPluginVersionNotFoundError(f"插件版本不存在: {plugin_id} ({version})")
        assert plugin_id in str(error)
        assert str(version) in str(error)
