"""在已有监控项数据上验证两种部署模式的加列与反向迁移。"""

from importlib import import_module

import pytest
from django.db import connections
from django.db.migrations.state import ModelState, ProjectState

from bkmonitor.models import ItemModel


@pytest.mark.django_db(databases="__all__", transaction=True)
@pytest.mark.parametrize(
    ("app_label", "database", "migration_module"),
    [
        ("bkmonitor", "monitor_api", "bkmonitor.migrations.0206_item_access_lookback_periods"),
        ("strategy", "default", "bk_monitor_base.domains.strategy.migrations.0004_item_access_lookback_periods"),
    ],
)
def test_access_lookback_migration_preserves_existing_rows(app_label, database, migration_module):
    """临时表执行真实迁移：旧记录默认 NULL，写入有效，反向迁移保留旧数据。"""
    model_state = ModelState.from_model(ItemModel)
    model_state.app_label = app_label
    model_state.options["db_table"] = "test_access_lookback_column_migration"
    model_state.fields.pop("access_lookback_periods")
    old_state = ProjectState()
    old_state.add_model(model_state)
    old_model = old_state.apps.get_model(app_label, "ItemModel")
    connection = connections[database]
    operation = import_module(migration_module).Migration.operations[0]
    new_state = old_state.clone()
    operation.state_forwards(app_label, new_state)
    new_model = new_state.apps.get_model(app_label, "ItemModel")

    with connection.schema_editor() as editor:
        editor.create_model(old_model)
    try:
        old_row = old_model.objects.using(database).create(strategy_id=1, name="existing", meta={"owner": "monitor"})
        with connection.schema_editor() as editor:
            operation.database_forwards(app_label, editor, old_state, new_state)
        row = new_model.objects.using(database).get(pk=old_row.pk)
        assert row.access_lookback_periods is None
        assert row.meta == {"owner": "monitor"}
        row.access_lookback_periods = 15
        row.save(using=database, update_fields=["access_lookback_periods"])
        row.refresh_from_db(using=database)
        assert row.access_lookback_periods == 15
        with connection.schema_editor() as editor:
            operation.database_backwards(app_label, editor, new_state, old_state)
        restored = old_model.objects.using(database).get(pk=old_row.pk)
        assert restored.name == "existing"
        assert restored.meta == {"owner": "monitor"}
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, old_model._meta.db_table)
        assert "access_lookback_periods" not in {column.name for column in columns}
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(old_model)
