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
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier, Lock
from unittest.mock import Mock, patch

from django.db import close_old_connections, connections
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.translation import gettext
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIRequestFactory

from apps.log_search.constants import ASYNC_EXPORT_SCENE_ID, ExportStatus, ExportType, IndexSetType
from apps.log_search.exceptions import (
    AsyncExportRequestBusyException,
    AsyncExportTaskNotDownloadableException,
    ConcurrentExportLimitException,
)
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
from apps.log_unifyquery.handler.scene_async_export import SceneAsyncExportHandler


SEARCH_DICT = {
    "bk_biz_id": 2,
    "start_time": "2026-06-25 00:00:00",
    "end_time": "2026-06-25 01:00:00",
    "size": 321,
}

TEST_MAX_CONCURRENT_EXPORT_TASKS = 3


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


class BarrierRedisLock:
    """使用同步屏障和线程锁模拟多个请求同时竞争同一个 Redis 锁。"""

    def __init__(self, shared_lock, acquire_barrier, blocking_timeout):
        self.shared_lock = shared_lock
        self.acquire_barrier = acquire_barrier
        self.blocking_timeout = blocking_timeout

    def acquire(self):
        self.acquire_barrier.wait(timeout=5)
        return self.shared_lock.acquire(timeout=self.blocking_timeout)

    def release(self):
        self.shared_lock.release()


class BarrierRedisCache:
    """为并发测试按 Redis key 提供共享的功能型假锁。"""

    def __init__(self, request_count):
        self.acquire_barrier = Barrier(request_count)
        self.locks_by_key = {}
        self.lock_keys = []
        self.lock_timeouts = []
        self.lock_registry_guard = Lock()

    def lock(self, lock_key, timeout, blocking_timeout):
        with self.lock_registry_guard:
            self.lock_keys.append(lock_key)
            self.lock_timeouts.append(timeout)
            shared_lock = self.locks_by_key.setdefault(lock_key, Lock())
        return BarrierRedisLock(shared_lock, self.acquire_barrier, blocking_timeout)


class TestAsyncExportProgress(TestCase):
    @override_settings(USE_REDIS=True)
    def test_async_export_creates_task_with_export_total_count(self):
        with ExitStack() as stack:
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            stack.enter_context(patch("apps.log_search.models.cache.lock", return_value=mock_lock))
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
        mock_lock.acquire.assert_called_once_with()
        mock_lock.release.assert_called_once_with()

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


class TestAsyncExportConcurrentCheckOrder(TestCase):
    def test_unify_query_handlers_check_concurrent_limit_first(self):
        for handler_class in (UnifyQueryAsyncExportHandlers, UnifyQueryUnionAsyncExportHandlers):
            with self.subTest(handler_class=handler_class.__name__):
                handler = handler_class.__new__(handler_class)
                handler.request_user = "test_user"

                with (
                    patch.object(
                        AsyncTask,
                        "check_running_count_by_user",
                        side_effect=ConcurrentExportLimitException(),
                    ) as mock_check_running_count,
                    patch(
                        "apps.log_unifyquery.handler.async_export_handlers.FeatureToggleObject.switch"
                    ) as mock_duplicate_check,
                ):
                    with self.assertRaises(ConcurrentExportLimitException):
                        handler.async_export()

                mock_check_running_count.assert_called_once_with("test_user")
                mock_duplicate_check.assert_not_called()

    def test_scene_handler_checks_concurrent_limit_first(self):
        handler = SceneAsyncExportHandler.__new__(SceneAsyncExportHandler)
        handler.request_user = "test_user"

        with (
            patch.object(
                AsyncTask,
                "check_running_count_by_user",
                side_effect=ConcurrentExportLimitException(),
            ) as mock_check_running_count,
            patch("apps.log_unifyquery.handler.scene_async_export.FeatureToggleObject.switch") as mock_duplicate_check,
        ):
            with self.assertRaises(ConcurrentExportLimitException):
                handler.async_export()

        mock_check_running_count.assert_called_once_with("test_user", is_scene=True)
        mock_duplicate_check.assert_not_called()


@override_settings(MAX_CONCURRENT_EXPORT_TASKS=TEST_MAX_CONCURRENT_EXPORT_TASKS)
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
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
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
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
            self._create_running_task(self.other_username, scenario_id=Scenario.LOG)
        # other_user 已满，但 test_user 不受影响
        AsyncTask.check_running_count_by_user(self.username)

    # ---- 场景分组 ----

    def test_scene_under_limit_does_not_raise(self):
        """场景分组未达上限时不抛异常"""
        self._create_running_task(self.username, scenario_id=ASYNC_EXPORT_SCENE_ID)
        AsyncTask.check_running_count_by_user(self.username, is_scene=True)

    def test_scene_at_limit_raises(self):
        """场景分组达到上限时抛出异常"""
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
            self._create_running_task(self.username, scenario_id=ASYNC_EXPORT_SCENE_ID)
        with self.assertRaises(ConcurrentExportLimitException):
            AsyncTask.check_running_count_by_user(self.username, is_scene=True)

    # ---- 分组隔离 ----

    def test_scene_and_non_scene_are_independent(self):
        """场景和非场景分组独立计数，互不影响"""
        # 非场景已满
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
            self._create_running_task(self.username, scenario_id=Scenario.LOG)
        # 场景分组不受影响
        AsyncTask.check_running_count_by_user(self.username, is_scene=True)

        # 反过来：场景已满
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
            self._create_running_task(self.other_username, scenario_id=ASYNC_EXPORT_SCENE_ID)
        # 非场景不受影响
        AsyncTask.check_running_count_by_user(self.other_username)

    def test_scene_tasks_do_not_affect_non_scene_limit(self):
        """场景任务不计入非场景分组的限流"""
        for _ in range(TEST_MAX_CONCURRENT_EXPORT_TASKS):
            self._create_running_task(self.username, scenario_id=ASYNC_EXPORT_SCENE_ID)
        # scene 任务不会让 non-scene 超限
        AsyncTask.check_running_count_by_user(self.username, is_scene=False)

    # ---- override_settings ----

    def test_override_settings_changes_limit(self):
        """override_settings 可以动态修改并发上限"""
        self._create_running_task(self.username, scenario_id=Scenario.LOG)
        with self.settings(MAX_CONCURRENT_EXPORT_TASKS=1):
            with self.assertRaises(ConcurrentExportLimitException):
                AsyncTask.check_running_count_by_user(self.username)

    @override_settings(USE_REDIS=False)
    def test_create_with_running_limit_falls_back_when_redis_is_disabled(self):
        task = AsyncTask.async_export_task_create_with_running_limit(
            username=self.username, request_param=SEARCH_DICT, scenario_id=Scenario.LOG
        )

        self.assertEqual(task.created_by, self.username)
        self.assertEqual(task.export_type, ExportType.ASYNC)

    @override_settings(USE_REDIS=False, MAX_CONCURRENT_EXPORT_TASKS=1)
    def test_create_with_running_limit_still_checks_limit_when_redis_is_disabled(self):
        self._create_running_task(self.username, scenario_id=Scenario.LOG)

        with self.assertRaises(ConcurrentExportLimitException):
            AsyncTask.async_export_task_create_with_running_limit(
                username=self.username, request_param=SEARCH_DICT, scenario_id=Scenario.LOG
            )

        self.assertEqual(AsyncTask.objects.filter(created_by=self.username).count(), 1)

    @override_settings(USE_REDIS=True)
    def test_create_with_running_limit_uses_separate_group_locks(self):
        default_lock = Mock()
        default_lock.acquire.return_value = True
        scene_lock = Mock()
        scene_lock.acquire.return_value = True
        task_params = {key: value for key, value in self.common_params.items() if key != "export_type"}

        with patch("apps.log_search.models.cache.lock", return_value=default_lock) as mock_cache_lock:
            default_task = AsyncTask.async_export_task_create_with_running_limit(
                username=self.username, scenario_id=Scenario.LOG, **task_params
            )
        default_lock_key = mock_cache_lock.call_args.args[0]
        self.assertEqual(mock_cache_lock.call_args.kwargs, {"timeout": 30, "blocking_timeout": 5})

        with patch("apps.log_search.models.cache.lock", return_value=scene_lock) as mock_cache_lock:
            scene_task = AsyncTask.async_export_task_create_with_running_limit(
                username=self.username,
                is_scene=True,
                scenario_id=ASYNC_EXPORT_SCENE_ID,
                **task_params,
            )
        scene_lock_key = mock_cache_lock.call_args.args[0]
        self.assertEqual(mock_cache_lock.call_args.kwargs, {"timeout": 30, "blocking_timeout": 5})

        self.assertIn(":default:", default_lock_key)
        self.assertIn(":scene:", scene_lock_key)
        self.assertNotEqual(default_lock_key, scene_lock_key)
        self.assertEqual(default_task.created_by, self.username)
        self.assertEqual(scene_task.created_by, self.username)
        self.assertEqual(default_task.export_type, ExportType.ASYNC)
        self.assertEqual(scene_task.export_type, ExportType.ASYNC)
        default_lock.release.assert_called_once_with()
        scene_lock.release.assert_called_once_with()

    @override_settings(USE_REDIS=True, MAX_CONCURRENT_EXPORT_TASKS=1)
    def test_create_with_running_limit_rechecks_count_inside_lock(self):
        self._create_running_task(self.username, scenario_id=Scenario.LOG)
        lock = Mock()
        lock.acquire.return_value = True

        with patch("apps.log_search.models.cache.lock", return_value=lock):
            with self.assertRaises(ConcurrentExportLimitException):
                AsyncTask.async_export_task_create_with_running_limit(
                    username=self.username, request_param=SEARCH_DICT, scenario_id=Scenario.LOG
                )

        lock.release.assert_called_once_with()
        self.assertEqual(AsyncTask.objects.filter(created_by=self.username).count(), 1)

    @override_settings(USE_REDIS=True)
    def test_create_with_running_limit_does_not_create_when_lock_is_busy(self):
        lock = Mock()
        lock.acquire.return_value = False

        with patch("apps.log_search.models.cache.lock", return_value=lock):
            with self.assertRaisesMessage(
                AsyncExportRequestBusyException,
                gettext("当前有导出任务正在创建中，请稍后重试"),
            ):
                AsyncTask.async_export_task_create_with_running_limit(
                    username=self.username, request_param=SEARCH_DICT, scenario_id=Scenario.LOG
                )

        lock.release.assert_not_called()
        self.assertFalse(AsyncTask.objects.filter(created_by=self.username).exists())

    @override_settings(USE_REDIS=True)
    def test_create_with_running_limit_falls_back_when_redis_connection_fails(self):
        lock = Mock()
        lock.acquire.side_effect = RedisConnectionError("Redis unavailable")

        with (
            patch("apps.log_search.models.cache.lock", return_value=lock),
            patch("apps.log_search.models.logger.exception") as mock_logger_exception,
        ):
            task = AsyncTask.async_export_task_create_with_running_limit(
                username=self.username,
                request_param=SEARCH_DICT,
                scenario_id=Scenario.LOG,
            )

        self.assertEqual(task.created_by, self.username)
        self.assertEqual(task.export_type, ExportType.ASYNC)
        lock.acquire.assert_called_once_with()
        lock.release.assert_not_called()
        mock_logger_exception.assert_called_once()

    @override_settings(USE_REDIS=True, MAX_CONCURRENT_EXPORT_TASKS=1)
    def test_redis_connection_fallback_still_checks_running_limit(self):
        self._create_running_task(self.username, scenario_id=Scenario.LOG)
        lock = Mock()
        lock.acquire.side_effect = RedisConnectionError("Redis unavailable")

        with patch("apps.log_search.models.cache.lock", return_value=lock):
            with self.assertRaises(ConcurrentExportLimitException):
                AsyncTask.async_export_task_create_with_running_limit(
                    username=self.username,
                    request_param=SEARCH_DICT,
                    scenario_id=Scenario.LOG,
                )

        self.assertEqual(AsyncTask.objects.filter(created_by=self.username).count(), 1)

    @override_settings(USE_REDIS=True)
    def test_release_connection_error_does_not_abort_created_task(self):
        lock = Mock()
        lock.acquire.return_value = True
        lock.release.side_effect = RedisConnectionError("Redis unavailable")

        with (
            patch("apps.log_search.models.cache.lock", return_value=lock),
            patch("apps.log_search.models.logger.exception") as mock_logger_exception,
        ):
            task = AsyncTask.async_export_task_create_with_running_limit(
                username=self.username,
                request_param=SEARCH_DICT,
                scenario_id=Scenario.LOG,
            )

        self.assertTrue(AsyncTask.objects.filter(id=task.id).exists())
        lock.release.assert_called_once_with()
        mock_logger_exception.assert_called_once()


@override_settings(USE_REDIS=True, MAX_CONCURRENT_EXPORT_TASKS=TEST_MAX_CONCURRENT_EXPORT_TASKS)
class TestAsyncTaskConcurrentCreation(TransactionTestCase):
    def test_same_user_same_scene_concurrent_creation_does_not_exceed_limit(self):
        username = "concurrent_test_user"
        request_count = TEST_MAX_CONCURRENT_EXPORT_TASKS + 1
        fake_cache = BarrierRedisCache(request_count)
        database_connection = connections["default"]
        share_database_connection = database_connection.vendor == "sqlite" and database_connection.is_in_memory_db()

        def create_task():
            if share_database_connection:
                connections["default"] = database_connection
            else:
                close_old_connections()
            try:
                task = AsyncTask.async_export_task_create_with_running_limit(
                    username=username,
                    is_scene=True,
                    request_param=SEARCH_DICT,
                    scenario_id=ASYNC_EXPORT_SCENE_ID,
                )
                return "created", task.id
            except ConcurrentExportLimitException as error:
                return "rejected", error
            except Exception as error:  # pylint: disable=broad-except
                return "unexpected_error", error
            finally:
                if not share_database_connection:
                    close_old_connections()

        if share_database_connection:
            database_connection.inc_thread_sharing()
        try:
            with patch("apps.log_search.models.cache", fake_cache):
                with ThreadPoolExecutor(max_workers=request_count) as executor:
                    futures = [executor.submit(create_task) for _ in range(request_count)]
                    results = [future.result(timeout=10) for future in futures]
        finally:
            if share_database_connection:
                database_connection.dec_thread_sharing()

        created_results = [result for result in results if result[0] == "created"]
        rejected_results = [result for result in results if result[0] == "rejected"]
        unexpected_errors = [result[1] for result in results if result[0] == "unexpected_error"]

        self.assertFalse(unexpected_errors, unexpected_errors)
        self.assertEqual(len(created_results), TEST_MAX_CONCURRENT_EXPORT_TASKS)
        self.assertEqual(len(rejected_results), request_count - TEST_MAX_CONCURRENT_EXPORT_TASKS)
        self.assertTrue(all(isinstance(result[1], ConcurrentExportLimitException) for result in rejected_results))
        self.assertEqual(len(fake_cache.lock_keys), request_count)
        self.assertEqual(len(set(fake_cache.lock_keys)), 1)
        self.assertEqual(set(fake_cache.lock_timeouts), {30})
        self.assertIn(f":{ASYNC_EXPORT_SCENE_ID}:", fake_cache.lock_keys[0])
        self.assertEqual(
            AsyncTask.objects.filter(
                created_by=username,
                scenario_id=ASYNC_EXPORT_SCENE_ID,
                export_type=ExportType.ASYNC,
            ).count(),
            TEST_MAX_CONCURRENT_EXPORT_TASKS,
        )


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
            self.assertEqual(
                task.failed_reason,
                gettext("异步导出任务超过 24 小时未启动或未完成，自动标记为失败"),
            )

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
