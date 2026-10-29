"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import datetime
import json
from unittest.mock import patch

import pytest

from bkmonitor.data_source import q_to_dict
from bkmonitor.data_source.utils.apm import LevelTarget, TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.handlers.query.base import equal_filter
from rum_web.handlers.query.fallback import BaseFallbackRumQuery
from rum_web.handlers.query.session import SessionQuery
from rum_web.handlers.query.view import ViewQuery


def target(level=None):
    return TraceDatasourceTarget.build(
        bk_biz_id=2,
        app_name="test",
        table_id="bk_rum.test.span",
        retention=3,
        levels=[LevelTarget(level, [f"bk_rum.test.{level}"])] if level else [],
    )


COMMON = {
    "app_name",
    "resource.service.name",
    "resource.service.version",
    "resource.deployment.environment.name",
    "resource.telemetry.sdk.name",
    "resource.telemetry.sdk.version",
    "resource.telemetry.sdk.language",
    "resource.device.type",
    "resource.user_agent.name",
    "resource.user_agent.version",
    "resource.user_agent.os.name",
    "attributes.network.connection.type",
    "attributes.network.effective_type",
    "attributes.user.id",
    "attributes.session.id",
}
COMPUTED = {
    "trace_count",
    "error_count",
    "action_count",
    "frustration_count",
    "request_count",
    "request_error_count",
    "long_task_count",
    "is_active",
    "close_reason",
    "close_time",
    "duration",
    "start_time",
}
VIEW_RAW = {
    "attributes.view.id",
    "attributes.view.name",
    "attributes.view.loading_type",
    "attributes.view.url",
    "attributes.view.previous",
    "attributes.view.url_template",
    "attributes.view.previous_url_template",
    "attributes.view.loading_time",
}
VIEW_DERIVED = {f"web_vitals.{metric}" for metric in ("cls", "lcp", "fcp", "inp", "ttfb")}
SESSION_DERIVED = {"view_count", "enter_url_template", "exit_url_template"}


@pytest.mark.parametrize(
    "mode, expected_raw, expected_derived",
    [
        ("session", COMMON | {"attributes.session.has_replay"}, COMPUTED | SESSION_DERIVED),
        ("view", COMMON | VIEW_RAW, COMPUTED | VIEW_DERIVED),
    ],
)
def test_field_catalog_matches_retained_table_without_uq(mode, expected_raw, expected_derived):
    handler = RumLevelHandlerFactory.create(mode, [target()])
    with patch.object(BaseQuery, "_query_fields", side_effect=AssertionError("不得发现原始表字段")):
        config = handler.view_config(None, None)
    fields = {field["field_name"]: field for field in config["fields"]}
    assert fields.keys() == expected_raw | expected_derived
    for name in expected_raw:
        assert fields[name]["is_agg"] and fields[name]["is_searchable"] and fields[name]["is_real"]
        assert fields[name]["supported_operations"]
    for name in expected_derived:
        assert not fields[name]["is_agg"] and not fields[name]["is_searchable"] and not fields[name]["is_real"]
        assert fields[name]["supported_operations"] == []
    grouped = [name for group in config["groups"] for name in group["field_names"]]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == fields.keys()
    assert set(config["display_fields"]) <= fields.keys()
    assert config["display_fields"][0] == f"attributes.{mode}.id"
    assert set(config["resident_fields"]) <= expected_raw
    resident_fields_by_mode: dict[str, list[str]] = {
        "session": [
            "attributes.session.id",
            "attributes.user.id",
            "resource.user_agent.name",
            "resource.user_agent.os.name",
        ],
        "view": [
            "attributes.view.id",
            "attributes.view.url_template",
            "attributes.view.loading_type",
            "attributes.user.id",
        ],
    }
    assert config["resident_fields"] == resident_fields_by_mode[mode]
    assert all("supported_span_types" not in group for group in config["groups"])
    assert fields["duration"]["field_unit"] == "us"
    assert fields["close_time"]["field_display_type"] == "datetime"
    assert fields["frustration_count"]["field_type"] == "long"


@pytest.mark.parametrize(
    "query_class, mode, phase", [(SessionQuery, "session", "start"), (ViewQuery, "view", "update")]
)
def test_analysis_uses_required_event_and_keeps_user_filters(query_class, mode, phase):
    query = query_class([target()])
    filters = [equal_filter("attributes.user.id", ["alice"])]
    original = copy.deepcopy(filters)
    configs = query.get_queries(filters, 'resource.service.version:"1"')
    assert filters == original
    config = configs[0].query
    where = json.dumps(q_to_dict(config.where))
    assert f"attributes.{mode}.phase" in where and phase in where
    assert "attributes.span_type" in where and mode in where
    assert "alice" in where and "attributes.user.id" in where
    assert config.raw_query_string == 'resource.service.version:"1"'
    assert config.table_name == "bk_rum.test.span"


@pytest.mark.parametrize("query_class, mode", [(SessionQuery, "session"), (ViewQuery, "view")])
def test_list_collapses_before_pagination_and_does_not_filter_analysis_phase(query_class, mode):
    query = query_class([target()])
    with (
        patch.object(BaseQuery, "_query_list", return_value=[{query.group_field: "id1"}]) as execute,
        patch.object(query, "query_summaries", return_value={"id1": {}}),
    ):
        result = query.query_list(10, 20, 30, 10, [equal_filter("attributes.user.id", ["alice"])], "hello")
    queries, start, end, offset, limit = execute.call_args.args
    assert (start, end, offset, limit) == (10, 20, 30, 10)
    assert queries[0].query.distinct == f"attributes.{mode}.id"
    assert queries[0].query.order_by == ["start_time desc"]
    where = json.dumps(q_to_dict(queries[0].query.where))
    assert "attributes.span_type" not in where
    assert f"attributes.{mode}.id__exists" in q_to_dict(queries[0].query.where)
    assert f"attributes.{mode}.id" in where
    assert f"attributes.{mode}.phase" not in where
    assert "alice" in where and queries[0].query.raw_query_string == "hello"
    assert result[0][query.group_field] == "id1"


@pytest.mark.parametrize("query_class, mode", [(SessionQuery, "session"), (ViewQuery, "view")])
def test_precomputed_tables_enable_fields_and_skip_fold_and_supplement(query_class, mode):
    handler = RumLevelHandlerFactory.create(mode, [target(mode)])
    assert handler.query.use_precomputed
    fields = handler.query.query_fields(None, None)
    assert fields["error_count"]["is_agg"] and fields["error_count"]["is_searchable"]
    assert fields["frustration_count"]["is_agg"] and fields["frustration_count"]["is_searchable"]
    configs = handler.query.get_queries([equal_filter("error_count", [1])])
    assert configs[0].query.table_name == f"bk_rum.test.{mode}"
    assert configs[0].query.time_field == "start_time"
    assert "attributes.span_type" not in json.dumps(q_to_dict(configs[0].query.where))
    with patch.object(handler.query.level_query, "query_list", return_value=[{"error_count": 4}]) as query_list:
        with patch.object(handler.query, "query_summaries", side_effect=AssertionError("不得补查")):
            assert handler.list_records(10, 20, sort=["-error_count"]) == [{"error_count": 4}]
    assert query_list.call_args.args[-1] == ["-error_count"]
    mixed = query_class([target(mode), target()])
    assert not mixed.use_precomputed
    assert all(config.query.table_name.endswith(".span") for config in mixed.get_queries())


@pytest.mark.parametrize("query_class, mode", [(SessionQuery, "session"), (ViewQuery, "view")])
@pytest.mark.parametrize("precomputed", [False, True])
def test_option_values_use_list_scope(query_class, mode, precomputed):
    query = query_class([target(mode if precomputed else None)])
    filters = [equal_filter("resource.user_agent.name", ["Chrome"])]
    original = copy.deepcopy(filters)
    values = {"attributes.user.id": ["alice"]}
    with patch.object(BaseQuery, "_query_option_values", return_value=values) as execute:
        assert query.query_option_values(10, 20, ["attributes.user.id"], 5, filters, "alice") == values
    queries, start, end, fields, limit = execute.call_args.args
    assert (start, end, fields, limit) == (10, 20, ["attributes.user.id"], 5)
    config = queries[0].query
    where = q_to_dict(config.where)
    assert filters == original
    assert config.raw_query_string == "alice"
    assert "Chrome" in json.dumps(where)
    assert "attributes.span_type" not in json.dumps(where)
    assert f"attributes.{mode}.phase" not in json.dumps(where)
    if precomputed:
        assert config.table_name == f"bk_rum.test.{mode}"
        assert config.time_field == "start_time"
        assert f"attributes.{mode}.id__exists" not in where
    else:
        assert config.table_name == "bk_rum.test.span"
        assert f"attributes.{mode}.id__exists" in where


def test_original_field_statistics_and_option_protocol():
    handler = RumLevelHandlerFactory.create("session", [target()])
    with patch.object(
        handler.query, "query_field_aggregated_value", side_effect=lambda *args: 4 if args[3] == "count" else 2
    ):
        with patch.object(
            handler.query, "query_field_topk", return_value=[{"attributes.session.has_replay": "false", "_result_": 3}]
        ):
            result = handler.field_topk(1, 2, "attributes.session.has_replay")
    assert result["distinct_count"] == 2
    assert result["list"][0]["value"] is False
    assert float(result["list"][0]["proportions"]) == 75
    with patch.object(
        handler.query, "query_option_values", return_value={"attributes.session.has_replay": ["false", "true"]}
    ):
        assert handler.get_fields_option_values(1, 2, ["attributes.session.has_replay"]) == {
            "attributes.session.has_replay": [False, True]
        }


def test_supplement_batches_by_page_ids_not_rows():
    query = SessionQuery([target()])
    ids = ["s1", "s2"]
    captured_metrics = []
    captured_records = []

    def execute(table_id, query_body):
        config = query_body["query_configs"][0]
        filters = config["filter_dict"]
        assert filters["attributes.session.id"] == ids
        assert query_body["limit"] == (query.QUERY_MAX_LIMIT if config["metrics"] else len(ids))
        if config["metrics"]:
            captured_metrics.append(config)
            if len(config["group_by"]) == 2:
                return [{"attributes.session.id": "s1", "attributes.span_type": "error", "_result_": 2}]
            metric = config["metrics"][0]
            values = {
                ("start_time", "min"): 100,
                ("end_time", "max"): 900,
                ("links.trace_id", "count"): 3,
                ("attributes.view.id", "distinct"): 2,
            }
            return [{"attributes.session.id": "s1", "_result_": values.get((metric["field"], metric["method"]), 1)}]
        captured_records.append(config)
        if filters.get("attributes.span_type") == ["session"]:
            return [{"attributes": {"session.id": "s1", "session.phase": "end"}, "end_time": 850}]
        return [
            {
                "attributes.session.id": "s1",
                "attributes.view.url_template": "/first" if config["order_by"] == ["start_time"] else "/last",
            }
        ]

    with patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute):
        summaries = query.query_summaries(ids)
    assert len(captured_metrics) == 8 and len(captured_records) == 3
    assert summaries["s1"]["view_count"] == 2
    assert summaries["s1"]["error_count"] == 2
    assert summaries["s1"]["frustration_count"] == 1
    assert summaries["s1"]["enter_url_template"] == "/first"
    assert summaries["s1"]["exit_url_template"] == "/last"
    assert summaries["s1"]["snapshot"]["attributes.session.phase"] == "end"
    error_query = next(config for config in captured_metrics if "status.code" in config["filter_dict"])
    assert error_query["filter_dict"]["status.code"] == [2]
    assert error_query["filter_dict"]["attributes.resource.type"] == ["xhr", "fetch"]


def test_vitals_use_latest_snapshot_per_metric_and_preserve_zero():
    query = ViewQuery([target()])

    def execute(table_id, query_body):
        config = query_body["query_configs"][0]
        if config["metrics"]:
            return []
        metric = config["filter_dict"].get("attributes.vital.metric", [None])[0]
        if metric:
            assert config["order_by"] == ["end_time desc"]
            return [{"attributes.view.id": "v1", "attributes.vital.value": 0}] if metric == "cls" else []
        assert config["order_by"] == ["attributes.view.version desc", "end_time desc"]
        return [{"attributes.view.id": "v1", "attributes.view.phase": "update", "end_time": 400}]

    with patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute):
        summaries = query.query_summaries(["v1"])
    assert summaries["v1"]["web_vitals.cls"] == 0
    assert "web_vitals.lcp" not in summaries["v1"]
    row = query.fill_records([{"attributes.view.id": "v1"}], summaries)[0]
    assert row["web_vitals.cls"] == 0 and row["web_vitals.lcp"] is None
    assert row["frustration_count"] == 0
    assert row["is_active"] is True and row["close_time"] is None and row["close_reason"] is None


@pytest.mark.parametrize("mode", ["session", "view"])
def test_frustration_count_uses_one_document_count_for_all_types(mocker, mode):
    handler = RumLevelHandlerFactory.create(mode, [target()])
    group_field = f"attributes.{mode}.id"
    matched_queries = []

    def execute(table_id, query_body):
        config = query_body["query_configs"][0]
        filters = config["filter_dict"]
        types = filters.get("attributes.action.frustration.type")
        if types is None:
            return []
        assert filters == {
            f"{group_field}": ["id1", "id2"],
            "attributes.span_type": ["action"],
            "attributes.action.frustration.type": types,
        }
        assert set(types) == {"rage_click", "dead_click", "error_click"}
        # 数组只用于筛选；按文档计数且只按实体分组，不累加各类型的桶。
        assert config["group_by"] == [group_field]
        assert len(config["metrics"]) == 1
        assert config["metrics"][0]["field"] == "_index"
        assert config["metrics"][0]["method"].lower() == "count"
        matched_queries.append(config)
        return [{group_field: "id1", "_result_": 2}]

    query_backend = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute)
    query_backend.assert_not_called()
    assert isinstance(handler.query, BaseFallbackRumQuery)
    summaries = handler.query.query_summaries(["id1", "id2"])
    rows = handler.query.fill_records([{group_field: "id1"}, {group_field: "id2"}], summaries)
    assert len(matched_queries) == 1
    assert [row["frustration_count"] for row in rows] == [2, 0]


def test_list_assembly_preserves_page_order_and_does_not_invent_timeout():
    records = [{"attributes": {"session.id": "s2", "user.id": "bob"}}, {"attributes.session.id": "s1"}]
    original = copy.deepcopy(records)
    rows = SessionQuery([target()]).fill_records(
        records,
        {
            "s1": {
                "start_time": 0,
                "end_time": 100,
                "view_count": 2,
                "snapshot": {"attributes.session.phase": "end", "end_time": 100},
            }
        },
    )
    assert records == original
    assert [row["attributes.session.id"] for row in rows] == ["s2", "s1"]
    assert rows[0]["is_active"] is None and rows[0]["duration"] is None
    assert rows[0]["close_reason"] is None
    assert rows[1]["duration"] == 100 and rows[1]["start_time"] == 0
    assert rows[1]["is_active"] is False and rows[1]["close_reason"] == "normal" and rows[1]["close_time"] == 100


@pytest.mark.parametrize("mode", ["view", "session"])
def test_empty_page_avoids_supplement(mode):
    handler = RumLevelHandlerFactory.create(mode, [target()])
    assert isinstance(handler.query, BaseFallbackRumQuery)
    with patch.object(handler.query, "query_list", return_value=[]):
        with patch.object(handler.query, "query_summaries", side_effect=AssertionError("空页不得补查")):
            assert handler.list_records(1, 2) == []


def test_resource_to_uq_list_and_supplement(mocker):
    from rum_web.query.resources import RumRecordsResource
    from rum_web.query.serializers import RumRecordsRequestSerializer

    app = mocker.Mock(bk_biz_id=2, app_name="test", span_result_table_id="bk_rum.test.span", retention_days=3)
    mocker.patch("rum_web.query.resources._get_application", return_value=app)
    captured = []

    def execute(table_id, query_body):
        body = query_body
        captured.append(body)
        config = body["query_configs"][0]
        assert config["table"] == "bk_rum.test.span"
        where = json.dumps(config["filter_dict"])
        if config["metrics"]:
            metric = config["metrics"][0]
            if len(config["group_by"]) == 2:
                return [{"attributes.view.id": "v1", "attributes.span_type": "action", "_result_": 7}]
            if "attributes.action.frustration.type" in where:
                return [{"attributes.view.id": "v1", "_result_": 2}]
            values = {"start_time": 100, "end_time": 900, "links.trace_id": 2}
            return [{"attributes.view.id": "v1", "_result_": values.get(metric["field"], 0)}]
        assert config["distinct"] == "attributes.view.id"
        if "attributes.vital.metric" in where:
            return [{"attributes.view.id": "v1", "attributes.vital.value": 0.05}] if "cls" in where else []
        if "attributes.span_type" in where:
            return [{"attributes": {"view.id": "v1", "view.phase": "end", "view.name": "首页"}, "end_time": 800}]
        assert body["offset"] == 10 and body["limit"] == 2
        return [
            {"attributes": {"view.id": "v1", "view.url_template": "/home", "span_type": "resource"}, "start_time": 700}
        ]

    mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute)
    serializer = RumRecordsRequestSerializer(
        data={
            "bk_biz_id": 2,
            "app_name": "test",
            "mode": "view",
            "start_time": 10,
            "end_time": 20,
            "offset": 10,
            "limit": 2,
        }
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    assert isinstance(data, dict)
    response = RumRecordsResource().perform_request(data)
    row = response["list"][0]
    assert row["attributes.view.name"] == "首页"
    assert row["attributes.view.url_template"] == "/home"
    assert row["start_time"] == 100 and row["duration"] == 800
    assert row["action_count"] == 7 and row["trace_count"] == 2
    assert row["frustration_count"] == 2
    assert row["web_vitals.cls"] == 0.05 and row["web_vitals.lcp"] is None
    assert row["is_active"] is False and row["close_time"] == 800
    assert len(captured) == 14


def test_shared_targets_keep_application_isolation():
    from constants.apm import ApmGlobalTablePrefix

    sources = [
        TraceDatasourceTarget.build(2, "one", ApmGlobalTablePrefix.SHARED + "test"),
        TraceDatasourceTarget.build(2, "two", ApmGlobalTablePrefix.SHARED + "test"),
    ]
    query = SessionQuery(sources)
    for config, app in zip(query.get_queries(), ("one", "two")):
        where = json.dumps(q_to_dict(config.query.where))
        assert "app_name" in where and app in where and "bk_biz_id" in where


@pytest.mark.parametrize("offset, limit", [(-1, 10), (0, 0)])
def test_records_serializer_rejects_invalid_pagination(offset, limit):
    from rum_web.query.serializers import RumRecordsRequestSerializer

    serializer = RumRecordsRequestSerializer(
        data={
            "bk_biz_id": 2,
            "app_name": "test",
            "mode": "view",
            "start_time": 10,
            "end_time": 20,
            "offset": offset,
            "limit": limit,
        }
    )
    assert not serializer.is_valid()


def test_records_serializer_accepts_page_without_extra_query_cap():
    from rum_web.query.serializers import RumRecordsRequestSerializer

    serializer = RumRecordsRequestSerializer(
        data={
            "bk_biz_id": 2,
            "app_name": "test",
            "mode": "view",
            "start_time": 10,
            "end_time": 20,
            "offset": 0,
            "limit": 1001,
        }
    )
    assert serializer.is_valid(), serializer.errors
    query = ViewQuery([target()])
    with patch.object(query.span_query, "query_group_list", return_value=[]) as execute:
        assert query.query_list(10, 20, 0, 1001) == []
    assert execute.call_args.args[4] == 1001


@pytest.mark.parametrize("mode", ["span", "session", "view"])
def test_semantic_catalog_survives_metadata_failure(mode):
    from semconv.rum.trace import SpanSpec
    from semconv.rum.session import SessionSpec
    from semconv.rum.view import ViewSpec

    handler = RumLevelHandlerFactory.create(mode, [target(mode) if mode != "span" else target()])
    spec = {"span": SpanSpec, "session": SessionSpec, "view": ViewSpec}[mode]
    with patch.object(BaseQuery, "_query_fields", side_effect=RuntimeError("UQ unavailable")):
        fields = handler.query.query_fields(None, None)
    assert fields.keys() == {field.get_full_field_name() for field in spec.fields()}
    assert fields["attributes.user.id"]["is_real"]
    assert fields["attributes.user.id"]["field_alias"]


def test_statistical_supplement_uses_existing_failed_window_behavior():
    query = SessionQuery([target()])
    q = query._get_q("end_time")
    with patch(
        "bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=RuntimeError("UQ unavailable")
    ):
        assert query._query_metric_records(q, "_index", "count", 2) == []


def test_summaries_skip_invalid_and_unrequested_ids():
    query = SessionQuery([target()])
    records = [
        {},
        {query.group_field: None},
        {query.group_field: 42},
        {query.group_field: []},
        {query.group_field: "unrequested"},
        {query.group_field: "s1", "_result_": 3},
    ]

    summaries = query._collect_summaries(
        ["s1"], [lambda: query._project_records(records, ["s1"], {"trace_count": "_result_"})]
    )

    assert summaries == {"s1": {"trace_count": 3}}


def test_span_counts_skip_invalid_types_and_keep_multiple_counts(mocker):
    query = SessionQuery([target()])
    mocker.patch.object(
        query,
        "_query_metric_records",
        return_value=[
            {query.group_field: "s1", "attributes.span_type": None, "_result_": 99},
            {query.group_field: "s1", "attributes.span_type": [], "_result_": 99},
            {query.group_field: "s1", "attributes.span_type": "action", "_result_": 2},
            {query.group_field: "s1", "attributes.span_type": "error", "_result_": 3},
            {query.group_field: "unrequested", "attributes.span_type": "action", "_result_": 4},
        ],
    )

    assert query._query_span_counts(["s1"], query._get_q("end_time")) == {"s1": {"action_count": 2, "error_count": 3}}


@pytest.mark.parametrize("method, field", [("MIN", "start_time"), ("MAX", "end_time")])
@pytest.mark.parametrize("query_class", [SessionQuery, ViewQuery])
def test_grouped_time_extrema_preserve_record_ids(mocker, method, field, query_class):
    query = query_class([target()])
    group_field = query.group_field
    records = [{group_field: "id1", "_result_": 100}, {group_field: "id2", "_result_": 200}]

    def execute(table_id, query_body):
        config = query_body["query_configs"][0]
        reference = config["reference_name"]
        assert query_body["expression"] == reference
        assert config["metrics"][0]["alias"] == reference
        assert config["metrics"][0]["field"] == field
        assert config["metrics"][0]["method"] == method.lower()
        assert config["group_by"] == [group_field]
        return records

    mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute)

    q = query._get_q("end_time")
    assert query._query_metric_records(q, field, method.lower(), 2) == records


@pytest.mark.parametrize("query_class", [SessionQuery, ViewQuery])
@pytest.mark.parametrize("source_count, shared", [(1, False), (2, False), (1, True), (2, True)])
def test_summary_builders_preserve_sources_windows_and_metric_values(mocker, query_class, source_count, shared):
    from constants.apm import ApmGlobalTablePrefix

    sources: list[TraceDatasourceTarget] = [
        TraceDatasourceTarget.build(
            2,
            f"app{index}",
            ApmGlobalTablePrefix.SHARED + "test" if shared else f"bk_rum.app{index}.span",
            retention=3,
        )
        for index in range(source_count)
    ]
    query = query_class(sources)
    requests: list[dict] = []
    now = datetime.datetime(2026, 10, 29, 12, 0, 0)
    now_seconds: int = int(now.timestamp())

    def execute(table_id, query_body):
        requests.append(query_body)
        assert query_body["bk_biz_id"] == 2
        assert len(query_body["query_configs"]) == source_count
        assert query_body["start_time"] == (now_seconds - 3 * 86400) * 1000
        assert query_body["end_time"] == (now_seconds + (0 if query_body["instant"] else 5)) * 1000
        for config, target in zip(query_body["query_configs"], sources):
            assert config["table"] == target.table_id
            assert config["time_field"] == "end_time"
            assert config["filter_dict"][f"{query.group_field}"] == ["id1", "id2"]
            if shared:
                assert config["filter_dict"]["bk_biz_id__eq"] == 2
                assert config["filter_dict"]["app_name__eq"] == target.app.app_name
            else:
                assert "bk_biz_id__eq" not in config["filter_dict"]
                assert "app_name__eq" not in config["filter_dict"]
            assert len(config["metrics"]) <= 1
        config = query_body["query_configs"][0]
        if not config["metrics"]:
            return []
        return [
            {query.group_field: "id1", "attributes.span_type": "action", "_result_": 3.4567},
            {query.group_field: "id2", "attributes.span_type": "error", "_result_": None},
        ]

    with patch("bkmonitor.data_source.utils.query.datetime", wraps=datetime) as clock:
        clock.datetime.now.return_value = now
        mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=execute)
        summaries = query.query_summaries(["id1", "id2"])

    assert len(requests) == (11 if query.MODE == "session" else 13)
    assert summaries["id1"]["trace_count"] == 3
    assert summaries["id1"]["start_time"] == 3.46
    assert summaries["id1"]["action_count"] == 3
    assert summaries["id2"]["trace_count"] is None
    assert summaries["id2"]["start_time"] is None
    count_query = next(
        request["query_configs"][0]
        for request in requests
        if request["query_configs"][0]["metrics"]
        and request["query_configs"][0]["metrics"][0]["field"] == "links.trace_id"
    )
    assert count_query["filter_dict"] == {
        f"{query.group_field}": ["id1", "id2"],
        **({"bk_biz_id__eq": 2, "app_name__eq": "app0"} if shared else {}),
    }


@pytest.mark.parametrize("mode", ["session", "view"])
@pytest.mark.parametrize("precomputed", [False, True])
@pytest.mark.parametrize("span_id", ["first", "last"])
def test_business_detail_matches_each_lifecycle_span(mode, precomputed, span_id):
    from rum_web.handlers.level.span import SpanLevelHandler

    canonical = {
        "span_id": "first",
        "app_name": "test",
        "start_time": 1000,
        "end_time": 1000,
        "attributes": {
            "span_type": mode,
            f"{mode}.id": "business-id",
            f"{mode}.phase": "start",
            "view.version": 1,
            "view.started_at": 1,
        },
    }
    latest = {
        "span_id": "last",
        "app_name": "test",
        "start_time": 5000,
        "end_time": 5000,
        "attributes": {
            "span_type": mode,
            f"{mode}.id": "business-id",
            f"{mode}.phase": "end",
            "view.version": 2,
            "view.started_at": 1,
            "user.id": "alice",
        },
    }
    related = [canonical, latest]
    if mode == "session":
        related += [
            {"span_id": "v1", "start_time": 1200, "attributes": {"span_type": "view", "view.url_template": "/enter"}},
            {"span_id": "v2", "start_time": 4000, "attributes": {"span_type": "view", "view.url_template": "/exit"}},
        ]
    data_source = target(mode if precomputed else None)
    business_handler = RumLevelHandlerFactory.create(mode, [data_source])
    span_handler = SpanLevelHandler([data_source])

    def execute(queries, start, end, offset, limit):
        config = queries[0].query
        where = q_to_dict(config.where)
        assert config.table_name == "bk_rum.test.span"
        assert f"attributes.{mode}.phase" not in json.dumps(where)
        assert (start, end, offset) == (None, None, 0)
        if limit != 1:
            return related
        if "span_id__eq" in where:
            return [canonical if span_id == "first" else latest]
        assert where[f"attributes.{mode}.id__eq"] == ["business-id"]
        assert where["attributes.span_type__eq"] == [mode]
        return [canonical]

    with patch.object(BaseQuery, "_query_list", side_effect=execute):
        business_detail = business_handler.record_detail("business-id")
        span_detail = span_handler.record_detail(span_id)
    assert business_detail == span_detail
    assert business_detail["origin_data"] == canonical
    if mode == "session":
        assert business_detail["sections"] == []
        items = {item["field_name"]: item["value"] for item in business_detail["overview"]["items"]}
        assert list(items) == [
            "display.span_type",
            "app_name",
            "enter_url_template",
            "exit_url_template",
            "start_time",
            "end_time",
            "attributes.user.id",
            "resource.deployment.environment.name",
        ]
        assert items["display.span_type"] == "Session"
        assert items["enter_url_template"] == "/enter"
        assert items["exit_url_template"] == "/exit"
        assert (items["start_time"], items["end_time"], items["attributes.user.id"]) == (1000, 5000, "alice")
