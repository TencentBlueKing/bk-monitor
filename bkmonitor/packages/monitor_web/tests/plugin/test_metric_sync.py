import copy

import pytest
from monitor_web.models import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import PluginType

pytestmark = pytest.mark.django_db


metric_json = [
    {
        "fields": [
            {
                "type": "double",  # 字段类型
                "monitor_type": "metric",  # 指标类型（metric or dimension）
                "unit": "none",  # 单位
                "name": "disk_usage",  # 字段名（指标或维度名）
                "source_name": "",  # 原指标名
                "description": "disk_usage_1",  # 描述（别名）
                "is_active": True,  # 是否启用
                "is_diff_metric": False,  # 是否差值指标
                "dimensions": ["disk_name"],
            },
            {
                "type": "string",
                "monitor_type": "dimension",
                "unit": "none",
                "name": "disk_name",
                "source_name": "",
                "description": "disk_name_1",
                "is_active": True,
            },
        ],
        "rule_list": ["di"],
        "table_name": "base",
        "table_desc": "123",
    }
]

group_data = [
    {
        "time_series_group_id": "haha",
        "time_series_group_name": "hahaha",
        "bk_data_id": 10010,
        "bk_biz_id": 2,
        "table_id": "hahah.base",
        "label": "os",
        "is_enable": True,
        "creator": "wz",
        "metric_info_list": [
            {
                "field_name": "diskkk",
                "metric_display_name": "",
                "unit": "",
                "type": "double",
                "is_disabled": False,
                "tag_list": [
                    {
                        "field_name": "dimensionA",
                        "metric_display_name": "",
                        "unit": "",
                        "type": "string",
                    }
                ],
            }
        ],
    }
]


class TestMetricSync(object):
    """
    测试指标回写功能
    """

    def clear_old_models(self):
        CollectorPluginMeta.objects.all().delete()
        CollectorPluginConfig.objects.all().delete()
        CollectorPluginInfo.objects.all().delete()
        PluginVersionHistory.objects.all().delete()

    def create_models(self):
        metrics = copy.deepcopy(metric_json)
        metrics[0]["fields"][1]["is_diff_metric"] = False
        plugin = CollectorPluginMeta.objects.create(plugin_id="test_r", plugin_type=PluginType.DATADOG, label="test")
        config = CollectorPluginConfig.objects.create(
            config_json=[],
            collector_json={
                "linux": {"filename": "test.sh", "type": "shell", "script_content_base64": "IyEvYmluL3NoCmVja"}
            },
        )
        info = CollectorPluginInfo.objects.create(
            plugin_display_name="test", metric_json=metrics, enable_field_blacklist=True
        )
        PluginVersionHistory.objects.create(
            plugin=plugin, config=config, info=info, config_version=1, info_version=1, stage="release", is_packaged=True
        )
        PluginVersionHistory.objects.create(
            plugin=plugin,
            config=config,
            info=info,
            config_version=1,
            info_version=2,
            stage="release",
            is_packaged=False,
        )

    def test_metric_sync(self, mocker):
        self.clear_old_models()
        self.create_models()
        plugin = CollectorPluginMeta.objects.get(plugin_id="test_r")
        assert len(plugin.current_version.info.metric_json[0]["fields"]) == 2
        plugin.update_metric_json_from_ts_group(group_data)
        assert len(plugin.current_version.info.metric_json[0]["fields"]) == 4
        assert "diskkk" in plugin.current_version.info.metric_set
