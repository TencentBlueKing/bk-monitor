from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import arrow
from django.test import SimpleTestCase

from apps.log_clustering.constants import NEW_CLASS_ALERT_SEARCH_PAGE_SIZE, SIGNATURE_FIELD, StrategiesType
from apps.log_clustering.handlers.pattern import PatternHandler


class TestPatternHandlerGetNewClass(SimpleTestCase):
    def setUp(self):
        self.handler = PatternHandler.__new__(PatternHandler)
        self.handler._index_set_id = 123
        self.handler._pattern_level = "05"
        self.handler._query = {
            "start_time": "2026-07-01 00:00:00",
            "end_time": "2026-07-02 00:00:00",
        }
        self.handler._clustering_config = SimpleNamespace(
            use_mini_link=False,
            new_cls_strategy_output="",
            new_cls_pattern_rt="",
            new_cls_strategy_enable=False,
            group_fields=["service_name"],
            bk_biz_id=2,
            related_space_pre_bk_biz_id=None,
            index_set_id=123,
            save=Mock(),
        )

    @patch("apps.log_clustering.handlers.pattern.generate_time_range")
    def test_get_new_class_routes_to_alerts_for_new_series_config(self, mock_generate_time_range):
        mock_generate_time_range.return_value = (
            arrow.get("2026-07-01 00:00:00"),
            arrow.get("2026-07-02 00:00:00"),
        )
        self.handler._get_new_class_from_alerts = Mock(return_value={("sig-a", "svc-a")})

        result = self.handler._get_new_class()

        self.assertEqual(result, {("sig-a", "svc-a")})
        self.handler._get_new_class_from_alerts.assert_called_once()

    @patch("apps.log_clustering.handlers.pattern.generate_time_range")
    @patch("apps.log_clustering.handlers.pattern.BkData")
    def test_get_new_class_keeps_legacy_pattern_rt_path(self, mock_bkdata_cls, mock_generate_time_range):
        self.handler._clustering_config.new_cls_pattern_rt = "2_bklog_123_agg"
        mock_generate_time_range.return_value = (
            arrow.get("2026-07-01 00:00:00"),
            arrow.get("2026-07-02 00:00:00"),
        )
        mock_bkdata_cls.return_value.select.return_value.where.return_value.time_range.return_value.query.return_value = [
            {SIGNATURE_FIELD: "legacy-sig"}
        ]

        result = self.handler._get_new_class()

        self.assertEqual(result, {("legacy-sig",)})
        mock_bkdata_cls.assert_called_once_with("2_bklog_123_agg")

    def test_extract_new_class_tuple_from_alert_with_group_fields(self):
        alert = {
            "dimensions": [
                {"key": SIGNATURE_FIELD, "value": "sig-1"},
                {"key": "service_name", "value": "order"},
            ]
        }
        select_fields = [SIGNATURE_FIELD, "service_name"]

        result = self.handler._extract_new_class_tuple_from_alert(alert, select_fields)

        self.assertEqual(result, ("sig-1", "order"))

    def test_extract_new_class_tuple_from_alert_normalizes_tag_dimensions(self):
        alert = {
            "dimensions": [
                {"key": "tags.path", "value": "/tmp/svm.log"},
                {"key": "tags.signature", "value": "sig-1"},
            ]
        }

        result_with_group = self.handler._extract_new_class_tuple_from_alert(alert, [SIGNATURE_FIELD, "path"])
        result_without_group = self.handler._extract_new_class_tuple_from_alert(alert, [SIGNATURE_FIELD])

        self.assertEqual(result_with_group, ("sig-1", "/tmp/svm.log"))
        self.assertEqual(result_without_group, ("sig-1",))

    @patch("apps.log_clustering.handlers.pattern.model_to_dict", return_value={})
    @patch("apps.log_clustering.handlers.clustering_monitor.ClusteringMonitorHandler")
    def test_update_group_fields_does_not_update_legacy_strategy(self, mock_monitor_handler_cls, _mock_model_to_dict):
        self.handler._clustering_config.new_cls_strategy_enable = True
        monitor_handler = mock_monitor_handler_cls.return_value
        monitor_handler.is_legacy_new_class_strategy.return_value = True

        self.handler.update_group_fields(["service_name", "pod_name"])

        self.assertEqual(self.handler._clustering_config.group_fields, ["service_name", "pod_name"])
        self.handler._clustering_config.save.assert_called_once()
        monitor_handler.resave_new_cls_clustering_strategy.assert_not_called()

    @patch("apps.log_clustering.handlers.pattern.model_to_dict", return_value={})
    @patch("apps.log_clustering.handlers.clustering_monitor.ClusteringMonitorHandler")
    def test_update_group_fields_resaves_enabled_new_series_strategy(
        self, mock_monitor_handler_cls, _mock_model_to_dict
    ):
        self.handler._clustering_config.new_cls_strategy_enable = True
        monitor_handler = mock_monitor_handler_cls.return_value
        monitor_handler.is_legacy_new_class_strategy.return_value = False

        self.handler.update_group_fields(["service_name", "pod_name"])

        monitor_handler.resave_new_cls_clustering_strategy.assert_called_once_with()

    def test_extract_new_class_tuple_from_alert_falls_back_to_dist_field(self):
        self.handler._pattern_level = "05"
        alert = {
            "dimensions": [
                {"key": "__dist_05", "value": "sig-dist"},
            ]
        }

        result = self.handler._extract_new_class_tuple_from_alert(alert, [SIGNATURE_FIELD])

        self.assertEqual(result, ("sig-dist",))

    @patch("apps.log_clustering.handlers.pattern.MonitorApi.search_alert")
    @patch("apps.log_clustering.handlers.pattern.SignatureStrategySettings.objects.filter")
    def test_get_new_class_from_alerts_paginates_and_builds_set(self, mock_filter, mock_search_alert):
        strategy_settings = SimpleNamespace(strategy_id=9527)
        mock_filter.return_value.first.return_value = strategy_settings
        mock_search_alert.side_effect = [
            {
                "total": NEW_CLASS_ALERT_SEARCH_PAGE_SIZE + 1,
                "alerts": [
                    {
                        "dimensions": [
                            {"key": SIGNATURE_FIELD, "value": "sig-1"},
                            {"key": "service_name", "value": "order"},
                        ]
                    }
                ],
            },
            {
                "total": NEW_CLASS_ALERT_SEARCH_PAGE_SIZE + 1,
                "alerts": [
                    {
                        "dimensions": [
                            {"key": SIGNATURE_FIELD, "value": "sig-2"},
                            {"key": "service_name", "value": "pay"},
                        ]
                    }
                ],
            },
        ]
        start_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end_time = datetime(2026, 7, 2, tzinfo=timezone.utc)

        result = self.handler._get_new_class_from_alerts(start_time, end_time)

        self.assertEqual(result, {("sig-1", "order"), ("sig-2", "pay")})
        self.assertEqual(mock_search_alert.call_count, 2)
        mock_filter.assert_called_once_with(
            index_set_id=123,
            strategy_type=StrategiesType.NEW_CLS_strategy,
            signature="",
            is_deleted=False,
        )
        first_call_params = mock_search_alert.call_args_list[0].args[0]
        self.assertEqual(first_call_params["page_size"], NEW_CLASS_ALERT_SEARCH_PAGE_SIZE)
        self.assertEqual(first_call_params["conditions"], [{"key": "strategy_id", "value": [9527]}])
        self.assertEqual(first_call_params["bk_biz_ids"], [2])

    @patch("apps.log_clustering.handlers.pattern.MonitorApi.search_alert")
    @patch("apps.log_clustering.handlers.pattern.SignatureStrategySettings.objects.filter")
    def test_get_new_class_from_alerts_skips_no_data_alerts(self, mock_filter, mock_search_alert):
        strategy_settings = SimpleNamespace(strategy_id=9527)
        mock_filter.return_value.first.return_value = strategy_settings
        mock_search_alert.return_value = {
            "total": 2,
            "alerts": [
                {
                    "dedupe_keys": ["strategy_id", "tags.__NO_DATA_DIMENSION__", "tags.signature"],
                    "dimensions": [
                        {"key": SIGNATURE_FIELD, "value": "no-data-sig"},
                    ],
                },
                {
                    "dedupe_keys": ["strategy_id", "tags.signature"],
                    "dimensions": [
                        {"key": SIGNATURE_FIELD, "value": "sig-1"},
                    ],
                },
            ],
        }

        result = self.handler._get_new_class_from_alerts(
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 2, tzinfo=timezone.utc),
        )

        self.assertEqual(result, {("sig-1", "")})

    @patch("apps.log_clustering.handlers.pattern.SignatureStrategySettings.objects.filter")
    def test_get_new_class_from_alerts_returns_empty_without_strategy(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        result = self.handler._get_new_class_from_alerts(
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 2, tzinfo=timezone.utc),
        )

        self.assertEqual(result, set())

    def test_monitor_bk_biz_id_uses_related_space_pre_biz_id(self):
        self.handler._clustering_config.related_space_pre_bk_biz_id = 99

        self.assertEqual(self.handler._monitor_bk_biz_id, 99)
