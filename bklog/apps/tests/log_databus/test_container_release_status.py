"""容器采集配置删除状态回归测试。"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.constants import ContainerCollectStatus
from apps.log_databus.tasks.collector import delete_container_release


class DeleteContainerReleaseStatusTests(SimpleTestCase):
    @patch("apps.log_databus.tasks.collector.ContainerCollectorConfig.objects.get")
    @patch("apps.log_databus.tasks.collector.Bcs")
    def test_delete_failure_is_reported_as_failed(self, mock_bcs, mock_get_config):
        mock_bcs.return_value.delete_bklog_config.side_effect = RuntimeError("delete failed")
        container_config = MagicMock()
        mock_get_config.return_value = container_config

        delete_container_release.run("BCS-K8S-00000", 31, "collector-31", delete_config=True)

        self.assertEqual(container_config.status, ContainerCollectStatus.FAILED.value)
        self.assertIn("delete failed", str(container_config.status_detail))
        container_config.delete.assert_not_called()
        container_config.save.assert_called_once_with(update_fields=["status", "status_detail"])

    @patch("apps.log_databus.tasks.collector.ContainerCollectorConfig.objects.get")
    @patch("apps.log_databus.tasks.collector.Bcs")
    def test_delete_success_sets_terminated_with_fresh_detail(self, mock_bcs, mock_get_config):
        container_config = MagicMock()
        mock_get_config.return_value = container_config

        delete_container_release.run("BCS-K8S-00000", 31, "collector-31")

        mock_bcs.return_value.delete_bklog_config.assert_called_once_with("collector-31")
        self.assertEqual(container_config.status, ContainerCollectStatus.TERMINATED.value)
        self.assertEqual(str(container_config.status_detail), "配置已停用")
        container_config.save.assert_called_once_with(update_fields=["status", "status_detail"])
