from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.log_clustering.constants import NEW_SERIES_ALGORITHM_TYPE, StrategiesType
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler


class TestClusteringMonitorHandler(TestCase):
    def setUp(self):
        self.handler = ClusteringMonitorHandler.__new__(ClusteringMonitorHandler)
        self.handler.index_set_id = 123
        self.handler.index_set = SimpleNamespace(index_set_name="test-index-set", time_field="dtEventTimeStamp")
        self.handler.clustering_config = SimpleNamespace(
            new_cls_index_set_id=None,
            new_cls_strategy_output="",
            new_cls_pattern_rt="",
            log_count_aggregation_flow={"agg": {"result_table_id": "2_legacy_new_class"}},
            group_fields=["service_name"],
            clustering_fields="log",
            bk_biz_id=2,
        )
        self.handler.bk_biz_id = 2
        self.handler.conf = {"agg_interval": 60}
        self.handler.get_notice = Mock(return_value={"signal": ["abnormal"]})
        self.handler.save_strategy_infos = Mock(return_value=9527)
        self.handler.is_new_class_new_series_enabled = Mock(return_value=True)

    @patch(
        "apps.log_clustering.handlers.dataflow.dataflow_handler.DataFlowHandler.sync_clustered_route",
        return_value=True,
    )
    def test_save_new_cls_clustering_strategy_builds_new_series_payload(self, mock_sync_clustered_route):
        result = self.handler.save_new_cls_clustering_strategy(
            params={"interval": 30, "threshold": 5, "level": 1, "user_groups": [42]}
        )

        request_params = self.handler.save_strategy_infos.call_args.kwargs["request_params"]
        item = request_params["items"][0]
        query_config = item["query_configs"][0]
        algorithm = item["algorithms"][0]

        self.assertEqual(result["strategy_id"], 9527)
        self.assertEqual(query_config["data_source_label"], "bk_log_search")
        self.assertEqual(query_config["data_type_label"], "log")
        self.assertEqual(query_config["index_set_id"], 123)
        self.assertEqual(query_config["result_table_id"], "")
        self.assertEqual(query_config["agg_dimension"], ["signature", "service_name"])
        self.assertEqual(
            query_config["agg_condition"],
            [
                {
                    "key": "__dist_05",
                    "dimension_name": "__dist_05",
                    "value": [""],
                    "method": "neq",
                    "condition": "and",
                }
            ],
        )
        self.assertEqual(algorithm["type"], NEW_SERIES_ALGORITHM_TYPE)
        self.assertEqual(algorithm["config"], {"detect_range": 30 * 24 * 60 * 60, "threshold": 5})
        self.assertEqual(request_params["detects"][0]["level"], 1)
        self.assertEqual(request_params["detects"][0]["trigger_config"]["count"], 1)
        mock_sync_clustered_route.assert_called_once_with(index_set_id=123, raise_exception=True)

    def test_new_class_and_normal_strategy_share_log_search_source_config(self):
        self.handler.save_new_cls_clustering_strategy(params={"interval": 30, "threshold": 5})
        new_class_query = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0][
            "query_configs"
        ][0]

        self.handler.save_normal_clustering_strategy(params={"sensitivity": 5})
        normal_query = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0]["query_configs"][
            0
        ]

        self.assertEqual(new_class_query["result_table_id"], "")
        self.assertEqual(normal_query["result_table_id"], "")
        different_fields = {"agg_dimension"}
        self.assertEqual(
            {key: value for key, value in new_class_query.items() if key not in different_fields},
            {key: value for key, value in normal_query.items() if key not in different_fields},
        )

    def test_create_or_update_keeps_legacy_new_class_strategy(self):
        self.handler.clustering_config.new_cls_pattern_rt = "2_legacy_new_class"
        self.handler.save_legacy_new_cls_clustering_strategy = Mock(return_value={"strategy_id": 1})
        self.handler.save_new_cls_clustering_strategy = Mock()

        result = self.handler.create_or_update_clustering_strategy(
            StrategiesType.NEW_CLS_strategy, {"interval": 30, "threshold": 5}
        )

        self.assertEqual(result, {"strategy_id": 1})
        self.handler.save_legacy_new_cls_clustering_strategy.assert_called_once_with(
            table_id="2_legacy_new_class",
            metric="log_count",
            params={"interval": 30, "threshold": 5},
        )
        self.handler.save_new_cls_clustering_strategy.assert_not_called()

    def test_create_or_update_uses_new_series_for_new_config(self):
        self.handler.save_legacy_new_cls_clustering_strategy = Mock()
        self.handler.save_new_cls_clustering_strategy = Mock(return_value={"strategy_id": 2})
        params = {"interval": 30, "threshold": 5}

        result = self.handler.create_or_update_clustering_strategy(StrategiesType.NEW_CLS_strategy, params)

        self.assertEqual(result, {"strategy_id": 2})
        self.handler.save_new_cls_clustering_strategy.assert_called_once_with(params=params)
        self.handler.save_legacy_new_cls_clustering_strategy.assert_not_called()

    def test_existing_new_series_config_does_not_fall_back_when_gray_switch_is_off(self):
        self.handler.clustering_config.log_count_aggregation_flow = {"include_agg": False}
        self.handler.is_new_class_new_series_enabled.return_value = False

        self.assertFalse(self.handler.is_legacy_new_class_strategy())

    def test_create_or_update_uses_legacy_strategy_when_gray_switch_is_off(self):
        self.handler.is_new_class_new_series_enabled.return_value = False
        self.handler.save_legacy_new_cls_clustering_strategy = Mock(return_value={"strategy_id": 1})
        self.handler.save_new_cls_clustering_strategy = Mock()
        params = {"interval": 30, "threshold": 5}

        result = self.handler.create_or_update_clustering_strategy(StrategiesType.NEW_CLS_strategy, params)

        self.assertEqual(result, {"strategy_id": 1})
        self.handler.save_legacy_new_cls_clustering_strategy.assert_called_once_with(
            table_id="2_legacy_new_class",
            metric="log_count",
            params=params,
        )
        self.handler.save_new_cls_clustering_strategy.assert_not_called()

    @patch("apps.log_clustering.handlers.clustering_monitor.SignatureStrategySettings.objects.filter")
    def test_resave_new_series_strategy_preserves_existing_params(self, mock_filter):
        mock_filter.return_value.first.return_value = SimpleNamespace(strategy_id=9527)
        params = {"interval": 30, "threshold": 5, "level": 1, "user_groups": [42]}
        self.handler.get_strategy = Mock(return_value=params)
        self.handler.save_new_cls_clustering_strategy = Mock(return_value={"strategy_id": 9527})

        result = self.handler.resave_new_cls_clustering_strategy()

        self.assertEqual(result, {"strategy_id": 9527})
        self.handler.get_strategy.assert_called_once_with(StrategiesType.NEW_CLS_strategy, 9527)
        self.handler.save_new_cls_clustering_strategy.assert_called_once_with(params=params)

    @patch("apps.feature_toggle.handlers.toggle.FeatureToggleObject.toggle", return_value=None)
    def test_new_series_gray_switch_defaults_to_on(self, _mock_toggle):
        enabled = ClusteringMonitorHandler.is_new_class_new_series_enabled(self.handler)

        self.assertTrue(enabled)

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.save_alarm_strategy_v3")
    @patch("apps.log_clustering.handlers.clustering_monitor.SignatureStrategySettings.objects.get_or_create")
    def test_save_strategy_infos_does_not_write_bkdata_output_for_new_series(
        self, mock_get_or_create, mock_save_strategy
    ):
        strategy_settings = Mock(strategy_id=None)
        mock_get_or_create.return_value = (strategy_settings, True)
        mock_save_strategy.return_value = {"id": 9527}
        self.handler.clustering_config = Mock()
        request_params = {
            "items": [{"algorithms": [{"type": NEW_SERIES_ALGORITHM_TYPE}]}],
        }

        result = ClusteringMonitorHandler.save_strategy_infos(
            self.handler,
            strategy_type=StrategiesType.NEW_CLS_strategy,
            pattern_level="05",
            request_params=request_params,
        )

        self.assertEqual(result, 9527)
        self.assertEqual(self.handler.clustering_config.new_cls_strategy_output, "")
        self.assertTrue(self.handler.clustering_config.new_cls_strategy_enable)

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.save_alarm_strategy_v3")
    @patch("apps.log_clustering.handlers.clustering_monitor.SignatureStrategySettings.objects.get_or_create")
    def test_save_strategy_infos_clears_normal_strategy_output(self, mock_get_or_create, mock_save_strategy):
        strategy_settings = Mock(strategy_id=None)
        mock_get_or_create.return_value = (strategy_settings, True)
        mock_save_strategy.return_value = {"id": 9527}
        self.handler.clustering_config = Mock()
        request_params = {
            "items": [{"algorithms": [{"type": "IntelligentDetect"}]}],
        }

        result = ClusteringMonitorHandler.save_strategy_infos(
            self.handler,
            strategy_type=StrategiesType.NORMAL_STRATEGY,
            pattern_level="05",
            request_params=request_params,
        )

        self.assertEqual(result, 9527)
        self.assertEqual(self.handler.clustering_config.normal_strategy_output, "")
        self.assertTrue(self.handler.clustering_config.normal_strategy_enable)

    def test_create_or_update_normal_strategy_does_not_resolve_table_id(self):
        self.handler.save_normal_clustering_strategy = Mock(return_value={"strategy_id": 3})
        params = {"sensitivity": 5}

        result = self.handler.create_or_update_clustering_strategy(StrategiesType.NORMAL_STRATEGY, params)

        self.assertEqual(result, {"strategy_id": 3})
        self.handler.save_normal_clustering_strategy.assert_called_once_with(params=params)

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.search_alarm_strategy_v3")
    def test_get_new_series_strategy_maps_detect_range_and_threshold(self, mock_search_strategy):
        mock_search_strategy.return_value = {
            "strategy_config_list": [
                {
                    "items": [
                        {
                            "algorithms": [
                                {
                                    "type": NEW_SERIES_ALGORITHM_TYPE,
                                    "level": 2,
                                    "config": {"detect_range": 30 * 24 * 60 * 60, "threshold": 5},
                                }
                            ]
                        }
                    ],
                    "notice": {"user_groups": [42]},
                }
            ]
        }

        result = self.handler.get_strategy(StrategiesType.NEW_CLS_strategy, 9527)

        self.assertEqual(result["interval"], 30)
        self.assertEqual(result["threshold"], 5)
