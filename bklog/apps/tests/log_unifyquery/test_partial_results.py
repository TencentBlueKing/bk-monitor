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

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.log_search.views.aggs_views import AggsViewSet
from apps.log_search.views.field_views import FieldViewSet
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
    def handler(self, allow_partial=False):
        handler = object.__new__(UnifyQueryHandler)
        handler.allow_partial_es_results = allow_partial
        handler.base_dict = {"query_list": [{"function": []}]}
        handler.search_params = {"size": 2, "begin": 0, "original_search": True, "scenario_id": "es"}
        handler.highlight = False
        handler.start_time, handler.end_time = 1, 100
        handler.query_ts_raw = Mock()
        handler._deal_query_result = lambda response, **_kwargs: response
        return handler

    def test_presearch_partial_full_page_retries_whole_window(self):
        handler = self.handler(allow_partial=True)
        handler.query_ts_raw.side_effect = [raw_partial([{}, {}]), {"list": [{}, {}], "total": 2}]
        result = handler.search()
        self.assertNotIn("is_partial", result)
        self.assertEqual(handler.query_ts_raw.call_count, 2)
        self.assertTrue(handler.query_ts_raw.call_args_list[0].kwargs["pre_search"])
        self.assertNotIn("pre_search", handler.query_ts_raw.call_args_list[1].kwargs)
        for call in handler.query_ts_raw.call_args_list:
            self.assertTrue(call.args[0]["allow_partial_es_results"])
        self.assertNotIn("allow_partial_es_results", handler.base_dict)

    def test_empty_partial_list_and_next_page_keep_flag(self):
        handler = self.handler(allow_partial=True)
        handler.start_time = handler.end_time = None
        handler.search_params["begin"] = 20
        handler.query_ts_raw.return_value = raw_partial()
        result = handler.search()
        self.assertEqual(result["list"], [])
        self.assertNotIn("is_partial", result)
        self.assertEqual(result["status"]["code"], "QUERY_RAW_PARTIAL")
        self.assertEqual(handler.query_ts_raw.call_args.args[0]["from"], 20)
        self.assertTrue(handler.query_ts_raw.call_args.args[0]["allow_partial_es_results"])

    def test_populated_histogram_preserves_values_and_partial(self):
        handler = self.handler(allow_partial=True)
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(
            return_value={"series": [{"values": [[1000, 7], [2000, 0]]}], "is_partial": True}
        )
        with patch(
            "apps.log_unifyquery.handler.base.timestamp_to_timeformat", side_effect=lambda value, **kw: str(value)
        ):
            result = handler.date_histogram()
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
        handler = self.handler(allow_partial=True)
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(side_effect=TimeoutError("timed out"))
        with self.assertRaises(TimeoutError):
            handler.date_histogram()

    def test_rollout_uses_one_resolved_business(self):
        handler = self.handler()
        handler.bk_biz_id = 456
        owner = SimpleNamespace(space_uid="bkcc__123", is_platform_index=False)
        handler.index_info_list = [{"index_set_obj": owner}, {"index_set_obj": owner}]
        self.assertEqual(handler._resolve_partial_results_biz_id(), 123)
        shared = SimpleNamespace(space_uid="bkcc__123", is_platform_index=True)
        handler.index_info_list = [{"index_set_obj": shared}]
        with patch("apps.log_search.models.LogIndexSet.is_platform_index_visible_to_space") as visible:
            visible.return_value = False
            self.assertIsNone(handler._resolve_partial_results_biz_id())
            visible.return_value = True
            self.assertEqual(handler._resolve_partial_results_biz_id(), 456)
            handler.index_info_list.append({"index_set_obj": owner})
            self.assertIsNone(handler._resolve_partial_results_biz_id())

    @patch("apps.log_search.views.search_views.UnifyQueryHandler")
    def test_json_and_stream_search_use_same_rollout(self, handler_cls):
        view = SearchViewSet()
        view.get_object = Mock(return_value=SimpleNamespace(space_uid="bkcc__123", is_platform_index=False))
        view.params_valid = Mock(side_effect=lambda *_: {"bk_biz_id": 456})
        handler = handler_cls.return_value
        handler.search.side_effect = lambda **_: {"list": [], "total": 0}
        for query, streaming in (("", False), ("?stream=true", True)):
            request = RequestFactory().post(f"/api/v1/search/index_set/10/search/{query}")
            response = view.search(request, index_set_id=10)
            self.assertEqual(handler_cls.call_args.kwargs, {"partial_results_biz_id": 123})
            handler.search.assert_called_with()
            self.assertEqual(response.streaming, streaming)

    @patch("apps.log_search.models.LogIndexSet.resolve_search_scope", side_effect=TimeoutError)
    def test_scope_lookup_failure_preserves_aggregation_queries(self, _scope):
        base = "apps.log_unifyquery.handler.base"
        for method, value in (
            ("UnifyQueryHandler._init_index_info_list", [{"index_set_obj": Mock(), "scenario_id": "es"}]),
            ("UnifyQueryHandler._init_desensitize", False),
            ("UnifyQueryHandler._init_sort", []),
            ("UnifyQueryHandler.init_base_dict", {"query_list": [{}]}),
            ("SearchHandler.init_time_field", None),
            ("DesensitizeConfig.objects.filter", Mock(first=Mock(return_value=None))),
            ("DesensitizeFieldConfig.objects.filter", []),
        ):
            self.enterContext(patch(f"{base}.{method}", return_value=value))
        params = {
            "bk_biz_id": 123,
            "index_set_ids": [10],
            "start_time": 1,
            "end_time": 100,
            "interval": "1m",
            "group_field": None,
        }
        handler = UnifyQueryFieldHandler(params, resolve_partial_results_biz=True)
        _scope.assert_called_once()
        with patch(f"{base}.FeatureToggleObject.switch", return_value=True) as switch:
            self.assertTrue(UnifyQueryHandler(params, partial_results_biz_id=123).allow_partial_es_results)
            self.assertFalse(UnifyQueryHandler(params).allow_partial_es_results)
            switch.assert_called_once_with("retrieve_partial_es_results", biz_id=123)
            _scope.assert_called_once()
        handler.query_ts_reference = Mock(side_effect=[{"series": []}, {"series": [{"values": [[1000, 7]]}]}])
        with patch("apps.log_search.views.aggs_views.UnifyQueryHandler", return_value=handler):
            view = AggsViewSet()
            view.params_valid = Mock(return_value={})
            self.assertEqual(view.date_histogram(RequestFactory().post("/"), 10).data, {"aggs": {}})
        with patch("apps.log_search.views.field_views.UnifyQueryFieldHandler", return_value=handler):
            view = FieldViewSet()
            view.params_valid = Mock(return_value={})
            self.assertEqual(view.fetch_statistics_total(RequestFactory().post("/")).data, {"total_count": 7})
        for call in handler.query_ts_reference.call_args_list:
            self.assertNotIn("allow_partial_es_results", call.args[0])
            self.assertFalse(call.kwargs["raise_exception"])

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
        handler.allow_partial_es_results = True
        self.assertEqual(handler.get_total_count(), 7)
        self.assertTrue(handler.query_ts_reference.call_args.args[0]["allow_partial_es_results"])
        handler.allow_partial_es_results = False
        self.assertEqual(handler.get_total_count(), 7)
        self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])
        self.assertFalse(handler.query_ts_reference.call_args.kwargs["raise_exception"])
