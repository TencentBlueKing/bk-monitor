"""场景化字段分析 handler 测试。"""

from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

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


@override_settings(TIME_ZONE="UTC")
class TestSceneAnalyzeField(TestCase):
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    def test_builds_scene_query_and_truncates_to_limit(self, _user, _ext_user, _local):
        handler = SceneUnifyQueryHandler(PARAMS)
        handler.query_ts_reference = Mock(
            return_value={
                "data": {"series": [{"dimensions": {"level": str(index)}} for index in range(5)]},
                "result": True,
            }
        )

        result = handler.analyze_field("level", group_by=True, order_by="value", limit=3, step="5m")

        query_body = handler.query_ts_reference.call_args.args[0]
        query_item = query_body["query_list"][0]
        self.assertEqual(query_item["table_id"], "")
        self.assertEqual(query_item["table_id_conditions"], SCENE_CONDITIONS)
        self.assertEqual(query_item["field_name"], "level")
        self.assertEqual(query_item["function"], [{"method": "count", "dimensions": ["level"]}])
        self.assertEqual(query_item["limit"], 3)
        self.assertEqual(query_body["order_by"], ["-_value"])
        self.assertEqual(query_body["step"], "5m")
        self.assertEqual(query_body["space_uid"], "bkcc__2")
        self.assertEqual(query_body["bk_biz_id"], 2)
        self.assertEqual(len(result["data"]["series"]), 3)

    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    def test_group_by_false_uses_plain_count(self, _user, _ext_user, _local):
        handler = SceneUnifyQueryHandler(PARAMS)
        handler.query_ts_reference = Mock(return_value={"data": {"series": [{"dimensions": {}}]}, "result": True})

        handler.analyze_field("level", group_by=False, order_by="time", limit=None, step="1h")

        query_body = handler.query_ts_reference.call_args.args[0]
        query_item = query_body["query_list"][0]
        self.assertEqual(query_item["function"], [{"method": "count"}])
        self.assertNotIn("limit", query_item)
        self.assertEqual(query_body["order_by"], ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"])

    def test_verify_scene_permission_reads_result_table_id_from_data(self):
        handler = SceneUnifyQueryHandler.__new__(SceneUnifyQueryHandler)
        handler.verify_result_table_search_permission = Mock()

        handler._verify_scene_permission({"data": {"result_table_id": ["bklog_index_set_1"]}})

        handler.verify_result_table_search_permission.assert_called_once_with(["bklog_index_set_1"])
