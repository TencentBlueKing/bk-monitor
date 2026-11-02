import copy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.log_clustering.handlers.quix.query import QuixPatternHandler, apply_query_scope, result_query
from apps.log_clustering.models import ClusteringConfig, ClusteringRemark, LogClusteringRuntime
from apps.log_search.models import LogIndexSet, Scenario
from apps.log_search.views.search_views import SearchViewSet
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
        rt = "bklog_index_set_42_pattern.__default__"
        route = self.start_patch(
            MODULE + ".TransferApi.get_result_table_storage",
            return_value={
                rt: {"cluster_config": {"cluster_id": 7}, "storage_config": {"index_set": self.runtime.pattern_index}}
            },
        )
        dsl = self.start_patch(
            MODULE + ".BkLogApi.dsl",
            return_value={"hits": {"hits": [{"_source": {"signature": "a", "pattern": "error <*>"}}]}},
        )
        self.start_patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle", return_value=None)
        ClusteringRemark.objects.create(bk_biz_id=2, signature="a", group_hash="", owners=["operator"])
        self.handler._include_origin_log = True
        raw = self.start_patch(
            "apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_raw",
            return_value={"list": [{"log_signature": "a", "message": "sample log", "host": "node"}]},
        )
        rows = self.handler.pattern_search()
        self.assertEqual([r["origin_log"] for r in rows], ["sample log", ""])
        raw.assert_called_once()
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
        self.assertEqual(route.call_args.args[0]["data_label"], "bklog_index_set_42_pattern")
        payload = dsl.call_args.args[0]
        self.assertEqual(
            (payload["indices"], payload["storage_cluster_id"], payload["index_set_id"]),
            (self.runtime.pattern_index, 7, 42),
        )
        self.assertEqual(dsl.call_args.kwargs["bk_tenant_id"], "system")
        self.assertEqual(
            set(payload["body"]["query"]["ids"]["values"]),
            {
                "8d06980787765a76ad75687053bad5b38dc255a56edd5198c8ae5e120bb6d32f",
                "909bcb0ace1e5b7241fd8f8e28b367cd9e39bc8ca8b2c42e9a9304cbb6c0e731",
            },
        )

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

    def test_missing_route_fails_without_querying_es(self):
        route = self.start_patch(MODULE + ".TransferApi.get_result_table_storage", return_value={})
        dsl = self.start_patch(MODULE + ".BkLogApi.dsl")
        self.assertEqual(self.handler._signature_patterns([]), [])
        route.assert_not_called()
        with self.assertRaises(ValidationError):
            self.handler._signature_patterns(["a"])
        dsl.assert_not_called()

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
