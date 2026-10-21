"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from bkmonitor.data_source.format import flatten_dict_data
from bkmonitor.data_source.unify_query.builder import QueryHelper
from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget
from bkmonitor.iam import ActionEnum, ResourceEnum
from rum_web.handlers.builder.span import build as build_span
from rum_web.handlers.builder.timeline import build as build_timeline
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.models.application import Application
from rum_web.query.resources import RumTimelineResource
from rum_web.query.serializers import RumTimelineRequestSerializer
from rum_web.query.views import SearchViewSet


def _span(span_id, span_type, start_time=1_000_000, view_id="view-1", attrs=None, **root):
    attributes = {"span_type": span_type, "session.id": "session-1", **(attrs or {})}
    if view_id is not None:
        attributes["view.id"] = view_id
    return {
        "span_id": span_id,
        "span_name": span_id,
        "start_time": start_time,
        "end_time": start_time,
        "elapsed_time": 0,
        "attributes": attributes,
        **root,
    }


def _view(span_id="view-span-1", view_id="view-1", started_at=1000, version=1, **root):
    return _span(
        span_id,
        "view",
        view_id=view_id,
        attrs={"view.started_at": started_at, "view.version": version, "view.phase": "start"},
        **root,
    )


def _handler():
    target = TraceDatasourceTarget.build(bk_biz_id=2, app_name="rum-demo", table_id="bk_rum.demo.span")
    return SpanLevelHandler([target])


class TestTimelineRequest:
    @pytest.mark.parametrize("scope", [{"session_id": "session-1"}, {"view_id": "view-1"}])
    def test_accepts_one_scope_without_time_window(self, scope):
        serializer = RumTimelineRequestSerializer(data={"bk_biz_id": 2, "app_name": "rum-demo", **scope})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {"bk_biz_id": 2, "app_name": "rum-demo", **scope}

    @pytest.mark.parametrize(
        "scope",
        [
            {},
            {"session_id": "session-1", "view_id": "view-1"},
            {"session_id": ""},
            {"view_id": " "},
            {"session_id": None},
        ],
    )
    def test_rejects_missing_ambiguous_or_empty_scope(self, scope):
        serializer = RumTimelineRequestSerializer(data={"bk_biz_id": 2, "app_name": "rum-demo", **scope})
        assert not serializer.is_valid()

    def test_protocol_only_exposes_application_and_scope(self):
        assert set(RumTimelineRequestSerializer().fields) == {"bk_biz_id", "app_name", "session_id", "view_id"}


class TestTimelineResource:
    @pytest.mark.parametrize("scope", [{"session_id": "session-1"}, {"view_id": "view-1"}])
    def test_uses_application_table_and_retention(self, mocker, scope):
        application = MagicMock(
            bk_biz_id=2, app_name="rum-demo", span_result_table_id="bk_rum.authorized.span", retention_days=14
        )
        get_application = mocker.patch("rum_web.query.resources._get_application", return_value=application)
        handler = MagicMock()
        handler.timeline.return_value = {"start_time": None, "end_time": None, "tree": [], "records": []}
        create = mocker.patch("rum_web.query.resources.RumLevelHandlerFactory.create", return_value=handler)

        result = RumTimelineResource().perform_request({"bk_biz_id": 2, "app_name": "rum-demo", **scope})

        get_application.assert_called_once_with(2, "rum-demo")
        mode, targets = create.call_args.args
        assert mode == "span"
        assert len(targets) == 1
        assert targets[0].table_id == "bk_rum.authorized.span"
        assert targets[0].retention == 14
        assert targets[0].app.bk_biz_id == 2
        assert targets[0].app.app_name == "rum-demo"
        handler.timeline.assert_called_once_with(session_id=scope.get("session_id"), view_id=scope.get("view_id"))
        assert result == handler.timeline.return_value

    def test_post_route_and_application_view_permission(self, mocker):
        routes = [route for route in SearchViewSet.resource_routes if route.endpoint == "timeline"]
        assert len(routes) == 1
        assert routes[0].method.upper() == "POST"
        assert routes[0].resource_class is RumTimelineResource

        permission = mocker.patch("rum_web.query.views.InstanceActionForDataPermission")
        view = SearchViewSet()
        view.action = "timeline"
        assert view.get_permissions() == [permission.return_value]
        permission.assert_called_once_with(
            "app_name",
            [ActionEnum.VIEW_RUM_APPLICATION],
            ResourceEnum.RUM_APPLICATION,
            get_instance_id=Application.get_application_id_by_app_name,
        )


class TestTimelineBuilder:
    def test_sorts_views_and_children_with_action_affinity(self):
        spans = [
            _view("view-span-2", "view-2", started_at=2000, start_time=10),
            _span("cross-view", "resource", 2_010_000, "view-2", {"action.id": "action-1"}),
            _span("resource-2", "resource", 1_040_000, attrs={"action.id": "action-1"}),
            _span("action", "action", 1_020_000, attrs={"action.id": "action-1"}),
            _span("resource-1", "resource", 1_030_000, attrs={"action.id": "action-1"}),
            _span("long-task", "long_task", 1_010_000, attrs={"action.id": "action-1"}),
            _span("error", "error", 1_050_000, attrs={"action.id": "action-1"}),
            _span("custom", "custom", 1_060_000, attrs={"action.id": "action-1"}),
            _span("websocket", "websocket", 1_070_000, attrs={"action.id": "action-1"}),
            _view(start_time=3_000_000),
        ]

        result = build_timeline(spans)

        assert result["tree"] == [
            {
                "span_id": "view-span-1",
                "children": [
                    {
                        "span_id": "action",
                        "children": [
                            {"span_id": "long-task"},
                            {"span_id": "resource-1"},
                            {"span_id": "resource-2"},
                            {"span_id": "error"},
                            {"span_id": "custom"},
                            {"span_id": "websocket"},
                        ],
                    }
                ],
            },
            {"span_id": "view-span-2", "children": [{"span_id": "cross-view"}]},
        ]
        assert {record["span_id"] for record in result["records"]} == {span["span_id"] for span in spans}

    def test_keeps_unmatched_members_and_actions_on_the_view(self):
        spans = [
            _view(),
            _span("other-action", "action", 1_015_000, attrs={"action.id": "action-2"}),
            _span("action", "action", 1_020_000, attrs={"action.id": "action-1"}),
            _span("future", "navigation", 1_025_000, attrs={"action.id": "action-1"}),
            _span("owned-error", "error", 1_030_000, attrs={"action.id": "action-1"}),
            _span("loose-error", "error", 1_040_000, attrs={"action.id": "missing"}),
            _span("plain", "long_task", 1_050_000),
        ]

        result = build_timeline(spans)

        assert result["tree"] == [
            {
                "span_id": "view-span-1",
                "children": [
                    {"span_id": "other-action"},
                    {
                        "span_id": "action",
                        "children": [{"span_id": "future"}, {"span_id": "owned-error"}],
                    },
                    {"span_id": "loose-error"},
                    {"span_id": "plain"},
                ],
            }
        ]

    def test_sorts_by_earliest_snapshot_start_and_keeps_lowest_version_node(self):
        spans = [
            _view("other-view", "view-2", started_at=1000),
            _view("view-update", started_at=500, version=2),
            _view("view-first", started_at=2000, version=1),
        ]

        result = build_timeline(spans)

        assert result["tree"] == [{"span_id": "view-first"}, {"span_id": "other-view"}]
        assert [record["span_id"] for record in result["records"]] == ["view-first", "other-view"]

    @pytest.mark.parametrize(
        "first_start,latest_start,expected_order",
        [
            (1200, None, ["other-view", "view-first"]),
            (1200, "invalid", ["other-view", "view-first"]),
            (1200, "NaN", ["other-view", "view-first"]),
            (1200, float("inf"), ["other-view", "view-first"]),
            (1200, float("-inf"), ["other-view", "view-first"]),
            (1200, 0, ["view-first", "other-view"]),
            (None, "invalid", ["view-first", "other-view"]),
        ],
        ids=["missing", "invalid", "nan", "positive-inf", "negative-inf", "zero", "all-invalid"],
    )
    def test_view_sort_ignores_invalid_snapshot_starts_and_preserves_zero(
        self, first_start, latest_start, expected_order
    ):
        spans = [
            _view("view-first", started_at=first_start, version=1),
            _view("view-update", started_at=latest_start, version=2),
            _view("other-view", "view-2", started_at=1000),
        ]

        result = build_timeline(spans)

        assert result["tree"] == [{"span_id": span_id} for span_id in expected_order]
        assert [record["span_id"] for record in result["records"]] == expected_order

    @pytest.mark.parametrize("flatten", [False, True])
    def test_collapses_view_snapshots_and_matches_record_detail(self, mocker, flatten):
        canonical = _view("view-first", version=1, start_time=1_020_000)
        latest = _view("view-last", version=3, start_time=1_100_000, end_time=1_100_000)
        latest["attributes"].update({"view.phase": "end", "view.loading_time": 75})
        old_vital = _span("vital-old", "vital", 1_040_000, attrs={"vital.metric": "lcp", "vital.value": 32})
        new_vital = _span("vital-new", "vital", 1_090_000, attrs={"vital.metric": "lcp", "vital.value": 52})
        spans = [latest, old_vital, canonical, new_vital]
        if flatten:
            spans = [flatten_dict_data(span) for span in spans]
            canonical = flatten_dict_data(canonical)
        before = deepcopy(spans)

        result = build_timeline(spans)

        assert result["tree"] == [{"span_id": "view-first"}]
        assert len(result["records"]) == 1
        assert spans == before
        assert result["records"][0]["origin_data"] == canonical
        assert result["records"][0] == build_span(canonical, spans)
        handler = _handler()
        mocker.patch.object(handler.query, "query_detail", return_value=canonical)
        mocker.patch.object(handler.query, "query_list", return_value=spans)
        assert result["records"][0] == handler.record_detail("view-first")

    def test_excludes_orphans_and_vitals(self):
        spans = [
            _view(),
            _span("orphan", "resource", view_id="absent"),
            _span("no-view", "action", view_id=None),
            _span("vital", "vital", attrs={"vital.metric": "lcp", "vital.value": 15}),
            {"attributes": {"span_type": "action", "view.id": "view-1"}},
        ]

        result = build_timeline(spans)

        assert result["tree"] == [{"span_id": "view-span-1"}]
        assert [record["span_id"] for record in result["records"]] == ["view-span-1"]

    def test_repeated_span_ids_only_create_one_node_and_detail(self):
        view = _view()
        resource = _span("resource", "resource", 1_010_000)

        result = build_timeline([view, resource, deepcopy(view), deepcopy(resource)])

        assert result["tree"] == [{"span_id": "view-span-1", "children": [{"span_id": "resource"}]}]
        assert [record["span_id"] for record in result["records"]] == ["view-span-1", "resource"]

    @pytest.mark.parametrize(
        "phases,expected_start,expected_end",
        [
            ([("start", 100), ("rotate", 50), ("end", 200), ("end", 300)], 50, 300),
            ([("start", 100)], 100, None),
            ([("end", 300)], None, 300),
            ([], None, None),
        ],
    )
    def test_session_boundaries_only_use_session_lifecycle(self, phases, expected_start, expected_end):
        spans = [
            _span(f"session-{index}", "session", timestamp, None, {"session.phase": phase})
            for index, (phase, timestamp) in enumerate(phases)
        ]
        spans.append(_view())

        result = build_timeline(spans)

        assert result["start_time"] == expected_start
        assert result["end_time"] == expected_end
        assert [record["span_id"] for record in result["records"]] == ["view-span-1"]

    def test_empty_query_is_stable(self):
        assert build_timeline([]) == {"start_time": None, "end_time": None, "tree": [], "records": []}


class TestTimelineHandler:
    @pytest.mark.parametrize("scope", [{"session_id": "session-1"}, {"view_id": "view-1"}])
    def test_queries_once_even_when_result_reaches_limit(self, mocker, scope):
        handler = _handler()
        spans = [
            _view(),
            *(_span(f"resource-{index}", "resource", 1_010_000 + index) for index in range(9999)),
        ]
        query = mocker.patch.object(
            handler.query, "query_list", side_effect=[spans, [_span("after-limit", "resource", 2_000_000)]]
        )
        total = mocker.patch.object(handler.query, "query_total")

        result = handler.timeline(**scope)

        assert len(result["records"]) == 10000
        assert "after-limit" not in {record["span_id"] for record in result["records"]}
        if "session_id" in scope:
            filters = [{"key": "attributes.session.id", "value": ["session-1"], "operator": FilterOperator.EQUAL}]
        else:
            filters = [
                {"key": "attributes.view.id", "value": ["view-1"], "operator": FilterOperator.EQUAL},
                {"key": "attributes.span_type", "value": ["session"], "operator": FilterOperator.NOT_EQUAL},
            ]
        query.assert_called_once_with(
            start_time=None,
            end_time=None,
            offset=0,
            limit=10000,
            filters=filters,
            sort=["start_time", "span_id"],
        )
        total.assert_not_called()

    def test_record_detail_and_timeline_reuse_vital_data(self, mocker):
        handler = _handler()
        mocker.patch.object(handler, "VIEW_RELATED_SPAN_LIMIT", 5)
        first = _view()
        latest = _view("latest", version=3, start_time=1_200_000, end_time=1_200_000)
        latest["attributes"]["view.phase"] = "end"
        spans = [
            first,
            _view("middle", version=2, start_time=1_020_000),
            _span("fcp", "vital", 1_050_000, attrs={"vital.metric": "fcp", "vital.value": 25}),
            _span("lcp", "vital", 1_100_000, attrs={"vital.metric": "lcp", "vital.value": 50}),
            latest,
        ]

        def query_records(**kwargs):
            sort = kwargs.get("sort") or handler.query.DEFAULT_SORT
            records = sorted(spans, key=lambda span: span["end_time"], reverse=sort[0].startswith("-"))
            return records[kwargs["offset"] : kwargs["offset"] + kwargs["limit"]]

        query = mocker.patch.object(handler.query, "query_list", side_effect=query_records)
        mocker.patch.object(handler.query, "query_detail", return_value=first)

        timeline = handler.timeline(session_id="session-1")
        detail = handler.record_detail("view-span-1")

        assert timeline["records"] == [detail]
        web_vitals = next(section for section in detail["sections"] if section["key"] == "web_vitals")
        assert web_vitals["data"]["fcp"]["attributes.vital.value"] == 25
        assert web_vitals["data"]["lcp"]["attributes.vital.value"] == 50
        assert query.call_count == 2
        assert [call.kwargs["offset"] for call in query.call_args_list] == [0, 0]

    @pytest.mark.parametrize("ended", [False, True])
    @pytest.mark.parametrize(
        "started_at",
        [(1234, 1234, 1234), (1400, 1234, 1500), (None, 1234, "nan")],
        ids=["same-start", "middle-is-earliest", "only-middle-is-valid"],
    )
    def test_single_view_uses_navigation_start_and_end_snapshot(self, mocker, ended, started_at):
        handler = _handler()
        first = _view(started_at=started_at[0], start_time=1_500_000)
        middle = _view("middle", started_at=started_at[1], version=2, start_time=1_650_000)
        latest = _view("latest", started_at=started_at[2], version=3, start_time=1_800_000, end_time=1_800_000)
        latest["attributes"]["view.phase"] = "end" if ended else "update"
        query = mocker.patch.object(handler.query, "query_list", return_value=[first, middle, latest])

        result = handler.timeline(view_id="view-1")

        assert result["start_time"] == 1_234_000
        assert result["end_time"] == (1_800_000 if ended else None)
        assert result["tree"] == [{"span_id": "view-span-1"}]
        assert query.call_args.kwargs["filters"] == [
            {"key": "attributes.view.id", "value": ["view-1"], "operator": FilterOperator.EQUAL},
            {"key": "attributes.span_type", "value": ["session"], "operator": FilterOperator.NOT_EQUAL},
        ]

    def test_missing_single_view_has_null_boundaries(self, mocker):
        handler = _handler()
        mocker.patch.object(handler.query, "query_list", return_value=[])
        assert handler.timeline(view_id="absent") == {
            "start_time": None,
            "end_time": None,
            "tree": [],
            "records": [],
        }

    @pytest.mark.parametrize(
        "started_at,end_time,expected_start,expected_end",
        [
            (None, None, None, None),
            (0, 0, 0, 0),
            ("invalid", "invalid", None, None),
            ("nan", "nan", None, None),
            (float("inf"), float("-inf"), None, None),
        ],
    )
    def test_missing_zero_and_invalid_view_boundaries(self, mocker, started_at, end_time, expected_start, expected_end):
        handler = _handler()
        view = _view(started_at=started_at, end_time=end_time)
        view["attributes"]["view.phase"] = "end"
        mocker.patch.object(handler.query, "query_list", return_value=[view])

        result = handler.timeline(view_id="view-1")

        assert result["start_time"] == expected_start
        assert result["end_time"] == expected_end


class TestTimelineQuery:
    def test_query_preserves_scope_filters_and_paging(self, mocker):
        query = _handler().query
        mocker.patch.object(query, "_get_time_range", return_value=(1000, 2000))
        early = _span("early", "resource", 100)
        late = _span("late", "resource", 200)
        execute = mocker.patch.object(QueryHelper, "query", return_value=[late, early])

        result = query.query_list(
            start_time=None,
            end_time=None,
            offset=0,
            limit=10000,
            filters=[
                {"key": "attributes.view.id", "value": ["view-1"], "operator": FilterOperator.EQUAL},
                {"key": "attributes.span_type", "value": ["session"], "operator": FilterOperator.NOT_EQUAL},
            ],
            sort=["start_time", "span_id"],
        )

        assert result == [early, late]
        body = execute.call_args.kwargs["query_body"]
        assert body["bk_biz_id"] == 2
        assert body["is_es_batch"] is False
        assert body["offset"] == 0
        assert body["limit"] == 10000
        assert body["start_time"] == 1000
        assert body["end_time"] == 2000
        assert body["is_time_align"] is False
        assert body["order_by"] == ["start_time", "span_id"]
        assert len(body["query_configs"]) == 1
        config = body["query_configs"][0]
        assert config["table"] == "bk_rum.demo.span"
        assert config["time_field"] == "end_time"
        assert config["filter_dict"] == {
            "attributes.view.id__eq": ["view-1"],
            "attributes.span_type__neq": ["session"],
        }
