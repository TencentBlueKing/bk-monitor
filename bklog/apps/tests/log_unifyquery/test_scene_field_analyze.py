"""场景化字段分析 handler 和 MCP 入口测试。"""

import copy
from collections import Counter
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.api import UnifyQueryApi
from apps.log_search.views.scene_search_views import SceneAnalyzeFieldSerializer, SceneSearchViewSet
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.log_unifyquery.handler.scene_field import SceneFieldHandler


SCENE_CONDITIONS = [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]]

PARAMS = {
    "space_uid": "bkcc__2",
    "bk_biz_id": 2,
    "table_id_conditions": SCENE_CONDITIONS,
    "keyword": "*",
    "start_time": "1710000000000",
    "end_time": "1710003600000",
}


def make_series(value, count):
    return {"group_keys": ["level"], "group_values": [value], "columns": ["_time", "_value"], "values": [[0, count]]}


@override_settings(TIME_ZONE="UTC", IGNORE_IAM_PERMISSION=True)
class TestSceneAnalyzeField(TestCase):
    def setUp(self):
        for name, value in (
            ("get_local_param", "UTC"),
            ("get_request_external_username", ""),
            ("get_request_username", "admin"),
        ):
            self.enterContext(patch(f"apps.log_unifyquery.handler.scene_search.{name}", return_value=value))

    @staticmethod
    def make_handler():
        return SceneFieldHandler({**PARAMS, "agg_field": "level", "interval": "5m"})

    def test_endpoint_merges_per_table_candidates_and_preserves_unwrapped_data(self):
        table_counts = [{"A": 100, "X": 99}, {"B": 100, "X": 99}]

        def query_reference(query_body, *_args):
            merged_counts = Counter()
            candidate_limit = query_body["query_list"][0].get("limit")
            for counts in table_counts:
                merged_counts.update(dict(Counter(counts).most_common(candidate_limit)))
            payload = {
                "series": [make_series(value, count) for value, count in merged_counts.items()],
                "result_table_id": ["bklog_index_set_1", "bklog_index_set_2"],
                "trace_id": "scene-query",
                "is_partial": False,
            }
            return Mock(data=payload, is_success=Mock(return_value=True))

        request = APIRequestFactory().post(
            "/api/v1/search/scene/field/analyze/",
            {**PARAMS, "field_name": "level", "order_by": "value", "limit": 2, "step": "5m"},
            format="json",
        )
        with (
            patch.object(SceneSearchViewSet, "get_permissions", return_value=[]),
            patch.object(UnifyQueryApi.query_ts_reference, "_send_request", side_effect=query_reference) as query,
        ):
            response = SceneSearchViewSet.as_view({"post": "analyze_field"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["result"], True)
        payload = response.data["data"]
        self.assertEqual(payload["series"], [make_series("X", 198), make_series("A", 100)])
        self.assertEqual(payload["trace_id"], "scene-query")
        self.assertEqual(payload["result_table_id"], ["bklog_index_set_1", "bklog_index_set_2"])
        self.assertIs(payload["is_partial"], False)
        query_body = query.call_args.args[0]
        query_item = query_body["query_list"][0]
        self.assertEqual(query_item["limit"], 14)
        self.assertEqual(query_item["table_id"], "")
        self.assertEqual(query_item["table_id_conditions"], SCENE_CONDITIONS)
        self.assertEqual(query_item["field_name"], "level")
        self.assertEqual(query_item["function"], [{"method": "count", "dimensions": ["level"]}])
        self.assertIn({"field_name": "level", "value": [""], "op": "ne"}, query_item["conditions"]["field_list"])
        self.assertEqual(query_body["order_by"], ["-_value"])
        self.assertEqual(query_body["step"], "5m")
        self.assertEqual(query_body["space_uid"], "bkcc__2")
        self.assertEqual(query_body["bk_biz_id"], 2)

    def test_topk_reuses_baseline_candidate_aggregation(self):
        handler = self.make_handler()
        payload = {"series": [make_series("A", 100), make_series("X", 198), make_series("B", 50)]}
        handler.query_ts_reference = Mock(side_effect=lambda _body, **_kwargs: copy.deepcopy(payload))

        self.assertEqual(handler.get_topk_list(2), [["X", 198], ["A", 100]])
        page_body = handler.query_ts_reference.call_args.args[0]

        self.assertEqual(
            handler.analyze_field(group_by=True, order_by="value", limit=2)["series"],
            [make_series("X", 198), make_series("A", 100)],
        )
        mcp_body = handler.query_ts_reference.call_args.args[0]

        self.assertEqual(page_body, mcp_body)
        self.assertEqual(mcp_body["query_list"][0]["limit"], 14)
        self.assertIn(
            {"field_name": "level", "value": [""], "op": "ne"},
            mcp_body["query_list"][0]["conditions"]["field_list"],
        )
        self.assertIs(handler.query_ts_reference.call_args.kwargs["raise_exception"], True)

    def test_topk_preserves_empty_result_and_partial_status(self):
        handler = self.make_handler()
        payload = {"series": [], "is_partial": True, "status": {"code": "partial"}}
        handler.query_ts_reference = Mock(return_value=payload)

        self.assertEqual(handler.analyze_field(group_by=True, order_by="value", limit=5), payload)

    def test_group_by_false_uses_plain_count(self):
        handler = self.make_handler()
        payload = {"series": [{"group_keys": [], "group_values": [], "values": [[0, 398]]}]}
        handler.query_ts_reference = Mock(return_value=payload)

        for limit in (None, 5):
            with self.subTest(limit=limit):
                self.assertEqual(handler.analyze_field(group_by=False, limit=limit), payload)

                query_body = handler.query_ts_reference.call_args.args[0]
                query_item = query_body["query_list"][0]
                self.assertEqual(query_item["function"], [{"method": "count"}])
                if limit is None:
                    self.assertNotIn("limit", query_item)
                else:
                    self.assertEqual(query_item["limit"], limit)
                self.assertEqual(query_body["order_by"], ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"])
                self.assertIs(handler.query_ts_reference.call_args.kwargs["raise_exception"], True)

    def test_distribution_does_not_add_a_candidate_limit(self):
        handler = self.make_handler()
        payload = {"series": [make_series("A", 100), make_series("X", 198)]}
        handler.query_ts_reference = Mock(return_value=payload)

        for order_by in ("time", "value"):
            with self.subTest(order_by=order_by):
                self.assertEqual(handler.analyze_field(group_by=True, order_by=order_by, limit=None), payload)

                query_item = handler.query_ts_reference.call_args.args[0]["query_list"][0]
                self.assertEqual(query_item["function"], [{"method": "count", "dimensions": ["level"]}])
                self.assertNotIn("limit", query_item)

    def test_endpoint_time_series_passes_window_and_keeps_all_time_points(self):
        for step, step_ms in (("5m", 300_000), ("15m", 900_000), (None, 3_600_000)):
            with self.subTest(step=step):
                start_time = int(PARAMS["start_time"])
                series = make_series("ERROR", 10)
                series["values"] = [[start_time + index * step_ms, count] for index, count in enumerate((10, 20, 30))]
                payload = {
                    "series": [series],
                    "result_table_id": ["bklog_index_set_1", "bklog_index_set_2"],
                    "trace_id": "scene-time-series",
                    "is_partial": True,
                }
                params = {
                    **PARAMS,
                    "field_name": "level",
                    "order_by": "time",
                    "limit": 1,
                    "end_time": str(start_time + 3 * step_ms),
                }
                if step is not None:
                    params["step"] = step
                request = APIRequestFactory().post("/api/v1/search/scene/field/analyze/", params, format="json")
                with (
                    patch.object(SceneSearchViewSet, "get_permissions", return_value=[]),
                    patch.object(
                        UnifyQueryApi.query_ts_reference,
                        "_send_request",
                        side_effect=[
                            Mock(
                                data={"series": [make_series("ERROR", 60), make_series("WARN", 5)]},
                                is_success=Mock(return_value=True),
                            ),
                            Mock(data=copy.deepcopy(payload), is_success=Mock(return_value=True)),
                        ],
                    ) as query,
                ):
                    response = SceneSearchViewSet.as_view({"post": "analyze_field"})(request)

                self.assertEqual(response.status_code, 200)
                self.assertIs(response.data["result"], True)
                self.assertEqual(response.data["data"], payload)
                self.assertEqual(query.call_count, 2)
                query_body = query.call_args.args[0]
                query_item = query_body["query_list"][0]
                self.assertEqual(query_body["step"], step or "1h")
                self.assertEqual(
                    query_item["function"], [{"method": "count", "dimensions": ["level"], "window": step or "1h"}]
                )
                self.assertNotIn("limit", query_item)
                self.assertIn(
                    {"field_name": "level", "value": ["ERROR"], "op": "eq"}, query_item["conditions"]["field_list"]
                )
                self.assertEqual(query_item["table_id_conditions"], SCENE_CONDITIONS)

    def test_time_series_merges_all_tables_for_selected_values(self):
        table_values = [
            {"ERROR": [50, 50], "WARN": [40, 50]},
            {"WARN": [60, 40], "ERROR": [4, 6]},
        ]
        start_time = int(PARAMS["start_time"])

        def query_reference(query_body, *_args):
            query_item = query_body["query_list"][0]
            window = query_item["function"][0].get("window")
            selected_values = next(
                (
                    condition["value"]
                    for condition in query_item["conditions"]["field_list"]
                    if condition["field_name"] == "level" and condition["op"] == "eq"
                ),
                None,
            )
            merged_values = {}
            for values in table_values:
                counts = Counter(
                    {
                        value: sum(points)
                        for value, points in values.items()
                        if selected_values is None or value in selected_values
                    }
                )
                for value, count in counts.most_common(query_item.get("limit")):
                    points = values[value] if window else [count]
                    merged_values.setdefault(value, [0] * len(points))
                    merged_values[value] = [total + point for total, point in zip(merged_values[value], points)]
            bucket_topk = None
            if window and query_body["metric_merge"].startswith("topk("):
                limit = int(query_body["metric_merge"].split("(", 1)[1].split(",", 1)[0])
                bucket_topk = [
                    dict(Counter({value: points[index] for value, points in merged_values.items()}).most_common(limit))
                    for index in range(2)
                ]
            series = []
            for value, points in merged_values.items():
                item = make_series(value, sum(points))
                item["values"] = [
                    [start_time + index * 300_000, count]
                    for index, count in enumerate(points)
                    if bucket_topk is None or value in bucket_topk[index]
                ]
                if item["values"]:
                    series.append(item)
            payload = {
                "series": series,
                "result_table_id": ["bklog_index_set_1", "bklog_index_set_2"],
                "trace_id": "time-series" if window else "topk-candidates",
                "is_partial": False,
            }
            return Mock(data=payload, is_success=Mock(return_value=True))

        for action in ("analyze_field", "fetch_statistics_graph"):
            with self.subTest(action=action):
                params = {**PARAMS, "limit": 1}
                if action == "analyze_field":
                    params.update(field_name="level", order_by="time", step="5m")
                else:
                    params.update(agg_field="level", field_type="keyword", interval="5m")
                request = APIRequestFactory().post("/api/v1/search/scene/field/", params, format="json")
                with (
                    patch.object(SceneSearchViewSet, "get_permissions", return_value=[]),
                    patch.object(
                        UnifyQueryApi.query_ts_reference, "_send_request", side_effect=query_reference
                    ) as query,
                ):
                    response = SceneSearchViewSet.as_view({"post": action})(request)

                self.assertEqual(response.status_code, 200)
                series = response.data["data"]["series"]
                self.assertEqual(len(series), 1)
                self.assertEqual(series[0]["group_values"], ["WARN"])
                self.assertEqual(series[0]["values"], [[start_time, 100], [start_time + 300_000, 90]])
                self.assertEqual(query.call_count, 2)
                self.assertEqual(query.call_args_list[0].args[0]["query_list"][0]["limit"], 12)
                self.assertNotIn("limit", query.call_args_list[1].args[0]["query_list"][0])
                self.assertEqual(response.data["data"]["trace_id"], "time-series")

    def test_topk_time_series_uses_requested_limit_for_both_handlers(self):
        for handler_class in (SceneFieldHandler, UnifyQueryFieldHandler):
            for limit in (None, 1, 7):
                with self.subTest(handler=handler_class.__name__, limit=limit):
                    scene_handler = self.make_handler()
                    handler = handler_class.__new__(handler_class)
                    handler.search_params = scene_handler.search_params
                    handler.result_merge_base_dict = scene_handler.result_merge_base_dict
                    original_body = copy.deepcopy(handler.result_merge_base_dict)
                    candidates = [make_series(f"value_{index}", 10 - index) for index in range(9)]
                    expected_limit = limit if limit is not None else 5
                    payload = {"series": candidates[:expected_limit], "trace_id": "time-series"}
                    handler.query_ts_reference = Mock(
                        side_effect=[{"series": copy.deepcopy(candidates)}, copy.deepcopy(payload)]
                    )

                    result = handler.get_topk_ts_data() if limit is None else handler.get_topk_ts_data(limit)

                    self.assertEqual(result, payload)
                    queries = handler.query_ts_reference.call_args_list
                    self.assertEqual(len(queries), 2)
                    self.assertEqual(queries[0].args[0]["query_list"][0]["limit"], expected_limit * 2 + 10)
                    time_query = queries[1].args[0]
                    self.assertNotIn("limit", time_query["query_list"][0])
                    self.assertIn(
                        {
                            "field_name": "level",
                            "value": [f"value_{index}" for index in range(expected_limit)],
                            "op": "eq",
                        },
                        time_query["query_list"][0]["conditions"]["field_list"],
                    )
                    self.assertEqual(time_query["query_list"][0]["function"][0]["window"], "5m")
                    self.assertEqual(handler.result_merge_base_dict, original_body)

    def test_time_series_with_no_candidates_does_not_query_without_a_filter(self):
        handler = self.make_handler()
        payload = {
            "series": [],
            "result_table_id": ["bklog_index_set_1"],
            "trace_id": "topk-candidates",
            "is_partial": True,
            "status": {"code": "partial"},
        }
        handler.query_ts_reference = Mock(return_value=copy.deepcopy(payload))

        self.assertEqual(handler.analyze_field(group_by=True, order_by="time", limit=3), payload)

        handler.query_ts_reference.assert_called_once()
        query_item = handler.query_ts_reference.call_args.args[0]["query_list"][0]
        self.assertEqual(query_item["limit"], 16)
        self.assertNotIn("window", query_item["function"][0])

    def test_time_series_preserves_partial_candidate_status(self):
        for time_status in (None, {"code": "time-series-partial"}):
            with self.subTest(time_status=time_status):
                handler = self.make_handler()
                candidate_status = {"code": "candidate-partial"}
                candidates = {"series": [make_series("WARN", 190)], "is_partial": True, "status": candidate_status}
                payload = {
                    "series": [make_series("WARN", 100)],
                    "result_table_id": ["bklog_index_set_1", "bklog_index_set_2"],
                    "trace_id": "time-series",
                    "is_partial": False,
                    "status": time_status,
                }
                handler.query_ts_reference = Mock(side_effect=[copy.deepcopy(candidates), copy.deepcopy(payload)])

                result = handler.analyze_field(group_by=True, order_by="time", limit=1)

                self.assertEqual(result, {**payload, "is_partial": True, "status": time_status or candidate_status})

    def test_time_series_propagates_query_errors_in_both_phases(self):
        for failing_phase in (1, 2):
            with self.subTest(failing_phase=failing_phase):
                handler = self.make_handler()
                results = [{"series": [make_series("WARN", 190)]}] * (failing_phase - 1)
                results.append(RuntimeError("query failed"))
                with patch.object(UnifyQueryApi, "query_ts_reference", side_effect=results) as query:
                    with self.assertRaisesRegex(RuntimeError, "query failed"):
                        handler.analyze_field(group_by=True, order_by="time", limit=1)
                self.assertEqual(query.call_count, failing_phase)

    def test_page_time_series_keeps_default_exception_handling(self):
        handler = self.make_handler()
        with patch.object(UnifyQueryApi, "query_ts_reference", side_effect=RuntimeError("query failed")) as query:
            self.assertEqual(handler.get_topk_ts_data(), {"series": []})
        query.assert_called_once()

    def test_serializer_rejects_limits_out_of_range(self):
        for limit in (0, -1, 1001):
            with self.subTest(limit=limit):
                serializer = SceneAnalyzeFieldSerializer(data={**PARAMS, "field_name": "level", "limit": limit})
                self.assertFalse(serializer.is_valid())
                self.assertIn("limit", serializer.errors)
