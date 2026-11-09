"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.

Run with unittest. The source methods execute against in-memory dependencies,
without starting Django or connecting to databases and query services.
"""

import ast
import copy
import datetime
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


APPS = Path(__file__).resolve().parents[2]


def source_members(path, names, namespace, class_name=None):
    tree = ast.parse((APPS / path).read_text())
    if class_name:
        node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name)
        node.bases = []
        node.body = [item for item in node.body if getattr(item, "name", None) in names]
        tree.body = [node]
    else:
        tree.body = [item for item in tree.body if getattr(item, "name", None) in names]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    exec(compile(ast.fix_missing_locations(tree), str(APPS / path), "exec"), namespace)
    return namespace[class_name] if class_name else namespace


class IncompleteResultError(Exception):
    pass


def dependencies():
    namespace = {
        "copy": copy,
        "_": lambda message: message,
        "BaseSearchException": IncompleteResultError,
        "MAX_RESULT_WINDOW": 10000,
        "settings": SimpleNamespace(PRE_SEARCH_SECONDS=10),
        "arrow": SimpleNamespace(get=datetime.datetime.fromtimestamp),
        "AggsHandlers": SimpleNamespace(DATETIME_FORMAT_MAP={}, DATETIME_FORMAT=""),
        "timestamp_to_timeformat": lambda value, *_args, **_kwargs: str(value),
        "logger": Mock(),
        "UnifyQueryApi": Mock(),
        "Scenario": SimpleNamespace(ES="es"),
        "SEARCH_AFTER_KEY": "search_after",
        "MAX_ASYNC_COUNT": 10000,
    }
    source_members("log_unifyquery/partial.py", {"is_partial_result", "require_complete_result"}, namespace)
    return namespace


def raw_partial(rows=None):
    return {
        "list": [] if rows is None else rows,
        "total": 1,
        "status": {"code": "QUERY_RAW_PARTIAL", "message": "shard failure"},
    }


class PartialResultsTests(unittest.TestCase):
    def setUp(self):
        self.env = dependencies()
        self.base = source_members(
            "log_unifyquery/handler/base.py",
            {
                "search",
                "date_histogram",
                "_date_histogram_unify_query",
                "obtain_result_data",
                "project_export_rows",
                "pre_get_result",
                "search_after_result",
                "query_ts_raw_with_scroll",
            },
            self.env,
            "UnifyQueryHandler",
        )
        self.scene = source_members(
            "log_unifyquery/handler/scene_search.py",
            {"search", "aggs_date_histogram", "total", "pre_get_result"},
            self.env,
            "SceneUnifyQueryHandler",
        )

    def handler(self, handler_type=None):
        handler = (handler_type or self.base)()
        handler.base_dict = {"query_list": [{"function": []}]}
        handler.search_params = {"size": 2, "begin": 0, "original_search": True, "scenario_id": "es"}
        handler.highlight = False
        handler.start_time, handler.end_time = 1, 100
        handler.query_ts_raw = Mock()
        handler._deal_query_result = lambda response, **_kwargs: response
        handler._init_scene_desensitize = Mock()
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

    def test_scene_list_supports_partial_and_preserves_source_request(self):
        handler = self.handler(self.scene)
        handler.query_ts_raw.return_value = raw_partial([{"message": "available"}])
        result = handler.search(allow_partial_es_results=True)
        self.assertTrue(result["is_partial"])
        self.assertTrue(handler.query_ts_raw.call_args.args[0]["allow_partial_es_results"])
        self.assertNotIn("allow_partial_es_results", handler.base_dict)

    def test_shared_handler_defaults_do_not_enable_other_callers(self):
        for handler_type in (self.base, self.scene):
            with self.subTest(handler=handler_type.__name__):
                handler = self.handler(handler_type)
                handler.query_ts_raw.return_value = {"list": [{}, {}]}
                handler.search(search_type=None)
                self.assertNotIn("allow_partial_es_results", handler.query_ts_raw.call_args.args[0])
        handler = self.handler()
        handler.search_params.update(interval="1m", group_field=None)
        handler.query_ts_reference = Mock(return_value={"series": []})
        handler.date_histogram()
        self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])
        self.assertFalse(handler.query_ts_reference.call_args.kwargs["raise_exception"])

    def test_only_interactive_views_explicitly_enable_partial_results(self):
        for path, class_name, methods in (
            ("log_search/views/search_views.py", "SearchViewSet", ("search", "union_search")),
            ("log_search/views/aggs_views.py", "AggsViewSet", ("date_histogram", "union_search_date_histogram")),
            ("log_search/views/scene_search_views.py", "SceneSearchViewSet", ("search", "aggs_date_histogram")),
        ):
            for method in methods:
                with self.subTest(view=class_name, method=method):
                    child = Mock()
                    child.search.return_value = {}
                    env = {
                        "list_route": lambda **_kwargs: lambda function: function,
                        "detail_route": lambda **_kwargs: lambda function: function,
                        "search_history_record": lambda function: function,
                        "Response": lambda data: SimpleNamespace(data=data),
                        "UnifyQueryHandler": Mock(return_value=child),
                        "SceneUnifyQueryHandler": Mock(return_value=child),
                        "UnionSearchHandler": Mock(return_value=child),
                        "_apply_index_set_search_bk_biz_id": Mock(),
                        "_reject_platform_index_sets": Mock(),
                        "_merge_scene_filters_to_addition": lambda data: data,
                        "AllConditionsBuilder": SimpleNamespace(from_raw=lambda value: value),
                        "Permission": SimpleNamespace(get_auth_info=lambda *_args, **_kwargs: None),
                    }
                    for serializer in (
                        "SearchAttrSerializer",
                        "UnionSearchAttrSerializer",
                        "DateHistogramSerializer",
                        "UnionSearchDateHistogramSerializer",
                        "SceneSearchSerializer",
                        "SceneAggsDateHistogramSerializer",
                    ):
                        env[serializer] = object()
                    view = source_members(path, {method}, env, class_name)()
                    view.get_object = Mock()
                    view.request = object()
                    view.params_valid = Mock(
                        return_value={
                            "record_history": False,
                            "table_id_conditions": [],
                            "index_set_ids": [101],
                        }
                    )
                    getattr(view, method)(view.request)
                    called = {
                        "union_search": child.unifyquery_union_search,
                        "date_histogram": child.date_histogram,
                        "union_search_date_histogram": child.date_histogram,
                        "aggs_date_histogram": child.aggs_date_histogram,
                    }.get(method, child.search)
                    self.assertTrue(called.call_args.kwargs["allow_partial_es_results"])

    def test_interactive_lists_keep_hard_failure(self):
        for handler_type in (self.base, self.scene):
            with self.subTest(handler=handler_type.__name__):
                handler = self.handler(handler_type)
                handler.query_ts_raw.side_effect = TimeoutError("query timed out")
                with self.assertRaises(TimeoutError):
                    handler.search(allow_partial_es_results=True)

    def test_export_lists_require_complete_results(self):
        for handler_type in (self.base, self.scene):
            with self.subTest(handler=handler_type.__name__):
                handler = self.handler(handler_type)
                handler.query_ts_raw.return_value = raw_partial([{}])
                with self.assertRaises(IncompleteResultError):
                    handler.search(is_export=True, allow_partial_es_results=True)
                self.assertNotIn("allow_partial_es_results", handler.query_ts_raw.call_args.args[0])

    def test_empty_histograms_keep_partial_status(self):
        for scene in (False, True):
            with self.subTest(scene=scene):
                handler = self.handler()
                handler.search_params.update(interval="1m", group_field=None)
                handler.query_ts_reference = Mock(
                    return_value={"series": [], "is_partial": True, "status": {"code": "QUERY_TS_PARTIAL"}}
                )
                result = (
                    self.scene.aggs_date_histogram(handler, allow_partial_es_results=True)
                    if scene
                    else handler.date_histogram(allow_partial_es_results=True)
                )
                self.assertEqual(result["aggs"], {})
                self.assertTrue(result["is_partial"])
                self.assertEqual(result["status"]["code"], "QUERY_TS_PARTIAL")
                self.assertTrue(handler.query_ts_reference.call_args.args[0]["allow_partial_es_results"])
                self.assertTrue(handler.query_ts_reference.call_args.kwargs["raise_exception"])
                self.assertNotIn("allow_partial_es_results", handler.base_dict)

    def test_populated_histogram_preserves_values_and_partial(self):
        result = self.base.obtain_result_data(
            "1m",
            None,
            {
                "series": [{"values": [[1000, 7], [2000, 0]]}],
                "is_partial": True,
            },
        )
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

    def test_scroll_download_and_projection_reject_partial(self):
        self.env["UnifyQueryApi"].query_ts_raw_with_scroll.return_value = raw_partial([{}])
        with self.assertRaises(IncompleteResultError):
            self.base.query_ts_raw_with_scroll({})
        with self.assertRaises(IncompleteResultError):
            self.handler().project_export_rows(raw_partial([{}]))

    def test_export_precheck_and_exact_total_reject_partial(self):
        for handler_type in (self.base, self.scene):
            with self.subTest(handler=handler_type.__name__):
                handler = self.handler(handler_type)
                self.env["UnifyQueryApi"].query_ts_raw.return_value = raw_partial([{}])
                handler.query_ts_raw.return_value = raw_partial([{}])
                with self.assertRaises(IncompleteResultError):
                    handler.pre_get_result([], 1)
        scene = self.handler(self.scene)
        scene.space_uid = "test-space"
        scene.query_ts_raw.return_value = raw_partial([{}])
        with self.assertRaises(IncompleteResultError):
            scene.total()

    def test_export_statistics_reject_partial(self):
        self.env.update(
            ExportErrorCode=SimpleNamespace(STATISTICS_FAILED="statistics-failed"),
            apply_time_range=lambda *_args: None,
        )
        source_members(
            "log_search/export/planner.py",
            {"PlanError", "_series_points", "_statistics_params", "count_rows", "histogram", "sample_rows"},
            self.env,
        )
        handler = self.handler()
        handler.export_time_fields = []
        for marker in ({"is_partial": True}, {"status": {"code": "QUERY_TS_PARTIAL"}}):
            with self.subTest(marker=marker):
                self.env["UnifyQueryApi"].query_ts_reference.return_value = {
                    "series": [{"values": [[1000, 7]]}],
                    **marker,
                }
                for operation in ("count_rows", "histogram"):
                    with self.subTest(operation=operation), self.assertRaises(self.env["PlanError"]):
                        args = (handler, 0, 2000) if operation == "count_rows" else (handler, 0, 2000, 1000)
                        self.env[operation](*args)
        self.env["UnifyQueryApi"].query_ts_raw.return_value = raw_partial([{}])
        with self.assertRaises(IncompleteResultError):
            self.env["sample_rows"](handler, 0, 2000, 1)

    def test_page_total_count_requires_complete_response_and_preserves_zero(self):
        field_type = source_members(
            "log_unifyquery/handler/field.py",
            {"get_total_count", "handle_count_data"},
            self.env,
            "UnifyQueryFieldHandler",
        )
        handler = field_type()
        handler.result_merge_base_dict = {"query_list": [{}]}
        handler.query_ts_reference = Mock()
        for response in (
            {"series": [], "is_partial": True},
            {"series": [{"values": [[1000, 7]]}], "status": {"code": "QUERY_TS_PARTIAL"}},
        ):
            with self.subTest(response=response):
                handler.query_ts_reference.return_value = response
                with self.assertRaises(IncompleteResultError):
                    handler.get_total_count()
                self.assertTrue(handler.query_ts_reference.call_args.kwargs["raise_exception"])
                self.assertNotIn("allow_partial_es_results", handler.query_ts_reference.call_args.args[0])
        handler.query_ts_reference.side_effect = TimeoutError("count timed out")
        with self.assertRaises(TimeoutError):
            handler.get_total_count()
        handler.query_ts_reference.side_effect = None
        handler.query_ts_reference.return_value = {"series": [{"values": [[1000, 0]]}]}
        self.assertEqual(handler.get_total_count(), 0)
        handler.query_ts_reference.return_value = {"series": []}
        self.assertEqual(handler.get_total_count(), 0)

    def test_union_list_merges_partial_and_keeps_export_strict(self):
        env = dependencies()
        index_sets = [
            SimpleNamespace(
                index_set_id=index,
                scenario_id="es",
                time_field="timestamp",
                time_field_type="long",
                time_field_unit="millisecond",
            )
            for index in (101, 102)
        ]
        env.update(
            LogIndexSet=SimpleNamespace(objects=SimpleNamespace(filter=lambda **_kwargs: index_sets)),
            SearchHandler=SimpleNamespace(init_time_field=lambda *_args: ("timestamp", "long", "millisecond")),
            TIME_FIELD_MULTIPLE_MAPPING={},
            BaseSearchIndexSetException=ValueError,
            UnionSearchErrorException=ValueError,
        )

        class SequentialTasks:
            def __init__(self):
                self.tasks = {}

            def append(self, key, fn, params=None, multi_func_params=False):
                self.tasks[key] = lambda: fn(**(params or {}))

            def run(self, return_exception=False):
                return {key: operation() for key, operation in self.tasks.items()}

        env["MultiExecuteFunc"] = SequentialTasks
        union_type = source_members(
            "log_search/handlers/search/search_handlers_esquery.py",
            {"unifyquery_union_search"},
            env,
            "UnionSearchHandler",
        )
        calls = []

        def child_handler(params):
            index = params["index_set_ids"][0]

            def search(is_export=False, allow_partial_es_results=False):
                calls.append((is_export, allow_partial_es_results))
                row = {"__index_set_id__": index, "timestamp": index}
                return {
                    "list": [row],
                    "origin_log_list": [row.copy()],
                    "total": 1,
                    "took": 1,
                    "is_partial": index == 101 and not is_export,
                }

            return SimpleNamespace(search=search)

        base_module = types.ModuleType("apps.log_unifyquery.handler.base")
        base_module.UnifyQueryHandler = child_handler
        partial_module = types.ModuleType("apps.log_unifyquery.partial")
        partial_module.is_partial_result = env["is_partial_result"]
        union = union_type()
        union.index_set_ids = [101, 102]
        union.search_dict = {"size": 10}
        union.union_configs = [{"index_set_id": index, "begin": 0} for index in union.index_set_ids]
        union.desensitize_mapping = {}
        union.sort_list = []
        union._init_sort_list = lambda **_kwargs: []
        union._save_union_search_history = Mock()
        with patch.dict(
            sys.modules,
            {
                "apps.log_unifyquery.handler.base": base_module,
                "apps.log_unifyquery.partial": partial_module,
            },
        ):
            result = union.unifyquery_union_search(allow_partial_es_results=True)
            self.assertTrue(result["is_partial"])
            self.assertEqual(result["total"], 2)
            self.assertEqual(calls, [(False, True), (False, True)])
            calls.clear()
            union.unifyquery_union_search(is_export=True)
            self.assertEqual(calls, [(True, False), (True, False)])


if __name__ == "__main__":
    unittest.main()
