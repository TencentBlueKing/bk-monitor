from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from rest_framework.exceptions import ValidationError

from kernel_api.rpc.functions.admin import apm_trace
from kernel_api.rpc.registry import KernelRPCRegistry

APP = {"bk_tenant_id": "tenant-a", "bk_biz_id": 2, "app_name": "checkout"}
ROOT = {
    "trace_id": "trace-a",
    "span_id": "root",
    "parent_span_id": "",
    "resource": {"service.name": "checkout"},
    "attributes": {"foo": "bar"},
    "custom_extension": "preserved",
    "events": [{"name": "start"}],
    "links": [
        {"trace_id": "trace-b", "span_id": "target", "attributes": {"reason": "async"}},
        {"trace_id": "other-app", "span_id": "external", "attributes": {"reason": "external"}},
    ],
}
CHILD = {"trace_id": "trace-a", "span_id": "child", "parent_span_id": "root", "attributes": {"large": "value"}}
TARGET = {"trace_id": "trace-b", "span_id": "target"}
INCOMING = {
    "trace_id": "trace-c",
    "span_id": "incoming",
    "links": [{"trace_id": "trace-a", "span_id": "root", "attributes": {"reason": "retry"}}],
}


class SpanQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def build_queries(self, filters):
        query = Mock()
        query.filters = filters
        query.order_by.return_value = query
        return [query]

    def _query_list(self, queries, start, end, offset, limit):
        return self.query_list(start, end, offset, limit, queries[0].filters, ["keep_all"], "", None)

    def query_list(self, start, end, offset, limit, filters, exclude, query_string, sort):
        self.calls.append((start, end, offset, limit, filters, exclude, query_string, sort))
        rows = self.rows
        for item in filters:
            key = item["key"]
            if key.startswith("links."):
                rows = [row for row in rows if any(link.get(key[6:]) in item["value"] for link in row.get("links", []))]
            else:
                rows = [row for row in rows if row.get(key) in item["value"]]
        rows = rows[offset : offset + limit]
        return [
            dict(row)
            if exclude
            else {key: value for key, value in row.items() if key not in {"attributes", "events", "links"}}
            for row in rows
        ]


@pytest.fixture
def queries(monkeypatch):
    span = SpanQuery([ROOT, CHILD, TARGET, INCOMING])
    trace = SpanQuery([])
    proxy = Mock()
    proxy._get_query.side_effect = lambda mode, *_: trace if mode == "trace" else span
    monkeypatch.setattr(apm_trace, "_make_proxy", Mock(return_value=proxy))
    return proxy, span, trace


@pytest.mark.parametrize(
    "name", ["trace_list", "trace_detail", "span_list", "span_detail", "span_relation_list", "trace_application_list"]
)
def test_registered_json_schema_and_examples(name):
    detail = KernelRPCRegistry.get_function_detail(f"admin.apm.{name}")
    assert detail["params_schema"]["type"] == "object"
    assert detail["params_schema"]["additionalProperties"] is False
    assert "bk_tenant_id" in detail["params_schema"]["required"]
    assert detail["example_params"]["bk_tenant_id"] == "system"


@pytest.mark.parametrize(
    "overrides",
    [
        {"bk_tenant_id": "__all__"},
        {"bk_tenant_id": ""},
        {"page_size": 101},
        {"page": 0},
        {"start_time": 1},
        {"start_time": 3, "end_time": 2},
        {"hidden": True},
    ],
)
def test_input_validation(overrides):
    with pytest.raises(ValidationError):
        apm_trace.span_list({**APP, "trace_id": "trace-a", **overrides})


def test_ordinary_list_requires_time_but_id_filter_does_not(queries):
    with pytest.raises(ValidationError):
        apm_trace.span_list(APP)
    result = apm_trace.span_list(
        {**APP, "filters": [{"key": "trace_id", "operator": "equal", "value": ["trace-a"]}], "page_size": 1}
    )
    assert result["data"]["has_more"] is True
    assert len(result["data"]["items"]) == 1
    assert "total" not in result["data"]
    assert result["meta"]["safety_level"] == "inspect"


def test_explicit_time_filters_sort_and_next_page(queries):
    _, span, _ = queries
    result = apm_trace.span_list(
        {
            **APP,
            "trace_id": "trace-a",
            "start_time": 100,
            "end_time": 200,
            "page": 2,
            "page_size": 1,
            "sort": ["-start_time", "span_id"],
        }
    )
    assert result["data"]["items"][0]["span_id"] == "child"
    assert result["data"]["has_more"] is False
    assert span.calls[-1][:4] == (100, 200, 1, 2)
    assert span.calls[-1][-1] == ["start_time desc", "span_id"]


def test_precalculation_and_origin_are_explicit(queries):
    proxy, _, _ = queries
    for mode, expected in [("pre_calculation", "trace"), ("origin", "origin_trace")]:
        result = apm_trace.trace_list({**APP, "trace_id": "trace-a", "query_mode": mode})
        assert result["data"]["query_mode"] == mode
        assert proxy._get_query.call_args.args[0] == expected


def test_trace_detail_survives_missing_precalculation_and_paginates_spans(queries):
    result = apm_trace.trace_detail({**APP, "trace_id": "trace-a", "page_size": 1})
    assert result["data"]["summary"] is None
    assert result["data"]["spans"]["has_more"] is True
    assert "attributes" not in result["data"]["spans"]["items"][0]
    assert result["warnings"][0]["code"] == "TRACE_SUMMARY_UNAVAILABLE"


def test_span_detail_keeps_raw_fields_and_can_disambiguate_trace(queries):
    assert apm_trace.span_detail({**APP, "span_id": "root"})["data"]["span"] == ROOT
    assert apm_trace.span_detail({**APP, "span_id": "root", "trace_id": "wrong"})["data"]["span"] is None


def relation(kind, span_id="root", **extra):
    return apm_trace.span_relation_list({**APP, "span_id": span_id, "relation": kind, **extra})["data"]


def test_root_parent_children_and_missing_parent(queries):
    _, span, _ = queries
    assert relation("parent")["items"] == []
    parent = relation("parent", "child")["items"][0]
    assert parent["source"]["span_id"] == "root"
    assert parent["target"]["span_id"] == "child"
    assert "attributes" not in parent["span"]
    assert relation("children")["items"][0]["span"]["span_id"] == "child"
    assert relation("parent", "child", page=2)["items"] == []
    span.rows = [CHILD]
    assert relation("parent", "child")["items"][0]["span"] is None


def test_links_out_keep_direction_attributes_and_external_references(queries):
    first = relation("links_out", page_size=1)
    assert first["has_more"] is True
    item = first["items"][0]
    assert item["source"]["span_id"] == "root"
    assert item["target"]["trace_id"] == "trace-b"
    assert item["span"]["span_id"] == "target"
    assert item["link"]["attributes"] == {"reason": "async"}
    external = relation("links_out", page=2, page_size=1)["items"][0]
    assert external["span"] is None
    assert external["target"]["trace_id"] == "other-app"


def test_links_in_matches_both_ids_in_same_link_object(queries):
    _, span, _ = queries
    span.rows.append(
        {
            "trace_id": "false",
            "span_id": "false",
            "links": [{"trace_id": "trace-a", "span_id": "another"}, {"trace_id": "another", "span_id": "root"}],
        }
    )
    result = relation("links_in", page_size=1)
    assert result["has_more"] is False
    assert result["items"][0]["source"] == {"trace_id": "trace-c", "span_id": "incoming"}
    assert result["items"][0]["link"]["attributes"] == {"reason": "retry"}


def test_query_failure_is_not_empty_data(queries):
    proxy, _, _ = queries
    proxy._get_query.side_effect = RuntimeError("upstream down")
    with pytest.raises(RuntimeError, match="upstream down"):
        apm_trace.span_list({**APP, "trace_id": "trace-a"})


def test_application_is_looked_up_in_explicit_tenant():
    with patch.object(apm_trace.apm_models.ApmApplication.objects, "filter") as lookup:
        lookup.return_value.first.return_value = None
        with pytest.raises(Exception, match="指定租户"):
            apm_trace._make_proxy(APP)
        lookup.assert_called_once_with(bk_tenant_id="tenant-a", bk_biz_id=2, app_name="checkout")


def test_candidate_lookup_deduplicates_and_retains_partial_warning(monkeypatch):
    monkeypatch.setattr(apm_trace, "_precalc_tables", lambda: ["one", "two", "broken"])
    query = Mock(
        side_effect=[
            [{"biz_id": "2", "app_name": "checkout"}],
            [{"biz_id": 2, "app_name": "checkout"}],
            RuntimeError("down"),
        ]
    )
    monkeypatch.setattr(apm_trace, "_query_application_candidates", query)
    app = SimpleNamespace(id=1, bk_tenant_id="tenant-a", bk_biz_id=2, app_name="checkout", app_alias="订单")
    with patch.object(apm_trace.apm_models.ApmApplication.objects, "filter") as lookup:
        lookup.return_value.order_by.return_value.__getitem__.return_value = [app]
        result = apm_trace.trace_application_list({"bk_tenant_id": "tenant-a", "trace_id": "trace-a", "bk_biz_id": 2})
    assert len(result["data"]["items"]) == 1
    assert result["data"]["end_time"] - result["data"]["start_time"] == 7 * 86400
    assert lookup.call_args.kwargs == {"bk_tenant_id": "tenant-a"}
    assert len(lookup.call_args.args[0].children) == 2
    assert {warning["code"] for warning in result["warnings"]} == {
        "PRECALCULATION_DELAY",
        "PRECALCULATION_QUERY_FAILED",
    }


def test_no_precalculation_is_reported_not_treated_as_absent_trace(monkeypatch):
    monkeypatch.setattr(apm_trace, "_precalc_tables", lambda: [])
    result = apm_trace.trace_application_list({"bk_tenant_id": "tenant-a", "trace_id": "trace-a"})
    assert result["data"]["items"] == []
    assert result["warnings"][1]["code"] == "PRECALCULATION_UNAVAILABLE"


@pytest.fixture
def candidate_provider(monkeypatch):
    source = Mock()
    monkeypatch.setattr("bkmonitor.data_source.load_data_source", Mock(return_value=source))
    provider = Mock()
    provider.use_unify_query.return_value = True
    provider._query_reference_using_unify_query.return_value = [{"biz_id": "2", "app_name": "checkout"}]
    monkeypatch.setattr("bkmonitor.data_source.unify_query.query.UnifyQuery", Mock(return_value=provider))
    return provider, source


def test_candidate_query_pushes_tenant_business_and_time_to_storage(candidate_provider):
    provider, source = candidate_provider
    result = apm_trace._query_application_candidates(
        "precalc", {**APP, "trace_id": "trace-a", "start_time": 100, "end_time": 200}
    )
    assert result == [{"biz_id": "2", "app_name": "checkout"}]
    body = provider._query_reference_using_unify_query.call_args.kwargs
    assert body["start_time"] == 100000
    assert body["end_time"] == 200000
    config = source.call_args.kwargs
    assert config["filter_dict"] == {"trace_id__eq": "trace-a", "bk_tenant_id__eq": "tenant-a", "biz_id__eq": "2"}
    assert config["group_by"] == ["biz_id", "app_name"]
    assert config["is_time_agg"] is False


def test_native_span_query_routes_history_and_isolates_shared_application(monkeypatch):
    import time

    from apm.core.handlers.query.builder import QueryHelper
    from apm.core.handlers.query.proxy import QueryProxy

    now = int(time.time())
    monkeypatch.setattr(
        "apm.core.handlers.query.proxy._get_app_meta",
        lambda *_: {
            "table_id": "apm_global.shared_trace_0001",
            "retention": 7,
            "history_link_info": [{"table_id": "2_bkapm.trace_checkout", "switched_at": now - 3600, "retention": 7}],
        },
    )
    query_storage = Mock(return_value=[])
    monkeypatch.setattr(QueryHelper, "query", query_storage)
    params = apm_trace._validate(
        apm_trace.SpanListSerializer,
        {
            **APP,
            "trace_id": "trace-a",
            "start_time": now - 7200,
            "end_time": now,
            "page": 2,
            "page_size": 10,
        },
    )
    query = apm_trace._query(QueryProxy(2, "checkout"), params, "span")
    assert apm_trace._list(query, params) == []
    body = query_storage.call_args.kwargs["query_body"]
    assert {config["table"] for config in body["query_configs"]} == {
        "2_bkapm.trace_checkout",
        "apm_global.shared_trace_0001",
    }
    shared = next(config for config in body["query_configs"] if config["table"].startswith("apm_global."))
    assert "checkout" in str(shared["filter_dict"])
    assert "bk_biz_id__eq" in str(shared["filter_dict"])
    assert "trace-a" in str(shared["filter_dict"])
    assert (body["offset"], body["limit"]) == (10, 11)
    apm_trace._list(query, params, full=True, offset=0, limit=1)
    raw = query_storage.call_args.kwargs["query_body"]
    assert all(config["select"] == [] for config in raw["query_configs"])


def test_origin_summary_failure_propagates_instead_of_dropping_trace(monkeypatch):
    from apm.core.handlers.query.origin_trace_query import OriginTraceQuery
    from bkmonitor.data_source.utils.apm import TraceDatasourceTarget

    query = OriginTraceQuery([TraceDatasourceTarget.build(2, "checkout", "2_bkapm.trace_checkout", 7)])
    monkeypatch.setattr(query, "_query_list", Mock(return_value=[{"trace_id": "trace-a"}]))
    monkeypatch.setattr(query, "_query_trace_info", Mock(side_effect=RuntimeError("span storage down")))
    monkeypatch.setattr("apm.core.discover.precalculation.processor.PrecalculateProcessor", Mock())
    with pytest.raises(RuntimeError, match="span storage down"):
        apm_trace._list(query, {"start_time": 100, "end_time": 200})


def test_candidate_queries_continue_beyond_first_storage_page(monkeypatch):
    from bkmonitor.data_source.unify_query.query import UnifyQuery

    first = [{"biz_id": "2", "app_name": f"app-{i}"} for i in range(100)]
    monkeypatch.setattr("bkmonitor.data_source.load_data_source", Mock(return_value=Mock()))
    monkeypatch.setattr(UnifyQuery, "use_unify_query", Mock(return_value=True))
    monkeypatch.setattr(UnifyQuery, "process_data_sources", Mock())
    monkeypatch.setattr(
        UnifyQuery,
        "get_unify_query_params",
        Mock(
            side_effect=lambda *args: {
                "query_list": [{"reference_name": "a"}],
            }
        ),
    )
    monkeypatch.setattr(UnifyQuery, "process_unify_query_data", lambda self, params, data, end_time: data["records"])
    monkeypatch.setattr(UnifyQuery, "process_data_by_datasource", lambda self, rows: rows)
    monkeypatch.setattr(UnifyQuery, "query_reference", Mock(side_effect=AssertionError("不能依赖公共 offset 修复")))
    query = Mock(side_effect=[{"records": first}, {"records": [{"biz_id": "2", "app_name": "last"}]}])
    monkeypatch.setattr("bkmonitor.data_source.unify_query.query.api.unify_query.query_reference", query)
    results = apm_trace._query_application_candidates(
        "precalc", {**APP, "trace_id": "trace-a", "start_time": 100, "end_time": 200}
    )
    assert len(results) == 101
    assert [call.kwargs["query_list"][0]["from"] for call in query.call_args_list] == [0, 100]


def test_candidate_query_retains_native_datasource_path(candidate_provider):
    provider, _ = candidate_provider
    provider.use_unify_query.return_value = False
    provider.query_reference.return_value = []
    assert (
        apm_trace._query_application_candidates(
            "precalc", {**APP, "trace_id": "trace-a", "start_time": 100, "end_time": 200}
        )
        == []
    )
    provider._query_reference_using_unify_query.assert_not_called()
    assert provider.query_reference.call_args.kwargs["offset"] == 0


def test_precalculation_table_config_includes_overrides_and_deduplicates():
    with patch.object(
        apm_trace.apm_models.DataLink.objects,
        "values_list",
        return_value=[
            {"cluster": [{"table_name": "one"}]},
            None,
            {"cluster": [{"table_name": "two"}, {"table_name": "one"}]},
        ],
    ):
        assert apm_trace._precalc_tables() == ["one", "two"]
