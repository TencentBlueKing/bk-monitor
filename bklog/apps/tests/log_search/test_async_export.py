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
import tempfile
from contextlib import ExitStack
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.log_search.constants import ExportStatus, ExportType, IndexSetType
from apps.log_search.exceptions import AsyncExportTaskNotDownloadableException
from apps.log_search.handlers.search.async_export_handlers import AsyncExportHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import AsyncTask, Scenario
from apps.log_search.tasks.async_export import AsyncExportUtils, UnionAsyncExportUtils
from apps.log_search.tasks.unify_query_async_export import BaseExportUtils as UnifyQueryBaseExportUtils
from apps.log_search.views.search_views import SearchViewSet
from apps.log_unifyquery.handler.async_export_handlers import (
    UnifyQueryAsyncExportHandlers,
    UnifyQueryUnionAsyncExportHandlers,
)


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
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "apps.log_search.handlers.search.async_export_handlers.SearchHandler",
                    FakeSearchHandler,
                )
            )
            mock_delay = stack.enter_context(
                patch("apps.log_search.handlers.search.async_export_handlers.async_export.delay")
            )
            stack.enter_context(patch.object(AsyncExportHandlers, "_get_url", return_value="/download/"))
            stack.enter_context(patch.object(AsyncExportHandlers, "_get_search_url", return_value="/search/"))
            stack.enter_context(
                patch(
                    "apps.log_search.handlers.search.async_export_handlers.get_request_username",
                    return_value="admin",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_search.handlers.search.async_export_handlers.get_request_external_username",
                    return_value="",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_search.handlers.search.async_export_handlers.get_request_language_code",
                    return_value="zh-hans",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_search.handlers.search.async_export_handlers.get_request_external_user_email",
                    return_value="",
                )
            )
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

    def test_download_file_increments_download_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.SUCCESS,
            download_url="https://example.com/export.tar.gz",
            download_count=2,
            source_app_code="bk_log_search",
            created_by="admin",
        )
        request = APIRequestFactory().get("/api/v1/search/index_set/async_export/download_file/")
        view = SearchViewSet()
        view.request = request

        with (
            patch.object(
                SearchViewSet,
                "params_valid",
                return_value={"task_id": async_task.id, "bk_biz_id": async_task.bk_biz_id},
            ),
            patch("apps.log_search.views.search_views.get_request_app_code", return_value="bk_log_search"),
            patch("apps.log_search.views.search_views.get_request_external_username", return_value=""),
        ):
            response = view.async_export_download_file(request)

        async_task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, async_task.download_url)
        self.assertEqual(async_task.download_count, 3)

    def test_download_file_not_downloadable_does_not_increment_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.FAILED,
            download_url="https://example.com/export.tar.gz",
            download_count=2,
            source_app_code="bk_log_search",
            created_by="admin",
        )
        request = APIRequestFactory().get("/api/v1/search/index_set/async_export/download_file/")
        view = SearchViewSet()
        view.request = request

        with (
            patch.object(
                SearchViewSet,
                "params_valid",
                return_value={"task_id": async_task.id, "bk_biz_id": async_task.bk_biz_id},
            ),
            patch("apps.log_search.views.search_views.get_request_app_code", return_value="bk_log_search"),
            patch("apps.log_search.views.search_views.get_request_external_username", return_value=""),
        ):
            with self.assertRaises(AsyncExportTaskNotDownloadableException):
                view.async_export_download_file(request)

        async_task.refresh_from_db()
        self.assertEqual(async_task.download_count, 2)

    def test_union_write_file_increments_exported_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            created_by="admin",
        )
        export_util = UnionAsyncExportUtils.__new__(UnionAsyncExportUtils)
        export_util.async_task_id = async_task.id

        export_util.write_file(io.StringIO(), [{"origin_log_list": [{"log": "one"}, {"log": "two"}]}])

        async_task.refresh_from_db()
        self.assertEqual(async_task.exported_count, 2)

    def test_unify_query_write_file_increments_exported_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            created_by="admin",
        )
        export_util = UnifyQueryBaseExportUtils.__new__(UnifyQueryBaseExportUtils)
        export_util.async_task_id = async_task.id

        export_util.write_file(io.StringIO(), [{"origin_log_list": [{"log": "one"}, {"log": "two"}]}])

        async_task.refresh_from_db()
        self.assertEqual(async_task.exported_count, 2)

    def test_slice_data_increments_exported_count(self):
        async_task = AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=ExportType.ASYNC,
            created_by="admin",
        )
        search_handler = SearchHandler.__new__(SearchHandler)
        search_handler.storage_cluster_id = 1
        search_handler.slice_pre_get_result = Mock(return_value={"hits": {"hits": [{"log": "one"}]}})
        search_handler.sliced_scroll_result = Mock(
            return_value=[{"hits": {"hits": [{"log": "two"}, {"log": "three"}]}}]
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.ASYNC_DIR",
                tmpdir,
            ),
        ):
            search_handler.get_slice_data(
                slice_id=0,
                slice_max=1,
                file_name="export",
                export_file_type="txt",
                async_task_id=async_task.id,
            )

        async_task.refresh_from_db()
        self.assertEqual(async_task.exported_count, 3)

    def test_unify_query_export_history_returns_progress_fields(self):
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
            "exported_count": 20,
            "export_total_count": 50,
            "download_count": 4,
            "index_set_type": IndexSetType.SINGLE.value,
            "index_set_id": 3,
            "index_set_ids": [],
        }

        result = UnifyQueryAsyncExportHandlers.generate_export_history(history, index_set_retention={})

        self.assertEqual(result["exported_count"], 20)
        self.assertEqual(result["export_total_count"], 50)
        self.assertEqual(result["download_count"], 4)

    def test_unify_query_union_export_total_count_uses_union_limit(self):
        handler = UnifyQueryUnionAsyncExportHandlers.__new__(UnifyQueryUnionAsyncExportHandlers)
        handler.bk_biz_id = 2
        handler.unify_query_handler = Mock(
            index_info_list=[
                {"index_set_obj": Mock(max_async_count=10)},
                {"index_set_obj": Mock(max_async_count=20)},
            ]
        )

        with (
            patch(
                "apps.log_unifyquery.handler.async_export_handlers.FeatureToggleObject.switch",
                return_value=False,
            ),
            patch("apps.log_unifyquery.handler.async_export_handlers.MAX_ASYNC_COUNT", 10),
        ):
            total_count = handler.get_union_export_total_count(request_size=100)

        self.assertEqual(total_count, 30)
