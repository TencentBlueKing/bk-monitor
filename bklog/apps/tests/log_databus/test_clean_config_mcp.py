"""清洗配置 MCP 下游权限与复用边界测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.iam import ActionEnum
from apps.iam.handlers.drf import InstanceActionPermission
from apps.log_databus.handlers.itsm import ItsmHandler
from apps.log_databus.views.collector_views import CollectorViewSet


class CleanConfigMcpPermissionTests(SimpleTestCase):
    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__trusted_app__"},
    )
    @patch("apps.log_databus.views.collector_views.settings.ESQUERY_WHITE_LIST", ["__trusted_app__"])
    def test_clean_config_can_force_manage_permission_for_whitelisted_app(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "update_or_create_clean_config"
        view.request = SimpleNamespace(query_params={}, data={"enforce_permission": True})

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__trusted_app__"},
    )
    @patch("apps.log_databus.views.collector_views.settings.ESQUERY_WHITE_LIST", ["__trusted_app__"])
    def test_clean_config_requires_manage_permission_even_without_force_flag(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "update_or_create_clean_config"
        view.request = SimpleNamespace(query_params={}, data={})

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])

    @patch("apps.log_databus.views.collector_views.CollectorHandler.sync_scene_tags_to_index_set")
    @patch("apps.log_databus.views.collector_views.CollectorHandler.get_instance")
    @patch("apps.log_databus.views.collector_views.EtlHandler.get_instance")
    def test_clean_config_forwards_and_syncs_scene_labels(
        self, mock_get_instance, mock_collector_handler, mock_sync_scene_tags
    ):
        request_data = {
            "table_id": "app_log",
            "etl_config": "bk_log_text",
            "etl_params": {"retain_original_text": False},
            "fields": [],
            "storage_cluster_id": 501,
            "retention": 7,
            "allocation_min_days": 0,
            "storage_replies": 0,
            "es_shards": 1,
            "need_assessment": False,
        }
        handler = MagicMock()
        handler.itsm_pre_hook.side_effect = lambda data, _: (data, True)
        handler.update_or_create.return_value = {"collector_config_id": 101, "index_set_id": 202}
        mock_get_instance.return_value = handler
        collector_handler = MagicMock()
        collector_handler.build_scene_labels.return_value = {"scene": "host"}
        mock_collector_handler.return_value = collector_handler
        view = CollectorViewSet()
        view.params_valid = MagicMock(return_value=request_data.copy())

        response = view.update_or_create_clean_config(SimpleNamespace(), collector_config_id=101)

        handler.update_or_create.assert_called_once_with(
            table_id="app_log",
            etl_config="bk_log_text",
            etl_params={"retain_original_text": False},
            fields=[],
            storage_cluster_id=501,
            retention=7,
            allocation_min_days=0,
            storage_replies=0,
            es_shards=1,
            labels={"scene": "host"},
        )
        mock_sync_scene_tags.assert_called_once_with(202, {"scene": "host"})
        self.assertEqual(response.data, {"collector_config_id": 101, "index_set_id": 202})

    @patch("apps.log_databus.handlers.collector.base.CollectorHandler.sync_scene_tags_to_index_set")
    @patch("apps.log_databus.handlers.collector.base.CollectorHandler.get_instance")
    @patch("apps.log_databus.handlers.etl.EtlHandler.get_instance")
    @patch("apps.log_databus.handlers.itsm.ItsmEtlConfig.objects.filter")
    def test_approved_itsm_task_syncs_current_scene_labels(
        self,
        mock_filter,
        mock_get_etl_handler,
        mock_get_collector_handler,
        mock_sync_scene_tags,
    ):
        itsm_config = MagicMock(
            request_param={
                "need_assessment": False,
                "assessment_config": {},
            }
        )
        mock_filter.return_value.first.return_value = itsm_config
        etl_handler = MagicMock()
        etl_handler.data.index_set_id = 101
        etl_handler.update_or_create.return_value = {"index_set_id": 202}
        mock_get_etl_handler.return_value = etl_handler
        collector_handler = MagicMock()
        collector_handler.build_scene_labels.return_value = {"scene": "k8s", "stream": "stdout"}
        mock_get_collector_handler.return_value = collector_handler

        ItsmHandler()._create_task(collect_id=1, sn="ticket-sn")

        etl_handler.update_or_create.assert_called_once_with(labels={"scene": "k8s", "stream": "stdout"})
        mock_sync_scene_tags.assert_called_once_with(202, {"scene": "k8s", "stream": "stdout"})
