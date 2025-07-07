from django.test import TestCase
from packages.monitor_web.plugin.resources import CreatePluginResource, PluginRegisterResource
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
from unittest.mock import patch

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

REGISTER_VALIDATED_REQUEST_DATA = {"plugin_id": PLUGIN_ID, "config_version": 1, "info_version": 1}

RESULT = {
    "metric_json": [],
    "config_json": [],
    "plugin_display_name": "ghjghj",
    "description_md": "",
    "logo": "",
    "config_version": 1,
    "info_version": 1,
    "is_support_remote": False,
    "version_log": "",
    "plugin_id": PLUGIN_ID,
    "data_label": "",
    "bk_biz_id": 2,
    "bk_supplier_id": 0,
    "plugin_type": "Script",
    "tag": "",
    "label": "os",
    "import_plugin_metric_json": [],
    "collector_json": {"linux": {"filename": "plugin_01.sh", "type": "shell", "script_content_base64": "xxxx"}},
    "bk_tenant_id": "system",
    "enable_field_blacklist": True,
    "os_type_list": ["linux"],
    "need_debug": True,
}


class Base:
    pass


request = Base()
request.user = Base()
request.user.tenant_id = "system"


class TestCreatePluginResource(TestCase):
    def test_perform_request(self):
        creat_plugin = CreatePluginResource()
        validated_request_data = creat_plugin.validate_request_data(VALIDATED_REQUEST_DATA)
        params = creat_plugin.perform_request(validated_request_data)
        params.pop("signature")
        self.assertEqual(params, RESULT)

        item = CollectorPluginMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertIsNotNone(item)

        version_his = PluginVersionHistory.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertIsNotNone(version_his)

        item = CollectorPluginInfo.objects.filter(id=version_his.info_id).first()
        self.assertIsNotNone(item)

        item = CollectorPluginConfig.objects.filter(id=version_his.config_id).first()
        self.assertIsNotNone(item)


class TestPluginRegisterResource111111(TestCase):
    @patch("core.drf_resource.api.node_man.create_config_template", return_value="")
    @patch("core.drf_resource.api.node_man.plugin_info", return_value=[{"md5": ""}])
    @patch("core.drf_resource.api.node_man.register_package", return_value={"job_id": 1})
    @patch("core.drf_resource.api.node_man.query_register_task", return_value={"message": "", "is_finish": 1})
    @patch("core.drf_resource.api.node_man.upload", return_value={"name": "name_01"})
    def test_perform_request(self, mock_1, mock_2, mock_3, mock_4, mock_5):
        CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Pushgateway")
        plugin_config = CollectorPluginConfig.objects.create(config_json=[])
        plugin_info = CollectorPluginInfo.objects.create()
        PluginVersionHistory.objects.create(
            is_packaged=False,
            config_version=1,
            info_version=1,
            config_id=plugin_config.id,
            info_id=plugin_info.id,
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )

        PluginRegisterResource().perform_request(REGISTER_VALIDATED_REQUEST_DATA)
        version = PluginVersionHistory.objects.filter(
            bk_tenant_id="system",
            plugin_id=PLUGIN_ID,
        ).first()
        self.assertTrue(version.is_packaged)


class TestCollectorPluginViewSet(TestCase):
    @patch("core.drf_resource.api.metadata.create_time_series_group", return_value="")
    @patch("core.drf_resource.api.node_man.release_plugin", return_value="")
    def test_release(self, mock_release_plugin, mock_create_time_series_group):
        plugin_meta = CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Pushgateway")
        plugin_config = CollectorPluginConfig.objects.create(config_json=[])
        plugin_info = CollectorPluginInfo.objects.create()
        PluginVersionHistory.objects.create(
            stage="DEBUG",
            is_packaged=1,
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

        mock_request = mock.Mock(spec=Request)
        mock_request.data = JSON_DATA

        collector_plugin = CollectorPluginViewSet()
        collector_plugin.request = request
        collector_plugin.release(mock_request, plugin_id=PLUGIN_ID)

        config_meta = CollectConfigMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertEqual(config_meta.deployment_config.plugin_version.stage, "release")
