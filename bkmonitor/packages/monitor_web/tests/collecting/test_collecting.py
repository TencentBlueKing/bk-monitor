"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import os

from unittest import mock
from django.test import TestCase

from bkmonitor.utils.local import local
from config import celery_app
from core.drf_resource import APIResource, resource
from monitor_web.models import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    PluginVersionHistory,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.custom_report import CustomEventGroup, CustomEventItem
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.collecting.deploy import get_collect_installer
from packages.monitor_web.collecting.resources.backend import SaveCollectConfigResource
from unittest.mock import patch

PLUGIN_ID = "plugin_01"

DATA = {
    "name": "name626",
    "bk_biz_id": 2,
    "collect_type": "Script",
    "target_object_type": "HOST",
    "target_node_type": "INSTANCE",
    "plugin_id": PLUGIN_ID,
    "target_nodes": [{"bk_host_id": 54}, {"bk_host_id": 587}],
    "remote_collecting_host": None,
    "params": {"collector": {"period": 60, "timeout": 60}, "plugin": {}},
    "label": "os",
    "operation": "EDIT",
    "metric_relabel_configs": [],
}

INSTALL_CONFIG = {
    "name": "name626",
    "bk_biz_id": 2,
    "collect_type": "Script",
    "target_object_type": "HOST",
    "target_node_type": "INSTANCE",
    "plugin_id": PLUGIN_ID,
    "target_nodes": [{"bk_host_id": 54}, {"bk_host_id": 587}],
    "remote_collecting_host": None,
    "params": {
        "collector": {"period": 60, "timeout": 60, "metric_relabel_configs": []},
        "plugin": {},
        "target_node_type": "INSTANCE",
        "target_object_type": "HOST",
    },
    "label": "os",
    "operation": "CREATE",
}
INSTALL_RESULT = {
    "diff_node": {
        "is_modified": True,
        "added": [{"bk_host_id": 54}, {"bk_host_id": 587}],
        "removed": [],
        "unchanged": [],
        "updated": [],
    },
    "can_rollback": False,
    "id": 1,
    "deployment_id": 1,
}


class Base:
    pass


request = Base()
request.user = Base()
request.user.username = "admin"
request.COOKIES = ""
request.GET = ""


class TestCollectingViewSet(TestCase):
    def setUp(self):
        self.delete_model()
        celery_app.conf.task_always_eager = True

    def tearDown(self):
        self.delete_model()

    def delete_model(self):
        CollectorPluginMeta.objects.all().delete()
        CollectorPluginInfo.objects.all().delete()
        CollectorPluginConfig.objects.all().delete()
        PluginVersionHistory.objects.all().delete()
        CustomEventItem.objects.all().delete()
        CustomEventGroup.objects.all().delete()
        CollectConfigMeta.objects.all().delete()
        celery_app.conf.task_always_eager = False

    @mock.patch.object(APIResource, "perform_request")
    def test_create_collect(self, mock_api):
        group_info = {
            "bk_biz_id": 2,
            "event_group_id": "456",
            "label": "component",
            "event_group_name": "test_create",
            "bk_data_id": "123",
            "table_id": "2_bkmonitor_plugin",
            "event_info_list": [
                {
                    "event_id": "234",
                    "event_group_id": "111",
                    "event_name": "test_event",
                    "dimension_list": [{"dimension_name": "test_ip"}],
                }
            ],
        }

        def mock_request(*args, **kwargs):
            if "data_name" in args[0]:
                return {"bk_data_id": "123"}
            elif "bk_data_id" in args[0]:
                return group_info
            elif "scope" in args[0]:
                return {"subscription_id": "123456", "task_id": "234567"}

        mock_api.side_effect = mock_request
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_file", "test.json")
        with open(file_path) as fp:
            post_data = json.load(fp)
        local.current_request = request
        content = resource.collecting.save_collect_config.request(post_data)
        self.assertTrue(content["deployment_id"], DeploymentConfigVersion.objects.last().pk)


class TestSaveCollectConfigResource(TestCase):
    @patch("core.drf_resource.api.node_man.release_plugin", return_value="")
    @patch("core.drf_resource.api.node_man.create_config_template", return_value="")
    @patch("core.drf_resource.api.node_man.plugin_info", return_value=[{"md5": ""}])
    @patch("core.drf_resource.api.node_man.register_package", return_value={"job_id": 1})
    @patch("core.drf_resource.api.node_man.query_register_task", return_value={"message": "", "is_finish": 1})
    @patch("core.drf_resource.api.node_man.upload", return_value={"name": "name_01"})
    def test_perform_request(self, mock_1, mock_2, mock_3, mock_4, mock_5, mock_6):
        CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Pushgateway")
        plugin_config = CollectorPluginConfig.objects.create(config_json=[])
        plugin_info = CollectorPluginInfo.objects.create()
        PluginVersionHistory.objects.create(
            config_version=1,
            info_version=1,
            config_id=plugin_config.id,
            info_id=plugin_info.id,
            stage="release",
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )

        SaveCollectConfigResource().perform_request(data=DATA)
        items = DeploymentConfigVersion.objects.filter()
        self.assertTrue(items.exists())


class TestBaseInstaller(TestCase):
    def setUp(self):
        self.collect_config = CollectConfigMeta(
            bk_tenant_id="system",
            bk_biz_id=2,
            name="name626",
            last_operation="CREATE",
            operation_result="PREPARING",
            collect_type="Script",
            plugin_id=PLUGIN_ID,
            target_object_type="HOST",
            label="os",
        )
        CollectorPluginMeta.objects.create(plugin_id=PLUGIN_ID, bk_biz_id=2, plugin_type="Pushgateway")
        self.plugin_config = CollectorPluginConfig.objects.create(config_json=[])
        self.plugin_info = CollectorPluginInfo.objects.create()
        PluginVersionHistory.objects.create(
            config_version=1,
            info_version=1,
            config_id=self.plugin_config.id,
            info_id=self.plugin_info.id,
            stage="release",
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )

        self.installer = get_collect_installer(self.collect_config)

    def test_create(self):
        self._test_install()
        self._test_instance_status()
        self._test_retry()
        self._test_upgrade()
        self._test_rollback()
        self._test_stop()
        self._test_start()
        self._test_update_status()
        self._test_status()
        self._test_revoke()
        self._test_uninstall()

    def _test_install(self):
        self.assertEqual(self.installer.install(INSTALL_CONFIG, "CREATE"), INSTALL_RESULT)

    def _test_stop(self):
        self.installer.stop()
        self.assertEqual(self.collect_config.last_operation, "STOP")

    def _test_uninstall(self):
        self._test_stop()
        self.installer.uninstall()
        item = CollectConfigMeta.objects.filter(bk_tenant_id="system", plugin_id=PLUGIN_ID)
        self.assertFalse(item.exists())
        item = DeploymentConfigVersion.objects.filter()
        self.assertFalse(item.exists())

    def _test_start(self):
        self.installer.start()
        self.assertEqual(self.collect_config.last_operation, "START")

    @patch.object(CollectConfigMeta, "get_cache_data", return_value=1)
    def _test_upgrade(self, mock_get_cache_data):
        PluginVersionHistory.objects.create(
            config_version=2,
            info_version=2,
            config_id=self.plugin_config.id,
            info_id=self.plugin_info.id,
            stage="release",
            is_packaged=True,
            plugin_id=PLUGIN_ID,
            bk_tenant_id="system",
        )

        self.installer.upgrade({"collector": {}, "plugin": {}})
        self.assertEqual(self.collect_config.last_operation, "UPGRADE")

    def _test_rollback(self):
        self.installer.rollback()
        self.assertEqual(self.collect_config.last_operation, "ROLLBACK")

    def _test_retry(self):
        self.installer.retry()
        self.assertEqual(self.collect_config.operation_result, "PREPARING")

    @patch("core.drf_resource.api.node_man.revoke_subscription", return_value="")
    def _test_revoke(self, mock_subscription):
        self.installer.revoke(["host|instance|host|275"])
        self.assertTrue(mock_subscription.called)

    def _test_status(self):
        result = self.installer.status(diff=True)
        self.assertEqual(result[0]["child"][0]["action"], "install")

    @patch("core.drf_resource.api.node_man.task_result_detail", return_value={"steps": []})
    def _test_instance_status(self, mock_task_result_detail):
        self.installer.instance_status("1")
        self.assertTrue(mock_task_result_detail.called)

    @patch("core.drf_resource.api.node_man.batch_task_result", return_value=[])
    def _test_update_status(self, mock_batch_task_result):
        self.installer.update_status()
        self.assertTrue(mock_batch_task_result.called)
