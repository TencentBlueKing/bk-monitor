import os
import tempfile
from io import StringIO
from unittest.mock import patch

import yaml
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.log_databus.models import CollectorConfig

COMMAND_MODULE = "apps.log_databus.management.commands.sync_built_in_platform_collect"
BUILT_IN_DATA_ID = 1110001


class TestSyncBuiltInPlatformCollect(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "builtin_collect.yaml")
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"builtin_collect": [{"dataId": BUILT_IN_DATA_ID, "moduleName": "bk-log-search-saas"}]},
                f,
            )

        # 其他用例可能残留请求上下文，导致 save() 用请求用户覆盖 updated_by
        request_patcher = patch("apps.utils.local._local.request", None, create=True)
        request_patcher.start()
        self.addCleanup(request_patcher.stop)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _call_command(self, *args):
        with patch.dict(os.environ, {"BK_LOG_BUILTIN_COLLECT_CONFIG_PATH": self.config_path}):
            call_command("sync_built_in_platform_collect", *args, stdout=StringIO())

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch("apps.utils.local.BKLoginApi.batch_lookup_virtual_user")
    def test_skips_operator_lookup_without_config(self, mock_lookup):
        with patch.dict(os.environ, {"BK_LOG_BUILTIN_COLLECT_CONFIG_PATH": ""}):
            call_command("sync_built_in_platform_collect", stdout=StringIO())

        mock_lookup.assert_not_called()

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch("apps.utils.local.BKLoginApi.batch_lookup_virtual_user")
    def test_skips_operator_lookup_when_config_empty(self, mock_lookup):
        empty_config_path = os.path.join(self.temp_dir.name, "empty_builtin_collect.yaml")
        with open(empty_config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"builtin_collect": []}, f)

        with patch.dict(os.environ, {"BK_LOG_BUILTIN_COLLECT_CONFIG_PATH": empty_config_path}):
            call_command("sync_built_in_platform_collect", stdout=StringIO())

        mock_lookup.assert_not_called()
        self.assertFalse(CollectorConfig.objects.filter(bk_data_id=BUILT_IN_DATA_ID).exists())

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch(f"{COMMAND_MODULE}.Command.create_etl_handle_and_index_set")
    @patch(f"{COMMAND_MODULE}.TransferApi.create_data_id", return_value=BUILT_IN_DATA_ID)
    @patch("apps.utils.local.BKLoginApi.batch_lookup_virtual_user", return_value=[{"bk_username": "bk_admin_t1"}])
    def test_uses_default_tenant_admin_in_multi_tenant_mode(self, mock_lookup, mock_create_data_id, _mock_etl):
        self._call_command()

        collect_config = CollectorConfig.objects.get(bk_data_id=BUILT_IN_DATA_ID)
        self.assertEqual(collect_config.created_by, "bk_admin_t1")
        self.assertEqual(collect_config.updated_by, "bk_admin_t1")

        params = mock_create_data_id.call_args.args[0]
        self.assertEqual(params["bk_username"], "bk_admin_t1")
        self.assertEqual(params["operator"], "bk_admin_t1")
        self.assertEqual(mock_lookup.call_args.kwargs["bk_tenant_id"], settings.BK_APP_TENANT_ID)

    @override_settings(ENABLE_MULTI_TENANT_MODE=False)
    @patch(f"{COMMAND_MODULE}.Command.create_etl_handle_and_index_set")
    @patch(f"{COMMAND_MODULE}.TransferApi.create_data_id", return_value=BUILT_IN_DATA_ID)
    def test_keeps_admin_in_single_tenant_mode(self, mock_create_data_id, _mock_etl):
        self._call_command()

        collect_config = CollectorConfig.objects.get(bk_data_id=BUILT_IN_DATA_ID)
        self.assertEqual(collect_config.created_by, "admin")
        self.assertEqual(collect_config.updated_by, "admin")

        params = mock_create_data_id.call_args.args[0]
        self.assertEqual(params["bk_username"], "admin")
        self.assertEqual(params["operator"], "admin")
