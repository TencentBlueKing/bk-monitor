"""增量版本字段迁移保留存量表身份。"""

from importlib import import_module

import pytest
from django.db import connections, models
from django.db.migrations.state import ModelState, ProjectState

from metadata import config
from metadata.models import DorisStorage


@pytest.mark.django_db(transaction=True, databases="__all__")
def test_version_migration_defaults_and_rollback():
    migration = import_module("metadata.migrations.0283_dorisstorage_table_version").Migration
    before = ProjectState()
    before.add_model(
        ModelState(
            "metadata",
            "DorisStorage",
            [
                ("id", models.AutoField(primary_key=True)),
                ("table_id", models.CharField(max_length=128)),
            ],
            options={"db_table": "test_doris_version_migration"},
        )
    )
    after = before.clone()
    operation = migration.operations[0]
    operation.state_forwards("metadata", after)
    old_model = before.apps.get_model("metadata", "DorisStorage")
    new_model = after.apps.get_model("metadata", "DorisStorage")
    assert (
        new_model._meta.get_field("table_version").deconstruct()[1:]
        == DorisStorage._meta.get_field("table_version").deconstruct()[1:]
    )
    connection = connections[config.DATABASE_CONNECTION_NAME]
    with connection.schema_editor() as editor:
        editor.create_model(old_model)
    try:
        row = old_model.objects.using(connection.alias).create(table_id="legacy")
        with connection.schema_editor() as editor:
            operation.database_forwards("metadata", editor, before, after)
        updated = new_model.objects.using(connection.alias).get(pk=row.pk)
        assert updated.table_version == 0
        updated.table_version = 2
        updated.save(using=connection.alias)
        with connection.schema_editor() as editor:
            operation.database_backwards("metadata", editor, after, before)
        assert old_model.objects.using(connection.alias).get(pk=row.pk).table_id == "legacy"
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(old_model)
