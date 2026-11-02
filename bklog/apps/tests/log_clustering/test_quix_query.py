import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.log_clustering.handlers.quix.query import (
    ClusteringPreviewQuery,
    QuixPatternHandler,
    apply_query_scope,
    result_query,
)
from apps.log_clustering.models import ClusteringConfig, ClusteringRemark, LogClusteringRuntime
from apps.log_search.models import LogIndexSet, Scenario
from apps.log_search.views.search_views import SearchViewSet
from apps.log_clustering.views.clustering_config_views import ClusteringConfigViewSet
from apps.log_clustering.views.pattern_views import PatternViewSet
from apps.tests.log_clustering.test_pattern_search import PARAMS

MODULE = "apps.log_clustering.handlers.quix.query"


class TestQuixPatternQuery(TestCase):
    def setUp(self):
        self.index = LogIndexSet.objects.create(index_set_id=42, space_uid="bkcc__2", scenario_id=Scenario.LOG)
        self.runtime = SimpleNamespace(
            index_set_id=42,
            bk_tenant_id="system",
            pattern_index="log-clustering-42-pattern",
            active_config={"distance_threshold": "0.5", "input_mapping": {"log": "message"}},
            pending_config={"distance_threshold": "0.7"},
        )
        self.params = {
            **copy.deepcopy(PARAMS),
            "bk_biz_id": 2,
            "sort_list": [["dtEventTimeStamp", "desc"]],
            "owner_config": "all",
            "group_by": ["host"],
            "addition": [{"field": "__dist_05", "operator": "is not", "value": ""}],
        }
        ClusteringConfig.objects.create(
            index_set_id=42,
            bk_biz_id=2,
            min_members=1,
            max_dist_list="0.5",
            predefined_varibles="",
            delimeter="",
            max_log_length=1000,
        )
        self.handler = QuixPatternHandler(self.runtime, self.params)
        self.start_patch(
            "apps.log_unifyquery.handler.mapping.UnifyQueryMappingHandler.get_all_fields_by_index_id",
            return_value=([], []),
        )
        self.start_patch(
            "apps.log_search.models.LogIndexSet.get_indexes", return_value=[{"result_table_id": "2_bklog.source"}]
        )

    def test_creation_preview_reads_source_and_preserves_rule_connectors(self):
        view = ClusteringConfigViewSet()
        view.params_valid = lambda _: {
            "start_time": self.params["start_time"],
            "end_time": self.params["end_time"],
            "addition": [
                {"field": "level", "operator": "=", "value": ["error"]},
                {"field": "message", "operator": "contains", "value": ["timeout"], "condition": "OR"},
            ],
        }
        request = SimpleNamespace(data={"bk_biz_id": 2}, query_params={})
        with (
            patch.object(ClusteringPreviewQuery, "search", return_value={"list": []}) as search,
            patch.object(ClusteringPreviewQuery, "date_histogram", autospec=True, return_value={"aggs": {}}) as trend,
        ):
            response = view.preview_access(request, index_set_id=42)
        search.assert_called_once_with(search_type="")
        query = trend.call_args.args[0]
        self.assertEqual(query.index_set_ids, [42])
        conditions = query.base_dict["query_list"][0]["conditions"]
        self.assertEqual(conditions["condition_list"], ["or"])
        self.assertEqual([f["op"] for f in conditions["field_list"]], ["eq", "contains"])
        self.assertEqual(response.data, {"list": [], "aggs": {}})

    def start_patch(self, target, **kwargs):
        p = patch(target, **kwargs)
        obj = p.start()
        self.addCleanup(p.stop)
        return obj

    def test_page_counts_from_clustered_and_templates_from_pattern(self):
        # 保留真实条件组装、响应解析和备注继承，只替换外部传输。
        self.start_patch("apps.log_clustering.handlers.pattern.PatternHandler._get_new_class", return_value=set())

        def run(tasks):
            for task in tasks.task_list:
                task.run(return_exception=True)
            for value in tasks.results.values():
                if isinstance(value, Exception):
                    raise value
            return tasks.results

        self.start_patch(MODULE + ".QuixPatternHandler._run_multi_execute", side_effect=run)
        query = self.start_patch(
            "apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_reference",
            return_value={
                "series": [
                    {"group_keys": ["host", "log_signature"], "group_values": ["node", "a"], "values": [[0, 3]]},
                    {"group_keys": ["host", "log_signature"], "group_values": ["node", "b"], "values": [[0, 2]]},
                ]
            },
        )
        self.start_patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle", return_value=None)
        ClusteringRemark.objects.create(bk_biz_id=2, signature="a", group_hash="", owners=["operator"])
        self.handler._include_origin_log = True
        raw = self.start_patch(
            "apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_raw",
            side_effect=[
                {"list": [{"signature": "a", "pattern": "error <*>"}]},
                {"list": [{"log_signature": "a", "message": "sample log", "host": "node"}]},
            ],
        )
        rows = self.handler.pattern_search()
        self.assertEqual([r["origin_log"] for r in rows], ["sample log", ""])
        self.assertEqual(raw.call_count, 2)
        self.assertEqual(raw.call_args.args[0]["query_list"][0]["collapse"], {"field": "log_signature"})
        self.assertEqual(
            [(row["signature"], row["count"], row["pattern"], row["group"]) for row in rows],
            [("a", 3, "error <*>", ["node"]), ("b", 2, "", ["node"])],
        )
        self.assertEqual(rows[0]["owners"], ["operator"])
        args = query.call_args.args[0]
        q = args["query_list"][0]
        self.assertEqual(q["table_id"], "bklog_index_set_42_clustered")
        self.assertEqual(q["function"][0]["dimensions"], ["log_signature", "host"])
        self.assertIn(
            {"field_name": "log_cluster_distance_threshold", "op": "eq", "value": ["0.5"]},
            q["conditions"]["field_list"],
        )
        template_call = raw.call_args_list[0]
        self.assertEqual(template_call.kwargs["bk_tenant_id"], "system")
        template_request = template_call.args[0]
        self.assertEqual(template_request["bk_biz_id"], 2)
        template = template_request["query_list"][0]
        self.assertEqual(template["table_id"], "bklog_index_set_42_pattern")
        conditions = {f["field_name"]: set(f["value"]) for f in template["conditions"]["field_list"]}
        self.assertEqual(conditions, {"signature": {"a", "b"}, "index_set_id": {"42"}, "distance_threshold": {"0.5"}})

    def test_historical_page_template_window_includes_later_refresh(self):
        self.start_patch(MODULE + ".get_local_param", return_value="Asia/Shanghai")
        now = datetime(2026, 11, 2, 4, tzinfo=timezone.utc)
        self.start_patch(MODULE + ".timezone.now", return_value=now)
        raw = self.start_patch(MODULE + ".UnifyQueryApi.query_ts_raw", return_value={"list": []})
        self.params.update(start_time="2026-11-01 10:00:00", end_time="2026-11-01 11:00:00")
        self.handler._signature_patterns(["a"])
        payload = raw.call_args.args[0]
        expected_start = datetime(2026, 10, 31, 2, tzinfo=timezone.utc)
        self.assertEqual(payload["start_time"], str(int(expected_start.timestamp() * 1000)))
        self.assertEqual(payload["end_time"], str(int(now.timestamp() * 1000)))

    def test_drilldown_keeps_time_group_and_effective_level(self):
        params = {
            **self.params,
            "addition": [
                {"field": "host", "operator": "is", "value": ["node"]},
                {"field": "__dist_05", "operator": "is", "value": ["a"]},
            ],
        }
        query = result_query(42, self.runtime.active_config, params).base_dict
        self.assertLess(int(query["start_time"]), int(query["end_time"]))
        fields = query["query_list"][0]["conditions"]["field_list"]
        self.assertEqual(
            [(x["field_name"], x["value"]) for x in fields],
            [("host", ["node"]), ("log_signature", ["a"]), ("log_cluster_distance_threshold", ["0.5"])],
        )
        self.assertEqual(query["query_list"][0]["table_id"], "bklog_index_set_42_clustered")
        self.assertEqual(params["addition"][-1]["field"], "__dist_05")
        params["addition"][-1]["field"] = "__dist_07"
        with self.assertRaises(ValidationError):
            result_query(42, self.runtime.active_config, params)
        self.assertEqual(QuixPatternHandler(self.runtime, {**self.params, "pattern_level": "07"}).pattern_search(), [])

    def test_template_query_error_is_not_a_missing_template(self):
        raw = self.start_patch(MODULE + ".UnifyQueryApi.query_ts_raw", side_effect=RuntimeError("route unavailable"))
        self.assertEqual(self.handler._signature_patterns([]), [])
        raw.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "route unavailable"):
            self.handler._signature_patterns(["a"])

    def test_product_entry_points_use_effective_runtime_after_close(self):
        LogClusteringRuntime.objects.create(
            index_set_id=42,
            bk_biz_id=2,
            collector_config_id=1,
            bk_data_id=1,
            table_id="2_bklog.source",
            phase="stopped",
            active_config=self.runtime.active_config,
            pending_config=self.runtime.pending_config,
            pattern_index=self.runtime.pattern_index,
        )
        request = SimpleNamespace(data={}, query_params={})
        search_params = {
            **self.params,
            "begin": 0,
            "size": 1,
            "addition": [{"field": "__dist_05", "operator": "is", "value": ["a"]}],
        }
        raw = self.start_patch(
            "apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_raw",
            return_value={"list": [{"log_signature": "a", "message": "original"}], "total": 1},
        )
        self.start_patch("apps.log_unifyquery.handler.base.UnifyQueryHandler._analyze_field_length", return_value={})
        self.start_patch("apps.log_unifyquery.handler.base.UnifyQueryHandler._save_history")
        view = SimpleNamespace(params_valid=lambda serializer: search_params, get_object=lambda: self.index)
        response = SearchViewSet.search(view, request, "42")
        self.assertEqual(response.data["list"][0]["message"], "original")
        q = raw.call_args.args[0]["query_list"][0]
        self.assertEqual(q["table_id"], "bklog_index_set_42_clustered")
        self.assertEqual(
            [(f["field_name"], f["value"]) for f in q["conditions"]["field_list"]],
            [("log_signature", ["a"]), ("log_cluster_distance_threshold", ["0.5"])],
        )
        page = SimpleNamespace(params_valid=lambda serializer: {**self.params, "pattern_level": "07"})
        self.assertEqual(PatternViewSet.search(page, request, "42").data, [])

    def test_cross_space_request_denied(self):
        self.index.is_platform_index = True
        with self.assertRaises(PermissionDenied):
            apply_query_scope(self.index, {"bk_biz_id": 3}, SimpleNamespace(data={}, query_params={}))
