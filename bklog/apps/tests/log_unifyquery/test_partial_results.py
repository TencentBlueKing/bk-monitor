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

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.log_search.views.search_views import SearchViewSet
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
        self.assertNotIn("is_partial", result)
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
        self.assertNotIn("is_partial", result)
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
        self.assertNotIn("is_partial", result)
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

    def test_rollout_requires_local_page_and_listed_index_owner(self):
        handler = self.handler()
        page = RequestFactory().post("/api/v1/search/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        page.user = SimpleNamespace(is_authenticated=True)
        handler.index_set_ids = [10]
        index = SimpleNamespace(is_platform_index=False, space_uid="bkcc__123")
        handler.index_set = {"index_set_obj": index}
        toggles = self.enterContext(patch("apps.log_unifyquery.handler.base.FeatureToggleObject"))
        for status, businesses, expected in (
            ("debug", [123], True),
            ("debug", [124], False),
            ("debug", [], False),
            ("off", [123], False),
            ("on", [123], False),
        ):
            with self.subTest(status=status, businesses=businesses):
                toggles.toggle.return_value = SimpleNamespace(status=status, biz_id_white_list=businesses)
                self.assertEqual(handler.accepts_partial_page_results(page), expected)
        toggles.toggle.return_value = None
        self.assertFalse(handler.accepts_partial_page_results(page))
        toggles.toggle.return_value = SimpleNamespace(status="debug", biz_id_white_list=[123])
        for headers in (
            {},
            {"HTTP_X_BKAPI_JWT": "gateway", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"},
            {"HTTP_X_SOURCE_APP_CODE": "monitor", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"},
        ):
            caller = RequestFactory().post("/", {"allow_partial_es_results": True}, **headers)
            caller.user = page.user
            self.assertFalse(handler.accepts_partial_page_results(caller))
        page.jwt = object()
        self.assertFalse(handler.accepts_partial_page_results(page))
        del page.jwt
        page.user = AnonymousUser()
        self.assertFalse(handler.accepts_partial_page_results(page))
        page.user = SimpleNamespace(is_authenticated=True)
        index.is_platform_index = True
        self.assertFalse(handler.accepts_partial_page_results(page))
        index.is_platform_index = False
        handler.index_set_ids.append(11)
        self.assertFalse(handler.accepts_partial_page_results(page))

    @patch("apps.log_search.views.search_views.UnifyQueryHandler")
    @patch("apps.log_search.views.search_views._apply_index_set_search_bk_biz_id")
    def test_only_page_stream_enables_raw_search(self, _apply_scope, handler_cls):
        view = SearchViewSet()
        view.get_object = Mock()
        view.params_valid = Mock(side_effect=lambda *_: {})
        handler = handler_cls.return_value
        handler.accepts_partial_page_results.return_value = True
        handler.search.side_effect = lambda **_: {"list": [], "total": 0}
        for query, enabled in (("", False), ("?stream=true", True)):
            request = RequestFactory().post(f"/api/v1/search/index_set/10/search/{query}")
            response = view.search(request, index_set_id=10)
            handler.search.assert_called_with(allow_partial_es_results=enabled)
            self.assertEqual(response.streaming, enabled)

    def test_shared_calls_omit_opt_in(self):
        handler = self.handler()
        handler.query_ts_raw.return_value = {"list": [{}, {}]}
        handler.search()
        self.assertNotIn("allow_partial_es_results", handler.query_ts_raw.call_args.args[0])
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(return_value={"series": []})
        self.assertEqual(handler.date_histogram(), {"aggs": {}})
        self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])

    def test_only_page_total_uses_partial_count(self):
        handler = object.__new__(UnifyQueryFieldHandler)
        handler.result_merge_base_dict = {"query_list": [{}]}
        handler.query_ts_reference = Mock(return_value={"series": [{"values": [[1000, 7]]}], "is_partial": True})
        self.assertEqual(handler.get_total_count(allow_partial_es_results=True), 7)
        self.assertTrue(handler.query_ts_reference.call_args.args[0]["allow_partial_es_results"])
        self.assertEqual(handler.get_total_count(), 7)
        self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])
        self.assertFalse(handler.query_ts_reference.call_args.kwargs["raise_exception"])
