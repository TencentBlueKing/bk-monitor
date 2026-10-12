"""容器采集配置下发/删除状态回归测试。"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.constants import RETRY_TIMES, WAIT_FOR_RETRY, ContainerCollectStatus
from apps.log_databus.models import ContainerCollectorConfig
from apps.log_databus.tasks.collector import create_container_release, delete_container_release


class CreateContainerReleaseStatusTests(SimpleTestCase):
    @patch("apps.log_databus.tasks.collector.time.sleep")
    @patch("apps.log_databus.tasks.collector.ContainerCollectorConfig.objects.get")
    @patch("apps.log_databus.tasks.collector.Bcs")
    def test_missing_config_retries_without_attribute_error(self, mock_bcs, mock_get_config, mock_sleep):
        mock_get_config.side_effect = ContainerCollectorConfig.DoesNotExist

        create_container_release.run("BCS-K8S-00000", 5070, "collector-5070", {"foo": "bar"})

        self.assertEqual(mock_get_config.call_count, RETRY_TIMES)
        mock_sleep.assert_called_with(WAIT_FOR_RETRY)
        self.assertEqual(mock_sleep.call_count, RETRY_TIMES)
        mock_bcs.return_value.save_bklog_config.assert_not_called()

    @patch("apps.log_databus.tasks.collector.time.sleep")
    @patch("apps.log_databus.tasks.collector.ContainerCollectorConfig.objects.get")
    @patch("apps.log_databus.tasks.collector.Bcs")
    def test_retries_until_config_is_visible_then_succeeds(self, mock_bcs, mock_get_config, mock_sleep):
        container_config = MagicMock()
        mock_get_config.side_effect = [ContainerCollectorConfig.DoesNotExist(), container_config]

        create_container_release.run("BCS-K8S-00000", 5070, "collector-5070", {"foo": "bar"})

        mock_sleep.assert_called_once_with(WAIT_FOR_RETRY)
        mock_bcs.return_value.save_bklog_config.assert_called_once()
        self.assertEqual(container_config.status, ContainerCollectStatus.SUCCESS.value)
        self.assertEqual(str(container_config.status_detail), "配置下发成功")

    @patch("apps.log_databus.tasks.collector.ContainerCollectorConfig.objects.get")
    @patch("apps.log_databus.tasks.collector.Bcs")
    def test_save_failure_is_reported_as_failed(self, mock_bcs, mock_get_config):
        mock_bcs.return_value.save_bklog_config.side_effect = RuntimeError("save failed")
        container_config = MagicMock()
        mock_get_config.return_value = container_config

        create_container_release.run("BCS-K8S-00000", 5070, "collector-5070", {"foo": "bar"})

        self.assertEqual(container_config.status, ContainerCollectStatus.FAILED.value)
        self.assertIn("save failed", str(container_config.status_detail))
        self.assertEqual(container_config.save.call_count, 2)
        container_config.save.assert_called_with(update_fields=["status", "status_detail"])


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
