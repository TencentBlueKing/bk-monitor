from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from apps.log_clustering.handlers.dataflow.constants import ActionEnum
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.tasks.flow import restart_flow


class TestOnlineTenantFlow(SimpleTestCase):
    def setUp(self):
        super().setUp()
        switch_patcher = patch("apps.log_clustering.handlers.aiops.base.FeatureToggleObject.switch", return_value=True)
        toggle_patcher = patch(
            "apps.log_clustering.handlers.aiops.base.FeatureToggleObject.toggle",
            return_value=Mock(feature_config={"project_id": 1, "bk_biz_id": 2, "bk_username": "system_admin"}),
        )
        self.addCleanup(switch_patcher.stop)
        self.addCleanup(toggle_patcher.stop)
        switch_patcher.start()
        toggle_patcher.start()

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ActionHandler.get_action_handler")
    def test_operator_flow_passes_business_id_for_tenant_getter(self, mock_get_action):
        action = mock_get_action.return_value

        DataFlowHandler().operator_flow(flow_id=11, action=ActionEnum.START, bk_biz_id=2)

        action.assert_called_once()
        request_params = action.call_args.args[0]
        self.assertEqual(request_params["bk_biz_id"], 2)
        self.assertEqual(request_params["bk_username"], "system_admin")
        self.assertEqual(request_params["operator"], "system_admin")
        self.assertTrue(request_params["no_request"])
        self.assertNotIn("bk_tenant_id", action.call_args.kwargs)

    @patch("retrying.time.sleep", return_value=None)
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ActionHandler.get_action_handler")
    def test_operator_flow_does_not_retry_failed_action(self, mock_get_action, mock_sleep):
        action = mock_get_action.return_value
        action.side_effect = RuntimeError("start failed")

        with self.assertRaises(RuntimeError):
            DataFlowHandler().operator_flow(flow_id=11, action=ActionEnum.START, bk_biz_id=2)

        action.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.get_dataflow")
    def test_get_dataflow_info_does_not_retry_failed_result(self, mock_get_dataflow):
        DataFlowHandler().get_dataflow_info(flow_id=11, bk_biz_id=2)

        self.assertNotIn("data_api_retry_cls", mock_get_dataflow.call_args.kwargs)

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.get_latest_deploy_data")
    def test_get_latest_deploy_data_does_not_retry_failed_result(self, mock_get_latest_deploy_data):
        DataFlowHandler().get_latest_deploy_data(flow_id=11, bk_biz_id=2)

        self.assertNotIn("data_api_retry_cls", mock_get_latest_deploy_data.call_args.kwargs)

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDatabusApi.post_tasks")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataMetaApi.result_tables.retrieve")
    def test_check_and_start_clean_task_passes_business_params(self, mock_retrieve, mock_post_tasks):
        mock_retrieve.return_value = {"processing_type": "clean"}

        DataFlowHandler().check_and_start_clean_task("2_bklog_clean", bk_biz_id=2)

        retrieve_params = mock_retrieve.call_args.args[0]
        post_params = mock_post_tasks.call_args.args[0]
        for params in [retrieve_params, post_params]:
            self.assertEqual(params["bk_biz_id"], 2)
            self.assertEqual(params["bk_username"], "system_admin")
            self.assertEqual(params["operator"], "system_admin")
            self.assertTrue(params["no_request"])

    @patch.object(DataFlowHandler, "_render_template", return_value="[]")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ClusteringConfig.get_by_index_set_id")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.create_flow")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.get_online_clustering_config")
    def test_aggregation_flow_uses_tenant_project_and_storage(
        self, mock_resolve, mock_create_flow, mock_get_config, mock_render
    ):
        mock_resolve.return_value = {
            "project_id": 1001,
            "bk_biz_id": 2001,
            "model_id": "tenant_model",
            "bk_username": "tenant_admin",
            "tspider_cluster": "tenant_ts",
            "pattern_storage_cluster": "tenant_pattern",
        }
        mock_get_config.return_value = Mock(
            bk_biz_id=2,
            index_set_id=30,
            predict_flow={"clustering_predict": {"result_table_id": "2_bklog_30_clustering_output"}},
            group_fields=[],
            save=Mock(),
        )
        mock_create_flow.return_value = {"flow_id": 91}

        result = DataFlowHandler().create_log_count_aggregation_flow(30)

        request_params = mock_create_flow.call_args.args[0]
        render_obj = mock_render.call_args.kwargs["render_obj"]["log_count_aggregation"]
        self.assertEqual(request_params["project_id"], 1001)
        self.assertEqual(request_params["bk_biz_id"], 2)
        self.assertEqual(request_params["bk_username"], "tenant_admin")
        self.assertEqual(request_params["operator"], "tenant_admin")
        self.assertTrue(request_params["no_request"])
        self.assertEqual(render_obj["pattern"]["storage"], "tenant_pattern")
        self.assertEqual(render_obj["tspider_storage"]["cluster"], "tenant_ts")
        self.assertEqual(result["flow_id"], 91)

    @patch("apps.log_clustering.tasks.flow.cache.get", return_value=None)
    @patch("apps.log_clustering.tasks.flow.DataFlowHandler.operator_flow")
    @patch("apps.log_clustering.tasks.flow.ClusteringConfig.get_by_index_set_id")
    def test_restart_flow_passes_business_id_for_online_flows(
        self, mock_get_config, mock_operator_flow, mock_cache_get
    ):
        mock_get_config.return_value = Mock(
            bk_biz_id=2,
            predict_flow_id=11,
            log_count_aggregation_flow_id=22,
        )

        restart_flow(index_set_id=30, flow_ids=[11, 22])

        mock_operator_flow.assert_has_calls(
            [
                call(flow_id=11, action=ActionEnum.RESTART, bk_biz_id=2),
                call(flow_id=22, action=ActionEnum.RESTART, bk_biz_id=2),
            ]
        )
