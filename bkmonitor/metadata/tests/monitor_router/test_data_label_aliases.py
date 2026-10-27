import json

import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext

from metadata import config, models
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

pytestmark = pytest.mark.django_db(databases="__all__")
TENANT = "alias-test"
OPTION = models.ResultTableOption.OPTION_DATA_LABEL_ALIASES


def make_table(table_id, data_label="primary", tenant=TENANT, **kwargs):
    return models.ResultTable.objects.create(
        table_id=table_id, bk_tenant_id=tenant, data_label=data_label, is_custom_table=False, **kwargs
    )


def set_aliases(table_id, aliases, tenant=TENANT):
    return models.ResultTableOption.objects.update_or_create(
        table_id=table_id,
        bk_tenant_id=tenant,
        name=OPTION,
        defaults={"value": json.dumps(aliases), "value_type": "list", "creator": "system"},
    )[0]


@pytest.fixture
def router(mocker, settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    write = mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis")
    publish = mocker.patch("metadata.utils.redis_tools.RedisTools.publish")
    return SpaceTableIDRedis(), write, publish


@pytest.mark.parametrize("mode", ["table", "label", "full"])
@pytest.mark.parametrize("aliases", [[{}], [["nested"]], ["shared", {}, ["nested"], 1, True, None]])
def test_invalid_stored_alias_members_do_not_interrupt_other_routes(router, mode, aliases):
    client, write, publish = router
    make_table("plugin.invalid", "bad_primary")
    make_table("plugin.valid", "good_primary")
    set_aliases("plugin.invalid", aliases)
    set_aliases("plugin.valid", ["shared"])
    params = {"table_id_list": ["plugin.invalid", "plugin.valid"]} if mode == "table" else {}
    if mode == "label":
        params = {"data_label_list": ["shared"]}
    client.push_data_label_table_ids(bk_tenant_id=TENANT, is_publish=True, **params)
    routes = {label: json.loads(value) for label, value in write.call_args.args[1].items()}
    shared_tables = {"plugin.valid"}
    if "shared" in aliases:
        shared_tables.add("plugin.invalid")
    assert set(routes.pop("shared")) == shared_tables
    assert routes == ({} if mode == "label" else {"bad_primary": ["plugin.invalid"], "good_primary": ["plugin.valid"]})
    assert publish.called


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("mode", ["table", "label", "full"])
def test_list_aliases_extend_legacy_labels(router, settings, multi_tenant, mode):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    client, write, publish = router
    table = make_table("plugin.default", "primary,shared")
    aliases = [f"plugin.group{i}" for i in range(20)]
    set_aliases(table.table_id, ["primary", *aliases, aliases[0]])
    params = {"table_id_list": [table.table_id]} if mode == "table" else {}
    if mode == "label":
        params = {"data_label_list": [aliases[0]]}
    client.push_data_label_table_ids(bk_tenant_id=TENANT, is_publish=True, **params)
    key, payload = write.call_args.args
    suffix = f"|{TENANT}" if multi_tenant else ""
    expected_labels = [aliases[0]] if mode == "label" else ["primary", "shared", *aliases]
    assert key == DATA_LABEL_TO_RESULT_TABLE_KEY
    assert {label: json.loads(value) for label, value in payload.items()} == {
        f"{label}{suffix}": [table.table_id] for label in expected_labels
    }
    assert publish.called
    table.refresh_from_db()
    assert table.data_label == "primary,shared"


def test_scoped_refresh_preserves_all_tables_sharing_alias(router):
    client, write, _ = router
    first = make_table("plugin.first", "one")
    second = make_table("plugin.second", "two")
    third = make_table("plugin.third", "shared")
    set_aliases(first.table_id, ["shared"])
    set_aliases(second.table_id, ["shared"])
    client.push_data_label_table_ids(bk_tenant_id=TENANT, table_id_list=[first.table_id])
    assert set(json.loads(write.call_args.args[1]["shared"])) == {first.table_id, second.table_id, third.table_id}


def test_aliases_are_exact_tenant_scoped_and_only_publish_enabled_tables(router):
    client, write, _ = router
    make_table("plugin.exact", data_label=None)
    set_aliases("plugin.exact", ["alias"])
    for table_id, flags in [("plugin.disabled", {"is_enable": False}), ("plugin.deleted", {"is_deleted": True})]:
        make_table(table_id, **flags)
        set_aliases(table_id, ["alias"])
    make_table("plugin.foreign", tenant="other")
    set_aliases("plugin.foreign", ["alias"], tenant="other")
    make_table("plugin.longer")
    set_aliases("plugin.longer", ["alias_suffix", "Alias"])
    set_aliases("plugin.orphan", ["alias"])
    make_table("plugin.wrong_type")
    models.ResultTableOption.objects.create(
        table_id="plugin.wrong_type",
        bk_tenant_id=TENANT,
        name=OPTION,
        value="alias",
        value_type="string",
        creator="system",
    )
    client.push_data_label_table_ids(bk_tenant_id=TENANT, data_label_list=["alias"])
    assert json.loads(write.call_args.args[1]["alias"]) == ["plugin.exact"]


def test_removed_alias_can_be_refreshed_to_empty_route(router):
    client, write, publish = router
    make_table("plugin.default")
    set_aliases("plugin.default", ["removed"])
    client.push_data_label_table_ids(bk_tenant_id=TENANT, data_label_list=["removed"])
    set_aliases("plugin.default", [])
    client.push_data_label_table_ids(bk_tenant_id=TENANT, data_label_list=["removed"], is_publish=True)
    assert json.loads(write.call_args.args[1]["removed"]) == []
    assert publish.called


def test_combined_table_and_label_filters_include_option_only_alias(router):
    client, write, _ = router
    make_table("plugin.default")
    set_aliases("plugin.default", ["legacy.rt", "unrequested"])
    client.push_data_label_table_ids(
        bk_tenant_id=TENANT, table_id_list=["plugin.default"], data_label_list=["legacy.rt"]
    )
    assert set(write.call_args.args[1]) == {"legacy.rt"}


@pytest.mark.parametrize("size", [1, 30])
@pytest.mark.parametrize("mode, query_count", [("table", 4), ("label", 2), ("full", 2)])
def test_route_query_count_is_constant(router, size, mode, query_count, django_assert_num_queries):
    client, _, _ = router
    table_ids = [f"plugin.table{i}" for i in range(size)]
    models.ResultTable.objects.bulk_create(
        [
            models.ResultTable(table_id=table_id, bk_tenant_id=TENANT, data_label=f"primary{i}", is_custom_table=False)
            for i, table_id in enumerate(table_ids)
        ]
    )
    for table_id in table_ids:
        set_aliases(table_id, ["shared"])
    params = {"table_id_list": table_ids} if mode == "table" else {}
    if mode == "label":
        params = {"data_label_list": ["shared"]}
    with django_assert_num_queries(query_count, connection=connections[config.DATABASE_CONNECTION_NAME]):
        client.push_data_label_table_ids(bk_tenant_id=TENANT, **params)


def test_targeted_alias_lookup_filters_json_in_database(router, mocker):
    client, _, _ = router
    set_aliases("wanted.rt", ["目标.rt"])
    set_aliases("unrelated.rt", ["unrelated"])
    original = models.ResultTableOption.get_value
    decoded = []

    def decode(option):
        decoded.append(option.table_id)
        return original(option)

    mocker.patch.object(models.ResultTableOption, "get_value", autospec=True, side_effect=decode)
    with CaptureQueriesContext(connections[config.DATABASE_CONNECTION_NAME]) as queries:
        aliases = client._get_data_label_aliases(TENANT, data_label_list=["目标.rt"])
    assert aliases == {"wanted.rt": ["目标.rt"]}
    assert decoded == ["wanted.rt"]
    assert len(queries) == 1
    assert "JSON_CONTAINS" in queries[0]["sql"]


def test_edit_preserves_query_alias_option_when_omitted(router, mocker):
    table = make_table("plugin.default", default_storage=models.ClusterInfo.TYPE_VM)
    source = models.DataSource.objects.create(
        bk_tenant_id=TENANT,
        bk_data_id=50010,
        data_name="alias_plugin",
        mq_cluster_id=0,
        mq_config_id=0,
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=TENANT, bk_data_id=source.bk_data_id, table_id=table.table_id
    )
    set_aliases(table.table_id, ["legacy.rt"])
    mocker.patch.object(models.ResultTable, "apply_datalink")
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    table.modify(operator="system", option={})
    assert models.ResultTableOption.objects.get(
        bk_tenant_id=TENANT, table_id=table.table_id, name=OPTION
    ).get_value() == ["legacy.rt"]
    table.modify(operator="system", option={OPTION: []})
    assert (
        models.ResultTableOption.objects.get(bk_tenant_id=TENANT, table_id=table.table_id, name=OPTION).get_value()
        == []
    )
