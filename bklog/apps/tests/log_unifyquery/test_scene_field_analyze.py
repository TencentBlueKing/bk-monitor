"""场景化字段分析 handler 和 MCP 入口测试。"""

import copy
from collections import Counter
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.api import UnifyQueryApi
from apps.log_search.views.scene_search_views import SceneAnalyzeFieldSerializer, SceneSearchViewSet
from apps.log_unifyquery.handler.scene_field import SceneFieldHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler


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

    def test_endpoint_merges_expanded_candidates_and_preserves_unwrapped_data(self):
        table_counts = [{"A": 100, "X": 99}, {"B": 100, "X": 99}]

        def query_reference(query_body, *_args):
            merged_counts = Counter()
            candidate_limit = query_body["query_list"][0]["limit"]
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
            {**PARAMS, "field_name": "level", "order_by": "value", "limit": 1, "step": "5m"},
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
        self.assertEqual(payload["series"], [make_series("X", 198)])
        self.assertEqual(payload["trace_id"], "scene-query")
        self.assertEqual(payload["result_table_id"], ["bklog_index_set_1", "bklog_index_set_2"])
        self.assertIs(payload["is_partial"], False)
        query_body = query.call_args.args[0]
        query_item = query_body["query_list"][0]
        self.assertEqual(query_item["limit"], 12)
        self.assertEqual(query_item["table_id"], "")
        self.assertEqual(query_item["table_id_conditions"], SCENE_CONDITIONS)
        self.assertEqual(query_item["field_name"], "level")
        self.assertEqual(query_item["function"], [{"method": "count", "dimensions": ["level"]}])
        self.assertIn({"field_name": "level", "value": [""], "op": "ne"}, query_item["conditions"]["field_list"])
        self.assertEqual(query_body["order_by"], ["-_value"])
        self.assertEqual(query_body["step"], "5m")
        self.assertEqual(query_body["space_uid"], "bkcc__2")
        self.assertEqual(query_body["bk_biz_id"], 2)

    def test_existing_topk_list_keeps_its_response_format(self):
        handler = self.make_handler()
        payload = {"series": [make_series("A", 100), make_series("X", 198), make_series("B", 50)]}
        handler.query_ts_reference = Mock(side_effect=lambda _body: copy.deepcopy(payload))

        self.assertEqual(handler.get_topk_list(2), [["X", 198], ["A", 100]])
        self.assertEqual(
            handler.analyze_field(group_by=True, order_by="value", limit=2)["series"],
            [make_series("X", 198), make_series("A", 100)],
        )
        self.assertEqual(handler.query_ts_reference.call_args_list[0], handler.query_ts_reference.call_args_list[1])

    def test_topk_preserves_empty_result_and_partial_status(self):
        handler = self.make_handler()
        payload = {"series": [], "is_partial": True, "status": {"code": "partial"}}
        handler.query_ts_reference = Mock(return_value=payload)

        self.assertEqual(handler.analyze_field(group_by=True, order_by="value", limit=5), payload)

    def test_group_by_false_uses_plain_count(self):
        handler = self.make_handler()
        payload = {"series": [{"group_keys": [], "group_values": [], "values": [[0, 398]]}]}
        handler.query_ts_reference = Mock(return_value=payload)

        self.assertEqual(handler.analyze_field(group_by=False), payload)

        query_body = handler.query_ts_reference.call_args.args[0]
        query_item = query_body["query_list"][0]
        self.assertEqual(query_item["function"], [{"method": "count"}])
        self.assertNotIn("limit", query_item)
        self.assertEqual(query_body["order_by"], ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"])

    def test_distribution_does_not_add_a_candidate_limit(self):
        handler = self.make_handler()
        payload = {"series": [make_series("A", 100), make_series("X", 198)]}
        handler.query_ts_reference = Mock(return_value=payload)

        self.assertEqual(handler.analyze_field(group_by=True, limit=None), payload)

        query_item = handler.query_ts_reference.call_args.args[0]["query_list"][0]
        self.assertEqual(query_item["function"], [{"method": "count", "dimensions": ["level"]}])
        self.assertNotIn("limit", query_item)

    def test_grouped_time_order_keeps_the_requested_limit(self):
        handler = self.make_handler()
        handler.query_ts_reference = Mock(return_value={"series": [make_series("A", 100), make_series("B", 50)]})

        self.assertEqual(
            handler.analyze_field(group_by=True, order_by="time", limit=1)["series"], [make_series("A", 100)]
        )

    def test_serializer_rejects_nonpositive_limits(self):
        for limit in (0, -1):
            with self.subTest(limit=limit):
                serializer = SceneAnalyzeFieldSerializer(data={**PARAMS, "field_name": "level", "limit": limit})
                self.assertFalse(serializer.is_valid())
                self.assertIn("limit", serializer.errors)

    def test_verify_scene_permission_accepts_both_response_shapes(self):
        for result in (
            {"result_table_id": ["bklog_index_set_1"]},
            {"data": {"result_table_id": ["bklog_index_set_1"]}},
        ):
            with self.subTest(result=result):
                handler = SceneUnifyQueryHandler.__new__(SceneUnifyQueryHandler)
                handler.verify_result_table_search_permission = Mock()

                handler._verify_scene_permission(result)

                handler.verify_result_table_search_permission.assert_called_once_with(["bklog_index_set_1"])
