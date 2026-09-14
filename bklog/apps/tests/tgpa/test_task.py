from datetime import datetime, timezone
from unittest.mock import Mock, patch

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
                    "created_at": "2026-04-24 12:00:00",
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_3025221.zip")

        self.assertEqual(result, "ENQ_file_3025221_openid_1_20260424120000.zip")
        mock_get_task_page.assert_called_once_with(
            {"bk_biz_id": 2, "task_id": "3025221", "page": 1, "pagesize": 1},
            need_format=False,
            add_process_info=False,
        )

    @patch.object(TGPATaskHandler, "get_task_page")
    def test_convert_aware_create_time_to_configured_timezone(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [
                {
                    "file_name": "ENQ_file_1.zip",
                    "openid": "openid",
                    "created_at": datetime(2026, 4, 24, 4, tzinfo=timezone.utc),
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "ENQ_file_1_openid_20260424120000.zip")

    @patch.object(TGPATaskHandler, "get_task_page")
    def test_sanitize_openid(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [
                {
                    "file_name": "ENQ_file_1.zip",
                    "openid": 'openid/with spaces\r\n"',
                    "created_at": "2026-04-24 12:00:00",
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "ENQ_file_1_openid_with_spaces_20260424120000.zip")

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
    def test_fallback_when_task_file_does_not_match(self, mock_get_task_page):
        mock_get_task_page.return_value = {
            "total": 1,
            "list": [
                {
                    "file_name": "ENQ_file_2.zip",
                    "openid": "openid",
                    "created_at": "2026-04-24 12:00:00",
                }
            ],
        }

        result = TGPATaskHandler.get_download_file_name(2, "ENQ_file_1.zip")

        self.assertEqual(result, "ENQ_file_1.zip")


class TestTGPATaskStreamDownloadFile(SimpleTestCase):
    @patch("apps.tgpa.handlers.task.get_decrypt_handler", return_value=None)
    @patch.object(TGPATaskHandler, "get_download_file_name", return_value="renamed.zip")
    @patch("apps.tgpa.handlers.task.TGPAFileHandler")
    @patch("apps.tgpa.handlers.task.FeatureToggleObject.toggle")
    def test_direct_stream_uses_generated_download_file_name(
        self, mock_toggle, mock_file_handler, mock_get_download_file_name, mock_get_decrypt_handler
    ):
        mock_toggle.return_value.feature_config = {}
        mock_file_handler.get_file_info.return_value = {"content_length": 10}
        file_stream = Mock()
        mock_file_handler.get_file_stream.return_value = file_stream

        result = TGPATaskHandler.stream_download_file(2, "ENQ_file_1.zip")

        self.assertEqual(result, (file_stream, "renamed.zip", 10))
        mock_get_download_file_name.assert_called_once_with(2, "ENQ_file_1.zip")
        mock_get_decrypt_handler.assert_called_once_with(2)

    @patch("apps.tgpa.handlers.task.os.path.getsize", return_value=20)
    @patch("apps.tgpa.handlers.task.get_decrypt_handler", return_value=Mock())
    @patch.object(TGPATaskHandler, "get_download_file_name", return_value="renamed.zip")
    @patch("apps.tgpa.handlers.task.TGPAFileHandler")
    @patch("apps.tgpa.handlers.task.FeatureToggleObject.toggle")
    def test_repacked_stream_uses_generated_download_file_name(
        self,
        mock_toggle,
        mock_file_handler,
        mock_get_download_file_name,
        mock_get_decrypt_handler,
        mock_getsize,
    ):
        mock_toggle.return_value.feature_config = {}
        mock_file_handler.get_file_info.return_value = {"content_length": 10}
        mock_file_handler.return_value.download_and_repack_file.return_value = "/tmp/ENQ_file_1.zip"

        _, file_name, file_size = TGPATaskHandler.stream_download_file(2, "ENQ_file_1.zip")

        self.assertEqual(file_name, "renamed.zip")
        self.assertEqual(file_size, 20)
        mock_get_download_file_name.assert_called_once_with(2, "ENQ_file_1.zip")
        mock_get_decrypt_handler.assert_called_once_with(2)
        mock_getsize.assert_called_once_with("/tmp/ENQ_file_1.zip")
