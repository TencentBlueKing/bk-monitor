import logging
from unittest import mock
from django.test import TestCase
from metadata.models.space import Space
from metadata.task.sync_space import sync_bcs_space

logger = logging.getLogger("metadata")


class SyncBcsSpaceTestCase(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        # 清空所有测试数据，确保测试环境干净
        Space.objects.all().delete()

    @mock.patch("metadata.task.sync_space.get_valid_bcs_projects")
    @mock.patch("metadata.task.sync_space.create_bcs_spaces")
    @mock.patch("metadata.task.sync_space.metrics")
    def test_sync_bcs_space(self, mock_metrics, mock_create_spaces, mock_get_projects):
        # 场景1: 没有需要更新或新增的项目
        with self.subTest("no projects need update or create"):
            # 准备测试数据
            mock_get_projects.return_value = [
                {"project_code": "p1", "project_id": "pid1", "name": "项目1"},
                {"project_code": "p2", "project_id": "pid2", "name": "项目2"},
            ]

            # 创建已存在的空间记录
            Space.objects.create(space_type_id="bkci", space_id="p1", space_code="pid1", space_name="项目1")
            Space.objects.create(space_type_id="bkci", space_id="p2", space_code="pid2", space_name="项目2")

            sync_bcs_space()

            # 验证没有调用创建方法
            mock_create_spaces.assert_not_called()
            # 验证指标上报
            mock_metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.assert_called()
            # 当没有需要更新或新增的项目时，函数会提前返回，不会上报耗时指标
            mock_metrics.METADATA_CRON_TASK_COST_SECONDS.labels.assert_not_called()

        # 场景2: 有需要更新的项目
        with self.subTest("has projects need update"):
            # 重置mock
            mock_metrics.reset_mock()
            mock_create_spaces.reset_mock()

            # 准备测试数据
            mock_get_projects.return_value = [
                {"project_code": "p1_update", "project_id": "pid1", "name": "新项目名"},
                {"project_code": "p2", "project_id": "pid2", "name": "项目2"},
            ]

            # 创建需要更新的空间记录(使用不同的ID避免冲突)
            Space.objects.create(space_type_id="bkci", space_id="p1_update", space_code="", space_name="旧名称")

            sync_bcs_space()

            # 验证空间更新
            updated_space = Space.objects.get(space_id="p1_update")
            self.assertEqual(updated_space.space_code, "pid1")
            self.assertEqual(updated_space.space_name, "新项目名")
            self.assertTrue(updated_space.is_bcs_valid)

            # 验证指标上报
            mock_metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.assert_called()
            mock_metrics.METADATA_CRON_TASK_COST_SECONDS.labels.assert_called()

        # 场景3: 有需要新增的项目
        with self.subTest("has projects need create"):
            # 重置mock
            mock_metrics.reset_mock()
            mock_create_spaces.reset_mock()

            # 准备测试数据
            new_project = {"project_code": "p3", "project_id": "pid3", "name": "项目3"}
            mock_get_projects.return_value = [new_project]

            sync_bcs_space()

            # 验证创建方法被调用
            mock_create_spaces.assert_called_once_with([new_project])

            # 验证指标上报
            mock_metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.assert_called()
            mock_metrics.METADATA_CRON_TASK_COST_SECONDS.labels.assert_called()

        # 场景4: 创建项目时抛出异常
        with self.subTest("create projects with exception"):
            # 重置mock
            mock_metrics.reset_mock()
            mock_create_spaces.reset_mock()

            # 准备测试数据
            mock_get_projects.return_value = [{"project_code": "p4", "project_id": "pid4", "name": "项目4"}]
            mock_create_spaces.side_effect = Exception("test error")

            with self.assertLogs(logger, level="ERROR") as log_context:
                sync_bcs_space()

            # 验证异常日志
            self.assertIn("create bcs project space error", log_context.output[0])
            mock_create_spaces.assert_called_once()

            # 验证指标上报
            mock_metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.assert_called()
            mock_metrics.METADATA_CRON_TASK_COST_SECONDS.labels.assert_called()
