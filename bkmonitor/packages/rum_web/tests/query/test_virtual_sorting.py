"""虚拟列排序：复用原字段排序、跨来源排序与分页。"""

from copy import deepcopy

import pytest

from bkmonitor.data_source.backends.elastic_search.connection import DatabaseConnection
from bkmonitor.data_source.unify_query.builder import QueryHelper
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.handlers.query.span import SpanQuery


def make_query(tables=("bk_rum.default.span",)):
    return SpanQuery([TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table) for table in tables])


@pytest.fixture(autouse=True)
def direct_storage(mocker):
    mocker.patch("bkmonitor.data_source.data_source.BkRumDataSource.switch_unify_query", return_value=False)
    mocker.patch("bkmonitor.data_source.data_source.bk_biz_id_to_bk_tenant_id", return_value="system")


def test_numeric_sort_expands_to_raw_fields_and_stable_tiebreak():
    query = make_query()
    order_by = query.process_sort_fields(query.expand_sort_fields(["-virtual.viewport"]))
    assert order_by == [
        "attributes.browser.viewport.width desc",
        "attributes.browser.viewport.height desc",
        "end_time desc",
        "span_id",
    ]


def test_sort_keeps_first_direction_when_a_member_or_default_is_explicit():
    width = "attributes.browser.viewport.width"
    height = "attributes.browser.viewport.height"
    assert make_query().expand_sort_fields([width, "-virtual.viewport", "end_time"]) == [
        width,
        f"-{height}",
        "end_time",
        "span_id",
    ]


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
        filters=[{"key": "virtual.network", "operator": "equal", "value": ["wifi / 4g"]}],
    )
    assert records[0]["virtual"]["viewport"] == "900 x 600"
    table, dsl = captured[0]
    assert table == table_id
    assert dsl["size"] == 1 and dsl.get("from", 0) == 0
    assert dsl["sort"] == [
        {"attributes.browser.viewport.width": "asc"},
        {"attributes.browser.viewport.height": "asc"},
        {"end_time": "desc"},
        {"span_id": "asc"},
    ]
    assert dsl["bk_tenant_id"] == "system"
    assert "my_app" in str(dsl["query"])
    assert "1000000" in str(dsl["query"])
    assert "attributes.network.connection.type" in str(dsl["query"])
    assert "attributes.network.effective_type" in str(dsl["query"])
    assert "virtual." not in str(dsl["query"])


@pytest.mark.parametrize("group_field", ["", "attributes.session.id"])
def test_virtual_sort_delegates_paging_to_one_queryset(mocker, group_field):
    tables = ("bk_rum.a.span", "bk_rum.b.span")
    query = make_query(tables)
    execute = mocker.patch.object(QueryHelper, "query", return_value=[])
    if group_field:
        query.query_group_list(1, 2, group_field, offset=20, limit=10, sort=["-virtual.viewport"])
    else:
        query.query_list(1, 2, offset=20, limit=10, sort=["-virtual.viewport"])

    execute.assert_called_once()
    body = execute.call_args.kwargs["query_body"]
    assert (body["offset"], body["limit"]) == (20, 10)
    assert body["order_by"] == [
        "-attributes.browser.viewport.width",
        "-attributes.browser.viewport.height",
        "-end_time",
        "span_id",
    ]
    assert [q["table"] for q in body["query_configs"]] == list(tables)
    assert all(q["distinct"] == group_field for q in body["query_configs"])


@pytest.mark.parametrize("prefix,expected", [("", ["empty", "named", "missing"]), ("-", ["named", "empty", "missing"])])
def test_browser_sort_treats_empty_and_missing_like_raw_members(mocker, prefix, expected):
    query = make_query(("bk_rum.a.span", "bk_rum.b.span"))
    field = "resource.user_agent.name"
    empty = {"span_id": "empty", field: ""}
    named = {"span_id": "named", field: "Chrome"}
    rows = {
        "bk_rum.a.span": [empty, {"span_id": "missing"}],
        "bk_rum.b.span": [named],
    }

    def execute(connection, table, params):
        return {"hits": {"total": len(rows[table]), "hits": [{"_source": row} for row in rows[table]]}}

    mocker.patch.object(DatabaseConnection, "execute", execute)
    for ordering in ("virtual.browser", field):
        page = query.query_list(1, 2, 0, 3, sort=[prefix + ordering])
        assert [row["span_id"] for row in page] == expected
