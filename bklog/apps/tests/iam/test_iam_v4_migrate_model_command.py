from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.exceptions import V4ResponseError, V4TransportError
from apps.iam.backends.v4.model_migrator import (
    is_auto_migration_enabled,
    migrate_v4_model_on_post_migrate,
)


def unregistered_system_client():
    """模拟一个还没注册过任何模型的权限中心。"""
    client = Mock()
    client.retrieve_system.return_value = None
    return client


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_APP_TENANT_ID="system",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_IAM_V4_SYSTEM_ID="bklog_test",
    BK_IAM_V4_APIGATEWAY_URL="https://bkiam.example/prod/",
    BK_IAM_RESOURCE_API_HOST="https://bklog.example/o/bk_log_search/",
    BK_IAM_V4_CALLBACK_URL="",
    BK_IAM_V4_MODEL_MANAGERS="",
)
class IamV4MigrateModelCommandTest(SimpleTestCase):
    def setUp(self):
        self.client = unregistered_system_client()
        patcher = patch("apps.iam.backends.v4.model_migrator.V4ModelClient")
        self.client_class = patcher.start()
        self.client_class.from_settings.return_value = self.client
        self.addCleanup(patcher.stop)

    def run_command(self, *args):
        stdout = StringIO()
        call_command("iam_v4_migrate_model", *args, stdout=stdout, stderr=StringIO())
        return stdout.getvalue()

    def test_dry_run_prints_plan_without_writing(self):
        output = self.run_command()

        self.assertIn("system: bklog_test (tenant=system)", output)
        self.assertIn("create system: 日志平台", output)
        self.assertIn("create resource_type: space", output)
        self.assertIn("dry-run", output)
        self.assertEqual([call[0] for call in self.client.method_calls], ["retrieve_system"])

    def test_dry_run_uses_settings_driven_callback_url(self):
        output = self.run_command()

        self.assertIn("dry-run", output)
        self.client_class.from_settings.assert_called_once_with(username="admin", bk_tenant_id="system")

    def test_apply_writes_the_plan(self):
        self.run_command("--apply")

        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            [
                "retrieve_system",
                "create_system",
                "batch_create_resource_types",
                "batch_create_actions",
                "batch_create_roles",
            ],
        )

    def test_apply_reports_nothing_to_do_when_converged(self):
        model_client = self.client
        model_client.retrieve_system.return_value = {
            "id": "bklog_test",
            "name": "日志平台",
            "clients": ["bk_log_search", "log-search-4", "bk_bklog", "paasv3cli", "bk_paas3"],
            "callback_url": "https://bklog.example/o/bk_log_search/api/v1/iam/v4/resource/",
        }
        # description 与基线一致时才算收敛，这里用实际基线内容回填。
        from apps.iam.backends.v4.model_definition import load_model_definition

        desired = load_model_definition()
        model_client.retrieve_system.return_value["description"] = desired.system.description
        model_client.list_resource_types.return_value = [
            {"id": item.id, "name": item.name, "ancestors": list(item.ancestors)} for item in desired.resource_types
        ]
        model_client.list_actions.return_value = [
            {"id": item.id, "name": item.name, "resource_type_id": item.resource_type_id} for item in desired.actions
        ]
        model_client.list_roles.return_value = [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "actions": [{"id": action.id, "resource_type_id": action.resource_type_id} for action in role.actions],
            }
            for role in desired.roles
        ]

        output = self.run_command("--apply")

        self.assertIn("already up to date", output)
        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            ["retrieve_system", "list_resource_types", "list_actions", "list_roles"],
        )

    def test_apply_refuses_blocking_plan(self):
        self.client.retrieve_system.return_value = {"id": "bklog_test"}
        self.client.list_resource_types.return_value = []
        self.client.list_actions.return_value = [
            {"id": "search_log", "name": "日志检索", "resource_type_id": "space"},
        ]
        self.client.list_roles.return_value = []

        with self.assertRaisesRegex(CommandError, "cannot be applied automatically"):
            self.run_command("--apply")

    def test_unknown_baseline_file_is_reported_as_command_error(self):
        with self.assertRaisesRegex(CommandError, "baseline is invalid"):
            self.run_command("--file", "9999_missing.json")

    def test_unreadable_current_model_is_reported_as_command_error(self):
        self.client.retrieve_system.side_effect = V4TransportError("gateway unreachable")

        with self.assertRaisesRegex(CommandError, "failed to read the current IAM V4 model"):
            self.run_command()

    def test_failed_write_is_reported_as_command_error(self):
        self.client.create_system.side_effect = V4ResponseError("unexpected status 500")

        with self.assertRaisesRegex(CommandError, "failed to apply the IAM V4 model plan"):
            self.run_command("--apply")

    def test_explicit_tenant_overrides_settings(self):
        output = self.run_command("--tenant", "tenant-1")

        self.assertIn("tenant=tenant-1", output)
        self.client_class.from_settings.assert_called_once_with(username="admin", bk_tenant_id="tenant-1")

    def test_drift_is_reported_but_not_deleted(self):
        self.client.retrieve_system.return_value = {"id": "bklog_test"}
        self.client.list_resource_types.return_value = [{"id": "cluster", "name": "集群", "ancestors": []}]
        self.client.list_actions.return_value = []
        self.client.list_roles.return_value = []

        output = self.run_command()

        self.assertIn("drift: resource_type cluster exists in IAM but not in the baseline", output)


@override_settings(
    APP_CODE="bk_log_search",
    BK_APP_TENANT_ID="system",
    BK_IAM_V4_APIGATEWAY_URL="https://bkiam.example/prod/",
)
class PostMigrateHookTest(SimpleTestCase):
    def setUp(self):
        patcher = patch("apps.iam.backends.v4.model_migrator.V4ModelMigrator.from_settings")
        self.from_settings = patcher.start()
        self.addCleanup(patcher.stop)

    def test_hook_is_skipped_outside_migrate(self):
        with patch("apps.iam.backends.v4.model_migrator.sys.argv", ["manage.py", "runserver"]):
            self.assertIsNone(migrate_v4_model_on_post_migrate())

        self.from_settings.assert_not_called()

    def test_hook_is_skipped_when_v4_gateway_is_not_configured(self):
        with patch("apps.iam.backends.v4.model_migrator.sys.argv", ["manage.py", "migrate"]):
            with self.settings(BK_IAM_V4_APIGATEWAY_URL=""):
                with self.assertLogs("iam.v4.model_migrator", level="INFO"):
                    self.assertIsNone(migrate_v4_model_on_post_migrate())

        self.from_settings.assert_not_called()

    def test_hook_applies_when_gateway_is_configured(self):
        with patch("apps.iam.backends.v4.model_migrator.sys.argv", ["manage.py", "migrate"]):
            migrate_v4_model_on_post_migrate()

        self.from_settings.assert_called_once_with(bk_tenant_id="system")
        self.from_settings.return_value.migrate.assert_called_once_with(dry_run=False)

    def test_hook_ignores_permission_mode(self):
        """v3 单栈也要收敛：创建者授权双写只看网关是否配置，与鉴权模式无关。"""

        for mode in ("", "v3", "v4", "union"):
            with self.subTest(mode=mode):
                self.from_settings.reset_mock()
                with patch("apps.iam.backends.v4.model_migrator.sys.argv", ["manage.py", "migrate"]):
                    with self.settings(BK_IAM_PERMISSION_MODE=mode):
                        migrate_v4_model_on_post_migrate()

                self.from_settings.return_value.migrate.assert_called_once_with(dry_run=False)

    def test_hook_never_breaks_migrate_on_failure(self):
        self.from_settings.side_effect = RuntimeError("iam is down")

        with patch("apps.iam.backends.v4.model_migrator.sys.argv", ["manage.py", "migrate"]):
            with self.assertLogs("iam.v4.model_migrator", level="ERROR") as logs:
                self.assertIsNone(migrate_v4_model_on_post_migrate())

        self.assertIn("iam_v4_migrate_model --apply", logs.output[0])

    def test_auto_migration_requires_only_the_gateway(self):
        self.assertTrue(is_auto_migration_enabled())

        with self.settings(BK_IAM_V4_APIGATEWAY_URL=""):
            self.assertFalse(is_auto_migration_enabled())
