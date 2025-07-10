import os
from django.conf import settings
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
from monitor_web.plugin.manager import PluginManagerFactory

PLUGIN_ID = "test_plugin"

VALIDATED_REQUEST_DATA = {
    "bk_biz_id": 2,
    "plugin_id": PLUGIN_ID,
    "plugin_display_name": "ghjghj",
    "plugin_type": "Script",
    "logo": "",
    "collector_json": {
        "linux": {
            "filename": "test_plugin.sh",
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
    "collector_json": {"linux": {"filename": "test_plugin.sh", "type": "shell", "script_content_base64": "xxxx"}},
    "bk_tenant_id": "system",
    "enable_field_blacklist": True,
    "os_type_list": ["linux"],
    "need_debug": True,
}


HOST_INFO = {"bk_biz_id": 2, "bk_host_id": 32, "bk_supplier_id": 0}
START_DEBUG_PARAM = {"collector": {"host": "127.0.0.1", "period": "10"}, "plugin": {}}
IMPORT_TMP_PATH = os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/import_test_package/")

PARAM = {
    "collector": {
        "period": "60",
        "timeout": "60",
        "metric_relabel_configs": [],
        "task_id": "9",
        "bk_biz_id": "2",
        "config_name": "aaaa710",
        "config_version": "1.0",
        "namespace": "aaaa710",
        "max_timeout": "60",
        "dataid": "1574943",
        "labels": {
            "$for": "cmdb_instance.scope",
            "$item": "scope",
            "$body": {
                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                "bk_collect_config_id": 9,
            },
        },
    },
    "plugin": {},
    "target_node_type": "INSTANCE",
    "target_object_type": "HOST",
    "subscription_id": 0,
}
RESULT_DEPLOY_PARAMS = [
    {
        "id": "test_plugin",
        "type": "PLUGIN",
        "config": {
            "plugin_name": "test_plugin",
            "plugin_version": "1.1",
            "config_templates": [{"name": "env.yaml", "version": "1"}],
        },
        "params": {"context": {"cmd_args": ""}},
    },
    {
        "id": "bkmonitorbeat",
        "type": "PLUGIN",
        "config": {
            "plugin_name": "bkmonitorbeat",
            "plugin_version": "latest",
            "config_templates": [{"name": "bkmonitorbeat_script.conf", "version": "latest"}],
        },
        "params": {
            "context": {
                "period": "60",
                "timeout": "60",
                "metric_relabel_configs": [],
                "task_id": "9",
                "bk_biz_id": "2",
                "config_name": "aaaa710",
                "config_version": "1.0",
                "namespace": "aaaa710",
                "max_timeout": "60",
                "dataid": "1574943",
                "labels": {
                    "$for": "cmdb_instance.scope",
                    "$item": "scope",
                    "$body": {
                        "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                        "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                        "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                        "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                        "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                        "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                        "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                        "bk_collect_config_id": 9,
                    },
                },
                "command": "{{ step_data.test_plugin.control_info.setup_path }}/{{ step_data.test_plugin.control_info.start_cmd }}",
            }
        },
    },
]


class Base:
    pass


request = Base()
request.user = Base()
request.user.tenant_id = "system"


class TestPlugin(TestCase):
    @patch("core.drf_resource.api.metadata.create_time_series_group", return_value="")
    @patch("core.drf_resource.api.node_man.release_plugin", return_value="")
    @patch("core.drf_resource.api.node_man.create_config_template", return_value="")
    @patch("core.drf_resource.api.node_man.plugin_info", return_value=[{"md5": ""}])
    @patch("core.drf_resource.api.node_man.register_package", return_value={"job_id": 1})
    @patch("core.drf_resource.api.node_man.query_register_task", return_value={"message": "", "is_finish": 1})
    @patch("core.drf_resource.api.node_man.upload", return_value={"name": "name_01"})
    def test_create_register_release(self, mock_1, mock_2, mock_3, mock_4, mock_5, mock_6, mock_7):
        # 指标插件创建
        creat_plugin = CreatePluginResource()
        validated_request_data = creat_plugin.validate_request_data(VALIDATED_REQUEST_DATA)
        params = creat_plugin.perform_request(validated_request_data)
        params.pop("signature")
        self.assertEqual(params, RESULT)

        plugin_meta_item = CollectorPluginMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertIsNotNone(plugin_meta_item)
        version_his = PluginVersionHistory.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertIsNotNone(version_his)
        item = CollectorPluginInfo.objects.filter(id=version_his.info_id).first()
        self.assertIsNotNone(item)
        item = CollectorPluginConfig.objects.filter(id=version_his.config_id).first()
        self.assertIsNotNone(item)

        # 指标插件注册
        PluginRegisterResource().perform_request(REGISTER_VALIDATED_REQUEST_DATA)
        version = PluginVersionHistory.objects.filter(
            bk_tenant_id="system",
            plugin_id=PLUGIN_ID,
        ).first()
        self.assertTrue(version.is_packaged)

        # 指标插件release接口
        deployment_ver = DeploymentConfigVersion.objects.create(
            target_node_type="INSTANCE",
            # plugin_version_id=1,
            plugin_version_id=version_his.id,
            config_meta_id=1,
        )
        CollectConfigMeta.objects.create(
            bk_biz_id=2,
            name="demo01",
            collect_type="Script",
            target_object_type="HOST",
            last_operation="CREATE",
            operation_result="SUCCESS",
            plugin_id=plugin_meta_item.plugin_id,
            deployment_config=deployment_ver,
        )

        mock_request = mock.Mock(spec=Request)
        mock_request.data = JSON_DATA

        collector_plugin = CollectorPluginViewSet()
        collector_plugin.request = request
        collector_plugin.release(mock_request, plugin_id=PLUGIN_ID)

        config_meta = CollectConfigMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertEqual(config_meta.deployment_config.plugin_version.stage, "release")


class TestPluginManager(TestCase):
    def setUp(self):
        plugin_meta = CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Script")
        plugin_config = CollectorPluginConfig.objects.create(config_json=[])
        plugin_info = CollectorPluginInfo.objects.create()
        self.plugin_version = PluginVersionHistory.objects.create(
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
            plugin_version_id=self.plugin_version.id,
            config_meta_id=1,
        )
        CollectConfigMeta.objects.create(
            bk_biz_id=2,
            name="demo01",
            collect_type="Script",
            target_object_type="HOST",
            last_operation="CREATE",
            operation_result="SUCCESS",
            plugin_id=plugin_meta.plugin_id,
            deployment_config=deployment_ver,
        )

        self.plugin_manager = PluginManagerFactory.get_manager(
            plugin=plugin_meta, operator="admin", tmp_path=IMPORT_TMP_PATH
        )

    @patch("core.drf_resource.api.metadata.create_time_series_group", return_value="")
    @patch("core.drf_resource.api.node_man.release_plugin", return_value="")
    def test_release(self, mock_release_plugin, mock_create_time_series_group):
        self.plugin_manager.release(1, 1)
        config_meta = CollectConfigMeta.objects.filter(plugin_id=PLUGIN_ID).first()
        self.assertEqual(config_meta.deployment_config.plugin_version.stage, "release")
        self._test_run_export()

    @patch("core.drf_resource.api.node_man.render_config_template", return_value={"id": 1})
    @patch("core.drf_resource.api.node_man.start_debug", return_value="1")
    def test_start_debug(self, mock_start_debug, mock_render_config_template):
        task_id = self.plugin_manager.start_debug(
            config_version="1", info_version="1", param=START_DEBUG_PARAM, host_info=HOST_INFO
        )
        self.assertEqual(task_id, "1")

    @patch(
        "monitor_web.plugin.manager.base.api.node_man.query_debug",
        return_value={"status": "INSTALL", "message": "installing", "step": ""},
    )
    def test_query_debug_install(self, mock_query_debug):
        result = self.plugin_manager.query_debug(1)
        self.assertEqual(result["status"], "INSTALL")
        self.assertEqual(result["log_content"], "installing")

    @patch(
        "monitor_web.plugin.manager.base.api.node_man.query_debug",
        return_value={"status": "SUCCESS", "message": "is_success"},
    )
    def test_query_debug_success(self, mock_query_debug):
        result = self.plugin_manager.query_debug(1)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["log_content"], "is_success")

    @patch("monitor_web.plugin.manager.base.api.node_man.stop_debug", return_value=True)
    def test_stop_debug(self, mock_stop_debug):
        self.assertTrue(self.plugin_manager.stop_debug(11))

    def test_get_tmp_version(self):
        self.assertEqual(self.plugin_manager.get_tmp_version(), self.plugin_manager.version)

    @patch(
        "core.drf_resource.api.node_man.export_query_task",
        return_value={"is_finish": True, "is_failed": False, "download_url": "download_url", "error_message": ""},
    )
    def _test_run_export(self, mock_export_query_task):
        self.assertEqual(self.plugin_manager.run_export(), "download_url")
        self.assertTrue(mock_export_query_task.called)

    def test_get_deploy_steps_params(self):
        result = self.plugin_manager.get_deploy_steps_params(
            plugin_version=self.plugin_version, param=PARAM, target_nodes=""
        )
        self.assertEqual(result, RESULT_DEPLOY_PARAMS)
