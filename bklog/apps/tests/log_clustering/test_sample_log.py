from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import InstanceActionPermission
from apps.log_clustering.exceptions import ClusteringAccessNotSupportedException
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.views.clustering_config_views import ClusteringConfigViewSet

TEST_INDEX_SET_ID = 1001
TEST_COLLECTOR_CONFIG_ID = 88
TEST_FALLBACK_COLLECTOR_CONFIG_ID = 99
SAMPLE_RESULT = [{"etl": {"data": "raw log from kafka tail"}}]


class TestClusteringConfigSampleLog(SimpleTestCase):
    """聚类调试抽样必须复用 CollectorHandler.tail，并按索引集反查采集项"""

    @patch("apps.log_databus.handlers.collector.CollectorHandler.get_instance")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_sample_log_reuses_collector_handler_tail(self, mock_get_config, mock_get_instance):
        mock_get_config.return_value = Mock(collector_config_id=TEST_COLLECTOR_CONFIG_ID)
        mock_handler = Mock()
        mock_handler.tail.return_value = SAMPLE_RESULT
        mock_get_instance.return_value = mock_handler

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).sample_log()

        mock_get_instance.assert_called_once_with(TEST_COLLECTOR_CONFIG_ID)
        mock_handler.tail.assert_called_once_with()
        self.assertEqual(result, SAMPLE_RESULT)

    @patch("apps.log_clustering.handlers.clustering_config.LogIndexSet.objects.filter")
    @patch("apps.log_databus.handlers.collector.CollectorHandler.get_instance")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_sample_log_falls_back_to_index_set_collector(self, mock_get_config, mock_get_instance, mock_filter):
        mock_get_config.return_value = Mock(collector_config_id=None)
        mock_filter.return_value.first.return_value = Mock(collector_config_id=TEST_FALLBACK_COLLECTOR_CONFIG_ID)
        mock_handler = Mock()
        mock_handler.tail.return_value = SAMPLE_RESULT
        mock_get_instance.return_value = mock_handler

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).sample_log()

        mock_filter.assert_called_once_with(index_set_id=TEST_INDEX_SET_ID)
        mock_get_instance.assert_called_once_with(TEST_FALLBACK_COLLECTOR_CONFIG_ID)
        self.assertEqual(result, SAMPLE_RESULT)

    @patch("apps.log_clustering.handlers.clustering_config.LogIndexSet.objects.filter")
    @patch("apps.log_databus.handlers.collector.CollectorHandler.get_instance")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_sample_log_rejects_index_set_without_collector(self, mock_get_config, mock_get_instance, mock_filter):
        mock_get_config.return_value = Mock(collector_config_id=None)
        mock_filter.return_value.first.return_value = Mock(collector_config_id=None)

        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).sample_log()

        mock_get_instance.assert_not_called()

    @patch("apps.log_clustering.handlers.clustering_config.LogIndexSet.objects.filter")
    @patch("apps.log_databus.handlers.collector.CollectorHandler.get_instance")
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_sample_log_rejects_missing_index_set(self, mock_get_config, mock_get_instance, mock_filter):
        mock_get_config.return_value = Mock(collector_config_id=None)
        mock_filter.return_value.first.return_value = None

        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).sample_log()

        mock_get_instance.assert_not_called()

    def test_sample_log_rejects_when_index_set_id_missing(self):
        with self.assertRaises(ClusteringAccessNotSupportedException):
            ClusteringConfigHandler().sample_log()


class TestClusteringConfigSampleLogViewPermissions(SimpleTestCase):
    """抽样接口不得进 open_actions，必须走索引集 SEARCH_LOG"""

    def test_sample_log_is_not_open_action(self):
        self.assertNotIn("sample_log", ClusteringConfigViewSet.open_actions)

    def test_sample_log_requires_search_log_on_indices(self):
        view = ClusteringConfigViewSet()
        view.action = "sample_log"

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.SEARCH_LOG])
        self.assertEqual(permissions[0].resource_meta, ResourceEnum.INDICES)

    @patch("apps.log_clustering.views.clustering_config_views.ClusteringConfigHandler")
    def test_sample_log_view_delegates_to_handler(self, mock_handler_cls):
        mock_handler_cls.return_value.sample_log.return_value = SAMPLE_RESULT
        view = ClusteringConfigViewSet()

        response = view.sample_log(request=Mock(), index_set_id=TEST_INDEX_SET_ID)

        mock_handler_cls.assert_called_once_with(index_set_id=TEST_INDEX_SET_ID)
        mock_handler_cls.return_value.sample_log.assert_called_once_with()
        self.assertEqual(response.data, SAMPLE_RESULT)
