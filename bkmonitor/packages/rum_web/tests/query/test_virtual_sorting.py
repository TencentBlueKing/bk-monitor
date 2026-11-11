"""虚拟列排序：存储侧空值规则、跨来源排序与分页。"""

from copy import deepcopy

import pytest

from bkmonitor.data_source.backends.elastic_search.connection import DatabaseConnection
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.handlers.query.sorting import build_virtual_sort
from rum_web.handlers.query.span import SpanQuery


def make_query(tables=("bk_rum.default.span",)):
    return SpanQuery([TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table) for table in tables])


@pytest.fixture(autouse=True)
def tenant(mocker):
    mocker.patch("bkmonitor.data_source.data_source.bk_biz_id_to_bk_tenant_id", return_value="system")


def test_numeric_sort_uses_raw_values_and_missing_last():
    query = make_query()
    order_by = query.process_sort_fields(query.expand_sort_fields(["-virtual.viewport"]))
    assert order_by == [
        "attributes.browser.viewport.width desc",
        "attributes.browser.viewport.height desc",
        "end_time desc",
        "span_id",
    ]
    sorts = build_virtual_sort(query, order_by)
    assert sorts[0] == {
        "attributes.browser.viewport.width": {"order": "desc", "missing": "_last", "unmapped_type": "long"}
    }
    assert sorts[1]["attributes.browser.viewport.height"]["missing"] == "_last"


@pytest.mark.parametrize("direction", ["", "-"])
def test_keyword_empty_values_normalized_before_next_member(direction):
    query = make_query()
    sorts = build_virtual_sort(
        query, query.process_sort_fields(query.expand_sort_fields([f"{direction}virtual.browser"]))
    )
    assert [sort["_script"]["type"] for sort in sorts[:4]] == ["number", "string", "number", "string"]
    assert [sort["_script"]["order"] for sort in sorts[:4]] == [
        "asc",
        "desc" if direction else "asc",
        "asc",
        "desc" if direction else "asc",
    ]
    for index, name in [(0, "resource.user_agent.name"), (2, "resource.user_agent.version")]:
        assert sorts[index]["_script"]["script"]["params"]["field"] == name
        assert "== ''" in sorts[index]["_script"]["script"]["source"]
        assert "return '';" in sorts[index + 1]["_script"]["script"]["source"]


def test_storage_receives_sort_filter_and_limit_before_materialization(mocker):
    from constants.apm import ApmGlobalTablePrefix

    table_id = f"{ApmGlobalTablePrefix.SHARED}test"
    query = make_query((table_id,))
    captured = []

    def execute(connection, table, params):
        captured.append((table, deepcopy(params)))
        return {
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "_source": {
                            "span_id": "s1",
                            "attributes": {"browser.viewport.width": 900, "browser.viewport.height": 600},
                        }
                    }
                ],
            }
        }

    mocker.patch.object(DatabaseConnection, "execute", execute)
    query._get_time_range = lambda start, end: (1000, 2000)
    handler = SpanLevelHandler(query.data_sources)
    handler.query = query
    records = handler.list_records(
        1,
        2,
        0,
        1,
        sort=["virtual.viewport"],
        filters=[{"key": "virtual.span_kind", "operator": "equal", "value": ["resource（xhr）"]}],
    )
    assert records[0]["virtual"]["viewport"] == "900 x 600"
    table, dsl = captured[0]
    assert table == table_id
    assert dsl["size"] == 1 and dsl.get("from", 0) == 0
    assert dsl["sort"][0] == {
        "attributes.browser.viewport.width": {"order": "asc", "missing": "_last", "unmapped_type": "long"}
    }
    assert dsl["bk_tenant_id"] == "system"
    assert "my_app" in str(dsl["query"])
    assert "1000000" in str(dsl["query"])
    assert "attributes.resource.type" in str(dsl["query"])
    assert "virtual." not in str(dsl["query"])


def test_merge_source_prefixes_then_page_and_materialize(mocker):
    query = make_query(("bk_rum.a.span", "bk_rum.b.span"))
    rows = {
        "bk_rum.a.span": [
            {"span_id": "a1", "attributes": {"browser.viewport.width": 900, "browser.viewport.height": 600}},
            {"span_id": "a2", "attributes": {"browser.viewport.width": 1440, "browser.viewport.height": 900}},
            {"span_id": "a3", "attributes": {"browser.viewport.width": 2000, "browser.viewport.height": 1000}},
        ],
        "bk_rum.b.span": [
            {"span_id": "b1", "attributes": {"browser.viewport.width": 1024, "browser.viewport.height": 768}},
            {"span_id": "b2", "attributes": {"browser.viewport.width": 1920, "browser.viewport.height": 1080}},
            {"span_id": "b3", "attributes": {}},
        ],
    }
    limits = []

    def execute(connection, table, params):
        limits.append((params.get("from", 0), params["size"]))
        return {
            "hits": {"total": len(rows[table]), "hits": [{"_source": row} for row in rows[table][: params["size"]]]}
        }

    mocker.patch.object(DatabaseConnection, "execute", execute)
    handler = SpanLevelHandler(query.data_sources)
    handler.query = query
    records = handler.list_records(1, 2, 1, 2, sort=["virtual.viewport"])
    assert [row["span_id"] for row in records] == ["b1", "a2"]
    assert [row["virtual"]["viewport"] for row in records] == ["1024 x 768", "1440 x 900"]
    assert limits == [(0, 3), (0, 3)]


def test_grouped_source_records_are_deduplicated_before_pagination(mocker):
    query = make_query(("bk_rum.a.span", "bk_rum.b.span"))
    rows = {
        "bk_rum.a.span": [
            {"span_id": "s1", "attributes.session.id": "a", "resource.user_agent.name": "Chrome"},
            {"span_id": "s2", "attributes.session.id": "b", "resource.user_agent.name": "Firefox"},
        ],
        "bk_rum.b.span": [
            {"span_id": "s3", "attributes.session.id": "a", "resource.user_agent.name": "Chrome"},
            {"span_id": "s4", "attributes.session.id": "c", "resource.user_agent.name": "Safari"},
        ],
    }

    def execute(connection, table, params):
        assert params["collapse"] == {"field": "attributes.session.id"}
        return {"hits": {"total": 2, "hits": [{"_source": row} for row in rows[table]]}}

    mocker.patch.object(DatabaseConnection, "execute", execute)
    records = query.query_group_list(1, 2, "attributes.session.id", 1, 2, sort=["virtual.browser"])
    assert [row["attributes.session.id"] for row in records] == ["b", "c"]
