from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.exceptions import ApiResultError, PermissionError as BklogPermissionError, ValidationError
from apps.log_admin_resource.handlers.monitor_strategy import (
    FUNC_NAME,
    FUNCTIONS,
    get_monitor_strategy_snapshot,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_clustering.constants import StrategiesType
from apps.log_clustering.models import SignatureStrategySettings
from apps.tests.log_admin_resource.test_clustering_inspection import create_clustering_config
from django.test import TestCase


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
class MonitorStrategySnapshotTest(SimpleTestCase):
    def test_registry_exposes_monitor_strategy_snapshot(self):
        metadata = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="reader-a")
        self.assertIn(FUNC_NAME, metadata["functions"])
        self.assertEqual(FUNCTIONS[FUNC_NAME]["safety_level"], "inspect")
        self.assertTrue(FUNCTIONS[FUNC_NAME]["validate_params"])

    def test_schema_requires_biz_and_strategy_and_rejects_tenant_override(self):
        schema = FUNCTIONS[FUNC_NAME]["params_schema"]
        validate_params({"bk_biz_id": 2, "strategy_id": 1001}, schema)
        validate_params({"bk_biz_id": -4298, "strategy_id": 1001}, schema)
        with self.assertRaises(ValidationError):
            validate_params({"bk_biz_id": 2, "strategy_id": 1001, "bk_tenant_id": "other"}, schema)
        with self.assertRaises(ValidationError):
            validate_params({"strategy_id": 1001}, schema)

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_keyword_strategy_marks_serving_flow_not_applicable(self, mock_search):
        mock_search.return_value = {
            "strategy_config_list": [
                {
                    "id": 1001,
                    "name": "keyword-alert",
                    "is_enabled": True,
                    "scenario": "log",
                    "labels": ["LogClustering/Count/755"],
                    "items": [
                        {
                            "name": "item-1",
                            "algorithms": [
                                {"type": "Threshold", "level": 2, "config": {"method": "gte", "threshold": 1}}
                            ],
                            "query_configs": [
                                {
                                    "data_source_label": "bk_log_search",
                                    "data_type_label": "log",
                                    "metric_id": "bk_log_search.index_set.755",
                                    "index_set_id": 755,
                                    "query_string": "ERROR",
                                    "agg_dimension": ["serverIp"],
                                    "agg_condition": [],
                                }
                            ],
                        }
                    ],
                    "notice": {"user_groups": [11], "signal": ["abnormal"]},
                }
            ]
        }

        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 1001})

        request_params = mock_search.call_args[0][0]
        self.assertTrue(request_params["no_request"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["name"], "keyword-alert")
        self.assertEqual(result["items"][0]["algorithms"][0]["type"], "Threshold")
        self.assertEqual(result["serving_flow"]["applicability"], "not_applicable")
        self.assertIsNone(result["next_call"])
        validate_params(result, FUNCTIONS[FUNC_NAME]["response_schema"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_intelligent_detect_returns_next_call_to_flow_snapshot(self, mock_search):
        mock_search.return_value = {
            "strategy_config_list": [
                {
                    "id": 2002,
                    "name": "new-class-legacy",
                    "is_enabled": True,
                    "items": [
                        {
                            "name": "new-class",
                            "algorithms": [{"type": "IntelligentDetect", "level": 2, "config": {"args": {"$x": 1}}}],
                            "query_configs": [
                                {
                                    "data_source_label": "bkdata",
                                    "data_type_label": "time_series",
                                    "result_table_id": "2_bklog_755_agg",
                                    "intelligent_detect": {
                                        "status": "running",
                                        "data_flow_id": 66399,
                                        "result_table_id": "2_bklog_755_agg_plan",
                                        "message": "",
                                        "use_sdk": False,
                                    },
                                }
                            ],
                        }
                    ],
                    "notice": {"user_groups": []},
                }
            ]
        }

        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 2002})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["serving_flow"]["applicability"], "applicable")
        self.assertEqual(result["serving_flow"]["data_flow_id"], 66399)
        self.assertEqual(
            result["next_call"],
            {"func_name": "bklog.bkdata.flow.snapshot", "params": {"bk_biz_id": 2, "flow_id": 66399}},
        )
        validate_params(result, FUNCTIONS[FUNC_NAME]["response_schema"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_new_series_is_not_applicable_even_with_algorithm(self, mock_search):
        mock_search.return_value = {
            "strategy_config_list": [
                {
                    "id": 3003,
                    "name": "new-class-newseries",
                    "is_enabled": True,
                    "items": [
                        {
                            "algorithms": [
                                {"type": "NewSeries", "level": 2, "config": {"detect_range": 86400, "threshold": 0}}
                            ],
                            "query_configs": [
                                {
                                    "data_source_label": "bk_log_search",
                                    "data_type_label": "log",
                                    "index_set_id": 755,
                                    "query_string": "*",
                                }
                            ],
                        }
                    ],
                    "notice": {},
                }
            ]
        }

        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 3003})

        self.assertEqual(result["items"][0]["algorithms"][0]["type"], "NewSeries")
        self.assertEqual(result["serving_flow"]["applicability"], "not_applicable")
        self.assertIsNone(result["next_call"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_new_series_sdk_intelligent_detect_is_not_applicable(self, mock_search):
        mock_search.return_value = {
            "strategy_config_list": [
                {
                    "id": 3004,
                    "name": "new-class-sdk",
                    "is_enabled": True,
                    "items": [
                        {
                            "algorithms": [
                                {"type": "NewSeries", "level": 2, "config": {"detect_range": 86400, "threshold": 0}}
                            ],
                            "query_configs": [
                                {
                                    "data_source_label": "bk_log_search",
                                    "data_type_label": "log",
                                    "index_set_id": 755,
                                    "intelligent_detect": {"use_sdk": True, "status": "ready"},
                                }
                            ],
                        }
                    ],
                    "notice": {},
                }
            ]
        }

        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 3004})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["items"][0]["query_configs"][0]["intelligent_detect"]["use_sdk"], True)
        self.assertEqual(result["serving_flow"]["applicability"], "not_applicable")
        self.assertIsNone(result["next_call"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_empty_strategy_list_is_not_found(self, mock_search):
        mock_search.return_value = {"strategy_config_list": []}
        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 404})
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["summary"])
        self.assertIsNone(result["next_call"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_monitor_api_failure_is_unknown(self, mock_search):
        mock_search.side_effect = ApiResultError("timeout", code=500)
        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 1001})
        self.assertEqual(result["status"], "unknown")
        self.assertIn("monitor strategy lookup failed", result["status_detail"])
        self.assertNotEqual(result["status"], "not_found")

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_mismatched_strategy_id_is_not_found(self, mock_search):
        mock_search.return_value = {"strategy_config_list": [{"id": 9999, "name": "other", "items": [], "notice": {}}]}
        result = get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 1001})
        self.assertEqual(result["status"], "not_found")
        self.assertIsNone(result["summary"])

    @patch("apps.log_admin_resource.handlers.monitor_strategy.MonitorApi.search_alarm_strategy_v3")
    def test_unexpected_monitor_error_is_not_swallowed(self, mock_search):
        mock_search.side_effect = TypeError("broken client")
        with self.assertRaises(TypeError):
            get_monitor_strategy_snapshot({"bk_biz_id": 2, "strategy_id": 1001})

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch("apps.log_admin_resource.handlers.monitor_strategy.require_biz_in_request_tenant")
    def test_rejects_business_outside_request_tenant(self, mock_require_biz):
        mock_require_biz.side_effect = BklogPermissionError(
            "business does not belong to the current Resource Call tenant"
        )
        with self.assertRaises(BklogPermissionError):
            get_monitor_strategy_snapshot({"bk_biz_id": 999, "strategy_id": 1})


class ClusteringStrategyBindingsTest(TestCase):
    def test_clustering_detail_returns_index_level_strategy_bindings(self):
        from apps.log_admin_resource.handlers.clustering_config import get_clustering_config_detail

        config = create_clustering_config(
            index_set_id=18001,
            bk_biz_id=2,
            related_space_pre_bk_biz_id=99,
            new_cls_strategy_enable=True,
        )
        SignatureStrategySettings.objects.create(
            signature="",
            index_set_id=config.index_set_id,
            strategy_id=260806,
            enabled=True,
            bk_biz_id=99,
            strategy_type=StrategiesType.NEW_CLS_strategy,
        )
        SignatureStrategySettings.objects.create(
            signature="pattern-only",
            index_set_id=config.index_set_id,
            strategy_id=111,
            enabled=True,
            bk_biz_id=99,
            strategy_type=StrategiesType.NORMAL_STRATEGY,
        )
        SignatureStrategySettings.objects.create(
            signature="",
            index_set_id=config.index_set_id,
            strategy_id=None,
            enabled=True,
            bk_biz_id=99,
            strategy_type=StrategiesType.NORMAL_STRATEGY,
        )

        result = get_clustering_config_detail({"config_id": config.id})

        self.assertEqual(
            result["strategy_bindings"],
            [
                {
                    "strategy_type": StrategiesType.NEW_CLS_strategy,
                    "strategy_id": 260806,
                    "enabled": True,
                    "bk_biz_id": 99,
                    "signature": "",
                    "pattern_level": None,
                }
            ],
        )
