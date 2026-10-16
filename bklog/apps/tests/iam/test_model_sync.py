"""BKLog's actual mode/command/deployment adapters, without IAM writes."""

import sys
from io import StringIO
from unittest.mock import Mock, patch

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.signals import post_migrate
from django.test import SimpleTestCase, TestCase, override_settings
from iam import Resource

from apps.iam import model_sync
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.mode import get_deployment_mode_provider, get_mode_provider
from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from iam_engine.core.config import AuthMode
from iam_engine.core.types import AuthResult
from iam_engine.model.sync import ModelSyncError
from iam_engine.provider.bundle import LazyProviderBundles, ProviderBundle
from iam_engine.provider.router import ModeRouter
from apps.iam.concurrency import run_pair_concurrently


@override_settings(BK_IAM_SYSTEM_ID="bk_log_search", BK_APP_TENANT_ID="system")
class ModeCapabilityIsolationTest(SimpleTestCase):
    def test_dynamic_mode_changes_auth_and_grants_without_rebuilding_permission(self):
        for mode, targets in (
            (AuthMode.V3, (AuthMode.V3,)),
            (AuthMode.V4, (AuthMode.V4,)),
            (AuthMode.UNION, (AuthMode.V3, AuthMode.V4)),
        ):
            with self.subTest(mode=mode):
                selector = Mock(get_mode=Mock(return_value=mode))
                providers = {version: Mock() for version in (AuthMode.V3, AuthMode.V4)}
                writers = {version: Mock() for version in providers}
                for version, provider in providers.items():
                    provider.is_allowed.return_value = AuthResult.allow(version.value)
                factories = {
                    version: Mock(return_value=ProviderBundle(auth=provider, writer=writers[version]))
                    for version, provider in providers.items()
                }
                with (
                    patch.object(Permission, "get_iam_client", return_value=Mock()),
                    patch("apps.iam.handlers.permission.get_mode_provider", return_value=selector),
                ):
                    permission = Permission(username="alice", bk_tenant_id="system")
                permission._provider_bundles = LazyProviderBundles(factories)
                permission._mode_router = ModeRouter(
                    selector, permission._provider_bundles, pair_executor=run_pair_concurrently
                )
                assert permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE)
                permission.grant_creator_action(Resource("bk_log_search", "collection", "1", {}), raise_exception=True)
                assert selector.get_mode.call_count == 2
                for version in providers:
                    assert factories[version].call_count == (version in targets)
                    assert providers[version].is_allowed.call_count == (version in targets)
                    writer = writers[version]
                    method = writer.grant_resource_creator_actions
                    assert method.call_count == (version in targets)
                selector.get_mode.return_value = AuthMode.V4 if mode is AuthMode.V3 else AuthMode.V3
                assert permission.is_allowed(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE)
                assert selector.get_mode.call_count == 3


class ModelSyncCommandTest(SimpleTestCase):
    @override_settings(
        APP_CODE="bklog",
        SECRET_KEY="offline-only",
        BK_IAM_SYSTEM_ID="bk_log_search",
        BK_COMPONENT_API_URL="https://components.example.test/",
    )
    def test_both_clients_use_resolved_actual_request_urls(self):
        from apps.iam.backends.v3.client import build_v3_client
        from apps.iam.backends.v4.model_client import V4ModelClient

        for v3_url, v4_url in (
            ("", ""),
            ("  ", "  "),
            ("https://v3.example.test/dev", "https://v4.example.test/stage/"),
        ):
            with (
                self.subTest(v3_url=v3_url, v4_url=v4_url),
                override_settings(
                    BK_IAM_APIGATEWAY_URL=v3_url,
                    BK_IAM_V4_APIGATEWAY_URL=v4_url,
                ),
            ):
                with patch("iam.api.client.http_post", return_value=(True, "", {"code": 0, "data": {}})) as post:
                    build_v3_client("system")._client.policy_query({})
                expected_v3 = v3_url or "https://components.example.test/api/bk-iam/prod/"
                if not expected_v3.strip():
                    expected_v3 = "https://components.example.test/api/bk-iam/prod/"
                assert post.call_args.args[0] == expected_v3.strip().rstrip("/") + "/api/v1/policy/query"
                response = Mock(status_code=200, content=b"json")
                response.json.return_value = {"data": {"id": "bk_log_search"}}
                with patch("requests.request", return_value=response) as send:
                    V4ModelClient.from_settings(username="alice", bk_tenant_id="system").retrieve_system()
                expected_v4 = v4_url.strip() or "https://components.example.test/api/bkiam/prod/"
                assert (
                    send.call_args.kwargs["url"]
                    == expected_v4.rstrip("/") + "/api/v1/open/rbac/model/systems/bk_log_search/"
                )

    def test_manual_preview_and_apply_use_the_same_service(self):
        for apply in (False, True):
            with self.subTest(apply=apply):
                service = Mock()
                service.run.return_value = (AuthMode.V3, {"v3": model_sync.LegacyModelPlan(("initial.json",))})
                output = StringIO()
                with patch("apps.iam.management.commands.iam_migrate_model.Command.get_service", return_value=service):
                    call_command("iam_migrate_model", apply=apply, stdout=output)
                service.run.assert_called_once_with(apply=apply)
                assert ("completed" if apply else "nothing was written") in output.getvalue()

    def test_failed_sync_is_a_command_error_and_deployment_error(self):
        service = Mock(run=Mock(side_effect=ModelSyncError("offline failure")))
        with patch("apps.iam.management.commands.iam_migrate_model.Command.get_service", return_value=service):
            with self.assertRaises(CommandError):
                call_command("iam_migrate_model", apply=True)
        with (
            patch.object(sys, "argv", ["manage.py", "migrate"]),
            patch.object(model_sync, "get_model_sync_service", return_value=service),
        ):
            with self.assertRaises(ModelSyncError):
                model_sync.migrate_iam_models(using="default")

    def test_registered_hook_ignores_other_commands_and_databases(self):
        assert model_sync.migrate_iam_models in post_migrate._live_receivers(apps.get_app_config("log_search"))
        with patch.object(model_sync, "get_model_sync_service") as service:
            with patch.object(sys, "argv", ["manage.py", "check"]):
                assert model_sync.migrate_iam_models() is None
            with patch.object(sys, "argv", ["manage.py", "migrate"]):
                assert model_sync.migrate_iam_models(using="secondary") is None
                service.assert_not_called()
                model_sync.migrate_iam_models(using="default")
            service.return_value.run.assert_called_once_with(apply=True)

    def test_v3_preview_does_not_call_write_migrator_or_query_policies(self):
        with patch.object(model_sync, "IAMMigrator") as migrator, patch.object(Permission, "get_iam_client") as client:
            plan = model_sync.LegacyModelMigrator().migrate(dry_run=True)
        migrator.assert_not_called()
        client.assert_not_called()
        assert "not a remote diff" in plan.describe()

    def test_v3_apply_retains_sdk_flow_and_restores_command_guard(self):
        with (
            patch.object(sys, "argv", ["manage.py", "iam_migrate_model", "--apply"]),
            patch.object(model_sync, "IAMMigrator") as migrator,
            patch.object(Permission, "get_iam_client") as client,
        ):
            client.return_value.in_compatibility_mode.return_value = False
            migrator.return_value.migrate.side_effect = lambda: self.assertIn("migrate", sys.argv)
            model_sync.LegacyModelMigrator().migrate(dry_run=False)
            assert "migrate" not in sys.argv
        migrator.assert_called_once_with("initial.json")
        migrator.return_value.migrate.assert_called_once()


@override_settings(BK_IAM_PERMISSION_MODE="", FEATURE_TOGGLE={})
class DeploymentModeTest(TestCase):
    def test_runtime_and_deployment_read_same_dynamic_toggle(self):
        initial_toggle, _ = FeatureToggle.objects.get_or_create(
            name=IAM_PERMISSION_MODE, defaults={"status": "on", "feature_config": {"mode": "v3"}}
        )
        toggle, _ = FeatureToggle.objects.update_or_create(
            name=IAM_PERMISSION_MODE, defaults={"status": "on", "feature_config": {"mode": "union"}}
        )
        self.assertEqual(toggle.pk, initial_toggle.pk)
        self.assertEqual(FeatureToggle.objects.filter(name=IAM_PERMISSION_MODE).count(), 1)
        assert get_deployment_mode_provider().get_mode() is AuthMode.UNION
        assert get_mode_provider().get_mode() is AuthMode.UNION
        toggle.feature_config = {"mode": "v4"}
        toggle.save()
        assert get_deployment_mode_provider().get_mode() is AuthMode.V4
        assert get_mode_provider().get_mode() is AuthMode.V4

    def test_deployment_does_not_mask_database_failure_or_override_env(self):
        with patch.object(FeatureToggle.objects, "filter", side_effect=RuntimeError("config unreadable")):
            with self.assertRaisesRegex(RuntimeError, "config unreadable"):
                get_deployment_mode_provider().get_mode()
            with override_settings(BK_IAM_PERMISSION_MODE="v4"):
                assert get_deployment_mode_provider().get_mode() is AuthMode.V4
