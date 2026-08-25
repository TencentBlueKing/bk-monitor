"""清洗配置 MCP 下游权限与复用边界测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.iam import ActionEnum
from apps.iam.handlers.drf import InstanceActionPermission
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

    @patch("apps.log_databus.views.collector_views.EtlHandler.get_instance")
    def test_clean_config_view_reuses_existing_etl_update_or_create(self, mock_get_instance):
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
        handler.itsm_pre_hook.return_value = (request_data.copy(), True)
        handler.update_or_create.return_value = {"collector_config_id": 101}
        mock_get_instance.return_value = handler
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
        )
        self.assertEqual(response.data, {"collector_config_id": 101})
