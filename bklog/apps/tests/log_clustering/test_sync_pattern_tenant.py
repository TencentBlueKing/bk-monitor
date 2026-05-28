from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_clustering.tasks.sync_pattern import sync, sync_pattern


class TestSyncPatternTenant(SimpleTestCase):
    @patch("apps.log_clustering.tasks.sync_pattern.sync.delay")
    @patch("apps.log_clustering.tasks.sync_pattern.LogIndexSet.objects.filter")
    @patch("apps.log_clustering.tasks.sync_pattern.ClusteringConfig.objects.filter")
    def test_same_model_from_two_businesses_schedules_two_tenant_calls(self, mock_configs, mock_index_sets, mock_delay):
        mock_configs.return_value.values.return_value = [
            {"model_id": "model_1", "model_output_rt": "", "index_set_id": 1, "bk_biz_id": 2},
            {"model_id": "model_1", "model_output_rt": "", "index_set_id": 2, "bk_biz_id": 3},
        ]
        mock_index_sets.return_value.values_list.return_value = [1, 2]

        sync_pattern()

        self.assertEqual(mock_delay.call_count, 2)
        mock_delay.assert_any_call(model_id="model_1", bk_biz_id=2)
        mock_delay.assert_any_call(model_id="model_1", bk_biz_id=3)


class TestSyncModelFileTenant(SimpleTestCase):
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.bulk_update")
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsSignatureAndPattern.objects.bulk_create")
    @patch("apps.log_clustering.tasks.sync_pattern.make_signature_objects", return_value=([], []))
    @patch("apps.log_clustering.tasks.sync_pattern.get_pattern", return_value=[])
    @patch("apps.log_clustering.tasks.sync_pattern.AiopsModelHandler")
    def test_sync_model_file_constructs_handler_with_business_context(
        self, mock_handler_cls, mock_get_pattern, mock_make_objects, mock_bulk_create, mock_bulk_update
    ):
        handler = mock_handler_cls.return_value
        handler.get_latest_released_id.return_value = "release_1"
        handler.aiops_release_model_release_id_model_file.return_value = {"file_content": "content"}
        mock_handler_cls.pickle_decode.return_value = []

        sync(model_id="model_1", bk_biz_id=2)

        mock_handler_cls.assert_called_once_with()
        handler.get_latest_released_id.assert_called_once_with(model_id="model_1", bk_biz_id=2)
        handler.aiops_release_model_release_id_model_file.assert_called_once_with(
            model_id="model_1", model_release_id="release_1", bk_biz_id=2
        )
