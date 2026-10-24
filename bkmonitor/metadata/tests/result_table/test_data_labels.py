import importlib
import json

import pytest
from django.db import connections
from django.db.migrations.state import ModelState, ProjectState

from metadata import config, models
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources.resources import GetDataLabelsMapResource, IsDataLabelExistResource
from metadata.service.vm_short_link import _get_result_table_data_label, _update_result_table_data_label

pytestmark = pytest.mark.django_db(databases="__all__")


def make_table(table_id="plugin.__default__", **kwargs):
    return models.ResultTable.objects.create(
        table_id=table_id, bk_tenant_id="labels_test", bk_biz_id=2, is_custom_table=False, **kwargs
    )


def test_legacy_create_populates_array():
    table = make_table(data_label="plugin,plugin.group1")
    table.refresh_from_db()
    assert table.data_labels == ["plugin", "plugin.group1"]
    assert table.data_label == "plugin,plugin.group1"


@pytest.mark.parametrize("length", [127, 128, 129, 304])
def test_array_write_preserves_legacy_value_on_overflow(length):
    table = make_table(data_label="previous")
    table.data_labels = ["a" * length]
    table.save(update_fields=["data_labels"])
    table.refresh_from_db()
    assert table.data_labels == ["a" * length]
    assert table.data_label == ("a" * length if length <= 128 else "previous")


def test_full_save_and_later_short_value():
    table = make_table(data_label="previous")
    table.data_labels = [f"plugin.group{i}" for i in range(30)]
    expected = table.data_labels
    table.save()
    table.refresh_from_db()
    assert table.data_labels == expected
    assert table.data_label == "previous"
    table.data_labels = ["new", "alias"]
    table.save(update_fields=["data_labels"])
    table.refresh_from_db()
    assert table.data_label == "new,alias"


def test_new_long_value_and_explicit_clear():
    table = make_table(data_labels=["a" * 200])
    table.refresh_from_db()
    assert table.data_label == ""
    assert table.data_labels == ["a" * 200]
    table.data_labels = []
    table.save(update_fields=["data_labels"])
    table.refresh_from_db()
    assert table.data_label == ""
    assert table.data_labels == []


def test_legacy_partial_save_synchronizes_array():
    table = make_table(data_label="previous")
    table.data_label = "new,alias"
    table.save(update_fields=["data_label"])
    table.refresh_from_db()
    assert table.data_labels == ["new", "alias"]


def test_unrelated_update_does_not_resurrect_legacy_label():
    table = make_table(data_label="stale")
    models.ResultTable.objects.filter(pk=table.pk).update(data_labels=[])
    table.refresh_from_db()
    table.table_name_zh = "renamed"
    table.save(update_fields=["table_name_zh"])
    table.refresh_from_db()
    assert table.data_labels == []
    assert table.data_label == "stale"


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_router_uses_arrays_exactly_and_keeps_tenant_isolation(mocker, settings, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    table = make_table(data_labels=["new", *[f"plugin.group{i}" for i in range(20)]])
    models.ResultTable.objects.filter(pk=table.pk).update(data_label="stale")
    make_table("plugin.other", data_labels=["new_longer"])
    models.ResultTable.objects.create(
        table_id="foreign.table", bk_tenant_id="other", is_custom_table=False, data_labels=["new"]
    )
    write = mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis")
    publish = mocker.patch("metadata.utils.redis_tools.RedisTools.publish")
    SpaceTableIDRedis().push_data_label_table_ids(
        bk_tenant_id="labels_test", data_label_list=["new", "plugin.group19", "stale"], is_publish=True
    )
    key, payload = write.call_args.args
    assert key == DATA_LABEL_TO_RESULT_TABLE_KEY
    suffix = "|labels_test" if multi_tenant else ""
    assert {name: json.loads(value) for name, value in payload.items()} == {
        f"new{suffix}": [table.table_id],
        f"plugin.group19{suffix}": [table.table_id],
        f"stale{suffix}": [],
    }
    assert publish.called


def test_router_refreshes_removed_alias_with_empty_route(mocker):
    table = make_table(data_labels=["new"])
    write = mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis")
    SpaceTableIDRedis().push_data_label_table_ids(bk_tenant_id="labels_test", data_label_list=["removed"])
    assert json.loads(next(iter(write.call_args.args[1].values()))) == []
    assert table.data_labels == ["new"]


def test_label_lookup_and_map_use_new_array_only():
    table = make_table(data_labels=["primary", "legacy.group1"])
    models.ResultTable.objects.filter(pk=table.pk).update(data_label="stale")
    resource = IsDataLabelExistResource()
    assert resource.perform_request({"bk_tenant_id": "labels_test", "data_label": "legacy.group1", "bk_data_id": None})
    assert not resource.perform_request({"bk_tenant_id": "labels_test", "data_label": "stale", "bk_data_id": None})
    result = GetDataLabelsMapResource().perform_request(
        {"bk_tenant_id": "labels_test", "bk_biz_id": "2", "table_or_labels": [table.table_id, "legacy.group1"]}
    )
    assert result["legacy.group1"] == "legacy.group1"
    assert result[table.table_id] == "primary"


def test_short_link_refresh_includes_full_previous_array():
    old_labels = [f"plugin.group{i}" for i in range(30)]
    table = make_table(data_labels=old_labels)
    assert _get_result_table_data_label(table.table_id, table.bk_tenant_id) == ",".join(old_labels)
    old = _update_result_table_data_label(table.table_id, table.bk_tenant_id, ["replacement"], "admin")
    assert old == ",".join(old_labels)
    table.refresh_from_db()
    assert table.data_labels == ["replacement"]
    assert table.data_label == "replacement"


def test_health_scene_substring_filter_uses_array():
    table = make_table(data_labels=["Primary", "Business_Log"])
    models.ResultTable.objects.filter(pk=table.pk).update(data_label="stale")
    assert list(
        models.ResultTable.objects.filter(bk_tenant_id=table.bk_tenant_id, data_labels__icontains="log").values_list(
            "table_id", flat=True
        )
    ) == [table.table_id]


def test_legacy_oversized_update_retains_stored_legacy_value():
    table = make_table(data_label="previous")
    table.data_label = ",".join(f"plugin.group{i}" for i in range(30))
    expected = table.data_label.split(",")
    table.save(update_fields=["data_label"])
    assert table.data_label == "previous"
    table.refresh_from_db()
    assert table.data_label == "previous"
    assert table.data_labels == expected


@pytest.mark.parametrize("group_model", [models.TimeSeriesGroup, models.EventGroup])
def test_custom_report_compatibility_fields_use_one_query(group_model, django_assert_num_queries):
    table = make_table(data_label="previous")
    table.data_labels = [f"plugin.group{i}" for i in range(30)]
    table.save(update_fields=["data_labels"])
    group = group_model(table_id=table.table_id, bk_tenant_id=table.bk_tenant_id)
    with django_assert_num_queries(1, connection=connections[config.DATABASE_CONNECTION_NAME]):
        fields = group.get_data_label_info()
    assert fields == {"data_label": "previous", "data_labels": table.data_labels}
    assert group.data_label == "previous"
    assert group.data_labels == table.data_labels


@pytest.mark.django_db(transaction=True, databases="__all__")
def test_migration_adds_json_field_and_copies_csv_in_batches():
    migration = importlib.import_module("metadata.migrations.0281_resulttable_data_labels")
    model_state = ModelState.from_model(models.ResultTable)
    model_state.fields.pop("data_labels")
    model_state.options["db_table"] = "test_resulttable_data_labels_migration"
    before = ProjectState()
    before.add_model(model_state)
    OldTable = before.apps.get_model("metadata", "ResultTable")
    connection = connections[config.DATABASE_CONNECTION_NAME]
    with connection.schema_editor() as editor:
        editor.create_model(OldTable)
    after = before.clone()
    operation = migration.Migration.operations[0]
    operation.state_forwards("metadata", after)
    NewTable = after.apps.get_model("metadata", "ResultTable")
    try:
        values = [None, "", "primary,alias", "primary,,alias"]
        OldTable.objects.using(connection.alias).bulk_create(
            [OldTable(table_id=f"migration.{i}", is_custom_table=False, data_label=values[i % 4]) for i in range(1005)]
        )
        with connection.schema_editor() as editor:
            operation.database_forwards("metadata", editor, before, after)
            migration.migrate_data_labels(after.apps, editor)
        rows = list(NewTable.objects.using(connection.alias).order_by("id").values("data_label", "data_labels"))
        assert len(rows) == 1005
        for i, row in enumerate(rows):
            assert row["data_label"] == values[i % 4]
            assert row["data_labels"] == ([] if i % 4 < 2 else ["primary", "alias"])
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(NewTable)
