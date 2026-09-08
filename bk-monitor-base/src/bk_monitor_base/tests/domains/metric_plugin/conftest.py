"""
metric_plugin 测试配置
"""

import pytest


@pytest.fixture
def sample_plugin():
    """创建示例插件"""
    from bk_monitor_base.domains.metric_plugin.define import MetricPlugin, MetricPluginParams, MetricPluginStatus

    return MetricPlugin(
        bk_tenant_id="test_tenant",
        bk_biz_id=1,
        id="test_plugin",
        type="script",
        name="测试插件",
        description_md="# 测试插件",
        params=[MetricPluginParams(name="param1", type="string")],
        define={"script": "echo 'test'"},
        version=(1, 0),
        version_log="初始版本",
        status=MetricPluginStatus.DEBUG,
        created_by="admin",
        updated_by="admin",
    )


@pytest.fixture
def sample_plugin_params():
    """创建示例插件参数"""
    from bk_monitor_base.domains.metric_plugin.define import MetricPluginParams

    return [
        MetricPluginParams(name="param1", type="string", required=True),
        MetricPluginParams(name="param2", type="int", default=100),
        MetricPluginParams(name="param3", type="bool", default=False),
    ]
