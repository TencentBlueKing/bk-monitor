from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.tgpa.handlers.task import TGPATaskHandler


@override_settings(TIME_ZONE="Asia/Shanghai")
class TestTGPATaskDownloadFileName(SimpleTestCase):
    @patch.object(TGPATaskHandler, "get_task_page")
    def test_build_download_file_name(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [
                {
                    "file_name": "ENQ_file_3025221.zip",
                    "openid": "openid_1",
                    "created_by": "zhangsan",
                    "created_at": "2026-04-24 12:00:00",
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_3025221.zip")

        self.assertEqual(result, "task_openid_1_3025221_zhangsan_20260424120000.zip")
        mock_get_task_page.assert_called_once_with(
            {"bk_biz_id": 2, "task_id": "3025221", "pagesize": 1},
            need_format=False,
            add_process_info=False,
        )

    @patch.object(TGPATaskHandler, "get_task_page")
    def test_sanitize_file_name_parts_and_preserve_unicode(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [
                {
                    "file_name": "ENQ_file_1.zip",
                    "openid": "openid/with spaces\r\nvalue",
                    "created_by": "创建 人/creator",
                    "created_at": "2026-04-24 12:00:00",
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "task_openid_with spaces_value_1_创建 人_creator_20260424120000.zip")

    @patch.object(TGPATaskHandler, "get_task_page")
    def test_keep_report_file_name_without_querying_task(self, mock_get_task_page):
        result = TGPATaskHandler.get_download_file_name(2, "tgpatask_out_1.zip")

        self.assertEqual(result, "tgpatask_out_1.zip")
        mock_get_task_page.assert_not_called()

    @patch.object(TGPATaskHandler, "get_task_page", side_effect=RuntimeError("task api unavailable"))
    def test_fallback_when_task_query_fails(self, mock_get_task_page):
        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "ENQ_file_1.zip")
        mock_get_task_page.assert_called_once()

    @patch.object(TGPATaskHandler, "get_task_page")
    def test_fallback_when_openid_is_none(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [{"openid": None, "created_by": "zhangsan", "created_at": "2026-04-24 12:00:00"}],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "ENQ_file_1.zip")
