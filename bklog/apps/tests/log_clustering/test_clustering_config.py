from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, TestCase

from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import MINI_CLUSTERING_CONFIG
from apps.log_clustering.components.collections.data_access_component import AddResourceGroupService
from apps.log_clustering.components.collections.flow_component import (
    UpdateClusteringField,
    UpdateClusteringFieldService,
)
from apps.log_clustering.constants import DEFAULT_SIGNATURE_FORMAT_UDF, RegexRuleTypeEnum, StorageTypeEnum
from apps.log_clustering.handlers.dataflow.constants import ActionEnum
from apps.log_clustering.handlers.pipline_service.aiops_service_online import UpdateOnlineService
from apps.log_clustering.exceptions import ClusteringConfigHasExistException, RegexTemplateNotExistException
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.models import ClusteringConfig, RegexTemplate
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario

TEST_INDEX_SET_ID = 1
TEST_BK_BIZ_ID = 2
TEST_CLUSTERED_RT = "test_clustered_rt"


class TestClusteringConfigHandler(SimpleTestCase):
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.objects.all")
    def test_list_all_configs_includes_placeholder_analysis_supported(self, mock_all):
        mock_all.return_value = [
            ClusteringConfig(
                index_set_id=TEST_INDEX_SET_ID,
                bk_biz_id=TEST_BK_BIZ_ID,
                min_members=1,
                max_dist_list="0.1",
                predefined_varibles="",
                delimeter=" ",
                max_log_length=1024,
                clustering_fields="log",
                storage_type=StorageTypeEnum.DORIS.value,
                clustered_rt=TEST_CLUSTERED_RT,
            )
        ]

        result = ClusteringConfigHandler.list_all_configs()

        self.assertTrue(result[0]["placeholder_analysis_supported"])

    @patch("apps.log_clustering.handlers.clustering_config.FeatureToggleObject.switch", return_value=False)
    def test_mini_clustering_toggle_off_keeps_online_flow(self, mock_switch):
        index_set = LogIndexSet(index_set_id=TEST_INDEX_SET_ID, scenario_id=Scenario.LOG, space_uid="bkcc__2")

        self.assertFalse(ClusteringConfigHandler._use_quix_clustering(index_set))

    @patch("apps.log_clustering.handlers.clustering_config.FeatureToggleObject.switch", return_value=True)
    def test_mini_clustering_toggle_ignores_bkdata_index_set(self, mock_switch):
        index_set = LogIndexSet(index_set_id=TEST_INDEX_SET_ID, scenario_id=Scenario.BKDATA, space_uid="bkcc__2")

        self.assertFalse(ClusteringConfigHandler._use_quix_clustering(index_set))
        mock_switch.assert_not_called()

    @patch("apps.log_clustering.handlers.clustering_config.LogIndexSet.objects.get")
    @patch("apps.log_clustering.handlers.clustering_config.QuixClusteringHandler")
    @patch("apps.log_clustering.handlers.clustering_config.LogClusteringRuntime.objects.filter")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_update_routes_to_quix_runtime(
        self, mock_get_clustering_config, mock_runtime_filter, mock_quix_handler, mock_get_index_set
    ):
        mock_runtime_filter.return_value.exists.return_value = True
        mock_quix_handler.return_value.update.return_value = "operation-id"

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).update({"filter_rules": []})

        self.assertEqual(result, "operation-id")
        mock_quix_handler.return_value.update.assert_called_once_with({"filter_rules": []})

    def test_save_schedules_both_online_flows_when_only_signature_udf_changes(self):
        config = Mock(
            index_set_id=TEST_INDEX_SET_ID,
            bk_biz_id=TEST_BK_BIZ_ID,
            predict_flow_id=11,
            log_count_aggregation_flow_id=12,
            predict_flow={"signature_format_udf": "tenant_udf"},
            log_count_aggregation_flow={},
            task_records=[],
        )
        with (
            patch.object(ClusteringConfig, "get_by_index_set_id", return_value=config),
            patch("apps.log_clustering.handlers.clustering_config.LogClusteringRuntime.objects.filter") as runtime,
            patch(
                "apps.log_clustering.handlers.pipline_service.aiops_service_online.get_online_clustering_config",
                return_value={"signature_format_udf": "tenant_udf"},
            ),
            patch(
                "apps.log_clustering.handlers.pipline_service.aiops_service_online.UpdateClusteringField",
                wraps=UpdateClusteringField,
            ) as step,
            patch.object(UpdateOnlineService, "start_pipeline") as start_pipeline,
            patch("apps.log_clustering.tasks.flow.restart_flow.apply_async") as restart,
        ):
            runtime.return_value.exists.return_value = False
            task_id = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).update({})

        step.assert_called_once_with(TEST_INDEX_SET_ID, "tenant_udf")
        self.assertEqual(task_id, start_pipeline.call_args.args[0].id)
        restart.assert_not_called()

    def test_old_snapshots_without_udf_match_the_default(self):
        config = Mock(
            bk_biz_id=TEST_BK_BIZ_ID,
            predict_flow_id=11,
            log_count_aggregation_flow_id=12,
            predict_flow={},
            log_count_aggregation_flow={},
        )
        with patch(
            "apps.log_clustering.handlers.pipline_service.aiops_service_online.get_online_clustering_config",
            return_value={},
        ):
            self.assertIsNone(UpdateOnlineService.get_changed_signature_format_udf(config))
            config.log_count_aggregation_flow = {"signature_format_udf": "previous_udf"}
            self.assertEqual(UpdateOnlineService.get_changed_signature_format_udf(config), DEFAULT_SIGNATURE_FORMAT_UDF)

    def test_signature_udf_updates_both_graphs_before_either_restart(self):
        config = Mock(bk_biz_id=TEST_BK_BIZ_ID, predict_flow_id=11, log_count_aggregation_flow_id=12)
        data = Mock()
        data.get_one_of_inputs.side_effect = {
            "index_set_id": TEST_INDEX_SET_ID,
            "signature_format_udf": "tenant_udf",
        }.get
        with (
            patch.object(ClusteringConfig, "get_by_index_set_id", return_value=config),
            patch("apps.log_clustering.components.collections.flow_component.DataFlowHandler") as handler_cls,
        ):
            handler = handler_cls.return_value
            step = UpdateClusteringFieldService()
            handler.update_log_count_aggregation_flow.side_effect = RuntimeError("aggregation SQL update failed")
            with self.assertRaisesRegex(RuntimeError, "aggregation SQL update failed"):
                step._execute(data, None)
            handler.operator_flow.assert_not_called()

            handler.reset_mock()
            handler.update_log_count_aggregation_flow.side_effect = None
            self.assertTrue(step._execute(data, None))

        self.assertEqual(
            handler.mock_calls,
            [
                call.update_predict_flow(TEST_INDEX_SET_ID, signature_format_udf="tenant_udf"),
                call.update_log_count_aggregation_flow(
                    TEST_INDEX_SET_ID, signature_format_udf="tenant_udf", restart=False
                ),
                call.operator_flow(flow_id=11, action=ActionEnum.RESTART, bk_biz_id=TEST_BK_BIZ_ID),
                call.operator_flow(flow_id=12, action=ActionEnum.RESTART, bk_biz_id=TEST_BK_BIZ_ID),
            ],
        )

    def test_placeholder_analysis_supported_property(self):
        supported_config = ClusteringConfig(storage_type=StorageTypeEnum.DORIS.value, clustered_rt=TEST_CLUSTERED_RT)
        unsupported_config = ClusteringConfig(storage_type=StorageTypeEnum.ELASTICSEARCH.value, clustered_rt="")

        self.assertTrue(supported_config.placeholder_analysis_supported)
        self.assertFalse(unsupported_config.placeholder_analysis_supported)

    def test_get_access_total_count_uses_statistics_total_handler(self):
        clustering_config = Mock(index_set_id=TEST_INDEX_SET_ID, bk_biz_id=TEST_BK_BIZ_ID)
        addition = [{"field": "__dist_05", "operator": "exists"}]

        with patch.object(ClusteringConfigHandler, "_get_access_check_time_range", return_value=(1000, 2000)):
            with patch("apps.log_clustering.handlers.clustering_config.UnifyQueryFieldHandler") as mock_handler:
                mock_handler.return_value.get_total_count.return_value = 3

                result = ClusteringConfigHandler()._get_access_total_count(clustering_config, addition=addition)

        self.assertEqual(result, 3)
        mock_handler.assert_called_once_with(
            {
                "bk_biz_id": TEST_BK_BIZ_ID,
                "index_set_ids": [TEST_INDEX_SET_ID],
                "start_time": 1000,
                "end_time": 2000,
                "time_range": "customized",
                "addition": addition,
            }
        )

    @patch("apps.log_clustering.handlers.clustering_config.LogIndexSet.objects.get")
    @patch("apps.log_clustering.handlers.clustering_config.QuixClusteringHandler")
    @patch("apps.log_clustering.handlers.clustering_config.LogClusteringRuntime.objects.filter")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_get_access_status_routes_to_quix_runtime(
        self, mock_get_clustering_config, mock_runtime_filter, mock_quix_handler, mock_get_index_set
    ):
        mock_runtime_filter.return_value.exists.return_value = True
        mock_quix_handler.return_value.get_access_status.return_value = {"access_finished": False}

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).get_access_status()

        self.assertEqual(result, {"access_finished": False})
        mock_quix_handler.assert_called_once_with(mock_get_index_set.return_value)

    @patch("apps.log_clustering.handlers.clustering_config.LogClusteringRuntime.objects.filter")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_get_access_status_uses_unified_count_for_origin_and_clustered(
        self, mock_get_clustering_config, mock_runtime_filter
    ):
        mock_runtime_filter.return_value.exists.return_value = False
        clustering_config = Mock(
            index_set_id=TEST_INDEX_SET_ID,
            bk_biz_id=TEST_BK_BIZ_ID,
            clustered_rt=TEST_CLUSTERED_RT,
            access_finished=False,
            task_records=[],
            task_details={},
            predict_flow_id=None,
            log_count_aggregation_flow_id=None,
        )
        mock_get_clustering_config.return_value = clustering_config

        with patch.object(ClusteringConfigHandler, "_get_access_total_count", side_effect=[1, 1]) as mock_total_count:
            result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).get_access_status()

        self.assertTrue(result["access_finished"])
        self.assertEqual(
            mock_total_count.call_args_list,
            [
                call(clustering_config),
                call(clustering_config, addition=[{"field": "__dist_05", "operator": "exists"}]),
            ],
        )
        clustering_config.save.assert_called_once_with(update_fields=["access_finished"])

    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_retrieve_includes_placeholder_analysis_supported(self, mock_get_clustering_config):
        clustering_config = ClusteringConfig(
            index_set_id=TEST_INDEX_SET_ID,
            bk_biz_id=TEST_BK_BIZ_ID,
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="",
            delimeter=" ",
            max_log_length=1024,
            clustering_fields="log",
            storage_type=StorageTypeEnum.DORIS.value,
            clustered_rt=TEST_CLUSTERED_RT,
        )
        mock_get_clustering_config.return_value = clustering_config

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).retrieve()

        self.assertTrue(result["placeholder_analysis_supported"])


class TestCreateClusteringInGrayBusiness(TestCase):
    def test_first_creation_persists_es_settings_and_duplicate_keeps_the_binding(self):
        index_set = LogIndexSet.objects.create(
            index_set_name="bkdata_es", space_uid=f"bkcc__{TEST_BK_BIZ_ID}", scenario_id=Scenario.BKDATA
        )
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_source")
        params = {"clustering_fields": "log", "new_cls_strategy_enable": False, "normal_strategy_enable": False}
        with (
            patch("apps.log_clustering.handlers.clustering_config.access_clustering.delay") as start,
            patch("apps.log_clustering.handlers.clustering_config.get_online_clustering_config") as get_config,
            patch(
                "apps.log_clustering.handlers.clustering_config.RegexTemplateHandler.list_templates",
                return_value=[{"id": 1, "predefined_varibles": "W10="}],
            ),
        ):
            get_config.return_value = {"predict_es_storage": {"cluster_name": "first_es", "cluster_id": 8}}
            ClusteringConfigHandler().create(index_set.index_set_id, params)
            get_config.return_value = {"predict_es_storage": {"cluster_name": "different_es", "cluster_id": 9}}
            with self.assertRaises(ClusteringConfigHasExistException):
                ClusteringConfigHandler().create(index_set.index_set_id, params)

        config = ClusteringConfig.get_by_index_set_id(index_set.index_set_id)
        self.assertEqual(config.es_storage, "first_es")
        self.assertEqual(config.predict_es_cluster_id, 8)
        start.assert_called_once_with(index_set_id=index_set.index_set_id)

        node_data = Mock()
        node_data.get_one_of_inputs.return_value = index_set.index_set_id
        with patch("apps.log_clustering.components.collections.data_access_component.DataAccessHandler") as handler:
            self.assertTrue(AddResourceGroupService()._execute(node_data, None))
        handler.return_value.add_cluster_group.assert_called_once_with(
            "2_source", TEST_BK_BIZ_ID, cluster_name="first_es"
        )

    def test_only_v4_collector_uses_quix(self):
        FeatureToggle.objects.create(name=MINI_CLUSTERING_CONFIG, status="debug", biz_id_white_list=[TEST_BK_BIZ_ID])
        params = {"clustering_fields": "log", "new_cls_strategy_enable": False, "normal_strategy_enable": False}
        for enable_v4 in (False, True):
            with self.subTest(enable_v4=enable_v4):
                name = "test_v4" if enable_v4 else "test_v3"
                table_id = f"{TEST_BK_BIZ_ID}_bklog.{name}"
                collector = CollectorConfig.objects.create(
                    bk_biz_id=TEST_BK_BIZ_ID,
                    collector_config_name=name,
                    collector_config_name_en=name,
                    table_id=table_id,
                    enable_v4=enable_v4,
                )
                index_set = LogIndexSet.objects.create(
                    index_set_name=name,
                    space_uid=f"bkcc__{TEST_BK_BIZ_ID}",
                    scenario_id=Scenario.LOG,
                    collector_config_id=collector.collector_config_id,
                )
                LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id=table_id)

                with (
                    patch("apps.log_clustering.handlers.clustering_config.QuixClusteringHandler") as quix,
                    patch("apps.log_clustering.handlers.clustering_config.access_clustering.delay") as legacy_task,
                    patch(
                        "apps.log_clustering.handlers.clustering_config.get_online_clustering_config",
                        return_value={"collector_clustering_es_storage": {"es_storage": "test_es"}},
                    ),
                    patch.object(CollectorConfig, "get_etl_config", return_value={"fields": [{"field_name": "log"}]}),
                    patch(
                        "apps.log_clustering.handlers.clustering_config.RegexTemplateHandler.list_templates",
                        return_value=[{"id": 1, "predefined_varibles": "W10="}],
                    ),
                ):
                    ClusteringConfigHandler().create(index_set.index_set_id, params)

                if enable_v4:
                    quix.assert_called_once_with(index_set)
                    quix.return_value.enable.assert_called_once_with(params)
                    legacy_task.assert_not_called()
                else:
                    quix.assert_not_called()
                    legacy_task.assert_called_once_with(index_set_id=index_set.index_set_id)


class TestSynchronousUpdateRegexTemplateSpace(TestCase):
    """更新聚类配置时，正则模板必须属于目标索引集所在空间"""

    SPACE_UID = "bkcc__2"
    OTHER_SPACE_UID = "bkcc__99"

    def setUp(self):
        self.index_set = LogIndexSet.objects.create(
            index_set_name="regex_template_space_index", space_uid=self.SPACE_UID, scenario_id="es"
        )
        ClusteringConfig.objects.create(
            index_set_id=self.index_set.index_set_id,
            bk_biz_id=TEST_BK_BIZ_ID,
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="origin",
            delimeter=" ",
            max_log_length=1024,
            clustering_fields="log",
        )
        self.local_template = RegexTemplate.objects.create(
            space_uid=self.SPACE_UID,
            template_name="local_template",
            predefined_varibles="local_vars",
        )
        self.foreign_template = RegexTemplate.objects.create(
            space_uid=self.OTHER_SPACE_UID,
            template_name="foreign_template",
            predefined_varibles="foreign_vars",
        )

    def _handler(self):
        return ClusteringConfigHandler(index_set_id=self.index_set.index_set_id)

    def test_same_space_template_copies_predefined_varibles(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.local_template.id,
        }

        with patch.object(handler, "update", return_value="pipeline-1") as mock_update:
            result = handler.synchronous_update(params)

        self.assertEqual(result, ["pipeline-1"])
        mock_update.assert_called_once_with(params)
        self.assertEqual(params["predefined_varibles"], "local_vars")

    def test_cross_space_template_id_is_rejected(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.foreign_template.id,
        }

        with patch.object(handler, "update") as mock_update:
            with self.assertRaises(RegexTemplateNotExistException):
                handler.synchronous_update(params)

        mock_update.assert_not_called()

    def test_unknown_template_id_is_rejected(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.foreign_template.id + 1000,
        }

        with patch.object(handler, "update") as mock_update:
            with self.assertRaises(RegexTemplateNotExistException):
                handler.synchronous_update(params)

        mock_update.assert_not_called()
