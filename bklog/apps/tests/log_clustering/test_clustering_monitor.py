from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from jinja2 import Environment

from apps.log_clustering.constants import NEW_SERIES_ALGORITHM_TYPE, StrategiesType
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler
from apps.log_clustering.serializers import NewClsStrategySerializer


class TestClusteringMonitorHandler(TestCase):
    def setUp(self):
        self.handler = ClusteringMonitorHandler.__new__(ClusteringMonitorHandler)
        self.handler.index_set_id = 123
        self.handler.index_set = SimpleNamespace(index_set_name="test-index-set", time_field="dtEventTimeStamp")
        self.handler.log_index_set_data = {"result_table_id": "2_bklog.rt_create"}
        self.handler.clustering_config = SimpleNamespace(
            new_cls_index_set_id=None,
            new_cls_strategy_output="",
            new_cls_pattern_rt="",
            model_output_rt="2_bklog_model_output",
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
        self.handler.is_quix = False

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
        self.assertEqual(query_config["result_table_id"], "2_bklog.rt_create")
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
        self.assertEqual(algorithm["config"], {"detect_range": 30 * 24 * 60 * 60, "threshold": 4})
        self.assertEqual(request_params["detects"][0]["level"], 1)
        self.assertEqual(request_params["detects"][0]["trigger_config"]["count"], 1)
        mock_sync_clustered_route.assert_called_once_with(index_set_id=123, raise_exception=True)

    def test_new_series_notice_preserves_related_fields_after_long_log(self):
        self.handler.is_quix = True
        del self.handler.get_notice
        self.handler.save_new_cls_clustering_strategy(params={"user_groups": [42]})
        notice = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["notice"]
        template = Environment().from_string(notice["config"]["template"][0]["message_tmpl"])
        link = "/#/retrieve/123?addition=signature&start_time=1&end_time=2"
        for size in (1024, 1025):
            with self.subTest(size=size):
                related = {
                    "log": "测" * size,
                    "owners": "owner",
                    "remark_text": "保留备注",
                    "remark_time": "10:00",
                    "remark_user": "tester",
                    "bklog_link": link,
                }
                body = template.render(
                    content={},
                    alarm={"log_related_fields": related, "current_value": 8},
                    strategy=SimpleNamespace(items=[SimpleNamespace(query_configs=[{"agg_interval": 60}])]),
                )
                sample = body.split("**日志示例:** ")[1].splitlines()[0]
                self.assertEqual(sample, "测" * 1024 if size == 1024 else "测" * 1021 + "...")
                self.assertIn("**内容:** 日志聚类检测到新类，近 1 分钟出现次数 (8)", body.splitlines())
                self.assertIn("**负责人:** owner", body)
                self.assertIn("保留备注【10:00】(tester", body)
                self.assertIn(f"[更多日志]({link})", body)

    @patch(
        "apps.log_clustering.handlers.dataflow.dataflow_handler.DataFlowHandler.sync_clustered_route",
        return_value=True,
    )
    def test_save_new_series_minimum_log_count_as_strict_threshold(self, _mock_sync_clustered_route):
        self.handler.save_new_cls_clustering_strategy(params={"interval": 30, "threshold": 1})

        request_params = self.handler.save_strategy_infos.call_args.kwargs["request_params"]
        algorithm_config = request_params["items"][0]["algorithms"][0]["config"]

        self.assertEqual(algorithm_config["threshold"], 0)

    def test_save_legacy_new_class_strategy_keeps_threshold(self):
        self.handler.save_legacy_new_cls_clustering_strategy(
            table_id="2_legacy_new_class",
            metric="log_count",
            params={"interval": 30, "threshold": 1},
        )

        request_params = self.handler.save_strategy_infos.call_args.kwargs["request_params"]
        algorithm_args = request_params["items"][0]["algorithms"][0]["config"]["args"]

        self.assertEqual(algorithm_args["$new_class_alert_th"], 1)

    def test_legacy_and_normal_notices_keep_model_alert_message(self):
        del self.handler.get_notice
        for save, kwargs in (
            (self.handler.save_legacy_new_cls_clustering_strategy, {"table_id": "2_legacy", "metric": "log_count"}),
            (self.handler.save_normal_clustering_strategy, {}),
        ):
            with self.subTest(strategy=save.__name__):
                save(params={"user_groups": [42]}, **kwargs)
                notice = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["notice"]
                self.assertIn("异常类型: {{alarm.bkm_info.alert_msg}}", notice["config"]["template"][0]["message_tmpl"])

    def test_new_class_and_normal_strategy_share_log_search_source_config(self):
        self.handler.save_new_cls_clustering_strategy(params={"interval": 30, "threshold": 5})
        new_class_query = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0][
            "query_configs"
        ][0]

        self.handler.save_normal_clustering_strategy(params={"sensitivity": 5})
        normal_query = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0]["query_configs"][
            0
        ]

        self.assertEqual(new_class_query["result_table_id"], "2_bklog.rt_create")
        self.assertEqual(normal_query["result_table_id"], "2_bklog.rt_create")
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

    def test_legacy_normal_strategy_keeps_dist_field(self):
        self.handler.save_normal_clustering_strategy(params={"sensitivity": 5})

        query_config = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0]["query_configs"][
            0
        ]
        self.assertEqual(query_config["agg_dimension"], ["__dist_05"])
        self.assertEqual(query_config["agg_condition"][0]["key"], "__dist_05")
        self.assertEqual(query_config["agg_condition"][0]["method"], "neq")

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

    def strategy_snapshot(self):
        return {
            "id": 17,
            "labels": ["custom"],
            "items": [
                {
                    "id": 21,
                    "query_configs": [
                        {
                            "id": 31,
                            "index_set_id": 123,
                            "agg_dimension": ["signature", "pod"],
                            "agg_condition": [{"key": "app", "method": "neq", "value": ["demo"]}],
                            "query_string": "severity:error",
                        }
                    ],
                    "algorithms": [
                        {
                            "id": 41,
                            "type": "NewSeries",
                            "level": 2,
                            "config": {"threshold": 4, "detect_range": 86400, "alert_mode": "continuous"},
                        }
                    ],
                }
            ],
            "notice": {"user_groups": [7], "options": {"chart_image_enabled": True}},
            "detects": [{"id": 51, "level": 2, "trigger_config": {"count": 1, "check_window": 9}}],
        }

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.update_partial_strategy_v3")
    def test_resave_preserves_query_filters_when_updating_dimensions(self, update):
        current = self.strategy_snapshot()
        self.handler._bound_strategy = Mock(side_effect=lambda _: deepcopy(current))
        self.handler.resave_new_cls_clustering_strategy()
        query = dict(current["items"][0]["query_configs"][0], agg_dimension=["signature", "service_name"])
        update.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "ids": [17],
                "edit_data": {"strategy_config": {"items": [{"id": 21, "query_configs": [query]}]}},
            }
        )
        self.handler.clustering_config.group_fields = ["pod"]
        self.handler.resave_new_cls_clustering_strategy()
        self.assertEqual(update.call_count, 1)

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.save_alarm_strategy_v3")
    def test_group_change_with_issue_keeps_filters_and_uses_validated_save(self, save):
        current = self.strategy_snapshot()
        current["issue_config"] = {"aggregate_dimensions": ["pod"], "alert_levels": [2]}
        self.handler._bound_strategy = Mock(return_value=deepcopy(current))
        self.handler.resave_new_cls_clustering_strategy()
        current["items"][0]["query_configs"][0]["agg_dimension"] = ["signature", "service_name"]
        save.assert_called_once_with(params=current)

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.update_partial_strategy_v3")
    def test_manual_save_applies_form_values_and_preserves_monitor_only_settings(self, update):
        current = self.strategy_snapshot()
        self.handler._bound_strategy = Mock(return_value=current)
        params = {"threshold": 11, "interval": 30, "level": 1, "user_groups": [42]}
        self.handler.create_or_update_clustering_strategy(StrategiesType.NEW_CLS_strategy, params)
        patch_data = update.call_args.kwargs["params"]["edit_data"]["strategy_config"]
        self.assertEqual(set(patch_data), {"items", "notice", "detects"})
        self.assertEqual(patch_data["notice"], {"user_groups": [42]})
        self.assertEqual(patch_data["detects"], [dict(current["detects"][0], level=1)])
        (item,) = patch_data["items"]
        # 手动保存不下发查询配置，包括监控侧的过滤条件和检索语句。
        self.assertEqual(set(item), {"id", "algorithms"})
        self.assertEqual(item["algorithms"][0]["level"], 1)
        self.assertEqual(
            item["algorithms"][0]["config"], {"threshold": 10, "detect_range": 30 * 86400, "alert_mode": "continuous"}
        )

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.update_partial_strategy_v3")
    def test_manual_save_skips_update_when_visible_values_match(self, update):
        self.handler._bound_strategy = Mock(return_value=self.strategy_snapshot())
        self.handler.create_or_update_clustering_strategy(
            StrategiesType.NEW_CLS_strategy, {"threshold": 5, "interval": 1, "level": 2, "user_groups": [7]}
        )
        update.assert_not_called()

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.update_partial_strategy_v3")
    def test_manual_level_preserves_trigger_and_notification_options(self, update):
        self.handler._bound_strategy = Mock(return_value=self.strategy_snapshot())
        self.handler.create_or_update_clustering_strategy(
            StrategiesType.NEW_CLS_strategy, {"level": 1, "user_groups": [8]}
        )
        patch_data = update.call_args.kwargs["params"]["edit_data"]["strategy_config"]
        self.assertEqual(patch_data["notice"], {"user_groups": [8]})
        self.assertEqual(
            patch_data["detects"], [{"id": 51, "level": 1, "trigger_config": {"count": 1, "check_window": 9}}]
        )
        self.assertEqual(patch_data["items"][0]["algorithms"][0]["level"], 1)
        self.assertNotIn("query_configs", patch_data["items"][0])

    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.save_alarm_strategy_v3")
    def test_legacy_and_count_alert_update_only_requested_argument(self, save):
        for strategy_type, params, arg in (
            (StrategiesType.NEW_CLS_strategy, {"threshold": 8}, "$new_class_alert_th"),
            (StrategiesType.NORMAL_STRATEGY, {"sensitivity": 8}, "$sensitivity"),
        ):
            with self.subTest(strategy_type=strategy_type):
                current = self.strategy_snapshot()
                algo = current["items"][0]["algorithms"][0]
                algo.update(type="IntelligentDetect", config={"args": {"$custom": 5}, "plan_id": 6})
                self.handler._bound_strategy = Mock(return_value=deepcopy(current))
                self.handler.create_or_update_clustering_strategy(strategy_type, params)
                algo["config"]["args"][arg] = 8
                save.assert_called_with(params=current)

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
                                    "config": {"detect_range": 30 * 24 * 60 * 60, "threshold": 0},
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
        self.assertEqual(result["threshold"], 1)

    @patch(
        "apps.log_clustering.handlers.dataflow.dataflow_handler.DataFlowHandler.sync_clustered_route",
        return_value=True,
    )
    @patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi.search_alarm_strategy_v3")
    def test_new_series_threshold_round_trip_does_not_drift(self, mock_search_strategy, _mock_sync_clustered_route):
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

        params = self.handler.get_strategy(StrategiesType.NEW_CLS_strategy, 9527)
        self.handler.save_new_cls_clustering_strategy(params=params)

        request_params = self.handler.save_strategy_infos.call_args.kwargs["request_params"]
        algorithm_config = request_params["items"][0]["algorithms"][0]["config"]
        self.assertEqual(params["threshold"], 6)
        self.assertEqual(algorithm_config["threshold"], 5)

    def test_new_class_strategy_serializer_rejects_zero_threshold(self):
        serializer = NewClsStrategySerializer(data={"interval": 30, "threshold": 0, "level": 2, "user_groups": [42]})

        self.assertFalse(serializer.is_valid())
        self.assertIn("threshold", serializer.errors)


QUIX_SIGNATURE_EXISTS_CONDITION = [
    {"key": "signature", "dimension_name": "signature", "value": [""], "method": "exists", "condition": "and"}
]


class TestQuixClusteringMonitorHandler(TestCase):
    """小型化索引集的三类聚类告警统一使用 signature，旧聚类保持 __dist_05。"""

    def setUp(self):
        TestClusteringMonitorHandler.setUp(self)
        self.handler.is_quix = True
        self.handler.clustering_config.log_count_aggregation_flow = None

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.DataFlowHandler.sync_clustered_route")
    def test_quix_new_class_strategy_uses_signature_without_route_sync(self, mock_sync_clustered_route):
        self.handler.save_new_cls_clustering_strategy(params={"interval": 30, "threshold": 5})

        query_config = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0]["query_configs"][
            0
        ]
        self.assertEqual(query_config["agg_dimension"], ["signature", "service_name"])
        self.assertEqual(query_config["agg_condition"], QUIX_SIGNATURE_EXISTS_CONDITION)
        mock_sync_clustered_route.assert_not_called()

    def test_quix_normal_strategy_uses_signature(self):
        self.handler.save_normal_clustering_strategy(params={"sensitivity": 5})

        query_config = self.handler.save_strategy_infos.call_args.kwargs["request_params"]["items"][0]["query_configs"][
            0
        ]
        self.assertEqual(query_config["agg_dimension"], ["signature"])
        self.assertEqual(query_config["agg_condition"], QUIX_SIGNATURE_EXISTS_CONDITION)
        self.assertEqual(self.handler.get_notice.call_args.kwargs["dimensions"], ["signature"])

    def test_new_class_uses_new_series_without_aggregation_flow_when_gray_switch_is_off(self):
        self.handler.is_new_class_new_series_enabled.return_value = False
        self.handler.save_legacy_new_cls_clustering_strategy = Mock()
        self.handler.save_new_cls_clustering_strategy = Mock(return_value={"strategy_id": 2})
        params = {"interval": 30, "threshold": 5}

        result = self.handler.create_or_update_clustering_strategy(StrategiesType.NEW_CLS_strategy, params)

        self.assertEqual(result, {"strategy_id": 2})
        self.handler.save_new_cls_clustering_strategy.assert_called_once_with(params=params)
        self.handler.save_legacy_new_cls_clustering_strategy.assert_not_called()


class TestPatternStrategySignatureField(TestCase):
    def _save_pattern_strategy(self, is_quix):
        handler = ClusteringMonitorHandler.__new__(ClusteringMonitorHandler)
        handler.index_set_id = 123
        handler.index_set = SimpleNamespace(index_set_name="test-index-set", time_field="dtEventTimeStamp")
        handler.clustering_config = SimpleNamespace(new_cls_index_set_id=None, group_fields=[], bk_biz_id=2)
        handler.bk_biz_id = 2
        handler.conf = {}
        handler.is_quix = is_quix
        remark = Mock(id=7, strategy_id=0, owners=["admin"], notice_group_id=42)
        with (
            patch(
                "apps.log_clustering.handlers.clustering_monitor.ClusteringRemark.materialize_inherited_remark",
                return_value=remark,
            ),
            patch("apps.log_clustering.handlers.clustering_monitor.is_remark_group_inherit_allowed", return_value=True),
            patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi") as monitor_api,
        ):
            monitor_api.search_user_groups.return_value = [{"id": 42}]
            monitor_api.save_alarm_strategy_v3.return_value = {"id": 9527}
            handler.save_pattern_strategy(
                table_id="2_bklog.rt_create",
                params={"signature": "abc", "groups": {}, "strategy_enabled": True},
            )
        return monitor_api.save_alarm_strategy_v3.call_args.kwargs["params"]["items"][0]["query_configs"][0]

    def test_quix_pattern_strategy_uses_signature(self):
        query_config = self._save_pattern_strategy(is_quix=True)

        self.assertEqual(query_config["agg_dimension"], ["signature"])
        self.assertEqual(query_config["agg_condition"][0]["key"], "signature")
        self.assertEqual(query_config["agg_condition"][0]["value"], ["abc"])

    def test_legacy_pattern_strategy_keeps_dist_field(self):
        query_config = self._save_pattern_strategy(is_quix=False)

        self.assertEqual(query_config["agg_dimension"], ["__dist_05"])
        self.assertEqual(query_config["agg_condition"][0]["key"], "__dist_05")
