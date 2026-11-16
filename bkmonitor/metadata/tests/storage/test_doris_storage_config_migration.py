"""新增 Doris 配置字段后，滚动升级中的旧进程仍能创建存储记录。"""

from importlib import import_module

import pytest
from django.db import connections
from django.db.migrations.state import ModelState, ProjectState

from metadata import config, models


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_old_writer_after_doris_config_migration():
    # 独立表上执行实际 AddField，避免改变测试库中的业务表及迁移状态。
    state = ProjectState()
    model_state = ModelState.from_model(models.DorisStorage)
    model_state.options["db_table"] = "test_doris_storage_rolling_upgrade"
    state.add_model(model_state)
    state.remove_field("metadata", "dorisstorage", "doris_storage_config")
    old_model = state.apps.get_model("metadata", "DorisStorage")
    connection = connections[config.DATABASE_CONNECTION_NAME]
    operation = import_module("metadata.migrations.0285_doris_storage_config").Migration.operations[0]
    new_state = state.clone()
    operation.state_forwards("metadata", new_state)
    new_model = new_state.apps.get_model("metadata", "DorisStorage")

    with connection.schema_editor() as editor:
        editor.create_model(old_model)
    try:
        old_model.objects.using(connection.alias).create(table_id="before_migration", storage_cluster_id=1)
        with connection.schema_editor() as editor:
            operation.database_forwards("metadata", editor, state, new_state)
        # 旧 ORM 不知道新列，不应因数据库非空约束而写入失败。
        old_model.objects.using(connection.alias).create(table_id="old_writer_after_migration", storage_cluster_id=1)
        rows = new_model.objects.using(connection.alias)
        assert rows.get(table_id="before_migration").doris_storage_config == {}
        assert rows.get(table_id="old_writer_after_migration").doris_storage_config is None
        assert rows.create(table_id="new_writer", storage_cluster_id=1).doris_storage_config == {}
        assert rows.count() == 3
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(new_model)
