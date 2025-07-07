from django.test import TestCase
from packages.monitor_web.plugin.resources import CreatePluginResource
from packages.monitor_web.plugin.views import CollectorPluginViewSet
from monitor_web.models.plugin import (
    CollectorPluginMeta,
    PluginVersionHistory,
    CollectorPluginInfo,
    CollectorPluginConfig,
)
from monitor_web.models.collecting import (
    CollectConfigMeta,
    DeploymentConfigVersion,
)
from rest_framework.request import Request
from unittest import mock
from unittest.mock import Mock, patch

PLUGIN_ID = "plugin_01"

VALIDATED_REQUEST_DATA = {
    "bk_biz_id": 2,
    "plugin_id": PLUGIN_ID,
    "plugin_display_name": "ghjghj",
    "plugin_type": "Script",
    "logo": "",
    "collector_json": {
        "linux": {
            "filename": "plugin_01.sh",
            "type": "shell",
            "script_content_base64": "xxxx",
        },
    },
    "config_json": [],
    "metric_json": [],
    "label": "os",
    "version_log": "",
    "signature": "",
    "is_support_remote": False,
    "description_md": "",
    "related_conf_count": 0,
    "config_version_old": None,
    "import_plugin_config": None,
    "import_plugin_metric_json": [],
}

JSON_DATA = {
    "config_version": 1,
    "info_version": 1,
    "token": [
        "23fe6d3774d0cf178fd3de3604f1acca",
    ],
    "bk_biz_id": 2,
}


class TestCreatePluginResource(TestCase):
    def test_perform_request(self):
        creat_plugin = CreatePluginResource()
        validated_request_data = creat_plugin.validate_request_data(VALIDATED_REQUEST_DATA)
        creat_plugin.perform_request(validated_request_data)
        items = CollectorPluginMeta.objects.filter(plugin_id=PLUGIN_ID)
        self.assertTrue(items.exists())

        items = PluginVersionHistory.objects.filter(plugin_id=PLUGIN_ID)
        self.assertTrue(items.exists())


class TestCollectorPluginViewSet(TestCase):
    @patch("packages.monitor_web.plugin.views.CollectorPluginViewSet.get_queryset")
    @patch("monitor_web.plugin.manager.PluginManagerFactory.get_manager")
    def test_release(self, mock_get_manager, mock_get_queryset):
        plugin_meta = CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Pushgateway")
        plugin_config = CollectorPluginConfig.objects.create()
        plugin_info = CollectorPluginInfo.objects.create()
        PluginVersionHistory.objects.create(
            config_version=1,
            info_version=1,
            config_id=plugin_config.id,
            info_id=plugin_info.id,
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )
        deployment_ver = DeploymentConfigVersion.objects.create(
            target_node_type="INSTANCE",
            plugin_version_id=1,
            config_meta_id=1,
        )
        CollectConfigMeta.objects.create(
            bk_biz_id=2,
            name="demo01",
            collect_type="Pushgateway",
            target_object_type="HOST",
            last_operation="CREATE",
            operation_result="SUCCESS",
            plugin_id=plugin_meta.plugin_id,
            deployment_config=deployment_ver,
        )

        new_plugin_his = PluginVersionHistory.objects.create(
            config_version=1,
            info_version=2,
            config_id=plugin_config.id,
            info_id=plugin_info.id,
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )

        mock_plugin_manager = Mock()
        mock_plugin_manager.release.return_value = new_plugin_his
        mock_get_manager.return_value = mock_plugin_manager

        mock_queryset = Mock()
        mock_queryset.get.return_value = plugin_meta
        mock_get_queryset.return_value = mock_queryset

        mock_request = mock.Mock(spec=Request)
        mock_request.data = JSON_DATA
        CollectorPluginViewSet().release(mock_request)

        config_meta = CollectConfigMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertEqual(config_meta.deployment_config.plugin_version, new_plugin_his)
