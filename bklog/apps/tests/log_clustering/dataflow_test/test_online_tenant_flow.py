import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from apps.log_clustering.constants import DEFAULT_SIGNATURE_FORMAT_UDF
from apps.log_clustering.handlers.dataflow.constants import ActionEnum, FlowMode
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_clustering.tasks.flow import restart_flow


class TestOnlineTenantFlow(SimpleTestCase):
    def setUp(self):
        super().setUp()
        global_config = {"project_id": 1, "bk_biz_id": 2, "bk_username": "system_admin"}
        switch_patcher = patch("apps.log_clustering.handlers.aiops.base.FeatureToggleObject.switch", return_value=True)
        toggle_patcher = patch(
            "apps.log_clustering.handlers.aiops.base.FeatureToggleObject.toggle",
            return_value=Mock(feature_config=global_config),
        )
        resolve_patcher = patch(
            "apps.log_clustering.handlers.aiops.base.get_online_clustering_config",
            side_effect=lambda bk_biz_id: dict(global_config),
        )
        self.addCleanup(switch_patcher.stop)
        self.addCleanup(toggle_patcher.stop)
        self.addCleanup(resolve_patcher.stop)
        switch_patcher.start()
        toggle_patcher.start()
        resolve_patcher.start()

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

    @patch("apps.log_clustering.handlers.aiops.base.get_online_clustering_config")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ActionHandler.get_action_handler")
    def test_operator_flow_uses_tenant_cluster_group(self, mock_get_action, mock_resolve):
        mock_resolve.return_value = {
            "project_id": 1001,
            "bk_biz_id": 2001,
            "bk_username": "tenant_admin",
            "aiops_default_cluster_group": "tenant_flink",
        }
        action = mock_get_action.return_value

        DataFlowHandler().operator_flow(flow_id=11, action=ActionEnum.START, bk_biz_id=2)

        mock_resolve.assert_called_once_with(2)
        request_params = action.call_args.args[0]
        self.assertEqual(request_params["cluster_group"], "tenant_flink")
        self.assertEqual(request_params["bk_biz_id"], 2)
        self.assertEqual(request_params["bk_username"], "tenant_admin")

    @patch("apps.log_clustering.handlers.aiops.base.get_online_clustering_config")
    @patch("apps.log_clustering.handlers.dataflow.dataflow_handler.ActionHandler.get_action_handler")
    def test_operator_flow_without_business_id_keeps_global_cluster_group(self, mock_get_action, mock_resolve):
        handler = DataFlowHandler()
        handler.conf = {"bk_biz_id": 2, "bk_username": "system_admin", "aiops_default_cluster_group": "global_flink"}
        action = mock_get_action.return_value

        handler.operator_flow(flow_id=11, action=ActionEnum.RESTART)

        mock_resolve.assert_not_called()
        request_params = action.call_args.args[0]
        self.assertEqual(request_params["cluster_group"], "global_flink")
        self.assertEqual(request_params["bk_biz_id"], 2)

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
        clustering_config = Mock(
            bk_biz_id=2,
            index_set_id=30,
            predict_flow={"clustering_predict": {"result_table_id": "2_bklog_30_clustering_output"}},
            group_fields=[],
            new_cls_strategy_output="",
            new_cls_pattern_rt="",
            log_count_aggregation_flow={},
            save=Mock(),
        )
        mock_get_config.return_value = clustering_config
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
        self.assertFalse(render_obj["include_agg"])
        self.assertEqual(clustering_config.new_cls_pattern_rt, "")
        self.assertEqual(result["flow_id"], 91)

    def test_predict_flow_uses_database_storage_on_create_retry_and_update(self):
        config = ClusteringConfig(
            bk_biz_id=2,
            index_set_id=30,
            bkdata_etl_result_table_id="2_bklog_clean",
            model_id="model_id",
            clustering_fields="log",
            es_storage="old_es",
            filter_rules=[],
            min_members=1,
            max_log_length=1000,
        )
        tenant_conf = {
            "project_id": 1001,
            "bk_username": "tenant_admin",
            "signature_format_udf": "tenant_signature_udf",
            "predict_es_storage": "tenant_es",
        }
        handler = DataFlowHandler()
        with (
            patch.object(ClusteringConfig, "get_by_index_set_id", return_value=config),
            patch("apps.log_clustering.handlers.dataflow.dataflow_handler.get_online_clustering_config") as resolve,
            patch.object(config, "save"),
            patch.object(handler, "check_and_start_clean_task"),
            patch.object(handler, "get_fields_dict", return_value={"log": "log"}),
            patch.object(handler, "get_latest_released_id", return_value=1),
            patch.object(handler, "get_es_storage_fields", return_value={"expires": 30}),
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.DataAccessHandler.get_fields",
                return_value=[{"field_name": "log"}],
            ),
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.create_flow",
                return_value={"flow_id": 91},
            ) as create_flow,
            patch.object(handler, "sync_clustered_route"),
            patch.object(handler, "get_serving_data_processing_id_config", return_value={"id": "test"}),
            patch.object(handler, "update_model_instance"),
            patch.object(handler, "create_online_task", return_value={"ci_id": 5}),
            patch.object(handler, "get_flow_graph") as get_graph,
            patch.object(handler, "deal_real_time_node") as patch_sql,
        ):
            resolve.return_value = {}
            handler.conf = {}
            baseline_config = asdict(handler._init_predict_flow("2_bklog_clean", "model_id", 1, 2, 30, config))
            baseline_nodes = json.loads(
                handler._render_template(FlowMode.PREDICT_FLOW.value, {"predict": baseline_config})
            )
            self.assertIn(f"{DEFAULT_SIGNATURE_FORMAT_UDF}(log_signature)", baseline_nodes[-2]["sql"])
            self.assertEqual(baseline_nodes[-1]["cluster"], "old_es")

            resolve.return_value = tenant_conf
            create_flow.side_effect = RuntimeError("create failed")
            with self.assertRaisesRegex(RuntimeError, "create failed"):
                handler.create_predict_flow(30)
            self.assertEqual(config.es_storage, "old_es")
            self.assertIsNone(config.predict_flow_id)

            create_flow.side_effect = None
            handler.create_predict_flow(30)
            nodes = create_flow.call_args.args[0]["nodes"]
            self.assertIn("tenant_signature_udf(log_signature)", nodes[-2]["sql"])
            self.assertEqual(nodes[-1]["cluster"], "old_es")
            self.assertEqual(config.es_storage, "old_es")
            self.assertEqual(config.predict_flow["es_cluster"], "old_es")

            get_graph.return_value = {
                "nodes": [
                    {
                        "node_type": "realtime",
                        "node_config": {"table_name": "bklog_30_clustered"},
                        "flow_id": 91,
                        "node_id": 71,
                    }
                ]
            }
            resolve.return_value = {
                **tenant_conf,
                "predict_es_storage": "other_es",
            }
            config.es_storage = "corrected_es"
            handler.update_predict_flow(30)
            self.assertIn("tenant_signature_udf(log_signature)", patch_sql.call_args.kwargs["sql"])
            self.assertEqual(config.predict_flow["es_cluster"], "corrected_es")
            self.assertEqual(config.es_storage, "corrected_es")

    def test_aggregation_creation_and_update_render_all_signature_udf_calls(self):
        config = Mock(
            bk_biz_id=2,
            index_set_id=30,
            predict_flow={"clustering_predict": {"result_table_id": "2_bklog_30_clustering_output"}},
            group_fields=[],
            new_cls_strategy_output="",
            new_cls_pattern_rt="2_bklog_30_agg",
            log_count_aggregation_flow={},
        )
        handler = DataFlowHandler()
        with (
            patch.object(ClusteringConfig, "get_by_index_set_id", return_value=config),
            patch("apps.log_clustering.handlers.dataflow.dataflow_handler.get_online_clustering_config") as resolve,
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.create_flow",
                return_value={"flow_id": 91},
            ) as create_flow,
            patch.object(handler, "get_flow_graph") as get_graph,
            patch.object(handler, "deal_real_time_node") as patch_sql,
            patch.object(handler, "operator_flow"),
        ):
            resolve.return_value = {"signature_format_udf": "tenant_signature_udf"}
            handler.create_log_count_aggregation_flow(30)
            nodes = create_flow.call_args.args[0]["nodes"]
            sql_nodes = [node for node in nodes if node["node_type"] == "realtime"]
            self.assertEqual(len(sql_nodes), 3)
            for node in sql_nodes:
                self.assertRegex(node["sql"], r"tenant_signature_udf\s*\(")

            get_graph.return_value = {
                "nodes": [
                    {
                        "node_type": "realtime",
                        "node_config": {"table_name": node["table_name"]},
                        "flow_id": 91,
                        "node_id": node["id"],
                    }
                    for node in sql_nodes
                ]
            }
            handler.update_log_count_aggregation_flow(30)
            self.assertEqual(patch_sql.call_count, 3)
            for node_call in patch_sql.call_args_list:
                self.assertRegex(node_call.kwargs["sql"], r"tenant_signature_udf\s*\(")

    def test_log_count_aggregation_flow_keeps_agg_for_legacy_config(self):
        clustering_config = Mock(
            new_cls_strategy_output="",
            new_cls_pattern_rt="2_bklog_30_agg",
            log_count_aggregation_flow={},
            bk_biz_id=2,
        )

        self.assertTrue(DataFlowHandler._should_include_log_count_agg(clustering_config))

    def test_log_count_aggregation_template_can_skip_agg_nodes(self):
        handler = DataFlowHandler()
        handler.conf = {}
        clustering_config = SimpleNamespace(group_fields=[])

        flow_config = asdict(
            handler._init_log_count_aggregation_flow(
                result_table_id="2_bklog_30_clustering_output",
                bk_biz_id=2,
                index_set_id=30,
                clustering_config=clustering_config,
                include_agg=False,
            )
        )
        rendered = handler._render_template(
            flow_mode=FlowMode.LOG_COUNT_AGGREGATION_FLOW.value,
            render_obj={"log_count_aggregation": flow_config},
        )

        nodes = json.loads(rendered)
        for node in nodes:
            if node["node_type"] == "realtime":
                self.assertRegex(node["sql"], rf"{DEFAULT_SIGNATURE_FORMAT_UDF}\s*\(")
        node_ids = {node["id"] for node in nodes}
        self.assertEqual(node_ids, {447364, 587866, 587868, 589424})
        self.assertNotIn(447374, node_ids)
        self.assertNotIn(447376, node_ids)

    def test_create_predict_flow_raises_when_clustered_route_sync_fails(self):
        clustering_config = Mock(
            bk_biz_id=2,
            index_set_id=30,
            bkdata_etl_result_table_id="2_bklog_clean",
            model_id="model_id",
            clustering_fields="log",
            save=Mock(),
        )
        predict_flow = {
            "clustering_predict": {"result_table_id": "2_bklog_30_clustering_output"},
            "format_signature": {"result_table_id": "2_bklog_30_clustered"},
        }

        with (
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.ClusteringConfig.get_by_index_set_id"
            ) as get_config,
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.get_online_clustering_config"
            ) as get_online_config,
            patch.object(DataFlowHandler, "check_and_start_clean_task"),
            patch.object(DataFlowHandler, "get_fields_dict", return_value={"log": "log"}),
            patch.object(DataFlowHandler, "get_latest_released_id", return_value=1),
            patch.object(DataFlowHandler, "_init_predict_flow", return_value=object()),
            patch("apps.log_clustering.handlers.dataflow.dataflow_handler.asdict", return_value=predict_flow),
            patch.object(DataFlowHandler, "_render_template", return_value="[]"),
            patch.object(DataFlowHandler, "_set_bkdata_request_params", return_value={"project_id": 1001}),
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.BkDataDataFlowApi.create_flow",
                return_value={"flow_id": 91},
            ),
            patch.object(
                DataFlowHandler,
                "sync_clustered_route",
                side_effect=RuntimeError("router sync failed"),
            ) as sync_route,
            patch.object(DataFlowHandler, "create_online_task") as create_online_task,
        ):
            get_config.return_value = clustering_config
            get_online_config.return_value = {"project_id": 1001, "bk_username": "tenant_admin"}

            with self.assertRaisesRegex(RuntimeError, "router sync failed"):
                DataFlowHandler().create_predict_flow(30)

        sync_route.assert_called_once_with(index_set_id=30, raise_exception=True)
        create_online_task.assert_not_called()

    def test_update_predict_flow_raises_when_clustered_route_sync_fails(self):
        clustering_config = Mock(
            bk_biz_id=2,
            index_set_id=30,
            bkdata_etl_result_table_id="2_bklog_clean",
            model_id="model_id",
            clustering_fields="log",
            predict_flow_id=91,
            save=Mock(),
        )
        predict_flow = {
            "clustering_predict": {"result_table_id": "2_bklog_30_clustering_output"},
            "format_signature": {"result_table_id": "2_bklog_30_clustered"},
        }

        with (
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.ClusteringConfig.get_by_index_set_id"
            ) as get_config,
            patch(
                "apps.log_clustering.handlers.dataflow.dataflow_handler.get_online_clustering_config"
            ) as get_online_config,
            patch.object(DataFlowHandler, "get_fields_dict", return_value={"log": "log"}),
            patch.object(DataFlowHandler, "get_latest_released_id", return_value=1),
            patch.object(DataFlowHandler, "get_flow_graph", return_value={"nodes": []}),
            patch.object(DataFlowHandler, "_init_predict_flow", return_value=object()),
            patch("apps.log_clustering.handlers.dataflow.dataflow_handler.asdict", return_value=predict_flow),
            patch.object(DataFlowHandler, "_render_template", return_value="[]"),
            patch.object(DataFlowHandler, "deal_predict_flow"),
            patch.object(
                DataFlowHandler,
                "sync_clustered_route",
                side_effect=RuntimeError("router sync failed"),
            ) as sync_route,
        ):
            get_config.return_value = clustering_config
            get_online_config.return_value = {"project_id": 1001, "bk_username": "tenant_admin"}

            with self.assertRaisesRegex(RuntimeError, "router sync failed"):
                DataFlowHandler().update_predict_flow(30)

        sync_route.assert_called_once_with(index_set_id=30, raise_exception=True)

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
