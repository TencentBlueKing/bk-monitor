"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from importlib import import_module
from unittest.mock import MagicMock

from django.apps import apps
from django.core.management.sql import emit_post_migrate_signal
from django.dispatch import Signal
from django.test import override_settings

from bkmonitor.iam.apps import IAMConfig


def test_semi_auto_migration_uses_model_bearing_sender_and_runs_once(monkeypatch):
    post_migrate = Signal()
    monkeypatch.setattr("django.db.models.signals.post_migrate", post_migrate)

    app_config = IAMConfig(
        "bkmonitor.iam",
        import_module("bkmonitor.iam"),
    )
    app_config._migration_done = False
    app_config._do_auto_migration = MagicMock()

    migration_config = {
        "mode": "semi_auto",
        "database": "default",
    }

    with override_settings(IAM_MODEL_MIGRATION=migration_config):
        app_config._maybe_auto_migrate()

    legacy_sender = apps.get_app_config("bkmonitor")
    assert legacy_sender.models_module is not None

    emit_post_migrate_signal(verbosity=0, interactive=False, db="monitor_api")
    app_config._do_auto_migration.assert_not_called()

    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")
    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")

    app_config._do_auto_migration.assert_called_once_with(migration_config)


def test_django_does_not_load_product_iam_model_files_as_database_migrations():
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(None, load=False)
    loader.load_disk()
    assert "bkmonitor_iam" in loader.unmigrated_apps
    assert not any(app == "bkmonitor_iam" for app, name in loader.disk_migrations)


def test_model_snapshot_command_uses_product_configuration_without_framework():
    from io import StringIO
    from pathlib import Path

    from django.core.management import call_command

    output = StringIO()
    directory = Path(__file__).resolve().parents[2] / "bkmonitor/iam/iam_migrations"
    with override_settings(IAM_MODEL_MIGRATION={"directory": str(directory)}):
        call_command("iam_engine_makemigrations", name="offline", dry_run=True, stdout=output)
    assert "No changes detected" in output.getvalue()


def test_model_registration_command_uses_permission_and_read_only_recorder(monkeypatch, tmp_path):
    from io import StringIO

    from django.core.management import call_command

    from bkmonitor.iam.permission import Permission
    from iam_engine.schema.diff import MigrationPlan, MigrationReport

    permission = Permission(username="offline", bk_tenant_id="system")
    provider = MagicMock(name="offline-provider")
    provider.name = "v4"
    provider.plan_migration.return_value = MigrationPlan(provider_name="v4", changes=[])
    provider.apply_migration.return_value = MigrationReport(provider_name="v4")
    permission._providers = {"v4": provider}
    recorder = MagicMock()
    recorder.return_value.get_applied.return_value = []
    module = "bkmonitor.iam.management.commands.iam_engine_migrate"
    monkeypatch.setattr(module + ".Permission", lambda **kwargs: permission)
    monkeypatch.setattr(module + ".DjangoMigrationRecorder", recorder)
    with override_settings(IAM_MODEL_MIGRATION={"directory": str(tmp_path)}):
        call_command("iam_engine_migrate", provider="v4", dry_run=True, stdout=StringIO())
    recorder.assert_called_once_with(database="default", table_name="iam_migration_state", read_only=True)
    provider.plan_migration.assert_called_once_with(permission.schema, scope="system")
    provider.apply_migration.assert_called_once_with(
        provider.plan_migration.return_value, dry_run=True, allow_destructive=False
    )
    recorder.return_value.record.assert_not_called()
    recorder.return_value.lock.assert_not_called()
