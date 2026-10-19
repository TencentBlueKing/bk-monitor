"""Shared convergence and the actual Monitor deployment/command adapters, offline."""

import copy
import json
from contextlib import contextmanager
from dataclasses import replace
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.signals import post_migrate

from bkmonitor.iam import model_sync as monitor
from bkmonitor.iam.backends.config import provider_options
from iam_engine.core.config import AuthMode
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.mode import FeatureToggleModeProvider
from iam_engine.model.client import V4ModelClient
from iam_engine.model.convergence import ActualModel, V4ModelMigrator, build_plan
from iam_engine.model.definition import build_model_definition
from iam_engine.model.django import model_sync_lock
from iam_engine.model.sync import ModelSyncError, ModelSyncService
from iam_engine.v4.exceptions import V4ResponseError


@pytest.mark.parametrize("app_code", ["custom-saas", "bk_monitorv3", "bkci"])
def test_monitor_v4_inherits_complete_v3_clients_without_changing_v3(settings, app_code):
    settings.SAAS_APP_CODE = app_code
    legacy = provider_options("v3")["system"]["clients"]
    assert legacy == [app_code, "bk_monitorv3", "bkci", "bk_paas3", "paasv3cli"]
    assert monitor.expected_v4_model().system.clients == tuple(dict.fromkeys(legacy))


def test_monitor_clients_follow_current_saas_identity_and_return_fresh_lists(settings):
    settings.SAAS_APP_CODE = "first-saas"
    first = provider_options("v3")["system"]["clients"]
    assert monitor.expected_v4_model().system.clients[0] == "first-saas"
    first.append("caller-local-mutation")
    settings.SAAS_APP_CODE = "second-saas"
    expected = ("second-saas", "bk_monitorv3", "bkci", "bk_paas3", "paasv3cli")
    assert monitor.expected_v4_model().system.clients == expected
    assert provider_options("v3")["system"]["clients"] == list(expected)


def test_monitor_v4_model_does_not_construct_v3_options_or_providers(settings):
    settings.SAAS_APP_CODE = "model-saas"
    with (
        patch.object(monitor, "provider_options", side_effect=AssertionError("must not construct V3 options")),
        patch("bkmonitor.iam.backends.config.build_provider", side_effect=AssertionError("must not build a provider")),
    ):
        assert monitor.expected_v4_model().system.clients == (
            "model-saas",
            "bk_monitorv3",
            "bkci",
            "bk_paas3",
            "paasv3cli",
        )


@pytest.mark.parametrize("existing", [False, True])
def test_monitor_system_sync_sends_full_clients_and_preserves_remote_additions(settings, existing):
    settings.SAAS_APP_CODE = "model-saas"
    settings.BK_COMPONENT_API_URL = "https://components.example.test/"
    settings.BK_IAM_V4_APIGATEWAY_URL = ""
    model = replace(monitor.expected_v4_model(), resource_types=(), actions=(), roles=())
    actual = ActualModel()
    if existing:
        actual = ActualModel(
            system={
                "name": model.system.name,
                "description": model.system.description,
                "callback_url": model.system.callback_url,
                "clients": ["model-saas", "remote-extra"],
            }
        )
    plan = build_plan(model, actual)
    response = Mock(status_code=204 if existing else 201, content=b"" if existing else b"body")
    response.json.return_value = {"data": {"id": model.system.id}}
    with patch("iam_engine.v4.client.requests.request", return_value=response) as send:
        V4ModelMigrator(monitor.v4_migrator().client, model).apply(plan)
    send.assert_called_once()
    call = send.call_args.kwargs
    assert call["method"] == ("PUT" if existing else "POST")
    assert "/api/bkiam/" in call["url"]
    assert call["json"]["clients"] == [
        "model-saas",
        "bk_monitorv3",
        "bkci",
        "bk_paas3",
        "paasv3cli",
        *(["remote-extra"] if existing else []),
    ]
    if existing:
        remote = dict(actual.system, **plan.update_system)
        assert not build_plan(model, ActualModel(system=remote)).has_changes()


def test_monitor_model_entry_uses_shared_transport_and_materialized_saas_credentials(settings):
    settings.BK_COMPONENT_API_URL = "https://components.example.test/"
    settings.BK_IAM_V4_APIGATEWAY_URL = ""
    settings.SAAS_APP_CODE = "model-saas"
    settings.SAAS_SECRET_KEY = "offline-model-secret"
    settings.BK_IAM_V4_SYSTEM_ID = ""
    settings.BK_IAM_SYSTEM_ID = "bk_monitorv3"
    settings.BK_APP_TENANT_ID = "tenant-model"
    response = Mock(status_code=200, content=b"body")
    response.json.return_value = {"data": {"id": "bk_monitorv3"}}
    with patch("iam_engine.v4.client.requests.request", return_value=response) as send:
        assert monitor.v4_migrator().client.retrieve_system() == {"id": "bk_monitorv3"}
    call = send.call_args.kwargs
    assert call["url"] == "https://components.example.test/api/bkiam/prod/api/v1/open/rbac/model/systems/bk_monitorv3/"
    assert call["headers"]["X-Bk-Tenant-Id"] == "tenant-model"
    auth = json.loads(call["headers"]["X-Bkapi-Authorization"])
    assert (auth["bk_app_code"], auth["bk_app_secret"]) == ("model-saas", "offline-model-secret")


@pytest.mark.parametrize("method", ["list_resource_types", "list_actions", "list_roles"])
@pytest.mark.parametrize("count", [5, -1, True, "0"])
def test_model_client_rejects_incomplete_or_invalid_inventory(method, count):
    client = V4ModelClient(Mock(model_base_path="model/", system_id="monitor"))
    client._request = Mock(return_value={"count": count, "results": []})
    with pytest.raises(V4ResponseError):
        getattr(client, method)()
    client._request.assert_called_once()


def test_model_client_accepts_successful_empty_inventory():
    client = V4ModelClient(Mock(model_base_path="model/", system_id="monitor"))
    client._request = Mock(return_value={"count": 0, "results": []})
    assert client.list_actions() == []


def test_incomplete_remote_inventory_blocks_all_model_writes():
    client = V4ModelClient(Mock(model_base_path="model/", system_id="monitor"))
    client._request = Mock(side_effect=[{"id": "monitor"}, {"count": 1, "results": []}])
    with pytest.raises(V4ResponseError, match="ended before the declared count"):
        V4ModelMigrator(client, desired_model()).migrate(dry_run=False)
    assert all(call.args[0] == "GET" for call in client._request.call_args_list)


@pytest.mark.parametrize(
    "mode,targets", [(AuthMode.V3, ("v3",)), (AuthMode.V4, ("v4",)), (AuthMode.UNION, ("v3", "v4"))]
)
@pytest.mark.parametrize("apply", [False, True])
def test_sync_uses_one_snapshot_and_only_selected_factories(mode, targets, apply):
    selector = Mock(get_mode=Mock(side_effect=[mode, AuthMode.V3]))
    factories = {version: Mock(return_value=Mock()) for version in (AuthMode.V3, AuthMode.V4)}
    locked = []

    @contextmanager
    def lock():
        locked.append("acquired")
        yield
        locked.append("released")

    resolved, plans = ModelSyncService(selector, factories, lock_factory=lock).run(apply=apply)
    assert resolved is mode
    assert tuple(plans) == targets
    selector.get_mode.assert_called_once()
    assert locked == (["acquired", "released"] if apply else [])
    for version, factory in factories.items():
        assert factory.call_count == (version.value in targets)
        if version.value in targets:
            factory.return_value.migrate.assert_called_once_with(dry_run=not apply)


@pytest.mark.parametrize("mode", ["invalid", "primary", "all_of"])
def test_invalid_sync_mode_never_reads_remote_or_writes(mode):
    loader = Mock()
    selector = FeatureToggleModeProvider(loader, env_loader=lambda: mode, raise_on_load_error=True)
    factory = Mock()
    with pytest.raises(InvalidAuthModeError):
        ModelSyncService(selector, {AuthMode.V3: factory, AuthMode.V4: factory}).run(apply=True)
    factory.assert_not_called()
    loader.assert_not_called()


def test_selected_sync_failure_is_propagated_and_lock_is_released():
    events = []

    @contextmanager
    def lock():
        try:
            yield
        finally:
            events.append("released")

    migrator = Mock(migrate=Mock(side_effect=RuntimeError("offline failure")))
    with pytest.raises(ModelSyncError, match="IAM v4 model sync failed"):
        ModelSyncService(
            Mock(get_mode=Mock(return_value=AuthMode.V4)), {AuthMode.V4: lambda: migrator}, lock_factory=lock
        ).run(apply=True)
    assert events == ["released"]


def desired_model():
    return build_model_definition(
        {
            "version": 1,
            "system": {"name": "Monitor", "description": "model", "clients": ["monitor"]},
            "resource_types": [{"id": "space", "name": "Space", "ancestors": []}],
            "actions": [{"id": "view", "name": "View", "resource_type_id": "space"}],
            "roles": [
                {
                    "id": "viewer",
                    "name": "Viewer",
                    "description": "",
                    "actions": [{"id": "view", "resource_type_id": "space"}],
                }
            ],
        },
        system_id="monitor",
        callback_url="https://monitor.example.test/iam/v4/resource/",
    )


class StatefulModelClient:
    """Store successful writes even when a later stage fails, like a remote IAM."""

    def __init__(self):
        self.system = None
        self.resource_types, self.actions, self.roles = [], [], []
        self.writes = []
        self.fail_actions_once = True

    def retrieve_system(self):
        return copy.deepcopy(self.system)

    def list_resource_types(self):
        return copy.deepcopy(self.resource_types)

    def list_actions(self):
        return copy.deepcopy(self.actions)

    def list_roles(self):
        return copy.deepcopy(self.roles)

    def create_system(self, payload):
        assert self.system is None
        self.system = copy.deepcopy(payload)
        self.writes.append("system")

    def batch_create_resource_types(self, payload):
        self.resource_types.extend(copy.deepcopy(payload))
        self.writes.append("resource_types")

    def batch_create_actions(self, payload):
        if self.fail_actions_once:
            self.fail_actions_once = False
            raise RuntimeError("partial failure")
        self.actions.extend(copy.deepcopy(payload))
        self.writes.append("actions")

    def batch_create_roles(self, payload):
        self.roles.extend(copy.deepcopy(payload))
        self.writes.append("roles")


def test_partial_failure_rerun_converges_then_noop_preserves_unmanaged_objects():
    client = StatefulModelClient()
    migrator = V4ModelMigrator(client, desired_model())
    preview = migrator.migrate(dry_run=True)
    assert preview.has_changes() and client.writes == []
    with pytest.raises(RuntimeError, match="partial failure"):
        migrator.migrate(dry_run=False)
    assert client.writes == ["system", "resource_types"]
    migrator.migrate(dry_run=False)
    assert client.writes == ["system", "resource_types", "actions", "roles"]
    client.actions.append({"id": "unmanaged", "name": "Manual", "resource_type_id": "space"})
    plan = migrator.migrate(dry_run=False)
    assert not plan.has_changes()
    assert any("unmanaged" in item for item in plan.drift)
    assert len(client.actions) == 2
    assert client.writes == ["system", "resource_types", "actions", "roles"]


def test_role_dimension_change_is_blocked_without_deleting_authorized_bindings():
    model = desired_model()
    actual = ActualModel(
        system={
            "name": model.system.name,
            "description": model.system.description,
            "clients": list(model.system.clients),
            "callback_url": model.system.callback_url,
        },
        resource_types=({"id": "space", "name": "Space", "ancestors": []},),
        actions=({"id": "view", "name": "View", "resource_type_id": "space"},),
        roles=(
            {"id": "viewer", "name": "Viewer", "description": "", "actions": [{"id": "view", "resource_type_id": ""}]},
        ),
    )
    plan = build_plan(model, actual)
    assert plan.blocking
    client = Mock()
    with pytest.raises(RuntimeError):
        V4ModelMigrator(client, model).apply(plan)
    assert client.method_calls == []


@pytest.mark.parametrize("apply", [False, True])
def test_actual_monitor_command_calls_the_shared_service(apply):
    service = Mock()
    service.run.return_value = (AuthMode.V3, {"v3": monitor.LegacyModelPlan(())})
    output = StringIO()
    with patch("bkmonitor.iam.management.commands.iam_migrate_model.Command.get_service", return_value=service):
        call_command("iam_migrate_model", apply=apply, stdout=output)
    service.run.assert_called_once_with(apply=apply)
    assert ("nothing was written" if not apply else "completed") in output.getvalue()


def test_actual_monitor_command_and_deployment_propagate_failure(monkeypatch):
    service = Mock(run=Mock(side_effect=ModelSyncError("offline failure")))
    with patch("bkmonitor.iam.management.commands.iam_migrate_model.Command.get_service", return_value=service):
        with pytest.raises(CommandError, match="offline failure"):
            call_command("iam_migrate_model", apply=True)
    monkeypatch.setattr(monitor, "get_model_sync_service", lambda: service)
    monkeypatch.setattr(monitor.sys, "argv", ["manage.py", "migrate"])
    with pytest.raises(ModelSyncError):
        monitor.migrate_iam_models(using="default")


def test_deployment_hook_is_registered_for_original_app_and_ignores_other_commands(monkeypatch):
    receivers = post_migrate._live_receivers(apps.get_app_config("bkmonitor"))
    assert monitor.migrate_iam_models in receivers
    service = Mock()
    monkeypatch.setattr(monitor, "get_model_sync_service", lambda: service)
    monkeypatch.setattr(monitor.sys, "argv", ["manage.py", "check"])
    assert monitor.migrate_iam_models() is None
    monkeypatch.setattr(monitor.sys, "argv", ["manage.py", "migrate"])
    assert monitor.migrate_iam_models(using="monitor_api") is None
    service.run.assert_not_called()
    monitor.migrate_iam_models(using="default")
    service.run.assert_called_once_with(apply=True)


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("dry_run", [False, True])
def test_original_v3_records_are_not_replayed_and_preview_never_writes(settings, pending, dry_run):
    settings.SKIP_IAM_PERMISSION_CHECK = False
    settings.RUN_MODE = "PRODUCT"
    migrator = Mock(migrations={"0001_initial", "0016_correct_action_groups"})
    applied = ["0001_initial"] if pending else list(migrator.migrations)
    with (
        patch("bkmonitor.migrate.Migrator", return_value=migrator),
        patch("bkmonitor.models.config.MonitorMigration.objects.filter") as records,
    ):
        records.return_value.values_list.side_effect = [applied, list(migrator.migrations)]
        plan = monitor.LegacyModelMigrator().migrate(dry_run=dry_run)
    assert all(call.kwargs == {"app": "iam"} for call in records.call_args_list)
    assert bool(plan.pending) is pending
    assert migrator.migrate.call_count == (pending and not dry_run)


def test_v3_preview_graph_is_not_loaded_twice_and_missing_completion_fails(settings):
    settings.SKIP_IAM_PERMISSION_CHECK = False
    settings.RUN_MODE = "PRODUCT"
    preview = Mock(migrations={"0001_initial"})
    apply = Mock()
    with (
        patch("bkmonitor.migrate.Migrator", side_effect=[preview, apply]),
        patch("bkmonitor.models.config.MonitorMigration.objects.filter") as records,
    ):
        records.return_value.values_list.return_value = []
        with pytest.raises(ModelSyncError, match="did not record completion"):
            monitor.LegacyModelMigrator().migrate(dry_run=False)
    preview.load_migration.assert_called_once()
    preview.migrate.assert_not_called()
    apply.load_migration.assert_not_called()
    apply.migrate.assert_called_once()


def test_deployment_reads_authoritative_mode_and_does_not_mask_config_failure(settings, monkeypatch):
    from bkmonitor.iam.mode import get_deployment_mode_provider

    monkeypatch.delenv("BKAPP_IAM_PERMISSION_MODE", raising=False)
    settings.USE_DYNAMIC_SETTINGS = True
    settings.BK_IAM_PERMISSION_MODE = "v3"
    with patch("bkmonitor.models.GlobalConfig.get", return_value="v4") as config:
        assert get_deployment_mode_provider().get_mode() is AuthMode.V4
        config.assert_called_once_with("BK_IAM_PERMISSION_MODE", "v3", raise_exception=True)
    with patch("bkmonitor.models.GlobalConfig.get", side_effect=RuntimeError("config unreadable")):
        with pytest.raises(RuntimeError, match="config unreadable"):
            get_deployment_mode_provider().get_mode()
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "union")
    with patch("bkmonitor.models.GlobalConfig.get", side_effect=AssertionError("env must win")):
        assert get_deployment_mode_provider().get_mode() is AuthMode.UNION


@pytest.mark.parametrize("acquired", [0, 1])
def test_mysql_lock_rejects_competitors_and_releases_on_failure(acquired):
    cursor = Mock()
    cursor.fetchone.return_value = (acquired,)
    connection = Mock(vendor="mysql")
    connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
    connection.cursor.return_value.__exit__ = Mock(return_value=False)
    with patch("iam_engine.model.django.connections", {"default": connection}):
        with pytest.raises(ModelSyncError if not acquired else RuntimeError):
            with model_sync_lock("monitor:system:bk_monitorv3"):
                raise RuntimeError("failure after acquisition")
    assert cursor.execute.call_count == (2 if acquired else 1)
    assert cursor.execute.call_args_list[0].args[0].startswith("SELECT GET_LOCK")
    if acquired:
        assert cursor.execute.call_args_list[-1].args[0].startswith("SELECT RELEASE_LOCK")
