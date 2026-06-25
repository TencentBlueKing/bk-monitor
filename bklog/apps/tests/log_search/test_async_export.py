"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import io
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import ExportStatus, ExportType, IndexSetType
from apps.log_search.handlers.search.async_export_handlers import AsyncExportHandlers
from apps.log_search.models import AsyncTask, Scenario
from apps.log_search.tasks.async_export import AsyncExportUtils


SEARCH_DICT = {
    "bk_biz_id": 2,
    "start_time": "2026-06-25 00:00:00",
    "end_time": "2026-06-25 01:00:00",
    "size": 321,
}


class FakeIndexSet:
    max_async_count = 0


class FakeSearchHandler:
    scenario_id = Scenario.LOG
    index_set = FakeIndexSet()
    size = SEARCH_DICT["size"]

    def __init__(self, index_set_id, search_dict, export_fields=None, export_log=False):
        self.index_set_id = index_set_id
        self.search_dict = search_dict
        self.export_fields = export_fields
        self.export_log = export_log

    def fields(self):
        return {
            "config": [
                {
                    "name": "async_export",
                    "is_active": True,
                    "extra": {"fields": [{"field_name": "dtEventTimeStamp"}]},
                }
            ]
        }

    def _get_user_sorted_list(self, async_export_fields):
        return async_export_fields

    def pre_get_result(self, sorted_fields, size):
        return {"_shards": {"total": 1, "successful": 1, "failures": []}}


class TestAsyncExportProgress(TestCase):
    def test_async_export_creates_task_with_export_total_count(self):
        with (
            patch(
                "apps.log_search.handlers.search.async_export_handlers.SearchHandler",
                FakeSearchHandler,
            ),
            patch("apps.log_search.handlers.search.async_export_handlers.async_export.delay") as mock_delay,
            patch.object(AsyncExportHandlers, "_get_url", return_value="/download/"),
            patch.object(AsyncExportHandlers, "_get_search_url", return_value="/search/"),
            patch("apps.log_search.handlers.search.async_export_handlers.get_request_username", return_value="admin"),
            patch(
                "apps.log_search.handlers.search.async_export_handlers.get_request_external_username", return_value=""
            ),
            patch(
                "apps.log_search.handlers.search.async_export_handlers.get_request_language_code",
                return_value="zh-hans",
            ),
            patch(
                "apps.log_search.handlers.search.async_export_handlers.get_request_external_user_email", return_value=""
            ),
        ):
            task_id, total_count = AsyncExportHandlers(
                index_set_id=3,
                bk_biz_id=2,
                search_dict=SEARCH_DICT,
            ).async_export()

        async_task = AsyncTask.objects.get(id=task_id)
        self.assertEqual(total_count, SEARCH_DICT["size"])
        self.assertEqual(async_task.export_total_count, SEARCH_DICT["size"])
        self.assertEqual(async_task.exported_count, 0)
        self.assertEqual(async_task.download_count, 0)
        self.assertEqual(mock_delay.call_args.kwargs["async_task_id"], task_id)

    def test_generate_export_history_returns_progress_fields(self):
        history = {
            "id": 1,
            "request_param": SEARCH_DICT,
            "start_time": SEARCH_DICT["start_time"],
            "end_time": SEARCH_DICT["end_time"],
            "export_type": ExportType.ASYNC,
            "export_status": ExportStatus.SUCCESS,
            "failed_reason": "",
            "download_url": "https://example.com/download",
            "file_name": "export.tar.gz",
            "file_size": 1.23,
            "created_at": "2026-06-25 01:00:00",
            "created_by": "admin",
            "completed_at": "2026-06-25 01:10:00",
            "exported_count": 88,
            "export_total_count": 100,
            "download_count": 2,
            "index_set_type": IndexSetType.SINGLE.value,
            "index_set_id": 3,
            "index_set_ids": [],
        }

        result = AsyncExportHandlers.generate_export_history(history, index_set_retention={})

        self.assertEqual(result["exported_count"], 88)
        self.assertEqual(result["export_total_count"], 100)
        self.assertEqual(result["download_count"], 2)
        self.assertTrue(result["download_able"])

    def test_write_file_increments_exported_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            export_total_count=5,
            created_by="admin",
        )
        export_util = AsyncExportUtils.__new__(AsyncExportUtils)
        export_util.async_task_id = async_task.id

        export_util.write_file(
            io.StringIO(),
            [
                {"origin_log_list": [{"log": "one"}, {"log": "two"}]},
                {"origin_log_list": [{"log": "three"}]},
            ],
        )

        async_task.refresh_from_db()
        self.assertEqual(async_task.exported_count, 3)

    def test_write_file_does_not_update_progress_without_task_id(self):
        export_util = AsyncExportUtils.__new__(AsyncExportUtils)
        export_util.async_task_id = None

        with patch("apps.log_search.tasks.async_export.AsyncTask.objects.filter") as mock_filter:
            export_util.write_file(io.StringIO(), [{"origin_log_list": [{"log": "one"}]}])

        mock_filter.assert_not_called()
