from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_clustering.handlers.data_access.data_access import DataAccessHandler


class TestDataAccessTenantParams(SimpleTestCase):
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

    @patch("apps.log_clustering.handlers.aiops.base.get_online_clustering_config")
    @patch.object(DataAccessHandler, "start_bkdata_clean")
    @patch.object(DataAccessHandler, "create_or_update_bkdata_etl")
    @patch("apps.log_clustering.handlers.data_access.data_access.ClusteringConfig.objects.get")
    def test_sync_bkdata_etl_uses_config_for_clustering_business(
        self, mock_get_config, mock_create_or_update, mock_start_clean, mock_resolve_config
    ):
        clustering_config = Mock(
            bk_biz_id=19078,
            bkdata_data_id=1596331,
            bkdata_etl_processing_id=None,
            save=Mock(),
        )
        mock_get_config.return_value = clustering_config
        mock_resolve_config.return_value = {"project_id": 1019, "bk_biz_id": 19078, "bk_username": "tenant_admin"}
        mock_create_or_update.return_value = {
            "processing_id": "19078_bklog_test",
            "result_table_id": "19078_bklog_test",
        }

        DataAccessHandler().sync_bkdata_etl(collector_config_id=3030)

        mock_resolve_config.assert_called_once_with(19078)
        mock_create_or_update.assert_called_once_with(
            3030,
            1596331,
            None,
            bk_biz_id=19078,
        )
        mock_start_clean.assert_called_once_with("19078_bklog_test", bk_biz_id=19078, from_tail=True)
        clustering_config.save.assert_called_once()

    @patch("apps.log_clustering.handlers.data_access.data_access.BkDataDatabusApi.post_tasks")
    def test_start_bkdata_clean_passes_business_and_conf_username(self, mock_post_tasks):
        handler = DataAccessHandler()
        handler.conf = {"bk_username": "tenant_admin"}

        handler.start_bkdata_clean("19078_bklog_test", bk_biz_id=19078, from_tail=True)

        params = mock_post_tasks.call_args.kwargs["params"]
        self.assertEqual(params["result_table_id"], "19078_bklog_test")
        self.assertEqual(params["bk_biz_id"], 19078)
        self.assertEqual(params["bk_username"], "tenant_admin")
        self.assertEqual(params["operator"], "tenant_admin")
        self.assertTrue(params["no_request"])
        self.assertEqual(params["consume_position"], "tail")
