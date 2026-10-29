"""DataSource 活跃 RT 的真实 ORM 统计与分页测试（独立内存 SQLite）。"""

from types import SimpleNamespace

import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext

from kernel_api.rpc.functions.admin import datasource


@pytest.fixture
def active_rt_context(monkeypatch, django_db_blocker):
    alias = "datasource_active_rt_test"
    connections.databases[alias] = {
        **connections.databases["default"],
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {},
    }
    connection = connections[alias]
    model_names = [
        "DataSource",
        "ResultTable",
        "DataSourceResultTable",
        "SpaceDataSource",
        "DataSourceOption",
        "DataIdConfig",
        "ClusterInfo",
    ]
    test_models = {name: getattr(datasource.models, name) for name in model_names}
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in test_models.values():
                editor.create_model(model)
        for model in test_models.values():
            monkeypatch.setattr(model, "objects", model.objects.using(alias))
        models = SimpleNamespace(**test_models)
        models.DataSource.objects.bulk_create(
            [
                models.DataSource(
                    bk_data_id=data_id,
                    bk_tenant_id=tenant,
                    data_name=f"source-{data_id}",
                    mq_cluster_id=0,
                    mq_config_id=0,
                    is_custom_source=False,
                    is_enable=data_id != 106,
                    etl_config="demo",
                )
                for data_id, tenant in [
                    (101, "a"),
                    (102, "a"),
                    (103, "a"),
                    (104, "a"),
                    (105, "a"),
                    (106, "a"),
                    (201, "b"),
                ]
            ]
        )
        models.ResultTable.objects.bulk_create(
            [
                models.ResultTable(
                    bk_tenant_id=tenant,
                    table_id=table_id,
                    is_enable=enabled,
                    is_deleted=deleted,
                    is_custom_table=False,
                )
                for tenant, table_id, enabled, deleted in [
                    ("a", "shared", True, False),
                    ("a", "off", False, False),
                    ("a", "extra", True, False),
                    ("a", "deleted", True, True),
                    ("b", "shared", False, False),
                    ("b", "off", True, False),
                ]
            ]
        )
        models.DataSourceResultTable.objects.bulk_create(
            [
                models.DataSourceResultTable(bk_tenant_id=tenant, bk_data_id=data_id, table_id=table_id)
                for tenant, data_id, table_id in [
                    ("a", 101, "shared"),
                    ("a", 101, "off"),
                    ("a", 101, "extra"),
                    ("a", 102, "off"),
                    ("a", 104, "missing"),
                    ("a", 105, "deleted"),
                    ("a", 106, "shared"),
                    ("b", 201, "shared"),
                ]
            ]
        )
        try:
            yield connection
        finally:
            connection.close()
            del connections[alias]
            del connections.databases[alias]


def _list(**params):
    return datasource.list_datasources({"ordering": "bk_data_id", **params})["data"]


def test_counts_only_existing_enabled_tables_in_the_same_tenant(active_rt_context):
    items = {item["bk_data_id"]: item for item in _list()["items"]}
    assert {key: item["active_result_table_count"] for key, item in items.items()} == {
        101: 2,
        102: 0,
        103: 0,
        104: 0,
        105: 1,
        106: 1,
        201: 0,
    }
    assert items[101]["result_table_count"] == 3
    assert items[104]["result_table_count"] == 1


def test_pagination_selects_datasources_before_rt_queries(active_rt_context):
    with CaptureQueriesContext(active_rt_context) as queries:
        first = _list(page=1, page_size=2)
    second = _list(page=2, page_size=2)
    assert first["total"] == second["total"] == 7
    assert [item["bk_data_id"] for item in first["items"]] == [101, 102]
    assert [item["active_result_table_count"] for item in first["items"]] == [2, 0]
    assert [item["bk_data_id"] for item in second["items"]] == [103, 104]
    for query in queries.captured_queries[:2]:
        assert datasource.models.ResultTable._meta.db_table not in query["sql"]
        assert datasource.models.DataSourceResultTable._meta.db_table not in query["sql"]


def test_relation_filter_does_not_narrow_active_count(active_rt_context):
    result = _list(bk_tenant_id="a", table_id="off", etl_config="demo")
    assert result["total"] == 2
    assert [item["active_result_table_count"] for item in result["items"]] == [2, 0]
    assert _list(bk_tenant_id="b")["items"][0]["active_result_table_count"] == 0
    assert _list(bk_tenant_id="a", is_enable=False)["items"][0]["active_result_table_count"] == 1


def test_batch_counts_do_not_add_queries_per_datasource(active_rt_context):
    with CaptureQueriesContext(active_rt_context) as one:
        _list(bk_tenant_id="a", page_size=1)
    with CaptureQueriesContext(active_rt_context) as many:
        _list(bk_tenant_id="a", page_size=6)
    assert len(one) == len(many)
