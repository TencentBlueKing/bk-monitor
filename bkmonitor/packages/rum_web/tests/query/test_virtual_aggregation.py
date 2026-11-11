"""虚拟维度聚合：真实 ES 编译路径与最终值归并。"""

import json
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from bkmonitor.data_source.models.sql import query as sql_query
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import ApmGlobalTablePrefix
from constants.data_source import DataSourceLabel, DataTypeLabel
from rum_web.handlers.query.span import SpanQuery
from rum_web.handlers.query.virtual import (
    _weighted_percentile,
    iter_joint_buckets,
    query_virtual_graph_configs,
    query_virtual_grouped_values,
    query_virtual_values,
)


START = 1737532800
END = START + 120
NAME = "resource.user_agent.name"
VERSION = "resource.user_agent.version"
BROWSER = "virtual.browser"
WIDTH = "attributes.browser.viewport.width"
HEIGHT = "attributes.browser.viewport.height"
VIEWPORT = "virtual.viewport"


def _target(table=None, biz=2, app="my_app"):
    return TraceDatasourceTarget.build(
        bk_biz_id=biz, app_name=app, table_id=table or f"{ApmGlobalTablePrefix.SHARED}rum"
    )


@pytest.fixture
def query():
    owner = SpanQuery([_target()])
    with patch.object(owner, "_get_time_range", side_effect=lambda start, end: (start * 1000, end * 1000)):
        yield owner


@pytest.fixture
def es(monkeypatch):
    endpoint = Mock()
    monkeypatch.setitem(sql_query.DATA_SOURCE[DataSourceLabel.BK_RUM][DataTypeLabel.LOG], "query", endpoint)
    with patch("bkmonitor.data_source.data_source.bk_biz_id_to_bk_tenant_id", side_effect=lambda biz: f"tenant-{biz}"):
        yield endpoint


def _page(rows, after=None):
    group = {"buckets": [{"key": key, "_records": {"value": count}} for key, count in rows]}
    if after is not None:
        group["after_key"] = after
    return {"aggregations": {"_group_": group}}


def test_pages_merge_before_topk_and_retain_guard_and_missing_members(query, es):
    after = {NAME: "Firefox", VERSION: "127"}
    es.side_effect = [
        _page([({NAME: "Chrome", VERSION: None}, 3), ({NAME: "Firefox", VERSION: "127"}, 4)], after),
        _page(
            [
                ({NAME: "Chrome", VERSION: ""}, 2),
                ({NAME: "Chrome", VERSION: "--"}, 1),
                ({NAME: None, VERSION: "131"}, 2),
                ({NAME: None, VERSION: None}, 5),
            ]
        ),
    ]
    topk = query.query_field_topk(
        START,
        END,
        BROWSER,
        1,
        filters=[{"key": "status.code", "operator": "equal", "value": [2]}],
        query_string="span_name:api*",
    )
    assert topk == [{BROWSER: "Chrome --", "_result_": 6}]
    assert es.call_count == 2
    request = es.call_args_list[0].kwargs
    assert request["bk_tenant_id"] == "tenant-2"
    assert request["table_id"] == query.data_sources[0].table_id
    assert request["use_full_index_names"] is True
    body = request["query_body"]
    composite = body["aggregations"]["_group_"]["composite"]
    assert composite["sources"] == [
        {NAME: {"terms": {"field": NAME, "missing_bucket": True}}},
        {VERSION: {"terms": {"field": VERSION, "missing_bucket": True}}},
    ]
    assert body["aggregations"]["_group_"]["aggregations"] == {"_records": {"value_count": {"field": "_index"}}}
    assert es.call_args_list[1].kwargs["query_body"]["aggregations"]["_group_"]["composite"]["after"] == after
    encoded = json.dumps(body["query"])
    for part in ("bk_biz_id", "app_name", "my_app", "status.code", "span_name:api*", str(START * 1000000)):
        assert part in encoded


def test_multi_source_merge_and_all_empty_value(query, es):
    query.data_sources.append(_target(table="other_rum", biz=3, app="other"))
    es.side_effect = [
        _page([({NAME: "Chrome", VERSION: None}, 3), ({NAME: None, VERSION: None}, 8)]),
        _page([({NAME: "Chrome", VERSION: "--"}, 4)]),
    ]
    assert query_virtual_values(query, query.get_queries(), START, END, BROWSER) == {"Chrome --": 7, None: 8}
    assert [call.kwargs["bk_tenant_id"] for call in es.call_args_list] == ["tenant-2", "tenant-3"]


def test_empty_page_ends_iteration_without_losing_full_last_page(query, es):
    after = {NAME: "Chrome", VERSION: "131"}
    es.side_effect = [_page([(after, 2)], after), _page([])]
    assert query_virtual_values(query, query.get_queries(), START, END, BROWSER) == {"Chrome 131": 2}
    assert es.call_count == 2


@pytest.mark.parametrize("partial", [{"timed_out": True}, {"_shards": {"failed": 1}}])
def test_partial_es_response_is_not_reported_as_exact_analysis(query, es, partial):
    es.return_value = {**_page([({NAME: "Chrome", VERSION: "131"}, 2)]), **partial}
    with pytest.raises(RuntimeError, match="未完整返回"):
        query_virtual_values(query, query.get_queries(), START, END, BROWSER)


def test_repeated_cursor_does_not_silently_finish(query, es):
    after = {NAME: "Chrome", VERSION: "131"}
    es.return_value = _page([(after, 2)], after)
    with pytest.raises(RuntimeError, match="游标未前进"):
        query_virtual_values(query, query.get_queries(), START, END, BROWSER)


def test_default_existing_composite_does_not_add_missing_bucket(query, es):
    from bkmonitor.data_source.data_source import BkRumDataSource

    es.return_value = _page([({NAME: "Chrome"}, 1)])
    queryset = (
        BkRumDataSource._get_queryset(
            bk_tenant_id="tenant-2",
            metrics=[{"field": "_index", "method": "COUNT", "alias": "_records"}],
            table="rum",
            where={},
            group_by=[NAME],
            time_field="end_time",
            limit=10,
        )
        .dsl_date_histogram(False)
        .dsl_search_after({})
    )
    assert queryset.raw_data == [{NAME: "Chrome", "_records": 1, "_after_key_": None}]
    assert es.call_args.kwargs["query_body"]["aggregations"]["_group_"]["composite"]["sources"] == [
        {NAME: {"terms": {"field": NAME}}}
    ]


def test_virtual_count_and_distinct_are_based_on_final_values(query):
    rows = [
        {NAME: "Chrome", VERSION: None, "_records": 3},
        {NAME: "Chrome", VERSION: "", "_records": 2},
        {NAME: "Chrome", VERSION: "--", "_records": 4},
        {NAME: None, VERSION: "131", "_records": 1},
        {NAME: None, VERSION: None, "_records": 10},
    ]
    with patch("rum_web.handlers.query.virtual.iter_joint_buckets", side_effect=lambda *args: iter(rows)):
        assert query_virtual_grouped_values(query, query.get_queries(), START, END, [BROWSER], "count") == [
            {"_result_": 10}
        ]
        assert query_virtual_grouped_values(query, query.get_queries(), START, END, [BROWSER], "distinct") == [
            {"_result_": 2}
        ]


@pytest.mark.parametrize("method,expected", [("sum", 40), ("count", 40), ("min", 10), ("max", 30), ("avg", 10)])
def test_metric_merge_retains_other_dimension_and_uses_weighted_average(query, method, expected):
    rows = [
        {NAME: "Chrome", VERSION: None, "status.code": 0, "_records": 3, "m0": 30, "n0": 3},
        {NAME: "Chrome", VERSION: "--", "status.code": 0, "_records": 1, "m0": 10, "n0": 1},
        {NAME: "Chrome", VERSION: "", "status.code": 2, "_records": 1, "m0": 5, "n0": 1},
    ]
    with patch("rum_web.handlers.query.virtual.iter_joint_buckets", return_value=iter(rows)) as fetch:
        result = query_virtual_grouped_values(
            query, query.get_queries(), START, END, ["elapsed_time"], method, [BROWSER, "status.code"]
        )
    assert result == [
        {BROWSER: "Chrome --", "status.code": 0, "_result_": expected},
        {BROWSER: "Chrome --", "status.code": 2, "_result_": 5},
    ]
    assert fetch.call_args.args[4] == [NAME, VERSION, "status.code"]
    if method == "avg":
        assert fetch.call_args.args[5][-2:] == [
            {"field": "elapsed_time", "method": "SUM", "alias": "m0"},
            {"field": "elapsed_time", "method": "COUNT", "alias": "n0"},
        ]


def test_real_distinct_enumerates_values_and_deduplicates_across_raw_groups(query):
    rows = [
        {NAME: "Chrome", VERSION: None, "user": "a", "_records": 3},
        {NAME: "Chrome", VERSION: "--", "user": "a", "_records": 2},
        {NAME: "Chrome", VERSION: "", "user": "b", "_records": 2},
        {NAME: "Chrome", VERSION: None, "user": None, "_records": 2},
    ]
    with patch("rum_web.handlers.query.virtual.iter_joint_buckets", return_value=iter(rows)) as fetch:
        result = query_virtual_grouped_values(query, query.get_queries(), START, END, ["user"], "distinct", [BROWSER])
    assert result == [{BROWSER: "Chrome --", "_result_": 2}]
    assert fetch.call_args.args[4] == [NAME, VERSION, "user"]


def test_time_buckets_keep_virtual_and_other_groups_with_timezone_alignment(query):
    row = {WIDTH: 1440, HEIGHT: None, "status.code": 0, "m0": 2, "_records": 2}
    start = START + 10
    with (
        timezone.override("Asia/Shanghai"),
        patch("rum_web.handlers.query.virtual.iter_joint_buckets", side_effect=lambda *args: iter([row])) as fetch,
    ):
        result = query_virtual_grouped_values(
            query, query.get_queries(), start, END, ["_index"], "count", [VIEWPORT, "status.code", "time"], 60
        )
    assert result == [
        {VIEWPORT: "1440 x --", "status.code": 0, "_result_": 2, "_time_": START * 1000},
        {VIEWPORT: "1440 x --", "status.code": 0, "_result_": 2, "_time_": (START + 60) * 1000},
    ]
    assert [call.args[2:4] for call in fetch.call_args_list] == [(start, START + 60), (START + 60, END)]


def test_time_group_windows_send_microsecond_ranges_to_actual_es_compiler(query, es):
    es.return_value = {
        "aggregations": {
            "_group_": {
                "buckets": [
                    {
                        "key": {WIDTH: 1440, HEIGHT: None},
                        "_records": {"value": 2},
                        "m0": {"value": 2},
                    }
                ]
            }
        }
    }
    result = query_virtual_grouped_values(
        query, query.get_queries(), START + 10, END, ["_index"], "count", [VIEWPORT, "time"], 60
    )
    assert [record["_time_"] for record in result] == [START * 1000, (START + 60) * 1000]
    for call, expected_start, expected_end in zip(
        es.call_args_list, [START + 10, START + 60], [START + 60, END], strict=True
    ):
        encoded = json.dumps(call.kwargs["query_body"]["query"])
        assert json.dumps({"end_time": {"gte": expected_start * 1000000}}) in encoded
        assert json.dumps({"end_time": {"lt": expected_end * 1000000}}) in encoded
    assert query._get_time_range.call_args_list[1].args == (START + 10, START + 60)


def test_percentiles_merge_sample_frequencies_across_pages_and_sources(query, es):
    query.data_sources.append(_target(table="other_rum", biz=3))
    after = {NAME: "Chrome", VERSION: None, "elapsed_time": 10}
    es.side_effect = [
        _page([(after, 9)], after),
        _page(
            [
                ({NAME: "Chrome", VERSION: "--", "elapsed_time": 20}, 1),
                ({NAME: "Chrome", VERSION: None, "elapsed_time": None}, 50),
                ({NAME: "Firefox", VERSION: None, "elapsed_time": 500}, 1),
            ]
        ),
        _page(
            [
                ({NAME: "Chrome", VERSION: "", "elapsed_time": 100}, 2),
                ({NAME: "Chrome", VERSION: "--", "elapsed_time": 200}, 8),
                ({NAME: "Firefox", VERSION: "--", "elapsed_time": 1000}, 1),
            ]
        ),
    ]
    result = query_virtual_grouped_values(query, query.get_queries(), START, END, ["elapsed_time"], "cp50", [BROWSER])
    # Chrome 的第 10、11 个有效样本为 20、100，不能对两来源的中位数 10、200 求和或平均。
    assert result == [{BROWSER: "Chrome --", "_result_": 60}, {BROWSER: "Firefox --", "_result_": 750}]
    assert es.call_count == 3
    for call in es.call_args_list:
        aggregation = call.kwargs["query_body"]["aggregations"]["_group_"]
        assert aggregation["aggregations"] == {"_records": {"value_count": {"field": "_index"}}}
        assert aggregation["composite"]["sources"][-1] == {
            "elapsed_time": {"terms": {"field": "elapsed_time", "missing_bucket": True}}
        }


@pytest.mark.parametrize(
    "frequencies,percentile,expected",
    [
        ({}, 50, 0),
        ({10: 1}, 50, 10),
        ({1: 1, 3: 1}, 50, 2),
        ({1: 4, 3: 1}, 50, 1),
        ({0: 1, 10: 1}, 90, 9),
        ({1: 1000000000, 100: 1}, 50, 1),
        ({-10: 1, 10: 1}, 0, -10),
        ({-10: 1, 10: 1}, 100, 10),
    ],
)
def test_weighted_percentile_uses_sample_ranks_without_expanding_records(frequencies, percentile, expected):
    assert _weighted_percentile(frequencies, percentile) == expected


def test_graph_counts_records_without_grouping_by_nullable_members(query):
    graphs = query_virtual_graph_configs(query, query.get_queries(), START, END, BROWSER, ["Chrome --"])
    assert len(graphs) == 1
    value, config = graphs[0]
    assert value == "Chrome --"
    source = config["query_configs"][0]
    assert source["group_by"] == []
    assert source["metrics"] == [{"field": "_index", "method": "COUNT", "alias": "a"}]
    encoded = json.dumps(source["filter_dict"])
    assert NAME in encoded and VERSION in encoded and "nexists" in encoded and "--" in encoded


def test_precomputed_targets_use_level_table_and_tenant(query, es):
    query.level_query = SpanQuery([_target(table="precomputed_view", biz=3)])
    es.return_value = _page([({WIDTH: 1440, HEIGHT: 900}, 2)])
    values = query_virtual_values(query, query.level_query.get_queries(), START, END, VIEWPORT)
    assert values == {"1440 x 900": 2}
    assert es.call_args.kwargs["table_id"] == "precomputed_view"
    assert es.call_args.kwargs["bk_tenant_id"] == "tenant-3"


def test_joint_buckets_preserves_non_count_metrics(query, es):
    es.return_value = {"aggregations": {"_group_": {"buckets": [{"key": {NAME: "Chrome"}, "total": {"value": 42}}]}}}
    records = list(
        iter_joint_buckets(
            query,
            query.get_queries(),
            START,
            END,
            [NAME],
            [{"field": "elapsed_time", "method": "SUM", "alias": "total"}],
        )
    )
    assert records == [{NAME: "Chrome", "total": 42}]
