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

import datetime
import io
import tempfile
from contextlib import ExitStack
from unittest.mock import Mock, patch

from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.log_search.constants import ExportStatus, ExportType, IndexSetType
from apps.log_search.exceptions import AsyncExportTaskNotDownloadableException, ConcurrentExportLimitException
from apps.log_search.handlers.search.async_export_handlers import AsyncExportHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import AsyncTask, Scenario
from apps.log_search.tasks.async_export import (
    AsyncExportUtils,
    UnionAsyncExportUtils,
    error_async_export_tasks_turn_to_failed,
)
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


class TestAsyncTaskConcurrentLimit(TestCase):
    """测试 AsyncTask.check_running_count_by_user 限流逻辑"""

    def setUp(self):
        self.username = "test_user"
        self.other_username = "other_user"
        self.common_params = {
            "request_param": SEARCH_DICT,
            "index_set_id": 3,
            "bk_biz_id": 2,
            "start_time": SEARCH_DICT["start_time"],
            "end_time": SEARCH_DICT["end_time"],
            "export_type": ExportType.ASYNC,
        }

    def _create_running_task(self, created_by, scenario_id=None, export_status=ExportStatus.DOWNLOAD_LOG):
        return AsyncTask.objects.create(
            created_by=created_by,
            scenario_id=scenario_id,
            export_status=export_status,
            **self.common_params,
        )

    # ---- 非场景分组 ----

    def test_non_scene_under_limit_does_not_raise(self):
        """未达上限时不抛异常"""
        self._create_running_task(self.username, scenario_id=Scenario.LOG)
        # 不应抛异常
        AsyncTask.check_running_count_by_user(self.username)

    def test_non_scene_at_limit_raises(self):
        """达到上限时抛出 ConcurrentExportLimitException"""
        for i in range(3):
            self._create_running_task(self.username, scenario_id=Scenario.LOG)
        with self.assertRaises(ConcurrentExportLimitException):
            AsyncTask.check_running_count_by_user(self.username)

    def test_null_export_status_counts_as_running(self):
        """export_status 为 NULL 时也算正在运行"""
        self._create_running_task(self.username, scenario_id=Scenario.LOG, export_status=ExportStatus.DOWNLOAD_LOG)
        self._create_running_task(self.username, scenario_id=Scenario.LOG, export_status=ExportStatus.EXPORT_PACKAGE)
        # export_status=NULL
        AsyncTask.objects.create(
            created_by=self.username,
            scenario_id=Scenario.LOG,
            export_status=None,
            **self.common_params,
        )
        with self.assertRaises(ConcurrentExportLimitException):
            AsyncTask.check_running_count_by_user(self.username)

    def test_different_users_are_isolated(self):
        """不同用户的任务互不影响"""
        for i in range(3):
            self._create_running_task(self.other_username, scenario_id=Scenario.LOG)
        # other_user 已满，但 test_user 不受影响
        AsyncTask.check_running_count_by_user(self.username)

    # ---- 场景分组 ----

    def test_scene_under_limit_does_not_raise(self):
        """场景分组未达上限时不抛异常"""
        self._create_running_task(self.username, scenario_id="scene")
        AsyncTask.check_running_count_by_user(self.username, is_scene=True)

    def test_scene_at_limit_raises(self):
        """场景分组达到上限时抛出异常"""
        for i in range(3):
            self._create_running_task(self.username, scenario_id="scene")
        with self.assertRaises(ConcurrentExportLimitException):
            AsyncTask.check_running_count_by_user(self.username, is_scene=True)

    # ---- 分组隔离 ----

    def test_scene_and_non_scene_are_independent(self):
        """场景和非场景分组独立计数，互不影响"""
        # 非场景已满
        for i in range(3):
            self._create_running_task(self.username, scenario_id=Scenario.LOG)
        # 场景分组不受影响
        AsyncTask.check_running_count_by_user(self.username, is_scene=True)

        # 反过来：场景已满
        for i in range(3):
            self._create_running_task(self.other_username, scenario_id="scene")
        # 非场景不受影响
        AsyncTask.check_running_count_by_user(self.other_username)

    def test_scene_tasks_do_not_affect_non_scene_limit(self):
        """场景任务不计入非场景分组的限流"""
        for i in range(3):
            self._create_running_task(self.username, scenario_id="scene")
        # scene 任务不会让 non-scene 超限
        AsyncTask.check_running_count_by_user(self.username, is_scene=False)

    # ---- override_settings ----

    def test_override_settings_changes_limit(self):
        """override_settings 可以动态修改并发上限"""
        self._create_running_task(self.username, scenario_id=Scenario.LOG)
        with self.settings(MAX_CONCURRENT_EXPORT_TASKS=1):
            with self.assertRaises(ConcurrentExportLimitException):
                AsyncTask.check_running_count_by_user(self.username)


class TestFailStaleAsyncExportTasks(TestCase):
    def _create_task(self, export_status=None, export_type=ExportType.ASYNC):
        return AsyncTask.objects.create(
            request_param=SEARCH_DICT,
            scenario_id=Scenario.LOG,
            index_set_id=3,
            bk_biz_id=2,
            start_time=SEARCH_DICT["start_time"],
            end_time=SEARCH_DICT["end_time"],
            export_type=export_type,
            export_status=export_status,
            created_by="admin",
        )

    def test_error_async_export_tasks_turn_to_failed(self):
        expired_time = timezone.now() - datetime.timedelta(hours=25)
        stale_tasks = [
            self._create_task(export_status=None),
            self._create_task(export_status=ExportStatus.DOWNLOAD_LOG),
            self._create_task(export_status=ExportStatus.EXPORT_PACKAGE),
            self._create_task(export_status=ExportStatus.EXPORT_UPLOAD),
        ]
        AsyncTask.objects.filter(id__in=[task.id for task in stale_tasks]).update(created_at=expired_time)

        with patch("apps.log_search.tasks.async_export.logger.warning") as mock_warning:
            error_async_export_tasks_turn_to_failed.run()

        expected_logs = {(task.id, task.export_status) for task in stale_tasks}
        actual_logs = {(call.args[1], call.args[2]) for call in mock_warning.call_args_list}
        self.assertEqual(actual_logs, expected_logs)
        for task in stale_tasks:
            task.refresh_from_db()
            self.assertEqual(task.export_status, ExportStatus.FAILED)
            self.assertTrue(task.failed_reason)

    def test_keep_recent_terminal_and_sync_tasks(self):
        expired_time = timezone.now() - datetime.timedelta(hours=25)
        recent_task = self._create_task(export_status=ExportStatus.DOWNLOAD_LOG)
        terminal_tasks = [
            self._create_task(export_status=ExportStatus.SUCCESS),
            self._create_task(export_status=ExportStatus.FAILED),
            self._create_task(export_status=ExportStatus.DOWNLOAD_EXPIRED),
            self._create_task(export_status=ExportStatus.DATA_EXPIRED),
        ]
        sync_task = self._create_task(export_status=None, export_type=ExportType.SYNC)
        AsyncTask.objects.filter(id__in=[task.id for task in [*terminal_tasks, sync_task]]).update(
            created_at=expired_time
        )

        error_async_export_tasks_turn_to_failed.run()

        recent_task.refresh_from_db()
        self.assertEqual(recent_task.export_status, ExportStatus.DOWNLOAD_LOG)
        for task in terminal_tasks:
            original_status = task.export_status
            task.refresh_from_db()
            self.assertEqual(task.export_status, original_status)
        sync_task.refresh_from_db()
        self.assertIsNone(sync_task.export_status)

    def test_keep_task_whose_status_changes_during_scan(self):
        expired_time = timezone.now() - datetime.timedelta(hours=25)
        stale_task = self._create_task(export_status=ExportStatus.DOWNLOAD_LOG)
        AsyncTask.objects.filter(id=stale_task.id).update(created_at=expired_time)

        original_iterator = QuerySet.iterator

        def change_status_before_update(queryset, *args, **kwargs):
            for task in original_iterator(queryset, *args, **kwargs):
                AsyncTask.objects.filter(id=stale_task.id).update(export_status=ExportStatus.SUCCESS)
                yield task

        with (
            patch.object(QuerySet, "iterator", change_status_before_update),
            patch("apps.log_search.tasks.async_export.logger.warning") as mock_warning,
        ):
            error_async_export_tasks_turn_to_failed.run()

        stale_task.refresh_from_db()
        self.assertEqual(stale_task.export_status, ExportStatus.SUCCESS)
        mock_warning.assert_not_called()
