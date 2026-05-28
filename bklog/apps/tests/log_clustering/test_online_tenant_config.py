from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase

from apps.log_clustering.handlers.aiops.config import get_online_clustering_config
from apps.log_clustering.handlers.pipline_service.aiops_service_online import operator_aiops_service_online


class TestOnlineTenantConfig(SimpleTestCase):
    @patch("apps.log_clustering.handlers.aiops.config.Space.get_tenant_id")
    @patch("apps.log_clustering.handlers.aiops.config.FeatureToggleObject.toggle")
    def test_default_tenant_uses_top_level_config(self, mock_toggle, mock_get_tenant_id):
        mock_get_tenant_id.return_value = settings.BK_APP_TENANT_ID
        mock_toggle.return_value = Mock(
            feature_config={
                "project_id": 1,
                "bk_biz_id": 2,
                "model_id": "system_model",
                "tspider_cluster": "system_ts",
            }
        )

        config = get_online_clustering_config(2)

        self.assertEqual(config["project_id"], 1)
        self.assertEqual(config["model_id"], "system_model")

    @patch("apps.log_clustering.handlers.aiops.config.Space.get_tenant_id")
    @patch("apps.log_clustering.handlers.aiops.config.FeatureToggleObject.toggle")
    def test_non_default_tenant_overrides_online_resource_config(self, mock_toggle, mock_get_tenant_id):
        mock_get_tenant_id.return_value = "tenant_a"
        mock_toggle.return_value = Mock(
            feature_config={
                "project_id": 1,
                "bk_biz_id": 2,
                "model_id": "system_model",
                "tspider_cluster": "system_ts",
                "pattern_storage_cluster": "system_pattern",
                "collector_clustering_es_storage": {"es_storage": "system_es"},
                "doris_storage": "system_doris",
                "log_pattern_expires": 30,
                "tenant_resource_configs": {
                    "tenant_a": {
                        "project_id": 1001,
                        "model_id": "tenant_model",
                        "tspider_cluster": "tenant_ts",
                    }
                },
            }
        )

        config = get_online_clustering_config(2)

        self.assertEqual(config["project_id"], 1001)
        self.assertEqual(config["bk_biz_id"], 2)
        self.assertEqual(config["model_id"], "tenant_model")
        self.assertEqual(config["tspider_cluster"], "tenant_ts")
        self.assertEqual(config["pattern_storage_cluster"], "system_pattern")
        self.assertEqual(config["log_pattern_expires"], 30)
        self.assertEqual(config["collector_clustering_es_storage"], {"es_storage": "system_es"})
        self.assertEqual(config["doris_storage"], "system_doris")

    @patch("apps.log_clustering.handlers.aiops.config.Space.get_tenant_id")
    @patch("apps.log_clustering.handlers.aiops.config.FeatureToggleObject.toggle")
    def test_non_default_tenant_falls_back_to_top_level_config_without_override(self, mock_toggle, mock_get_tenant_id):
        mock_get_tenant_id.return_value = "tenant_a"
        mock_toggle.return_value = Mock(
            feature_config={
                "project_id": 1,
                "bk_biz_id": 2,
                "model_id": "system_model",
                "tspider_cluster": "system_ts",
                "tenant_resource_configs": {},
            }
        )

        config = get_online_clustering_config(2)

        self.assertEqual(config["project_id"], 1)
        self.assertEqual(config["bk_biz_id"], 2)
        self.assertEqual(config["model_id"], "system_model")
        self.assertEqual(config["pattern_storage_cluster"], "system_ts")


class TestOnlineTenantPipeline(SimpleTestCase):
    @patch("apps.log_clustering.handlers.pipline_service.aiops_service_online.ClusteringOnlineService.get_instance")
    @patch("apps.log_clustering.handlers.pipline_service.aiops_service_online.get_online_clustering_config")
    @patch("apps.log_clustering.handlers.pipline_service.aiops_service_online.ClusteringConfig.get_by_index_set_id")
    def test_online_pipeline_uses_tenant_project_config(self, mock_get_config, mock_resolve, mock_service):
        mock_get_config.return_value = Mock(
            bk_biz_id=2,
            collector_config_id=None,
            collector_config_name_en="",
            source_rt_name="2_source",
            is_case_sensitive=0,
            max_log_length=1024,
            delimeter=" ",
            predefined_varibles="",
            max_dist_list="0.5",
            min_members=1,
            index_set_id=30,
            task_records=[],
            save=Mock(),
        )
        mock_resolve.return_value = {"project_id": 1001, "bk_biz_id": 2001}
        service = mock_service.return_value
        service.build_data_context.side_effect = lambda params: params
        service.build_pipeline.return_value.id = "pipeline-id"

        operator_aiops_service_online(30)

        params = service.build_data_context.call_args.args[0]
        self.assertEqual(params["project_id"], 1001)
        self.assertEqual(params["bk_biz_id"], 2001)
