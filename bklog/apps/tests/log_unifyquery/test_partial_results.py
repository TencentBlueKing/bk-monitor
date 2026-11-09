"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.

"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.log_search.exceptions import BaseSearchException
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler


def raw_partial(rows=None):
    return {
        "list": [] if rows is None else rows,
        "total": 1,
        "status": {"code": "QUERY_RAW_PARTIAL", "message": "shard failure"},
    }


@override_settings(PRE_SEARCH_SECONDS=10)
class PartialResultsTests(SimpleTestCase):
    def handler(self):
        handler = object.__new__(UnifyQueryHandler)
        handler.base_dict = {"query_list": [{"function": []}]}
        handler.search_params = {"size": 2, "begin": 0, "original_search": True, "scenario_id": "es"}
        handler.highlight = False
        handler.start_time, handler.end_time = 1, 100
        handler.query_ts_raw = Mock()
        handler._deal_query_result = lambda response, **_kwargs: response
        return handler

    def test_presearch_partial_full_page_retries_whole_window(self):
        handler = self.handler()
        handler.query_ts_raw.side_effect = [raw_partial([{}, {}]), {"list": [{}, {}], "total": 2}]
        result = handler.search(allow_partial_es_results=True)
        self.assertFalse(result["is_partial"])
        self.assertEqual(handler.query_ts_raw.call_count, 2)
        self.assertTrue(handler.query_ts_raw.call_args_list[0].kwargs["pre_search"])
        self.assertNotIn("pre_search", handler.query_ts_raw.call_args_list[1].kwargs)
        for call in handler.query_ts_raw.call_args_list:
            self.assertTrue(call.args[0]["allow_partial_es_results"])
        self.assertNotIn("allow_partial_es_results", handler.base_dict)

    def test_empty_partial_list_and_next_page_keep_flag(self):
        handler = self.handler()
        handler.start_time = handler.end_time = None
        handler.search_params["begin"] = 20
        handler.query_ts_raw.return_value = raw_partial()
        result = handler.search(allow_partial_es_results=True)
        self.assertEqual(result["list"], [])
        self.assertTrue(result["is_partial"])
        self.assertEqual(result["status"]["code"], "QUERY_RAW_PARTIAL")
        self.assertEqual(handler.query_ts_raw.call_args.args[0]["from"], 20)
        self.assertTrue(handler.query_ts_raw.call_args.args[0]["allow_partial_es_results"])

    def test_populated_histogram_preserves_values_and_partial(self):
        handler = self.handler()
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(
            return_value={"series": [{"values": [[1000, 7], [2000, 0]]}], "is_partial": True}
        )
        with patch(
            "apps.log_unifyquery.handler.base.timestamp_to_timeformat", side_effect=lambda value, **kw: str(value)
        ):
            result = handler.date_histogram(allow_partial_es_results=True)
        self.assertTrue(handler.query_ts_reference.call_args.args[0]["allow_partial_es_results"])
        self.assertTrue(result["is_partial"])
        self.assertEqual(
            result["aggs"]["group_by_histogram"]["buckets"],
            [
                {"key_as_string": "1000", "key": 1000, "doc_count": 7},
                {"key_as_string": "2000", "key": 2000, "doc_count": 0},
            ],
        )

    def test_histogram_hard_failure_propagates(self):
        handler = self.handler()
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(side_effect=TimeoutError("timed out"))
        with self.assertRaises(TimeoutError):
            handler.date_histogram(allow_partial_es_results=True)

    def test_rollout_requires_explicit_page_request_and_listed_index_owner(self):
        handler = self.handler()
        handler.index_set_ids = [10]
        index = SimpleNamespace(is_platform_index=False, space_uid="bkcc__123")
        handler.index_set = {"index_set_obj": index}
        toggles = self.enterContext(patch("apps.log_unifyquery.handler.base.FeatureToggleObject"))
        for status, businesses, requested, expected in (
            ("debug", [123], True, True),
            ("debug", [124], True, False),
            ("debug", [], True, False),
            ("off", [123], True, False),
            ("on", [123], True, False),
            ("debug", [123], None, False),
            ("debug", [123], "true", False),
        ):
            with self.subTest(status=status, businesses=businesses, requested=requested):
                toggles.toggle.return_value = SimpleNamespace(status=status, biz_id_white_list=businesses)
                self.assertEqual(handler.accepts_partial_page_results(requested), expected)
        toggles.toggle.return_value = None
        self.assertFalse(handler.accepts_partial_page_results(True))
        toggles.toggle.return_value = SimpleNamespace(status="debug", biz_id_white_list=[123])
        index.is_platform_index = True
        self.assertFalse(handler.accepts_partial_page_results(True))
        index.is_platform_index = False
        handler.index_set_ids.append(11)
        self.assertFalse(handler.accepts_partial_page_results(True))

    def test_shared_calls_omit_opt_in(self):
        handler = self.handler()
        handler.query_ts_raw.return_value = {"list": [{}, {}]}
        handler.search()
        self.assertNotIn("allow_partial_es_results", handler.query_ts_raw.call_args.args[0])
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(return_value={"series": []})
        self.assertEqual(handler.date_histogram(), {"aggs": {}})
        self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])

    def test_page_total_count_requires_complete_response_and_preserves_zero(self):
        handler = object.__new__(UnifyQueryFieldHandler)
        handler.result_merge_base_dict = {"query_list": [{}]}
        handler.query_ts_reference = Mock()
        for response in (
            {"series": [], "is_partial": True},
            {"series": [{"values": [[1000, 7]]}], "status": {"code": "QUERY_TS_PARTIAL"}},
        ):
            with self.subTest(response=response):
                handler.query_ts_reference.return_value = response
                with self.assertRaises(BaseSearchException):
                    handler.get_total_count(require_complete=True)
                self.assertTrue(handler.query_ts_reference.call_args.kwargs["raise_exception"])
                self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])
        self.assertEqual(handler.get_total_count(), 7)  # Shared count used by no-data inspection.
        handler.query_ts_reference.side_effect = TimeoutError("count timed out")
        with self.assertRaises(TimeoutError):
            handler.get_total_count(require_complete=True)
        handler.query_ts_reference.side_effect = None
        handler.query_ts_reference.return_value = {"series": [{"values": [[1000, 0]]}]}
        self.assertEqual(handler.get_total_count(require_complete=True), 0)
        handler.query_ts_reference.return_value = {"series": []}
        self.assertEqual(handler.get_total_count(require_complete=True), 0)
