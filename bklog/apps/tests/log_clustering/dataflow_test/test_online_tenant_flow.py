from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_clustering.handlers.dataflow.constants import ActionEnum
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler


class TestOnlineTenantFlow(SimpleTestCase):
    def setUp(self):
        super().setUp()
        switch_patcher = patch("apps.log_clustering.handlers.aiops.base.FeatureToggleObject.switch", return_value=True)
        toggle_patcher = patch(
            "apps.log_clustering.handlers.aiops.base.FeatureToggleObject.toggle",
            return_value=Mock(feature_config={"project_id": 1, "bk_biz_id": 2}),
        )
        self.addCleanup(switch_patcher.stop)
        self.addCleanup(toggle_patcher.stop)
        switch_patcher.start()
        toggle_patcher.start()

    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ActionHandler.get_action_handler")
    @patch("apps.log_clustering.handlers.aiops.base.get_online_clustering_config")
    def test_operator_flow_passes_tenant_header(self, mock_resolve, mock_get_action):
        mock_resolve.return_value = (
            {"project_id": 1001, "bk_biz_id": 2001, "model_id": "tenant_model", "tspider_cluster": "tenant_ts"},
            "tenant_a",
        )
        action = mock_get_action.return_value

        DataFlowHandler().operator_flow(flow_id=11, action=ActionEnum.START, bk_biz_id=2)

        action.assert_called_once()
        self.assertEqual(action.call_args.kwargs["bk_tenant_id"], "tenant_a")

    @patch.object(DataFlowHandler, "_render_template", return_value="[]")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ClusteringConfig.get_by_index_set_id")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.create_flow")
    @patch("apps.log_clustering.handlers.aiops.base.get_online_clustering_config")
    def test_aggregation_flow_uses_tenant_project_and_storage(
        self, mock_resolve, mock_create_flow, mock_get_config, mock_render
    ):
        mock_resolve.return_value = (
            {
                "project_id": 1001,
                "bk_biz_id": 2001,
                "model_id": "tenant_model",
                "tspider_cluster": "tenant_ts",
                "pattern_storage_cluster": "tenant_pattern",
            },
            "tenant_a",
        )
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
        self.assertEqual(render_obj["pattern"]["storage"], "tenant_pattern")
        self.assertEqual(render_obj["tspider_storage"]["cluster"], "tenant_ts")
        self.assertEqual(result["flow_id"], 91)
