"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import contextmanager

import pytest
from django.db import connections
from django.test import override_settings

from bkmonitor.iam.iam_engine.django.migration_recorder import DjangoMigrationRecorder


class TestDjangoMigrationRecorder:
    table_name = "iam_engine_recorder_test"

    def test_configurable_table_records_migrations_idempotently(self, django_db_blocker):
        """使用独立 SQLite alias 验证后端无关的建表、记录和锁行为。"""
        alias = "iam_recorder_sqlite"
        database_config = dict(connections.databases["default"])
        database_config.update({"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"})
        database_config["TEST"] = dict(database_config.get("TEST", {}))
        connections.databases[alias] = database_config

        with django_db_blocker.unblock():
            recorder = DjangoMigrationRecorder(database=alias, table_name=self.table_name)

            recorder.record("v4", "0001_initial", changes_count=2)
            recorder.record("v4", "0001_initial", changes_count=99)
            with recorder.lock("test_migration"):
                recorder.record("v4", "0002_add_document", changes_count=1)

            assert recorder.get_applied("v4") == ["0001_initial", "0002_add_document"]
            records = recorder._state_model.objects.using(alias).filter(provider="v4")
            assert records.count() == 2
            assert records.get(migration="0001_initial").changes_count == 2

    def test_read_only_recorder_does_not_create_state_or_lock_tables(self, django_db_blocker):
        alias = "iam_recorder_read_only_sqlite"
        table_name = "iam_engine_recorder_read_only_test"
        database_config = dict(connections.databases["default"])
        database_config.update({"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"})
        database_config["TEST"] = dict(database_config.get("TEST", {}))
        connections.databases[alias] = database_config

        with django_db_blocker.unblock():
            recorder = DjangoMigrationRecorder(database=alias, table_name=table_name, read_only=True)

            assert recorder.get_applied("v4") == []
            table_names = connections[alias].introspection.table_names()
            assert table_name not in table_names
            assert f"{table_name}_lock" not in table_names

            with pytest.raises(RuntimeError, match="read-only"):
                recorder.record("v4", "0001_initial", changes_count=1)
            with pytest.raises(RuntimeError, match="read-only"):
                with recorder.lock():
                    pass

    def test_read_only_recorder_reads_existing_state_without_creating_lock_table(self, django_db_blocker):
        alias = "iam_recorder_existing_state_sqlite"
        table_name = "iam_engine_recorder_existing_state_test"
        database_config = dict(connections.databases["default"])
        database_config.update({"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"})
        database_config["TEST"] = dict(database_config.get("TEST", {}))
        connections.databases[alias] = database_config

        with django_db_blocker.unblock():
            writable_recorder = DjangoMigrationRecorder(database=alias, table_name=table_name)
            writable_recorder.record("v4", "0001_initial", changes_count=1)

            recorder = DjangoMigrationRecorder(database=alias, table_name=table_name, read_only=True)
            assert recorder.get_applied("v4") == ["0001_initial"]

            table_names = connections[alias].introspection.table_names()
            assert table_name in table_names
            assert f"{table_name}_lock" not in table_names

    def test_rejects_invalid_table_name(self):
        with pytest.raises(ValueError, match="table_name"):
            DjangoMigrationRecorder(table_name="invalid-name")

    def test_migration_command_uses_configured_recorder_lock(self, monkeypatch):
        from bkmonitor.iam.iam_engine.django.management.commands import iam_engine_migrate

        events = []

        class Recorder:
            def __init__(self, *, database, table_name, read_only):
                events.append(("init", database, table_name, read_only))

            @contextmanager
            def lock(self, name):
                events.append(("enter", name))
                yield
                events.append(("exit", name))

        class Provider:
            name = "fake"

        class Framework:
            schema = object()
            providers = {"fake": Provider()}

        monkeypatch.setattr(iam_engine_migrate, "DjangoMigrationRecorder", Recorder)
        monkeypatch.setattr(iam_engine_migrate, "get_framework", lambda: Framework())

        with override_settings(
            IAM_FRAMEWORK={
                "MIGRATION": {
                    "database": "iam_history",
                    "table_name": "project_iam_history",
                }
            }
        ):
            iam_engine_migrate.Command().handle(
                provider=None,
                dry_run=False,
                skip_system=True,
                allow_destructive=False,
                directory=None,
            )

        assert events == [
            ("init", "iam_history", "project_iam_history", False),
            ("enter", "iam_engine_migrate"),
            ("exit", "iam_engine_migrate"),
        ]

    def test_migration_command_uses_read_only_recorder_for_dry_run(self, monkeypatch):
        from bkmonitor.iam.iam_engine.django.management.commands import iam_engine_migrate

        events = []

        class Recorder:
            def __init__(self, *, database, table_name, read_only):
                events.append(("init", database, table_name, read_only))

            def lock(self, name):
                raise AssertionError(f"dry-run must not acquire lock {name!r}")

        class Provider:
            name = "fake"

        class Framework:
            schema = object()
            providers = {"fake": Provider()}

        monkeypatch.setattr(iam_engine_migrate, "DjangoMigrationRecorder", Recorder)
        monkeypatch.setattr(iam_engine_migrate, "get_framework", lambda: Framework())

        with override_settings(
            IAM_FRAMEWORK={
                "MIGRATION": {
                    "database": "iam_history",
                    "table_name": "project_iam_history",
                }
            }
        ):
            iam_engine_migrate.Command().handle(
                provider=None,
                dry_run=True,
                skip_system=True,
                allow_destructive=False,
                directory=None,
            )

        assert events == [("init", "iam_history", "project_iam_history", True)]
