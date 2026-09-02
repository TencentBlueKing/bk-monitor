import copy
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.log_query import (
    CLUSTERING_PATTERN_PARAMS_SCHEMA,
    FUNCTIONS,
    SEARCH_PARAMS_SCHEMA,
    ResourceAggsHandlers,
    ResourceAggsViewAdapter,
    ResourceClusteringSearchHandler,
    ResourceClusteringUnifyQueryHandler,
    ResourceMappingHandlers,
    ResourceSceneUnifyQueryHandler,
    ResourceSearchHandler,
    ResourceUnifyQueryTermsAggsHandler,
    _bounded_items,
    _context_time_bounds,
    _index_set_fields,
    _resolve_source,
    _route_evidence,
    _run_query,
    _scene_target,
    _validate_context_anchor,
    aggregate_logs,
    get_log_context,
    search_clustering_patterns,
    search_logs,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_clustering.constants import PatternEnum, StorageTypeEnum
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.constants import IndexSetDataType
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers, AggsViewAdapter
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler as SearchHandlerEsquery
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario, Space
from apps.log_unifyquery.builder.context import CreateSearchContextBodyScenarioLog
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.local import del_local_param, get_local_param, set_local_param


def create_index_set(index_set_id, *, is_group=False, scenario_id=Scenario.LOG, fields_snapshot=None):
    return LogIndexSet.objects.create(
        index_set_id=index_set_id,
        index_set_name=f"index-{index_set_id}",
        space_uid="bkcc__2",
        category_id="application",
        scenario_id=scenario_id,
        is_group=is_group,
        fields_snapshot=fields_snapshot
        or {
            "fields": [
                {"field_name": "dtEventTimeStamp", "field_type": "long"},
                {"field_name": "level", "field_type": "keyword"},
            ]
        },
    )


def create_result_table(index_set_id, result_table_id, *, scenario_id=Scenario.LOG, index_id=None):
    return LogIndexSetData.objects.create(
        index_id=index_id or index_set_id,
        index_set_id=index_set_id,
        bk_biz_id=2,
        result_table_id=result_table_id,
        scenario_id=scenario_id,
        time_field="dtEventTimeStamp",
        time_field_type="date",
        time_field_unit="millisecond",
        apply_status=LogIndexSetData.Status.NORMAL,
        type=IndexSetDataType.RESULT_TABLE.value,
    )


def create_clustering_config(index_set_id, *, clustered_rt=None, new_cls_index_set_id=None, storage_type=None):
    return ClusteringConfig.objects.create(
        index_set_id=index_set_id,
        new_cls_index_set_id=new_cls_index_set_id,
        min_members=1,
        max_dist_list="0.5",
        predefined_varibles="",
        delimeter="",
        max_log_length=1024,
        clustering_fields="log",
        bk_biz_id=2,
        clustered_rt=clustered_rt if clustered_rt is not None else f"2_bklog_{index_set_id}_clustered",
        storage_type=storage_type or StorageTypeEnum.DORIS.value,
        signature_enable=True,
    )


class LogQueryMetadataTest(TestCase):
    def test_meta_exposes_six_strict_handlers_to_non_management_app(self):
        metadata = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        expected = {
            "bklog.log.fields",
            "bklog.log.search",
            "bklog.log.aggregate",
            "bklog.log.context",
            "bklog.log.scene.resolve",
            "bklog.clustering.pattern.search",
        }
        self.assertTrue(expected.issubset(set(metadata["functions"])))
        for func_name in expected:
            detail = AdminResourceRegistry.call(
                "__meta__",
                {"action": "detail", "target_func_name": func_name},
                app_code="resource-reader",
            )
            self.assertIn(detail["safety_level"], {"read", "inspect"})
            self.assertIn("params_schema", detail)
            self.assertIn("response_schema", detail)
            self.assertTrue(detail["examples"])
            self.assertTrue(detail["limits"])
            self.assertTrue(detail["errors"])

    def test_latest_search_contract_uses_existing_bklog_query_names(self):
        properties = SEARCH_PARAMS_SCHEMA["properties"]

        for field in (
            "keyword",
            "addition",
            "sort_list",
            "begin",
            "size",
            "track_total_hits",
            "is_desensitize",
        ):
            self.assertIn(field, properties)
        for obsolete in ("query_string", "filters", "sort", "page", "page_size", "highlight"):
            self.assertNotIn(obsolete, properties)
        clustering_schema = SEARCH_PARAMS_SCHEMA["properties"]["source"]["oneOf"][2]
        self.assertNotIn("pattern_level", clustering_schema["properties"])
        self.assertTrue(properties["is_desensitize"]["const"])

    def test_pattern_contract_uses_clustering_source_without_public_pattern_level(self):
        self.assertIn("source", CLUSTERING_PATTERN_PARAMS_SCHEMA["required"])
        self.assertNotIn("index_set_id", CLUSTERING_PATTERN_PARAMS_SCHEMA["properties"])
        self.assertNotIn("pattern_level", CLUSTERING_PATTERN_PARAMS_SCHEMA["properties"])

    def test_new_handlers_reject_obsolete_or_extra_fields(self):
        valid = {
            "source": {"type": "index_set", "index_set_id": 1},
            "start_time": 1,
            "end_time": 2,
        }
        for extra in ("query_string", "page_size", "cookie"):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                AdminResourceRegistry.call(
                    "bklog.log.search",
                    {**valid, extra: "not-allowed"},
                    app_code="resource-reader",
                )
        with self.assertRaises(ValidationError):
            AdminResourceRegistry.call(
                "bklog.log.search",
                {
                    **valid,
                    "source": {"type": "clustering", "index_set_id": 1, "pattern_level": "05"},
                },
                app_code="resource-reader",
            )

    def test_response_contract_is_direct_and_not_double_wrapped(self):
        search_response = FUNCTIONS["bklog.log.search"]["response_schema"]

        self.assertIn("items", search_response["properties"])
        self.assertIn("route", search_response["properties"])
        self.assertIn("warnings", search_response["properties"])
        self.assertNotIn("data", search_response["properties"])


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
class ClusteringRouteTest(TestCase):
    def setUp(self):
        self.original = create_index_set(100, scenario_id=Scenario.BKDATA)
        self.new_class = create_index_set(101, scenario_id=Scenario.BKDATA)
        self.group = create_index_set(102, is_group=True, scenario_id=Scenario.BKDATA)
        create_result_table(100, "2_bklog_source", scenario_id=Scenario.BKDATA, index_id=1100)
        LogIndexSetData.objects.create(
            index_id=1102,
            index_set_id=102,
            bk_biz_id=2,
            result_table_id="100",
            scenario_id=Scenario.BKDATA,
            apply_status=LogIndexSetData.Status.NORMAL,
            type=IndexSetDataType.INDEX_SET.value,
        )
        self.config = create_clustering_config(100, new_cls_index_set_id=101)

    def test_original_new_class_and_group_keep_entry_data_label(self):
        for entry_index_set_id in (100, 101, 102):
            with self.subTest(entry_index_set_id=entry_index_set_id):
                source = _resolve_source({"type": "clustering", "index_set_id": entry_index_set_id})
                route = _route_evidence(
                    source,
                    result_table_ids=[self.config.clustered_rt],
                    index_set_ids=[entry_index_set_id],
                )

                self.assertEqual(route["route_reason"], "explicit_source")
                self.assertFalse(route["fallback"])
                self.assertEqual(route["result_table_ids"], [self.config.clustered_rt])
                self.assertEqual(route["data_labels"], [f"bklog_index_set_{entry_index_set_id}_clustered"])

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch(
        "apps.log_unifyquery.handler.base.UnifyQueryHandler._transform_additions",
        return_value={"field_list": [], "condition_list": []},
    )
    def test_unify_query_route_is_pinned_before_keyword_and_addition_parsing(self, _mock_transform, _mock_switch):
        source = _resolve_source({"type": "clustering", "index_set_id": self.group.index_set_id})
        query = {
            "index_set_ids": [self.group.index_set_id],
            "bk_biz_id": 2,
            "start_time": 1767225600000,
            "end_time": 1767229200000,
            "keyword": "ordinary text without clustering markers",
            "addition": [],
            "sort_list": [["dtEventTimeStamp", "desc"]],
            "size": 10,
            "begin": 0,
            "is_desensitize": True,
        }

        handler = ResourceClusteringUnifyQueryHandler(query, clustering_config=source["clustering_config"])

        self.assertEqual(handler.base_dict["query_list"][0]["table_id"], "bklog_index_set_102_clustered")
        self.assertEqual(handler.index_info_list[0]["indices"], self.config.clustered_rt)
        self.assertEqual(handler.index_info_list[0]["scenario_id"], Scenario.BKDATA)

    def test_missing_config_and_missing_result_table_return_stable_errors(self):
        create_index_set(200)
        with self.assertRaises(ValidationError) as missing_config:
            _resolve_source({"type": "clustering", "index_set_id": 200})
        self.assertEqual(str(missing_config.exception.code), "3624112")

        create_index_set(201)
        create_clustering_config(201, clustered_rt="")
        with self.assertRaises(ValidationError) as missing_rt:
            _resolve_source({"type": "clustering", "index_set_id": 201})
        self.assertEqual(str(missing_rt.exception.code), "3624113")

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch("apps.log_admin_resource.handlers.log_query._clustering_search")
    def test_search_uses_explicit_clustering_route_without_marker_detection(self, mock_search, _mock_switch):
        mock_search.return_value = {
            "list": [
                {
                    "dtEventTimeStamp": 1767227400000,
                    "gseindex": 100,
                    "_iteration_idx": 1,
                    "ip": "127.0.0.1",
                    "path": "/data/log/app.log",
                    "log": "ordinary record",
                }
            ],
            "total": 1,
            "took": 0.1,
            "fields": {},
        }

        result = search_logs(
            {
                "source": {"type": "clustering", "index_set_id": self.group.index_set_id},
                "start_time": 1767225600000,
                "end_time": 1767229200000,
                "keyword": "ordinary text without clustering markers",
                "addition": [],
                "begin": 0,
                "size": 10,
                "is_desensitize": True,
            }
        )

        query = mock_search.call_args.args[1]
        self.assertEqual(query["keyword"], "ordinary text without clustering markers")
        self.assertEqual(query["addition"], [])
        self.assertEqual(result["route"]["clustered_rt"], self.config.clustered_rt)
        self.assertEqual(result["route"]["data_labels"], ["bklog_index_set_102_clustered"])
        self.assertEqual(result["items"][0]["context_anchor"]["result_table_id"], self.config.clustered_rt)
        validate_params(result, FUNCTIONS["bklog.log.search"]["response_schema"], "response")

    @patch("apps.log_admin_resource.handlers.log_query._clustering_search")
    def test_unregistered_clustering_route_returns_stable_error_without_fallback(self, mock_search):
        mock_search.side_effect = RuntimeError("data label route not found")

        with self.assertRaises(ValidationError) as error:
            search_logs(
                {
                    "source": {"type": "clustering", "index_set_id": self.original.index_set_id},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "keyword": "*",
                    "addition": [],
                    "begin": 0,
                    "size": 10,
                    "is_desensitize": True,
                }
            )

        self.assertEqual(str(error.exception.code), "3624115")

    def test_legacy_es_route_is_also_pinned_for_group_entry(self):
        handler = ResourceClusteringSearchHandler.__new__(ResourceClusteringSearchHandler)
        handler.index_set_id = self.group.index_set_id
        handler.search_dict = {
            "keyword": "ordinary text without clustering markers",
            "addition": [],
        }
        handler._index_set = self.group
        handler.resource_clustering_config = self.config

        self.assertEqual(handler._init_indices_str(), self.config.clustered_rt)
        self.assertEqual(handler.scenario_id, Scenario.BKDATA)
        self.assertTrue(handler.using_clustering_proxy)


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
class LogQueryHandlerTest(TestCase):
    def setUp(self):
        self.index_set = create_index_set(
            300,
            fields_snapshot={
                "fields": [
                    {"field_name": "dtEventTimeStamp", "field_type": "long"},
                    {"field_name": "gseIndex", "field_type": "long"},
                    {"field_name": "iterationIndex", "field_type": "long"},
                    {"field_name": "serverIp", "field_type": "keyword"},
                    {"field_name": "path", "field_type": "keyword"},
                    {"field_name": "log", "field_type": "text"},
                    {"field_name": "level", "field_type": "keyword"},
                ]
            },
        )
        create_result_table(300, "2_bklog_app", index_id=1300)
        self.record = {
            "dtEventTimeStamp": 1767227400000,
            "gseIndex": 100,
            "iterationIndex": 1,
            "serverIp": "127.0.0.1",
            "path": "/var/log/app.log",
            "log": "request failed",
            "level": "ERROR",
        }

    def test_resource_query_uses_dedicated_mapping_extension_points(self):
        self.assertIs(ResourceSearchHandler.mapping_handler_class, ResourceMappingHandlers)
        self.assertIs(SearchHandlerEsquery.mapping_handler_class, MappingHandlers)
        self.assertIs(ResourceAggsHandlers.search_handler_class, ResourceSearchHandler)
        self.assertIs(AggsHandlers.search_handler_class, SearchHandlerEsquery)
        self.assertIs(ResourceAggsViewAdapter()._aggs_handlers, ResourceAggsHandlers)
        self.assertIs(AggsViewAdapter()._aggs_handlers, AggsHandlers)

    @patch("apps.log_search.handlers.search.mapping_handlers.BkLogApi.mapping")
    @patch("apps.log_admin_resource.handlers.log_query.EsQuery")
    def test_resource_mapping_uses_local_read_only_client(self, mock_esquery, mock_api_mapping):
        mock_esquery.return_value.mapping.return_value = [{"properties": {"log": {"type": "text"}}}]
        handler = ResourceMappingHandlers.__new__(ResourceMappingHandlers)

        result = handler._direct_latest_mapping(
            {
                "indices": "2_bklog_app",
                "scenario_id": Scenario.LOG,
                "storage_cluster_id": -1,
                "start_time": "2026-01-01 00:00:00",
                "end_time": "2026-01-01 01:00:00",
            }
        )

        self.assertEqual(result, [{"properties": {"log": {"type": "text"}}}])
        mock_esquery.return_value.mapping.assert_called_once_with()
        mock_api_mapping.assert_not_called()

    @patch("apps.log_admin_resource.handlers.log_query.ResourceSearchHandler")
    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    def test_fields_legacy_route_uses_resource_search_handler(self, _mock_switch, mock_handler):
        mock_handler.return_value.fields.return_value = {"fields": []}

        result = _index_set_fields(
            {
                "type": "index_set",
                "bk_biz_id": 2,
                "index_set_id": self.index_set.index_set_id,
                "index_set": self.index_set,
            },
            {
                "start_time": 1767225600000,
                "end_time": 1767229200000,
                "time_zone": "UTC",
            },
            "default",
        )

        self.assertEqual(result, {"fields": []})
        mock_handler.assert_called_once()

    def test_context_anchor_accepts_unifyquery_route_label_and_container_path(self):
        anchor = {
            "result_table_id": "bklog_index_set_300_2_bklog_app.__default__",
            "gseIndex": 100,
            "iterationIndex": 1,
            "path": "/var/log/containers/app.log",
        }

        _validate_context_anchor(self.index_set, anchor)

        anchor["result_table_id"] = "bklog_index_set_301_3_bklog_other.__default__"
        with self.assertRaises(ValidationError) as error:
            _validate_context_anchor(self.index_set, anchor)
        self.assertEqual(str(error.exception.code), "3624107")

    def test_log_context_builder_omits_missing_server_ip_condition(self):
        body = CreateSearchContextBodyScenarioLog(
            body_data={"query_list": [{}]},
            sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
            size=10,
            start=0,
            order="+",
            gse_index=100,
            iteration_index=1,
            dt_event_time_stamp=1767227400000,
            path="/var/log/containers/app.log",
            server_ip=None,
            bk_host_id=None,
            container_id=None,
        ).body
        conditions = json.dumps(body["query_list"][0]["conditions"], ensure_ascii=False)

        self.assertNotIn("serverIp", conditions)
        self.assertIn("path", conditions)

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch("apps.log_admin_resource.handlers.log_query._index_set_search")
    def test_search_generates_replayable_context_anchor_and_pagination(self, mock_search, _mock_switch):
        mock_search.return_value = {
            "list": [copy.deepcopy(self.record)],
            "total": 2,
            "took": 0.25,
            "fields": {"log": 20},
            "result_table_id": ["2_bklog_app"],
        }

        result = search_logs(
            {
                "source": {"type": "index_set", "index_set_id": 300},
                "start_time": 1767225600000,
                "end_time": 1767229200000,
                "keyword": "error",
                "addition": [{"field": "level", "operator": "is", "value": "ERROR"}],
                "sort_list": [["dtEventTimeStamp", "desc"]],
                "begin": 0,
                "size": 1,
                "fields": ["log"],
                "track_total_hits": True,
                "is_desensitize": True,
            }
        )

        self.assertNotIn("data", result)
        self.assertEqual(result["items"][0]["record"], {"log": "request failed"})
        anchor = result["items"][0]["context_anchor"]
        self.assertEqual(anchor["index_set_id"], 300)
        self.assertEqual(anchor["result_table_id"], "2_bklog_app")
        self.assertEqual(anchor["sort_values"]["gseIndex"], 100)
        self.assertEqual(anchor["identity"]["serverIp"], "127.0.0.1")
        self.assertEqual(result["pagination"], {"begin": 0, "size": 1, "returned": 1, "has_more": True})
        validate_params(result, FUNCTIONS["bklog.log.search"]["response_schema"], "response")
        called_query = mock_search.call_args.args[1]
        self.assertEqual(called_query["keyword"], "error")
        self.assertEqual(called_query["addition"][0]["condition"], "and")
        self.assertTrue(called_query["is_desensitize"])

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=True)
    @patch("apps.log_admin_resource.handlers.log_query.ResourceUnifyQueryContextHandler")
    def test_context_replays_service_generated_anchor_with_zero_mode(self, mock_handler, _mock_switch):
        mock_handler.return_value.search.return_value = {
            "list": [copy.deepcopy(self.record)],
            "total": 1,
            "took": 0.1,
            "zero_index": 0,
        }
        anchor = {
            "index_set_id": 300,
            "result_table_id": "2_bklog_app",
            "scenario_id": "log",
            "sort_values": {
                "dtEventTimeStamp": 1767227400000,
                "gseIndex": 100,
                "iterationIndex": 1,
            },
            "identity": {"serverIp": "127.0.0.1", "path": "/var/log/app.log"},
        }

        result = get_log_context(
            {
                "source": {"type": "index_set", "index_set_id": 300},
                "context_anchor": anchor,
                "size": 20,
                "is_desensitize": True,
            }
        )

        query = mock_handler.call_args.args[0]
        self.assertTrue(query["zero"])
        self.assertEqual(query["size"], 20)
        self.assertEqual(query["gseIndex"], 100)
        self.assertEqual(result["anchor_index"], 0)
        self.assertFalse(result["pagination"]["has_before"])
        validate_params(result, FUNCTIONS["bklog.log.context"]["response_schema"], "response")

    def test_context_rejects_result_table_outside_the_index_set(self):
        anchor = {
            "index_set_id": 300,
            "result_table_id": "3_bklog_other_business",
            "scenario_id": "log",
            "sort_values": {
                "dtEventTimeStamp": 1767227400000,
                "gseIndex": 100,
                "iterationIndex": 1,
            },
            "identity": {"serverIp": "127.0.0.1", "path": "/var/log/app.log"},
        }

        with self.assertRaises(ValidationError) as error:
            get_log_context(
                {
                    "source": {"type": "index_set", "index_set_id": 300},
                    "context_anchor": anchor,
                    "size": 20,
                    "is_desensitize": True,
                }
            )

        self.assertEqual(str(error.exception.code), "3624107")

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch("apps.log_admin_resource.handlers.log_query._index_set_terms")
    def test_terms_aggregation_uses_single_controlled_field(self, mock_terms, _mock_switch):
        mock_terms.return_value = {
            "aggs": {"level": {"buckets": [{"key": "ERROR", "doc_count": 3}]}},
            "aggs_items": {"level": ["ERROR"]},
        }

        result = aggregate_logs(
            {
                "source": {"type": "index_set", "index_set_id": 300},
                "start_time": 1767225600000,
                "end_time": 1767229200000,
                "keyword": "*",
                "addition": [],
                "aggregation": {"type": "terms", "field": "level", "size": 20},
            }
        )

        self.assertEqual(result["buckets"], [{"key": "ERROR", "doc_count": 3}])
        self.assertIsNone(result["stats"])
        self.assertEqual(mock_terms.call_args.args[1]["fields"], ["level"])
        validate_params(result, FUNCTIONS["bklog.log.aggregate"]["response_schema"], "response")

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch("apps.log_admin_resource.handlers.log_query._index_set_fields", return_value={"fields": []})
    def test_aggregation_rejects_unknown_field_before_query(self, _mock_fields, _mock_switch):
        with self.assertRaises(ValidationError) as error:
            aggregate_logs(
                {
                    "source": {"type": "index_set", "index_set_id": 300},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "keyword": "*",
                    "addition": [],
                    "aggregation": {"type": "terms", "field": "missing_field", "size": 20},
                }
            )

        self.assertEqual(str(error.exception.code), "3624101")

    def test_explicit_time_zone_is_scoped_to_the_downstream_call(self):
        set_local_param("time_zone", "Asia/Shanghai")
        try:
            observed = _run_query(lambda: get_local_param("time_zone"), time_zone="UTC")

            self.assertEqual(observed, "UTC")
            self.assertEqual(get_local_param("time_zone"), "Asia/Shanghai")
        finally:
            del_local_param("time_zone")

    @patch.object(
        SceneUnifyQueryHandler,
        "_init_scene_base_dict",
        return_value={"timezone": "Asia/Shanghai"},
    )
    def test_scene_unify_query_base_dict_honors_explicit_time_zone(self, _mock_scene_base):
        handler = ResourceSceneUnifyQueryHandler.__new__(ResourceSceneUnifyQueryHandler)
        handler.search_params = {"time_zone": "UTC"}

        self.assertEqual(handler._init_scene_base_dict()["timezone"], "UTC")

    @patch.object(UnifyQueryHandler, "query_ts_reference", return_value={"series": []})
    def test_resource_aggregation_does_not_swallow_downstream_reference_errors(self, mock_query):
        handler = ResourceUnifyQueryTermsAggsHandler.__new__(ResourceUnifyQueryTermsAggsHandler)

        handler.query_ts_reference({"query_list": []})

        mock_query.assert_called_once_with({"query_list": []}, raise_exception=True)

    def test_scene_target_only_exposes_active_physical_result_tables(self):
        LogIndexSetData.objects.create(
            index_id=1301,
            index_set_id=self.index_set.index_set_id,
            bk_biz_id=2,
            result_table_id="another-index-set-id",
            scenario_id=Scenario.LOG,
            apply_status=LogIndexSetData.Status.NORMAL,
            type=IndexSetDataType.INDEX_SET.value,
        )
        failed_result_table = create_result_table(300, "2_bklog_failed", index_id=1302)
        failed_result_table.apply_status = LogIndexSetData.Status.ABNORMAL
        failed_result_table.save(update_fields=["apply_status"])

        target = _scene_target(self.index_set)

        self.assertEqual(target["result_table_ids"], ["2_bklog_app"])

    def test_millisecond_context_timestamp_does_not_overflow(self):
        start_time, end_time = _context_time_bounds(1767227400000)

        self.assertLess(start_time, end_time)
        self.assertEqual(end_time - start_time, 24 * 60 * 60)

    def test_bounded_items_reports_full_original_size_after_response_cutoff(self):
        first = {"log": "x" * (2 * 1024 * 1024)}
        second = {"log": "tail"}

        _items, truncation = _bounded_items([first, second])

        expected = len(str(first).replace("'", '"').encode("utf-8"))
        self.assertGreater(truncation["original_size_bytes"], expected)


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
class PatternResourceHandlerTest(TestCase):
    def setUp(self):
        create_index_set(400, scenario_id=Scenario.BKDATA)
        create_result_table(400, "2_bklog_source_400", scenario_id=Scenario.BKDATA, index_id=1400)
        self.config = create_clustering_config(400)

    @patch("apps.log_admin_resource.handlers.log_query.FeatureToggleObject.switch", return_value=False)
    @patch("apps.log_admin_resource.handlers.log_query.ResourcePatternHandler")
    def test_pattern_reuses_pattern_handler_without_public_level_or_origin_log(self, mock_handler, _mock_switch):
        items = [
            {
                "pattern": "request failed for <*>",
                "signature": "signature-1",
                "count": 3,
                "percentage": 100,
                "is_new_class": False,
                "year_on_year_count": 0,
                "year_on_year_percentage": 0,
                "group": [],
                "remark": [],
                "owners": [],
                "strategy_id": None,
                "strategy_enabled": False,
            }
        ]
        observed_time_zones = []

        def pattern_search():
            observed_time_zones.append(get_local_param("time_zone"))
            return items

        mock_handler.return_value.pattern_search.side_effect = pattern_search

        result = search_clustering_patterns(
            {
                "source": {"type": "clustering", "index_set_id": 400},
                "start_time": 1767225600000,
                "end_time": 1767229200000,
                "keyword": "*",
                "addition": [],
                "time_zone": "UTC",
                "filter_not_clustering": False,
                "show_new_pattern": False,
                "size": 100,
            }
        )

        query = mock_handler.call_args.args[1]
        self.assertEqual(query["pattern_level"], PatternEnum.LEVEL_05.value)
        self.assertFalse(query["include_origin_log"])
        self.assertEqual(query["addition"], [])
        self.assertEqual(observed_time_zones, ["UTC"])
        self.assertNotIn("pattern_level", result["source"])
        self.assertEqual(result["route"]["data_labels"], ["bklog_index_set_400_clustered"])
        self.assertEqual(result["items"][0]["signature"], "signature-1")
        validate_params(result, FUNCTIONS["bklog.clustering.pattern.search"]["response_schema"], "response")


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class LogQueryTenantScopeTest(TestCase):
    def setUp(self):
        for bk_biz_id, tenant_id in ((2, "tenant-a"), (3, "tenant-b")):
            Space.objects.create(
                space_uid=f"bkcc__{bk_biz_id}",
                bk_biz_id=bk_biz_id,
                space_type_id="bkcc",
                space_type_name="business",
                space_id=str(bk_biz_id),
                space_name=f"biz-{bk_biz_id}",
                bk_tenant_id=tenant_id,
            )
            LogIndexSet.objects.create(
                index_set_id=500 + bk_biz_id,
                index_set_name=f"index-{bk_biz_id}",
                space_uid=f"bkcc__{bk_biz_id}",
                category_id="application",
                scenario_id=Scenario.LOG,
            )
        create_result_table(502, "2_bklog_tenant_a", index_id=1502)
        create_result_table(503, "3_bklog_tenant_b", index_id=1503)

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    def test_index_set_source_cannot_cross_request_tenant(self, _mock_tenant):
        self.assertEqual(_resolve_source({"type": "index_set", "index_set_id": 502})["space_uid"], "bkcc__2")

        with self.assertRaises(ValidationError) as error:
            _resolve_source({"type": "index_set", "index_set_id": 503})

        self.assertEqual(str(error.exception.code), "3624102")

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    def test_scene_source_cannot_cross_request_tenant(self, _mock_tenant):
        with self.assertRaises(BklogPermissionError):
            _resolve_source(
                {
                    "type": "scene",
                    "space_uid": "bkcc__3",
                    "table_id_conditions": [[{"field_name": "scene", "value": ["log"], "op": "eq"}]],
                }
            )

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    @patch.object(SceneUnifyQueryHandler, "_resolve_table_id_from_conditions")
    def test_scene_field_fallback_rejects_cross_tenant_index_set(self, mock_parent_resolve, _mock_tenant):
        handler = ResourceSceneUnifyQueryHandler.__new__(ResourceSceneUnifyQueryHandler)
        handler.space_uid = "bkcc__2"

        mock_parent_resolve.return_value = "bklog_index_set_503"
        self.assertEqual(handler._resolve_table_id_from_conditions(), "")

        mock_parent_resolve.return_value = "bklog_index_set_502"
        self.assertEqual(handler._resolve_table_id_from_conditions(), "bklog_index_set_502")

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-a")
    def test_scene_result_table_mapping_is_tenant_scoped(self, _mock_tenant):
        handler = ResourceSceneUnifyQueryHandler.__new__(ResourceSceneUnifyQueryHandler)
        handler.space_uid = "bkcc__2"

        self.assertEqual(handler._map_result_tables_to_index_sets(["2_bklog_tenant_a"]), [502])
        self.assertEqual(handler._map_result_tables_to_index_sets(["3_bklog_tenant_b"]), [])
