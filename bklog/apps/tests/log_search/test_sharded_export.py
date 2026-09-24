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

import hashlib
import json
import tempfile
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from blueapps.core.celery.celery import app
from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from redis.exceptions import RedisError

from apps.api.exception import DataAPIException
from apps.constants import RemoteStorageType
from apps.log_search.constants import (
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    NON_SPLITTABLE_ERROR_CODES,
    ExportErrorCode,
    ExportJobStatus,
    ExportPlanStatus,
    ExportPartStatus,
    ExportStage,
    ExportStatus,
    ExportType,
)
from apps.log_search.exceptions import (
    AsyncExportRequestBusyException,
    ConcurrentExportLimitException,
    PreCheckAsyncExportException,
)
from apps.log_search.export import state
from apps.log_search.export.config import (
    CONTROL_QUEUE,
    COORDINATOR_QUEUE,
    PART_QUEUE,
    PART_TASK_NAME,
    ExportPolicy,
)
from apps.log_search.export.api import create_export_job, download_link, job_detail, job_results
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.models import AsyncTask, LogIndexSet, Scenario, Space
from apps.log_search.views.export_views import ExportJobViewSet
from apps.log_search.export.worker import _execute, _pack, _write_rows, run_part
from apps.log_search.export.planner import (
    INTERVAL_LADDER_MS,
    PlanError,
    PartSpec,
    build_handler,
    build_parts,
    choose_interval,
    is_definitely_empty,
    merge_adjacent,
    refine,
    run_planning,
)
from apps.log_search.export.scheduler import (
    _inflight_by_index_set,
    _send,
    dispatch_ready_parts,
    enqueue_finalization,
    enqueue_planning,
    finalize_export,
)
from apps.log_search.export.storage import (
    UnsupportedExportStorage,
    artifact_name,
    build_storage,
    job_object_prefix,
    manifest_name,
)
from apps.log_search.tasks.sharded_export import (
    PLANNING_SOFT_TIME_LIMIT,
    coordinate_sharded_exports,
    execute_sharded_export_part,
    plan_sharded_export,
)


def build_policy(**overrides):
    """按测试需要覆盖 ExportPolicy 的默认值。"""
    return replace(ExportPolicy(), **overrides)


def create_job(**overrides):
    values = {
        "space_uid": "bkcc__2",
        "created_by": "tester",
        "index_set_id": 1,
        "search_params": {"index_set_ids": [1]},
        "base_dict": {"query_list": [{"reference_name": "a"}]},
        "policy": ExportPolicy().snapshot(),
        "start_time": 0,
        "end_time": 4000,
        "status": ExportJobStatus.PENDING,
    }
    values.update(overrides)
    return ExportJob.objects.create(**values)


def fence_of(part):
    """取分片当前的栅栏令牌。"""
    return state.PartFence.of(part)


class FakeHandler:
    """只暴露 planner/worker 实际用到的最小接口。"""

    def __init__(self, result_window=100):
        self.index_info_list = [{"index_set_obj": SimpleNamespace(result_window=result_window)}]
        self.base_dict = {"query_list": [], "start_time": "0", "end_time": "1"}

    def _deal_query_result(self, result):
        return {"origin_log_list": [{"value": row} for row in result["list"]]}


class PolicyBoundsTests(SimpleTestCase):
    """FeatureConfig 没有 Schema，_BOUNDS 是唯一的字段白名单。"""

    def test_every_policy_field_is_registered_in_bounds(self):
        """漏登记的字段会被 _validated_policy 静默丢弃，运维配的值不生效也不报错。"""
        from apps.log_search.export import config

        self.assertEqual(set(ExportPolicy().snapshot()), set(config._BOUNDS))


class ChooseIntervalTests(SimpleTestCase):
    def test_density_based_interval_matches_sample_expectation(self):
        policy = build_policy(target_rows=30000, bucket_seconds=30, max_buckets=500)
        # 547 万条 / 6 小时 ≈ 110 秒一片，与方案文档中的样本结论一致
        interval = choose_interval(5471953, 0, 6 * 3600 * 1000, 1000, policy)
        self.assertGreater(interval, 100_000)
        self.assertLess(interval, 130_000)
        self.assertEqual(interval % 1000, 0)

    def test_bucket_count_is_bounded(self):
        policy = build_policy(target_rows=1, bucket_seconds=30, max_buckets=500)
        interval = choose_interval(1, 0, 30 * 24 * 3600 * 1000, 1000, policy)
        self.assertLessEqual((30 * 24 * 3600 * 1000) // interval, 500 + 1)

    def test_density_interval_is_snapped_to_a_supported_window(self):
        policy = build_policy(target_rows=500, bucket_seconds=30, max_buckets=500)

        interval = choose_interval(10165, 0, 3600 * 1000, 1, policy)

        self.assertEqual(interval, 180_000)
        self.assertIn(interval, INTERVAL_LADDER_MS)

    def test_interval_is_never_shorter_than_a_second(self):
        policy = build_policy(target_rows=30000, bucket_seconds=30, max_buckets=500)

        self.assertGreaterEqual(choose_interval(10**9, 0, 3600 * 1000, 1, policy), 1000)

    def test_interval_never_exceeds_the_query_span(self):
        policy = build_policy(target_rows=30000, bucket_seconds=30, max_buckets=500)

        self.assertLessEqual(choose_interval(1, 0, 40 * 1000, 1000, policy), 40 * 1000)


class RefineTests(SimpleTestCase):
    def test_hot_range_is_split_until_it_reaches_target(self):
        policy = build_policy(target_rows=100, split_factor=2.0)
        with patch("apps.log_search.export.planner.count_rows", side_effect=lambda _h, s, e: (e - s) // 10):
            parts = refine(None, 0, 4000, 400, 1000, policy, 1)
        self.assertEqual(
            [(part.start_time, part.end_time) for part in parts],
            [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000)],
        )
        self.assertTrue(all(part.estimated_rows == 100 for part in parts))

    def test_minimum_precision_is_marked_oversized(self):
        parts = refine(None, 0, 1000, 1000, 1000, build_policy(target_rows=100, split_factor=2.0), 1)
        self.assertEqual(len(parts), 1)
        self.assertTrue(parts[0].oversized)

    def test_non_hot_range_is_kept_as_single_part(self):
        parts = refine(None, 0, 4000, 10, 1000, build_policy(target_rows=100, split_factor=2.0), 1)
        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertFalse(parts[0].oversized)


class MergeTests(SimpleTestCase):
    def test_adjacent_small_parts_are_merged_within_limit(self):
        policy = build_policy(target_rows=100, merge_factor=2.0)
        parts = [
            PartSpec(0, 1000, 100, 100),
            PartSpec(1000, 2000, 100, 100),
            PartSpec(2000, 3000, 100, 100),
        ]
        merged = merge_adjacent(parts, policy)
        self.assertEqual([(part.start_time, part.end_time) for part in merged], [(0, 2000), (2000, 3000)])

    def test_oversized_part_is_never_merged(self):
        policy = build_policy(target_rows=1000, merge_factor=2.0)
        parts = [PartSpec(0, 1000, 10, 10, oversized=True), PartSpec(1000, 2000, 10, 10)]
        self.assertEqual(len(merge_adjacent(parts, policy)), 2)


class BuildPartsTests(TestCase):
    """build_parts 是规划链路的契约点：返回 (parts, total, result) 且完整覆盖任务区间。"""

    def setUp(self):
        self.job = create_job()

    def plan_with(self, *, total, buckets, sample=None, policy=None):
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=total),
            patch("apps.log_search.export.planner.sample_rows", return_value=sample or []),
            patch("apps.log_search.export.planner.histogram", return_value=buckets),
        ):
            return build_parts(self.job, policy or build_policy())

    def test_returns_parts_total_and_plan_result_for_the_whole_range(self):
        parts, total, result = self.plan_with(total=40, buckets={0: 40}, sample=[b"x" * 20])

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(total, 40)
        self.assertEqual(parts[0].estimated_rows, 40)
        self.assertEqual(parts[0].estimated_bytes, 800)
        self.assertEqual(result.total_rows, 40)
        self.assertEqual(result.avg_row_bytes, 20)

    def test_empty_histogram_is_a_retryable_statistics_failure(self):
        with self.assertRaises(PlanError) as context:
            self.plan_with(total=40, buckets={})

        self.assertEqual(context.exception.code, "STATISTICS_FAILED")
        self.assertTrue(context.exception.retryable)

    def test_bucket_keys_are_matched_on_unify_query_grid(self):
        """桶键锚点与按 start_time 推出的网格不一致时，仍要取到真实条数。"""
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=300),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"x" * 10]),
            patch("apps.log_search.export.planner.choose_interval", return_value=3000),
            patch("apps.log_search.export.planner.histogram", return_value={1500: 300}),
        ):
            parts, total, _ = build_parts(self.job, build_policy(target_rows=1000))

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(sum(part.estimated_rows for part in parts), 300)

    def test_build_parts_uses_split_step_from_policy(self):
        """切分步长完全由策略决定，refine 应收到配置的步长。"""
        policy = build_policy(target_rows=100, split_step_ms=5000)
        job = create_job(policy=policy.snapshot())
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=100),
            patch("apps.log_search.export.planner.sample_rows", return_value=[]),
            patch("apps.log_search.export.planner.histogram", return_value={0: 100}),
            patch("apps.log_search.export.planner.refine", return_value=[]) as refine_mock,
        ):
            build_parts(job, policy)

        self.assertTrue(refine_mock.call_args_list)
        self.assertTrue(all(call.args[4] == 5000 for call in refine_mock.call_args_list))

    def test_rows_over_quota_fail_before_any_density_query(self):
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=20_000_000),
            patch("apps.log_search.export.planner.histogram") as histogram,
        ):
            with self.assertRaises(PlanError) as context:
                build_parts(self.job, build_policy())

        self.assertEqual(context.exception.code, "QUOTA_EXCEEDED")
        histogram.assert_not_called()

    def test_empty_range_returns_one_covering_part(self):
        parts, total, result = self.plan_with(total=0, buckets={})

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(total, 0)
        self.assertEqual(result.total_rows, 0)


class BuildHandlerTests(TestCase):
    """分片时间范围只在冻结的 base_dict 上覆盖一次，不下发给构造器。"""

    def test_part_range_is_applied_only_to_the_frozen_body(self):
        job = create_job(
            search_params={"index_set_ids": [1], "start_time": 0, "end_time": 4000},
            base_dict={"start_time": "0", "end_time": "4000"},
        )
        with patch("apps.log_search.export.planner.UnifyQueryHandler") as handler_cls:
            handler = build_handler(job, 1000, 2000)

        self.assertEqual((handler.base_dict["start_time"], handler.base_dict["end_time"]), ("1000", "2000"))
        self.assertEqual(handler_cls.call_args.args[0]["start_time"], 0)


class RunPlanningTests(TestCase):
    """规划必须真的把任务推进到 READY，并把规划过程量写进当前计划版本。"""

    def test_run_planning_persists_plan_and_moves_job_to_ready(self):
        job = create_job()
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=40),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"x" * 20]),
            patch("apps.log_search.export.planner.histogram", return_value={0: 40}),
        ):
            run_planning(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.READY)
        self.assertEqual(job.plan_version, 1)
        self.assertEqual(job.estimated_total, 40)
        plan = ExportPlan.objects.get(job=job, plan_version=1)
        self.assertEqual(plan.status, ExportPlanStatus.SUCCESS)
        self.assertEqual(plan.total_rows, 40)
        self.assertEqual(plan.planned_parts, 1)
        self.assertIsNotNone(plan.finished_at)
        part = ExportPart.objects.get(job=job)
        self.assertEqual(part.plan_version, 1)
        self.assertEqual((part.start_time, part.end_time), (0, 4000))
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.estimated_rows, 40)


class PartRunnerTests(TestCase):
    def test_write_rows_streams_until_done(self):
        responses = [
            {"list": [{"v": 1}, {"v": 2}], "done": False},
            {"list": [{"v": 3}], "done": True},
            {"list": [{"v": 4}], "done": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            payload = Path(directory) / "logs.jsonl"
            with patch("apps.log_search.export.worker.UnifyQueryApi") as api:
                api.query_ts_raw_with_scroll.side_effect = responses
                rows, size = _write_rows(FakeHandler(), payload)
            lines = payload.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(rows, 3)
        self.assertEqual(len(lines), 3)
        self.assertEqual(size, sum(len(line.encode("utf-8")) + 1 for line in lines))
        self.assertEqual(api.query_ts_raw_with_scroll.call_count, 2)

    def test_write_rows_stops_on_empty_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("apps.log_search.export.worker.UnifyQueryApi") as api:
                api.query_ts_raw_with_scroll.side_effect = [{"list": [], "done": False}]
                rows, size = _write_rows(FakeHandler(), Path(directory) / "logs.jsonl")
        self.assertEqual((rows, size), (0, 0))

    def test_pack_puts_single_log_member(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "logs.jsonl").write_bytes(b"{}\n")
            archive = _pack(directory, SimpleNamespace(part_no=7))
            self.assertEqual(archive.name, "part-7.tar.gz")
            self.assertGreater(archive.stat().st_size, 0)

    def test_execute_uses_job_frozen_external_flag(self):
        """Worker 没有请求上下文，必须按任务冻结的外部标识上传到外部版的桶"""
        job = create_job(is_external=True, status=ExportJobStatus.RUNNING, end_time=1000)
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.RUNNING,
            task_id="task-1",
            attempts=1,
        )
        with (
            patch("apps.log_search.export.worker.build_storage") as build_storage,
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker.upload"),
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
        ):
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(job, part, fence_of(part))

        build_storage.assert_called_once_with(external=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)
        self.assertEqual(part.object_key, artifact_name(job, part, 1))

    @override_settings(ASYNC_EXPORT_UPLOAD_ATTEMPTS=3, ASYNC_EXPORT_UPLOAD_RETRY_INTERVAL_SECONDS=1)
    def test_execute_retries_upload_without_requerying(self):
        """上传抖动只重试上传本身：不重新查询、不重新压缩，退避按尝试次数递增。"""
        job = create_job(status=ExportJobStatus.RUNNING, end_time=1000)
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.RUNNING,
            task_id="task-1",
            attempts=1,
        )
        with (
            patch("apps.log_search.export.worker.build_storage"),
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker.upload") as upload,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
            patch("apps.log_search.export.worker.time.sleep") as sleep,
        ):
            upload.side_effect = [RuntimeError("cos 5xx"), RuntimeError("cos 5xx"), "etag"]
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(job, part, fence_of(part))

        self.assertEqual(upload.call_count, 3)
        self.assertEqual(api.query_ts_raw_with_scroll.call_count, 1)
        self.assertEqual([item.args[0] for item in sleep.call_args_list], [1, 2])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)

    @override_settings(ASYNC_EXPORT_UPLOAD_ATTEMPTS=2, ASYNC_EXPORT_UPLOAD_RETRY_INTERVAL_SECONDS=0)
    def test_run_part_returns_to_waiting_after_upload_attempts_exhausted(self):
        """上传重试耗尽后整片交回调度器，等待下一轮重新执行。"""
        job = create_job(status=ExportJobStatus.RUNNING, end_time=1000)
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.DISPATCHED,
            task_id="task-1",
        )
        with (
            patch("apps.log_search.export.worker.build_storage"),
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker.upload", side_effect=RuntimeError("cos down")) as upload,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
            patch("apps.log_search.export.worker.time.sleep"),
        ):
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            run_part(part.pk, "task-1")

        self.assertEqual(upload.call_count, 2)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.error_code, "UPLOAD_FAILED")

    def test_unify_query_failure_gets_its_own_code(self):
        """取数失败要能与其它执行异常区分开，并且仍然可重试。"""
        job = create_job(status=ExportJobStatus.RUNNING, end_time=1000)
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.DISPATCHED,
            task_id="task-1",
        )
        with (
            patch("apps.log_search.export.worker.build_storage"),
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
        ):
            api.query_ts_raw_with_scroll.side_effect = DataAPIException(None, "unify query 5xx")
            run_part(part.pk, "task-1")

        part.refresh_from_db()
        self.assertEqual(part.error_code, ExportErrorCode.UNIFY_QUERY_FAILED)
        self.assertEqual(part.status, ExportPartStatus.WAITING)


class PartArtifactLifecycleTests(TestCase):
    """
    产物归属由 fence 裁决：每个执行只写 (part, 认领序号) 决定的键，
    只有被接受为 SUCCESS 的执行留下对象，其余执行清掉自己的键。
    """

    def setUp(self):
        self.job = create_job(status=ExportJobStatus.RUNNING, end_time=1000)
        self.part = ExportPart.objects.create(
            job=self.job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.WAITING,
        )
        self.objects = {}
        self.uploaded = []
        self.deleted = []

    def claim(self, task_id):
        state.dispatch_part(self.part.pk, task_id)
        return state.claim_part(self.part.pk, task_id)

    def execute(self, part, fence, before_upload=None, discard_error=None):
        """执行一次分片，用一个 dict 充当对象存储。"""

        def upload_artifact(_storage, path, name):
            if before_upload is not None:
                before_upload()
            self.objects[name] = path.read_bytes()
            self.uploaded.append(name)

        def delete_artifact_file(_storage, name):
            if discard_error is not None:
                raise discard_error
            self.deleted.append(name)
            self.objects.pop(name, None)

        with (
            patch("apps.log_search.export.worker.build_storage"),
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker.upload", side_effect=upload_artifact),
            patch("apps.log_search.export.worker.delete_artifact", side_effect=delete_artifact_file),
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
        ):
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(self.job, part, fence)

    def test_accepted_execution_keeps_its_artifact(self):
        part = self.claim("task-1")

        self.execute(part, fence_of(part))

        key = artifact_name(self.job, part, 1)
        self.assertEqual(self.uploaded, [key])
        self.assertEqual(self.deleted, [])
        self.assertEqual(list(self.objects), [key])
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, ExportPartStatus.SUCCESS)
        self.assertEqual(self.part.object_key, key)

    def test_late_upload_never_overwrites_the_published_artifact(self):
        """旧执行的上传晚于新执行成功时，只写自己的键，并在被判出局后清掉它。"""
        late = self.claim("task-1")

        def publish_new_attempt():
            """旧执行还在上传的期间，新一次投递已经跑完并发布了产物。"""
            state.recover_part(self.part.pk, cutoff=timezone.now() + timedelta(seconds=1))
            winner = self.claim("task-2")
            self.execute(winner, fence_of(winner))

        self.execute(late, fence_of(late), before_upload=publish_new_attempt)

        late_key = artifact_name(self.job, late, 1)
        winner_key = artifact_name(self.job, self.part, 2)
        self.assertNotEqual(late_key, winner_key)
        self.assertEqual(self.uploaded, [winner_key, late_key])
        self.assertEqual(self.deleted, [late_key])
        self.assertEqual(list(self.objects), [winner_key])
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, ExportPartStatus.SUCCESS)
        self.assertEqual(self.part.object_key, winner_key)

    def test_artifact_is_discarded_when_the_job_is_canceled(self):
        part = self.claim("task-1")
        state.cancel_job(self.job.pk)

        self.execute(part, fence_of(part))

        key = artifact_name(self.job, part, 1)
        self.assertEqual(self.uploaded, [key])
        self.assertEqual(self.deleted, [key])
        self.assertEqual(self.objects, {})
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.CANCELED)

    def test_discard_failure_does_not_change_the_commit_result(self):
        """清理失败只影响存储占用，不能反过来影响分片状态。"""
        part = self.claim("task-1")
        state.cancel_job(self.job.pk)

        self.execute(part, fence_of(part), discard_error=RuntimeError("cos down"))

        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.CANCELED)
        self.assertEqual(list(self.objects), [artifact_name(self.job, part, 1)])


class PartTaskContractTests(SimpleTestCase):
    """分片任务的投递身份契约：消息体只带 part_id，身份走 Celery 消息 id。"""

    def test_message_carries_part_id_and_task_id_only(self):
        with patch("apps.log_search.export.scheduler.app.send_task") as send_task:
            _send(PART_TASK_NAME, 7, task_id="token-a")

        self.assertEqual(send_task.call_args.kwargs["args"], [7])
        self.assertEqual(send_task.call_args.kwargs["task_id"], "token-a")

    def test_task_passes_message_id_as_fence(self):
        with patch("apps.log_search.tasks.sharded_export.run_part") as run_part:
            execute_sharded_export_part.apply(args=[7], task_id="token-a", throw=True)

        run_part.assert_called_once_with(7, "token-a")


class ExportStateTestCase(TestCase):
    def setUp(self):
        self.job = create_job()

    def plan(self, parts=None):
        parts = parts or [
            PartSpec(0, 1000, 10, 10),
            PartSpec(1000, 2000, 10, 10),
            PartSpec(2000, 3000, 10, 10),
            PartSpec(3000, 4000, 10, 10),
        ]
        self.assertIsNotNone(state.claim_planning(self.job.pk))
        return state.persist_plan(self.job.pk, parts=parts, estimated_total=40)

    def complete_parts(self, count):
        for part in ExportPart.objects.filter(job=self.job).order_by("part_no")[:count]:
            state.dispatch_part(part.pk, f"task-{part.pk}")
            part = state.claim_part(part.pk, f"task-{part.pk}")
            state.complete_part(
                part.pk,
                fence_of(part),
                actual_rows=10,
                actual_bytes=100,
                compressed_bytes=50,
                object_key=f"object-{part.pk}",
                checksum="checksum",
            )

    def test_persist_plan_moves_job_to_ready(self):
        job = self.plan()
        self.assertEqual(job.status, ExportJobStatus.READY)
        self.assertEqual(job.plan_version, 1)
        self.assertEqual(ExportPart.objects.filter(job=job).count(), 4)
        self.assertEqual(ExportPart.objects.filter(job=job, plan_version=1).count(), 4)
        self.assertEqual(state.leaf_stats(job)["total"], 4)
        self.assertEqual(ExportPlan.objects.get(job=job, plan_version=1).planned_parts, 4)

    def test_persist_plan_rejects_incomplete_coverage(self):
        with self.assertRaises(ValueError):
            self.plan(parts=[PartSpec(0, 1000, 0, 0), PartSpec(2000, 4000, 0, 0)])

    def test_plan_boundaries_need_not_align_to_time_precision(self):
        """区间是否对齐时间精度不影响正确性，分片只需连续覆盖任务区间。"""
        job = self.plan(parts=[PartSpec(0, 1234, 10, 10), PartSpec(1234, 4000, 10, 10)])

        self.assertEqual(job.status, ExportJobStatus.READY)
        self.assertEqual(state.leaf_stats(job)["total"], 2)

    def test_oversized_part_may_be_narrower_than_the_split_step(self):
        """二分改为纯中点后，oversized 分片宽度只会小于等于切分步长。"""
        job = self.plan(parts=[PartSpec(0, 700, 10, 10, oversized=True), PartSpec(700, 4000, 10, 10)])

        self.assertEqual(job.status, ExportJobStatus.READY)
        self.assertTrue(ExportPart.objects.get(job=job, part_no=1).oversized)

    def test_oversized_part_wider_than_the_split_step_is_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(parts=[PartSpec(0, 1001, 10, 10, oversized=True), PartSpec(1001, 4000, 10, 10)])

    def test_split_step_comes_from_the_policy(self):
        self.assertEqual(state._split_step(create_job()), 1000)
        self.assertEqual(
            state._split_step(create_job(policy=build_policy(split_step_ms=1).snapshot())),
            1,
        )

    def test_planning_is_claimed_once(self):
        self.assertIsNotNone(state.claim_planning(self.job.pk))
        self.assertIsNone(state.claim_planning(self.job.pk))

    def test_full_part_lifecycle_completes_job(self):
        self.plan()
        self.complete_parts(4)
        job = ExportJob.objects.get(pk=self.job.pk)
        self.assertEqual(job.status, ExportJobStatus.RUNNING)
        self.assertEqual(state.leaf_stats(job)["success"], 4)
        self.assertEqual(job.actual_total, 40)
        self.assertIsNotNone(
            state.finalize_job(
                job.pk, manifest_object_key="manifest", manifest_bytes=10, manifest_checksum="manifest-checksum"
            )
        )
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.SUCCESS)
        self.assertIsNotNone(job.expires_at)

    def test_finalize_rejects_broken_leaf_boundaries(self):
        self.plan()
        self.complete_parts(4)
        ExportPart.objects.filter(job=self.job, part_no=3).update(start_time=2500)
        with self.assertRaises(ValueError):
            state.finalize_job(
                self.job.pk, manifest_object_key="manifest", manifest_bytes=10, manifest_checksum="manifest-checksum"
            )

    def test_failed_part_is_requeued_before_exhausting_attempts(self):
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="QUERY_FAILED", retryable=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.task_id, "")

    def test_exhausted_part_fails_the_job(self):
        self.job.policy = {**ExportPolicy().snapshot(), "part_max_attempts": 1}
        self.job.save(update_fields=["policy"])
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="QUERY_FAILED", retryable=True)
        part.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.FAILED)
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)

    @override_settings(ASYNC_EXPORT_PART_TIMEOUT=1)
    def test_recover_stale_parts_requeues_timeout_part(self):
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        ExportPart.objects.filter(pk=part.pk).update(started_at=timezone.now() - timedelta(seconds=10))
        self.assertEqual(state.recover_stale_parts(), [part.pk])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.error_code, "PART_TIMEOUT")

    @override_settings(ASYNC_EXPORT_PART_TIMEOUT=1)
    def test_recover_rechecks_staleness_inside_the_row_lock(self):
        """候选查询只做粗筛，回收必须在锁内按当前数据重判。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        ExportPart.objects.filter(pk=part.pk).update(started_at=timezone.now() - timedelta(seconds=10))

        with patch("apps.log_search.export.state._is_stale", return_value=False):
            self.assertEqual(state.recover_stale_parts(), [])

        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.RUNNING)

        # 事实未变时按超时正常回收
        self.assertEqual(state.recover_stale_parts(), [part.pk])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)

    def test_old_worker_cannot_change_reclaimed_part(self):
        """旧投递和旧执行在新一次认领后均不得修改分片或任务结果。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task-a")
        old = state.claim_part(part.pk, "task-a")
        state.fail_part(part.pk, fence_of(old), error_code="PART_TIMEOUT", retryable=True)
        state.dispatch_part(part.pk, "task-b")
        self.assertIsNone(state.claim_part(part.pk, "task-a"))
        self.assertIsNone(state.fail_part(part.pk, fence_of(old), error_code="OLD_FAILURE", retryable=False))
        self.assertEqual(ExportPart.objects.get(pk=part.pk).status, ExportPartStatus.DISPATCHED)
        current = state.claim_part(part.pk, "task-b")

        self.assertEqual(state.set_stage(part.pk, fence_of(old), ExportStage.UPLOAD), 0)
        self.assertIsNone(
            state.complete_part(
                part.pk,
                fence_of(old),
                actual_rows=999,
                actual_bytes=999,
                compressed_bytes=999,
                object_key="old-object",
                checksum="old-checksum",
            )
        )
        self.assertIsNone(state.fail_part(part.pk, fence_of(old), error_code="OLD_FAILURE", retryable=False))
        part.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.RUNNING)
        self.assertEqual(part.stage, ExportStage.DOWNLOAD_LOG)
        self.assertEqual(part.attempts, current.attempts)
        self.assertEqual(part.object_key, "")
        self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
        self.assertEqual(self.job.actual_total, 0)

        self.assertIsNotNone(
            state.complete_part(
                part.pk,
                fence_of(current),
                actual_rows=10,
                actual_bytes=100,
                compressed_bytes=50,
                object_key="current-object",
                checksum="current-checksum",
            )
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.actual_total, 10)

    def test_redelivered_task_reclaims_a_running_part(self):
        """worker 崩溃后 broker 重投递同一条消息，应当立即重新认领而不是干等超时回收。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        state.claim_part(part.pk, "task")

        again = state.claim_part(part.pk, "task")

        self.assertIsNotNone(again)
        self.assertEqual(again.attempts, 2)
        self.assertEqual(again.status, ExportPartStatus.RUNNING)

    def test_reclaim_invalidates_the_previous_attempt_fence(self):
        """重投递后 task_id 不变，执行代际只能靠 attempts 区分。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        old = state.claim_part(part.pk, "task")
        current = state.claim_part(part.pk, "task")

        self.assertIsNone(
            state.complete_part(
                part.pk,
                fence_of(old),
                actual_rows=10,
                actual_bytes=1,
                compressed_bytes=1,
                object_key="old-object",
                checksum="old-checksum",
            )
        )
        self.assertIsNone(state.fail_part(part.pk, fence_of(old), error_code="PART_TIMEOUT", retryable=True))
        self.assertIsNotNone(
            state.complete_part(
                part.pk,
                fence_of(current),
                actual_rows=10,
                actual_bytes=1,
                compressed_bytes=1,
                object_key="new-object",
                checksum="new-checksum",
            )
        )
        part.refresh_from_db()
        self.assertEqual(part.object_key, "new-object")

    def test_finalize_requires_every_part_success(self):
        self.plan()
        self.complete_parts(3)
        self.assertIsNone(
            state.finalize_job(
                self.job.pk, manifest_object_key="manifest", manifest_bytes=1, manifest_checksum="manifest-checksum"
            )
        )

    def test_cancel_job_cancels_waiting_parts(self):
        self.plan()
        state.cancel_job(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.CANCELED)
        self.assertFalse(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.WAITING).exists())

    def test_upload_stage_moves_part_to_uploading(self):
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")

        state.set_stage(part.pk, fence_of(part), ExportStage.PACKAGE)
        self.assertEqual(ExportPart.objects.get(pk=part.pk).status, ExportPartStatus.RUNNING)

        state.set_stage(part.pk, fence_of(part), ExportStage.UPLOAD)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.UPLOADING)
        self.assertEqual(part.stage, ExportStage.UPLOAD)

    def test_uploading_part_can_still_complete(self):
        """上传阶段仍是可回填结果的运行态，重新进入上传阶段不会让回填失效。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.set_stage(part.pk, fence_of(part), ExportStage.UPLOAD)

        self.assertIsNotNone(
            state.complete_part(
                part.pk,
                fence_of(part),
                actual_rows=10,
                actual_bytes=100,
                compressed_bytes=50,
                object_key="object",
                checksum="sum",
            )
        )
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)

    @override_settings(ASYNC_EXPORT_PART_TIMEOUT=1)
    def test_uploading_part_is_recovered_after_timeout(self):
        """上传阶段同样计入在途，卡住时按超时回收。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.set_stage(part.pk, fence_of(part), ExportStage.UPLOAD)
        ExportPart.objects.filter(pk=part.pk).update(started_at=timezone.now() - timedelta(seconds=10))

        self.assertEqual(state.recover_stale_parts(), [part.pk])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)

    def test_planning_attempt_budget_is_taken_from_job_policy(self):
        self.job.policy = {**ExportPolicy().snapshot(), "planning_attempts": 1}
        self.job.save(update_fields=["policy"])
        self.assertIsNotNone(state.claim_planning(self.job.pk))
        state.fail_planning(self.job.pk, "STATISTICS_FAILED", retryable=True)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)


class PlanRecordTests(TestCase):
    """计划版本的审计口径：失败的尝试复用同一版本，历史成功计划不被覆盖。"""

    def setUp(self):
        self.job = create_job()

    def test_claim_planning_reserves_the_current_version(self):
        state.claim_planning(self.job.pk)

        plan = ExportPlan.objects.get(job=self.job, plan_version=1)
        self.assertEqual(plan.status, ExportPlanStatus.PLANNING)
        self.assertEqual(plan.target_rows, ExportPolicy().target_rows)
        self.assertEqual(plan.target_bytes, ExportPolicy().target_bytes)
        self.assertIsNotNone(plan.started_at)

    def test_retryable_failure_reuses_the_same_version(self):
        state.claim_planning(self.job.pk)
        state.fail_planning(self.job.pk, "STATISTICS_FAILED", "统计失败", retryable=True)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.PENDING)

        state.claim_planning(self.job.pk)

        self.assertEqual(ExportPlan.objects.filter(job=self.job).count(), 1)
        plan = ExportPlan.objects.get(job=self.job)
        self.assertEqual(plan.plan_version, 1)
        self.assertEqual(plan.status, ExportPlanStatus.PLANNING)

    def test_failed_planning_marks_the_plan_row_failed(self):
        state.claim_planning(self.job.pk)
        state.fail_planning(self.job.pk, "QUOTA_EXCEEDED", "超过单任务上限")

        self.job.refresh_from_db()
        plan = ExportPlan.objects.get(job=self.job, plan_version=1)
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)
        self.assertEqual(plan.status, ExportPlanStatus.FAILED)
        self.assertIsNotNone(plan.finished_at)

    def test_new_version_never_overwrites_effective_history(self):
        self.job.plan_version = 1
        self.job.save(update_fields=["plan_version"])
        ExportPlan.objects.create(job=self.job, plan_version=1, status=ExportPlanStatus.SUCCESS, planned_parts=2)

        state.claim_planning(self.job.pk)

        self.assertTrue(
            ExportPlan.objects.filter(
                job=self.job, plan_version=1, status=ExportPlanStatus.SUCCESS, planned_parts=2
            ).exists()
        )
        self.assertEqual(ExportPlan.objects.get(job=self.job, plan_version=2).status, ExportPlanStatus.PLANNING)


class SplitTests(TestCase):
    """重试耗尽后按时间细分，父分片转 SPLIT。"""

    def setUp(self):
        self.job = create_job(policy={**ExportPolicy().snapshot(), "part_max_attempts": 1})
        self.assertIsNotNone(state.claim_planning(self.job.pk))
        state.persist_plan(self.job.pk, parts=[PartSpec(0, 4000, 40, 4000)], estimated_total=40)

    def fail_first_part(self, error_code="PART_TIMEOUT"):
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code=error_code, error_detail="执行超时", retryable=True)
        return part

    def children_of(self, parent):
        return list(ExportPart.objects.filter(job=self.job, parent_part=parent).order_by("part_no"))

    def test_exhausted_part_is_split_into_two_children(self):
        parent = self.fail_first_part()

        parent.refresh_from_db()
        self.assertEqual(parent.status, ExportPartStatus.SPLIT)
        self.assertEqual(parent.task_id, "")
        children = self.children_of(parent)
        self.assertEqual([(child.start_time, child.end_time) for child in children], [(0, 2000), (2000, 4000)])
        self.assertEqual([child.status for child in children], [ExportPartStatus.WAITING] * 2)
        self.assertEqual([child.plan_version for child in children], [1, 1])
        self.assertEqual(sum(child.estimated_rows for child in children), 40)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
        self.assertEqual(state.leaf_stats(self.job)["total"], 2)

    def test_part_at_split_step_fails_the_job_with_oversized_error(self):
        job = create_job(end_time=1000, policy={**ExportPolicy().snapshot(), "part_max_attempts": 1})
        state.claim_planning(job.pk)
        state.persist_plan(job.pk, parts=[PartSpec(0, 1000, 40, 4000, oversized=True)], estimated_total=40)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="PART_TIMEOUT", retryable=True)

        job.refresh_from_db()
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.FAILED)
        self.assertEqual(job.status, ExportJobStatus.FAILED)
        self.assertEqual(job.error_code, "OVERSIZED_PART_FAILED")

    def test_non_workload_error_is_never_split(self):
        parent = self.fail_first_part(error_code="STORAGE_UNSUPPORTED")

        parent.refresh_from_db()
        self.assertEqual(parent.status, ExportPartStatus.FAILED)
        self.assertEqual(self.children_of(parent), [])

    def test_upload_failure_is_never_split(self):
        """上传失败与工作量无关，重试耗尽后整片失败，不做无意义的时间细分。"""
        parent = self.fail_first_part(error_code="UPLOAD_FAILED")

        parent.refresh_from_db()
        self.assertEqual(parent.status, ExportPartStatus.FAILED)
        self.assertEqual(self.children_of(parent), [])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)

    def test_part_limit_stops_splitting(self):
        job = create_job(policy={**ExportPolicy().snapshot(), "part_max_attempts": 1, "max_parts": 1})
        state.claim_planning(job.pk)
        state.persist_plan(job.pk, parts=[PartSpec(0, 4000, 40, 4000)], estimated_total=40)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="PART_TIMEOUT", retryable=True)

        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.FAILED)

    def test_children_take_over_the_leaf_scope(self):
        parent = self.fail_first_part()
        for child in self.children_of(parent):
            state.dispatch_part(child.pk, f"task-{child.pk}")
            child = state.claim_part(child.pk, f"task-{child.pk}")
            state.complete_part(
                child.pk,
                fence_of(child),
                actual_rows=20,
                actual_bytes=200,
                compressed_bytes=100,
                object_key=f"object-{child.pk}",
                checksum="checksum",
            )

        job = ExportJob.objects.get(pk=self.job.pk)
        self.assertEqual(job.actual_total, 40)
        self.assertEqual(state.leaf_stats(job)["success"], 2)
        self.assertIsNotNone(
            state.finalize_job(
                job.pk, manifest_object_key="manifest", manifest_bytes=1, manifest_checksum="manifest-checksum"
            )
        )
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.SUCCESS)

    def test_late_result_of_a_split_parent_is_discarded(self):
        parent = self.fail_first_part()

        self.assertIsNone(
            state.complete_part(
                parent.pk,
                fence_of(parent),
                actual_rows=40,
                actual_bytes=400,
                compressed_bytes=1,
                object_key="stale",
                checksum="c",
            )
        )
        parent.refresh_from_db()
        self.assertEqual(parent.object_key, "")
        self.assertEqual(parent.status, ExportPartStatus.SPLIT)


class ArtifactNameTests(SimpleTestCase):
    """产物键包含认领序号：一个键只有一个执行在写，重复投递不会互相覆盖。"""

    def test_artifact_name_is_unique_per_attempt(self):
        job = SimpleNamespace(pk=11)
        part = SimpleNamespace(pk=3)

        self.assertEqual(artifact_name(job, part, 1), artifact_name(job, part, 1))
        self.assertEqual(artifact_name(job, part, 1), "exports/11/parts/3/attempt-1.tar.gz")
        self.assertNotEqual(artifact_name(job, part, 1), artifact_name(job, part, 2))
        self.assertNotEqual(artifact_name(job, part, 1), artifact_name(job, SimpleNamespace(pk=4), 1))

    def test_names_live_under_the_job_prefix(self):
        """分片对象与清单共用一个任务前缀，桶生命周期和任务级清理才能按前缀匹配。"""
        job = SimpleNamespace(pk=11)
        part = SimpleNamespace(pk=3)

        self.assertTrue(artifact_name(job, part, 2).startswith(job_object_prefix(11)))
        self.assertTrue(manifest_name(job).startswith(job_object_prefix(11)))
        self.assertEqual(manifest_name(job), "exports/11/manifest.json")


class BuildStorageTests(SimpleTestCase):
    """外部版与内部版必须读各自的存储开关，且都只接受对象存储。"""

    def _build(self, *, external, config):
        toggle = SimpleNamespace(feature_config=config)
        factory = MagicMock()
        with (
            patch("apps.log_search.export.storage.FeatureToggleObject.toggle", return_value=toggle) as toggle_mock,
            patch("apps.log_search.export.storage.StorageType.get_instance", return_value=factory) as get_instance,
        ):
            return build_storage(external=external), toggle_mock, get_instance, factory

    def test_internal_request_uses_common_toggle_and_cos_config(self):
        _, toggle, get_instance, factory = self._build(
            external=False,
            config={
                "storage_type": RemoteStorageType.COS.value,
                "qcloud_secret_id": "secret-id",
                "qcloud_secret_key": "secret-key",
                "qcloud_cos_region": "region",
                "qcloud_cos_bucket": "bucket",
            },
        )

        toggle.assert_called_once_with(FEATURE_ASYNC_EXPORT_COMMON)
        get_instance.assert_called_once_with(RemoteStorageType.COS.value)
        # 存储实例上的默认有效期不影响分片导出：下载链接由 download_link 按剩余保留时间逐次签发
        factory.assert_called_once_with("secret-id", "secret-key", "region", "bucket", 0)

    def test_external_request_uses_external_toggle(self):
        _, toggle, get_instance, factory = self._build(
            external=True, config={"storage_type": RemoteStorageType.BKREPO.value}
        )

        toggle.assert_called_once_with(FEATURE_ASYNC_EXPORT_EXTERNAL)
        get_instance.assert_called_once_with(RemoteStorageType.BKREPO.value)
        factory.assert_called_once_with()

    def test_external_nfs_configuration_is_rejected(self):
        with self.assertRaises(UnsupportedExportStorage):
            self._build(external=True, config={"storage_type": RemoteStorageType.NFS.value})


@override_settings(ASYNC_EXPORT_COORDINATE_BATCH=10)
class SchedulerTests(TestCase):
    def setUp(self):
        self.job = create_job(
            index_set_id=11,
            base_dict={},
            end_time=3000,
            status=ExportJobStatus.READY,
            plan_version=1,
        )
        for part_no, (start, end) in enumerate([(0, 1000), (1000, 2000), (2000, 3000)], start=1):
            ExportPart.objects.create(job=self.job, part_no=part_no, plan_version=1, start_time=start, end_time=end)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=2, global_parallelism=2),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_dispatch_respects_index_limit(self, send, _policy):
        dispatched = dispatch_ready_parts()
        self.assertEqual(len(dispatched), 2)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(ExportPart.objects.filter(status=ExportPartStatus.DISPATCHED).count(), 2)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.RUNNING)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=2, global_parallelism=2),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_dispatch_publish_failure_returns_part_to_waiting(self, send, _policy):
        send.side_effect = RuntimeError("broker down")
        self.assertEqual(dispatch_ready_parts(), [])
        self.assertEqual(ExportPart.objects.filter(status=ExportPartStatus.WAITING).count(), 3)
        self.assertEqual(ExportPart.objects.filter(error_code="DISPATCH_FAILED").count(), 1)

    @patch("apps.log_search.export.scheduler.current_policy", return_value=build_policy(global_parallelism=0))
    @patch("apps.log_search.export.scheduler._send")
    def test_dispatch_refuses_when_global_capacity_is_not_configured(self, send, _policy):
        self.assertEqual(dispatch_ready_parts(), [])
        send.assert_not_called()
        self.assertEqual(ExportPart.objects.filter(status=ExportPartStatus.WAITING).count(), 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=3),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_global_capacity_bounds_total_dispatch(self, send, _policy):
        self.assertEqual(len(dispatch_ready_parts()), 3)
        self.assertEqual(send.call_count, 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_global_capacity_is_shared_by_competing_jobs(self, send, _policy):
        """两个任务同时等待时按 2+2 均分，先到的任务不会一次占满全局槽位。"""
        second = create_job(index_set_id=12, base_dict={}, end_time=2000, status=ExportJobStatus.READY, plan_version=1)
        for part_no, (start, end) in enumerate([(0, 1000), (1000, 2000)], start=1):
            ExportPart.objects.create(job=second, part_no=part_no, plan_version=1, start_time=start, end_time=end)

        self.assertEqual(len(dispatch_ready_parts()), 4)
        self.assertEqual(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.DISPATCHED).count(), 2)
        self.assertEqual(ExportPart.objects.filter(job=second, status=ExportPartStatus.DISPATCHED).count(), 2)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_single_waiting_job_can_borrow_full_global_capacity(self, send, _policy):
        """只有一个任务在等待时它可以借满全局额度，不让槽位闲置。"""
        self.assertEqual(len(dispatch_ready_parts()), 3)
        self.assertEqual(send.call_count, 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_job_without_waiting_parts_does_not_consume_share(self, send, _policy):
        """没有待投递分片的任务不参与额度均分，剩余全局槽位由其他任务借用。"""
        runner = create_job(
            index_set_id=12, base_dict={}, end_time=1000, status=ExportJobStatus.RUNNING, plan_version=1
        )
        ExportPart.objects.create(
            job=runner,
            part_no=1,
            plan_version=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.DISPATCHED,
        )

        # 竞争任务只有 setUp 的任务：全局额度 4 减去在途 1，剩下 3 个都归它
        self.assertEqual(len(dispatch_ready_parts()), 3)
        self.assertEqual(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.DISPATCHED).count(), 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_share_left_by_a_job_is_reclaimed_in_the_same_round(self, send, _policy):
        """前面的任务分片少、用不完自己的份额时，空出的额度当轮就让给后面的任务。"""
        # 本任务只留 1 片：均分份额是 2，但实际只能用掉 1
        ExportPart.objects.filter(job=self.job, part_no__gt=1).delete()
        second = create_job(index_set_id=12, base_dict={}, end_time=5000, status=ExportJobStatus.READY, plan_version=1)
        for part_no, (start, end) in enumerate(
            [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000)], start=1
        ):
            ExportPart.objects.create(job=second, part_no=part_no, plan_version=1, start_time=start, end_time=end)

        self.assertEqual(len(dispatch_ready_parts()), 4)
        self.assertEqual(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.DISPATCHED).count(), 1)
        self.assertEqual(ExportPart.objects.filter(job=second, status=ExportPartStatus.DISPATCHED).count(), 3)

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_planning_only_picks_unplanned_jobs(self, send):
        self.assertEqual(enqueue_planning(10), [])
        create_job(index_set_id=12, status=ExportJobStatus.PENDING)
        self.assertEqual(len(enqueue_planning(10)), 1)

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_finalization_waits_for_all_parts(self, send):
        self.assertEqual(enqueue_finalization(10), [])
        ExportPart.objects.update(status=ExportPartStatus.SUCCESS)
        self.job.status = ExportJobStatus.RUNNING
        self.job.save(update_fields=["status"])
        self.assertEqual(enqueue_finalization(10), [self.job.pk])

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_finalization_ignores_split_parents(self, send):
        """收尾判定只看叶子分片。"""
        ExportPart.objects.filter(part_no=1).update(status=ExportPartStatus.SPLIT)
        ExportPart.objects.filter(part_no__in=[2, 3]).update(status=ExportPartStatus.SUCCESS)
        self.job.status = ExportJobStatus.RUNNING
        self.job.save(update_fields=["status"])
        self.assertEqual(enqueue_finalization(10), [self.job.pk])

    def test_inflight_count_groups_by_index_set(self):
        ExportPart.objects.filter(part_no=1).update(status=ExportPartStatus.DISPATCHED)
        ExportPart.objects.filter(part_no=2).update(status=ExportPartStatus.RUNNING)
        self.assertEqual(_inflight_by_index_set(), {11: 2})

    def test_uploading_part_still_occupies_a_slot(self):
        """上传阶段尚未收尾，仍然占用并行额度。"""
        ExportPart.objects.filter(part_no=1).update(status=ExportPartStatus.UPLOADING)
        self.assertEqual(_inflight_by_index_set(), {11: 1})


@override_settings(USE_REDIS=True)
class CoordinateLockTests(SimpleTestCase):
    """调度任务单轮互斥：上一轮没结束时跳过本轮，不重复发放额度。"""

    @patch("apps.log_search.tasks.sharded_export.coordinate")
    def test_skips_when_another_round_holds_the_lock(self, coordinate):
        cache = MagicMock()
        cache.set.return_value = False
        with patch("apps.utils.lock.cache", cache):
            coordinate_sharded_exports.run()
        coordinate.assert_not_called()
        self.assertEqual(
            cache.set.call_args.kwargs,
            {"timeout": settings.ASYNC_EXPORT_COORDINATE_LOCK_TIMEOUT, "nx": True},
        )

    @patch("apps.log_search.tasks.sharded_export.coordinate")
    def test_runs_and_releases_the_lock(self, coordinate):
        cache = MagicMock()
        cache.set.return_value = True
        cache.get.side_effect = lambda key: cache.set.call_args.args[1]
        with patch("apps.utils.lock.cache", cache):
            coordinate_sharded_exports.run()
        coordinate.assert_called_once_with()
        cache.delete.assert_called_once_with(cache.set.call_args.args[0])

    @override_settings(USE_REDIS=False)
    @patch("apps.log_search.tasks.sharded_export.coordinate")
    def test_runs_without_redis(self, coordinate):
        """没有配置 Redis 时不加锁，本轮照常执行。"""
        cache = MagicMock()
        with patch("apps.utils.lock.cache", cache):
            coordinate_sharded_exports.run()
        coordinate.assert_called_once_with()
        cache.set.assert_not_called()

    @patch("apps.log_search.tasks.sharded_export.coordinate")
    def test_redis_failure_skips_the_round(self, coordinate):
        """Redis 异常时本轮不执行，由下一个调度周期重试。"""
        cache = MagicMock()
        cache.set.side_effect = RedisError("redis down")
        with patch("apps.utils.lock.cache", cache), self.assertRaises(RedisError):
            coordinate_sharded_exports.run()
        coordinate.assert_not_called()


class ControlPipelineTests(SimpleTestCase):
    """规划、调度轮次、分片三类消息各自独占队列：规划排队再久也不会推迟回收、投递和收尾。"""

    def test_queues_are_distinct(self):
        self.assertEqual(len({PART_QUEUE, CONTROL_QUEUE, COORDINATOR_QUEUE}), 3)

    def test_coordinator_tick_has_its_own_queue(self):
        self.assertEqual(coordinate_sharded_exports.options, {"queue": COORDINATOR_QUEUE})
        self.assertEqual(
            app.conf.beat_schedule[coordinate_sharded_exports.name]["options"], {"queue": COORDINATOR_QUEUE}
        )

    def test_planning_is_bounded_before_the_reclaim_window(self):
        """规划软超时必须早于规划超时窗口，否则 Coordinator 会判定超时并重复投递同一份规划。"""
        self.assertEqual(plan_sharded_export.soft_time_limit, PLANNING_SOFT_TIME_LIMIT)
        self.assertLess(PLANNING_SOFT_TIME_LIMIT, settings.ASYNC_EXPORT_PLANNING_TIMEOUT)

    def test_supervisord_consumes_every_queue(self):
        """漏部署任一 worker 会让对应链路整体停摆，队列改动必须同步部署配置。"""
        conf_path = Path(__file__).resolve().parents[3] / "support-files" / "supervisord.conf"
        conf = conf_path.read_text(encoding="utf-8")
        for queue in (PART_QUEUE, CONTROL_QUEUE, COORDINATOR_QUEUE):
            with self.subTest(queue=queue):
                self.assertIn(f"-Q {queue} ", conf)


class JobFailureClassificationTests(TestCase):
    """任务级错误码只表达原因；OVERSIZED 仅用于「已到最小时间精度 + 工作量类原因」。"""

    FAILED_CASES = (
        # 工作量类原因且已到最小精度：只有缩小范围才有意义
        (ExportErrorCode.PART_TIMEOUT, 1000, 500, ExportErrorCode.OVERSIZED_PART_FAILED),
        (ExportErrorCode.UNIFY_QUERY_FAILED, 1000, 500, ExportErrorCode.OVERSIZED_PART_FAILED),
        (ExportErrorCode.PART_RETRIES_EXHAUSTED, 1000, 500, ExportErrorCode.OVERSIZED_PART_FAILED),
        # 存储、投递类原因与数据密度无关，不能被密度文案覆盖
        (ExportErrorCode.UPLOAD_FAILED, 1000, 500, ExportErrorCode.UPLOAD_FAILED),
        (ExportErrorCode.STORAGE_UNSUPPORTED, 1000, 500, ExportErrorCode.STORAGE_UNSUPPORTED),
        # 还能继续细分时保留原始原因，避免把「分片数到上限」误报成密度问题
        (ExportErrorCode.PART_TIMEOUT, 4000, 1, ExportErrorCode.PART_TIMEOUT),
        # 未登记的码不透给前端，否则前端只能拿到空文案
        ("QUERY_FAILED", 1000, 500, ExportErrorCode.PART_EXECUTION_FAILED),
    )

    def fail_single_part_job(self, error_code, span, max_parts):
        """造一个只含单个分片的任务并让它失败，返回刷新后的任务。"""
        job = create_job(
            end_time=span,
            policy={**ExportPolicy().snapshot(), "part_max_attempts": 1, "max_parts": max_parts},
        )
        state.claim_planning(job.pk)
        state.persist_plan(job.pk, parts=[PartSpec(0, span, 10, 10)], estimated_total=10)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code=error_code, retryable=True)
        job.refresh_from_db()
        return job

    def test_part_failure_is_classified_on_the_job(self):
        for error_code, span, max_parts, expected in self.FAILED_CASES:
            with self.subTest(error_code=error_code, span=span, max_parts=max_parts):
                job = self.fail_single_part_job(error_code, span, max_parts)

                self.assertEqual(job.status, ExportJobStatus.FAILED)
                self.assertEqual(job.error_code, expected)
                self.assertTrue(ExportErrorCode.label(job.error_code))

    def test_underlying_part_error_stays_in_the_detail(self):
        job = self.fail_single_part_job(ExportErrorCode.STORAGE_UNSUPPORTED, 1000, 500)

        self.assertEqual(job.error_code, ExportErrorCode.STORAGE_UNSUPPORTED)
        self.assertIn(ExportErrorCode.STORAGE_UNSUPPORTED, job.error_detail)

    def test_job_detail_exposes_detail_and_failed_part(self):
        job = self.fail_single_part_job(ExportErrorCode.PART_TIMEOUT, 1000, 500)

        detail = job_detail(job)

        self.assertEqual(detail["error_code"], ExportErrorCode.OVERSIZED_PART_FAILED)
        self.assertTrue(detail["error_message"])
        self.assertIn(ExportErrorCode.PART_TIMEOUT, detail["error_detail"])
        self.assertEqual(
            detail["failed_part"],
            {
                "part_no": 1,
                "error_code": ExportErrorCode.PART_TIMEOUT,
                "oversized": False,
                "start_time": 0,
                "end_time": 1000,
            },
        )

    def test_successful_job_has_no_failed_part(self):
        self.assertIsNone(job_detail(create_job())["failed_part"])

    def test_list_progress_lookup_stays_a_single_query(self):
        """列表页逐个任务取进度，进度查询必须只占一次查询（叶子计数走注解）。"""
        job = self.fail_single_part_job(ExportErrorCode.PART_TIMEOUT, 1000, 500)
        annotated = ExportJob.objects.annotate(**state.leaf_counts_annotation()).get(pk=job.pk)

        with CaptureQueriesContext(connection) as captured:
            job_detail(annotated)

        part_queries = [query for query in captured.captured_queries if "log_export_part" in query["sql"]]
        self.assertEqual(len(part_queries), 1)


class ManifestChecksumTests(TestCase):
    """清单上传后落库自身 checksum，下载方可以据此校验清单完整性。"""

    def setUp(self):
        self.job = create_job(status=ExportJobStatus.RUNNING, plan_version=1, end_time=1000)
        ExportPart.objects.create(
            job=self.job,
            part_no=1,
            plan_version=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            actual_rows=10,
            actual_bytes=100,
            object_key="part-object",
            checksum="part-checksum",
        )
        state.sync_actual_total(self.job)

    def test_manifest_checksum_matches_the_uploaded_content(self):
        captured = []
        with (
            patch("apps.log_search.export.scheduler.build_storage"),
            patch(
                "apps.log_search.export.scheduler.upload",
                side_effect=lambda _storage, path, _name: captured.append(path.read_bytes()),
            ),
        ):
            finalize_export(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.SUCCESS)
        content = captured[0]
        self.assertEqual(self.job.manifest_bytes, len(content))
        self.assertEqual(self.job.manifest_checksum, hashlib.sha256(content).hexdigest())
        self.assertEqual(self.job.manifest_object_key, manifest_name(self.job))

    def test_manifest_checksum_is_exposed_with_the_download_manifest(self):
        state.finalize_job(
            self.job.pk,
            manifest_object_key="manifest.json",
            manifest_bytes=10,
            manifest_checksum="manifest-checksum",
        )

        results = job_results(ExportJob.objects.get(pk=self.job.pk))
        self.assertEqual(results["manifest"]["checksum"], "manifest-checksum")
        self.assertEqual(results["manifest"]["checksum_algorithm"], "sha256")


class ExportErrorCodeTests(SimpleTestCase):
    """错误分类是给前端展示的稳定契约：新增错误码必须同时登记文案。"""

    def test_every_declared_code_has_a_message(self):
        codes = {value for name, value in vars(ExportErrorCode).items() if name.isupper() and isinstance(value, str)}

        self.assertTrue(codes)
        self.assertTrue(codes <= set(ExportErrorCode.MESSAGES))
        self.assertTrue(all(ExportErrorCode.MESSAGES[code] for code in codes))

    def test_non_splittable_codes_are_all_explained(self):
        self.assertTrue(NON_SPLITTABLE_ERROR_CODES <= set(ExportErrorCode.MESSAGES))

    def test_transient_query_failure_stays_retryable(self):
        """查询失败可能只是链路抖动或分片过重，不能当成「与工作量无关」的错误禁掉时间细分。"""
        self.assertNotIn(ExportErrorCode.UNIFY_QUERY_FAILED, NON_SPLITTABLE_ERROR_CODES)

    def test_unknown_or_empty_code_has_no_message(self):
        self.assertEqual(ExportErrorCode.label("NOT_A_CODE"), "")
        self.assertEqual(ExportErrorCode.label(""), "")


class JobDetailTests(TestCase):
    def test_expired_success_job_is_reported_as_expired(self):
        from apps.log_search.export.api import job_detail

        job = create_job(
            end_time=1000,
            status=ExportJobStatus.SUCCESS,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        detail = job_detail(job)
        self.assertEqual(detail["status"], "EXPIRED")
        self.assertEqual(detail["percent"], 100)
        self.assertEqual(detail["error_code"], ExportErrorCode.FILE_EXPIRED)
        self.assertTrue(detail["error_message"])

    def test_failed_job_exposes_stable_code_and_message(self):
        job = create_job(end_time=1000, status=ExportJobStatus.FAILED, error_code=ExportErrorCode.QUOTA_EXCEEDED)

        detail = job_detail(job)

        self.assertEqual(detail["error_code"], ExportErrorCode.QUOTA_EXCEEDED)
        self.assertEqual(detail["error_message"], ExportErrorCode.label(ExportErrorCode.QUOTA_EXCEEDED))

    def test_canceled_job_is_classified_as_canceled(self):
        job = create_job(end_time=1000, status=ExportJobStatus.CANCELED)

        detail = job_detail(job)

        self.assertEqual(detail["error_code"], ExportErrorCode.CANCELED)
        self.assertTrue(detail["error_message"])

    def test_unfinished_job_has_no_error(self):
        job = create_job(end_time=1000, status=ExportJobStatus.RUNNING)

        detail = job_detail(job)

        self.assertEqual(detail["error_code"], "")
        self.assertEqual(detail["error_message"], "")

    def test_manifest_snapshot_lists_success_parts(self):
        from apps.log_search.export.scheduler import manifest_snapshot

        job = create_job(end_time=1000, status=ExportJobStatus.RUNNING, actual_total=3)
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            actual_rows=3,
            actual_bytes=30,
            compressed_bytes=10,
            object_key="object",
            checksum="checksum",
        )
        snapshot = manifest_snapshot(job, [part])
        self.assertEqual(snapshot["consistency"], "weak_snapshot")
        self.assertEqual(snapshot["parts"][0]["object_key"], "object")
        json.dumps(snapshot)

    def test_job_detail_counts_leaf_parts_only(self):
        from apps.log_search.export.api import job_detail

        job = create_job(end_time=2000, status=ExportJobStatus.RUNNING, plan_version=1)
        parent = ExportPart.objects.create(
            job=job, part_no=1, plan_version=1, start_time=0, end_time=2000, status=ExportPartStatus.SPLIT
        )
        for part_no, (start, end) in enumerate([(0, 1000), (1000, 2000)], start=2):
            ExportPart.objects.create(
                job=job,
                part_no=part_no,
                plan_version=1,
                start_time=start,
                end_time=end,
                parent_part=parent,
                status=ExportPartStatus.SUCCESS,
                actual_rows=10,
            )
        detail = job_detail(job)
        self.assertEqual(detail["parts_total"], 2)
        self.assertEqual(detail["parts_completed"], 2)
        self.assertEqual(detail["plan_version"], 1)


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class ExternalIdentityTests(TestCase):
    """外部请求经代理转发后 request.user 是空间授权人，身份必须取外部用户。"""

    SPACE_UID = "bkcc__2"

    def setUp(self):
        Space.objects.create(
            space_uid=self.SPACE_UID,
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="biz-2",
            bk_tenant_id="tenant-a",
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=755,
            index_set_name="index-755",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )

    def create(self, external_username):
        handler = MagicMock(
            base_dict={"query_list": []},
            origin_order_by=[["dtEventTimeStamp", "desc"]],
            is_desensitize=True,
        )
        with (
            patch("apps.log_search.export.api.is_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.is_definitely_empty", return_value=False),
            patch("apps.log_search.export.api.get_request_username", return_value="authorizer"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=external_username),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            return create_export_job(
                {
                    "space_uid": self.SPACE_UID,
                    "index_set_id": self.index_set.pk,
                    "start_time": 0,
                    "end_time": 2000,
                    "keyword": "*",
                    "addition": [],
                    "ip_chooser": {},
                    "sort_list": [],
                    "export_fields": [],
                }
            )

    def test_external_creator_is_recorded_and_frozen(self):
        job = self.create("external_a")

        self.assertEqual(job.created_by, "external_a")
        self.assertTrue(job.is_external)

    def test_internal_creator_uses_login_username(self):
        job = self.create("")

        self.assertEqual(job.created_by, "authorizer")
        self.assertFalse(job.is_external)

    def get_queryset(self):
        view = ExportJobViewSet()
        view.request = SimpleNamespace(data={"space_uid": self.SPACE_UID}, query_params={})
        return view.get_queryset()

    def make_job(self, created_by):
        return create_job(space_uid=self.SPACE_UID, created_by=created_by, source_app_code=settings.APP_CODE)

    @patch("apps.log_search.views.export_views.get_request_external_username", return_value="external_a")
    def test_external_user_only_sees_own_jobs(self, _external):
        own = self.make_job("external_a")
        self.make_job("external_b")

        self.assertEqual(list(self.get_queryset().values_list("pk", flat=True)), [own.pk])

    @patch("apps.log_search.views.export_views.get_request_external_username", return_value="")
    def test_internal_user_sees_the_whole_space(self, _external):
        own = self.make_job("external_a")
        other = self.make_job("external_b")

        self.assertCountEqual(list(self.get_queryset().values_list("pk", flat=True)), [own.pk, other.pk])

    @patch("apps.log_search.export.api.get_request_username", return_value="authorizer")
    @patch("apps.log_search.export.api.get_request_external_username", return_value="external_a")
    def test_can_operate_follows_external_identity(self, _external, _username):
        from apps.log_search.export.api import job_detail

        own = self.make_job("external_a")
        other = self.make_job("external_b")

        self.assertTrue(job_detail(own)["can_operate"])
        self.assertFalse(job_detail(other)["can_operate"])


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class CreateJobRangeTests(TestCase):
    """导出时间区间不再要求对齐索引集时间精度，与旧异步导出链路保持一致。"""

    def test_range_need_not_align_to_time_precision(self):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="biz-2",
            bk_tenant_id="tenant-a",
        )
        index_set = LogIndexSet.objects.create(
            index_set_id=756,
            index_set_name="index-756",
            space_uid="bkcc__2",
            category_id="application",
            scenario_id=Scenario.LOG,
        )
        handler = MagicMock(base_dict={"query_list": []}, origin_order_by=[], is_desensitize=True)
        with (
            patch("apps.log_search.export.api.is_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.is_definitely_empty", return_value=False),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            job = create_export_job(
                {
                    "space_uid": "bkcc__2",
                    "index_set_id": index_set.pk,
                    "start_time": 1500,
                    "end_time": 3700,
                    "keyword": "*",
                    "addition": [],
                    "ip_chooser": {},
                    "sort_list": [],
                    "export_fields": [],
                }
            )

        self.assertEqual((job.start_time, job.end_time), (1500, 3700))


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class EmptyExportPreCheckTests(TestCase):
    """创建前的存在性预检查：只拒绝确定为空的区间，查询异常一律放行。"""

    SPACE_UID = "bkcc__3"

    def setUp(self):
        Space.objects.create(
            space_uid=self.SPACE_UID,
            bk_biz_id=3,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="3",
            space_name="biz-3",
            bk_tenant_id="tenant-a",
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=757,
            index_set_name="index-757",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )

    def probe(self, *, empty):
        """按空/非空两种返回驱动 create_export_job，并返回是否成功建任务。"""
        handler = MagicMock(base_dict={"query_list": []}, origin_order_by=[], is_desensitize=True)
        with (
            patch("apps.log_search.export.api.is_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.is_definitely_empty", return_value=empty),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            return create_export_job(
                {
                    "space_uid": self.SPACE_UID,
                    "index_set_id": self.index_set.pk,
                    "start_time": 0,
                    "end_time": 2000,
                    "keyword": "*",
                    "addition": [],
                    "ip_chooser": {},
                    "sort_list": [],
                    "export_fields": [],
                }
            )

    def test_empty_result_is_definitely_empty(self):
        handler = MagicMock(base_dict={"query_list": []})

        with patch("apps.log_search.export.planner.UnifyQueryApi.query_ts_raw", return_value={"list": []}):
            self.assertTrue(is_definitely_empty(handler, 0, 1000))

    def test_non_empty_result_is_not_rejected(self):
        handler = MagicMock(base_dict={"query_list": []})

        with patch("apps.log_search.export.planner.UnifyQueryApi.query_ts_raw", return_value={"list": [{"log": "x"}]}):
            self.assertFalse(is_definitely_empty(handler, 0, 1000))

    def test_query_failure_never_rejects(self):
        """预检查不是准入：统计链路抖动时交给 Planner 判定，不能拦住用户。"""
        handler = MagicMock(base_dict={"query_list": []})

        with patch(
            "apps.log_search.export.planner.UnifyQueryApi.query_ts_raw", side_effect=Exception("unify query down")
        ):
            self.assertFalse(is_definitely_empty(handler, 0, 1000))

    def test_unexpected_response_never_rejects(self):
        handler = MagicMock(base_dict={"query_list": []})

        with patch("apps.log_search.export.planner.UnifyQueryApi.query_ts_raw", return_value={"message": "internal"}):
            self.assertFalse(is_definitely_empty(handler, 0, 1000))

    def test_probe_only_requests_one_row(self):
        handler = MagicMock(base_dict={"query_list": []})

        with patch("apps.log_search.export.planner.UnifyQueryApi.query_ts_raw", return_value={"list": []}) as query:
            is_definitely_empty(handler, 0, 1000)

        self.assertEqual(query.call_args.args[0]["limit"], 1)

    def test_empty_range_is_rejected_without_creating_a_job(self):
        with self.assertRaises(PreCheckAsyncExportException):
            self.probe(empty=True)

        self.assertFalse(ExportJob.objects.exists())

    def test_range_with_data_still_creates_the_job(self):
        job = self.probe(empty=False)

        self.assertEqual(job.status, ExportJobStatus.PENDING)
        self.assertEqual(job.index_set_id, self.index_set.pk)


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a", MAX_CONCURRENT_EXPORT_TASKS=3)
class ExportJobAdmissionTests(TestCase):
    """分片导出任务与旧 AsyncTask 共用同一个用户级准入额度，并在同一把锁内占额度。"""

    SPACE_UID = "bkcc__12"

    def setUp(self):
        Space.objects.create(
            space_uid=self.SPACE_UID,
            bk_biz_id=12,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="12",
            space_name="biz-12",
            bk_tenant_id="tenant-a",
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=758,
            index_set_name="index-758",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )

    def create(self, username="tester"):
        """走创建入口建任务；配额不足时由准入校验抛异常。"""
        handler = MagicMock(base_dict={"query_list": []}, origin_order_by=[], is_desensitize=True)
        with (
            patch("apps.log_search.export.api.is_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.is_definitely_empty", return_value=False),
            patch("apps.log_search.export.api.get_request_username", return_value=username),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            return create_export_job(
                {
                    "space_uid": self.SPACE_UID,
                    "index_set_id": self.index_set.pk,
                    "start_time": 0,
                    "end_time": 2000,
                    "keyword": "*",
                    "addition": [],
                    "ip_chooser": {},
                    "sort_list": [],
                    "export_fields": [],
                }
            )

    def test_export_jobs_count_towards_the_user_limit(self):
        for _ in range(3):
            create_job(created_by="tester", status=ExportJobStatus.RUNNING)

        with self.assertRaises(ConcurrentExportLimitException):
            self.create()

        self.assertEqual(ExportJob.objects.filter(created_by="tester").count(), 3)

    def test_old_and_new_tasks_share_one_budget(self):
        for _ in range(2):
            AsyncTask.objects.create(
                created_by="tester",
                scenario_id=Scenario.LOG,
                request_param={"index_set_ids": [1]},
                export_type=ExportType.ASYNC,
                export_status=ExportStatus.DOWNLOAD_LOG,
            )
        create_job(created_by="tester", status=ExportJobStatus.PLANNING)

        with self.assertRaises(ConcurrentExportLimitException):
            self.create()

    def test_terminal_job_releases_the_quota(self):
        for _ in range(3):
            create_job(created_by="tester", status=ExportJobStatus.CANCELED)

        self.assertEqual(self.create().status, ExportJobStatus.PENDING)

    def test_other_user_quota_is_isolated(self):
        for _ in range(3):
            create_job(created_by="other", status=ExportJobStatus.RUNNING)

        self.assertEqual(self.create().status, ExportJobStatus.PENDING)

    @override_settings(USE_REDIS=True)
    def test_create_occupies_the_shared_user_lock(self):
        lock = Mock()
        lock.acquire.return_value = True

        with patch("apps.log_search.models.cache.lock", return_value=lock) as mock_cache_lock:
            job = self.create()

        lock.acquire.assert_called_once_with()
        lock.release.assert_called_once_with()
        self.assertEqual(mock_cache_lock.call_args.args[0], AsyncTask.export_create_lock_key("tester"))
        self.assertEqual(job.created_by, "tester")

    @override_settings(USE_REDIS=True)
    def test_busy_lock_rejects_creation_without_persisting(self):
        lock = Mock()
        lock.acquire.return_value = False

        with patch("apps.log_search.models.cache.lock", return_value=lock):
            with self.assertRaises(AsyncExportRequestBusyException):
                self.create()

        lock.release.assert_not_called()
        self.assertFalse(ExportJob.objects.exists())

    @override_settings(USE_REDIS=True)
    def test_redis_failure_falls_back_to_non_atomic_check(self):
        lock = Mock()
        lock.acquire.side_effect = RedisError("redis down")

        with patch("apps.log_search.models.cache.lock", return_value=lock):
            job = self.create()

        lock.release.assert_not_called()
        self.assertEqual(job.status, ExportJobStatus.PENDING)


class DownloadLinkTests(TestCase):
    """下载链接由对象存储预签名，不经过应用内下载路由。"""

    def setUp(self):
        self.job = create_job(
            end_time=1000,
            status=ExportJobStatus.SUCCESS,
            expires_at=timezone.now() + timedelta(seconds=600),
            manifest_object_key="manifest.json",
            is_external=True,
        )
        ExportPart.objects.create(
            job=self.job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            object_key="part.tar.gz",
        )

    def sign(self, artifact_id):
        with patch("apps.log_search.export.api.build_storage") as build_storage:
            build_storage.return_value.generate_download_url.return_value = "https://cos.example/x"
            return download_link(self.job, artifact_id), build_storage

    def test_manifest_link_uses_job_storage_config(self):
        result, build_storage = self.sign("manifest")
        signed = build_storage.return_value.generate_download_url.call_args.kwargs

        self.assertEqual(result["url"], "https://cos.example/x")
        build_storage.assert_called_once_with(external=True)
        self.assertEqual(signed["file_name"], "manifest.json")
        self.assertGreater(signed["expired"], 0)

    def test_part_link_targets_the_part_object(self):
        part = ExportPart.objects.get(job=self.job)

        _, build_storage = self.sign(str(part.pk))
        signed = build_storage.return_value.generate_download_url.call_args.kwargs

        self.assertEqual(signed["file_name"], "part.tar.gz")
