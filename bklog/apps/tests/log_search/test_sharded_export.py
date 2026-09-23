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
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.constants import RemoteStorageType
from apps.log_search.constants import (
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    ExportJobStatus,
    ExportPlanStatus,
    ExportPartStatus,
    ExportStage,
)
from apps.log_search.export import state
from apps.log_search.export.config import ExportPolicy
from apps.log_search.export.api import create_export_job, download_link, job_results
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.models import LogIndexSet, Scenario, Space
from apps.log_search.views.export_views import ExportJobViewSet
from apps.log_search.export.worker import _execute, _pack, _write_rows, run_part
from apps.log_search.export.planner import (
    PlanError,
    PartSpec,
    build_parts,
    choose_interval,
    merge_adjacent,
    refine,
    run_planning,
)
from apps.log_search.export.scheduler import (
    _inflight_by_index_set,
    dispatch_ready_parts,
    enqueue_finalization,
    enqueue_planning,
    finalize_export,
)
from apps.log_search.export.storage import UnsupportedExportStorage, artifact_name, build_storage, manifest_name


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
        "time_tick": 1000,
        "status": ExportJobStatus.PENDING,
    }
    values.update(overrides)
    return ExportJob.objects.create(**values)


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
            job=job, part_no=1, start_time=0, end_time=1000, status=ExportPartStatus.RUNNING
        )
        with (
            patch("apps.log_search.export.worker.build_storage") as build_storage,
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_search.export.worker.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker.upload"),
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
        ):
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(job, part)

        build_storage.assert_called_once_with(external=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)
        self.assertEqual(part.object_key, artifact_name(job, 1))

    @override_settings(ASYNC_EXPORT_UPLOAD_ATTEMPTS=3, ASYNC_EXPORT_UPLOAD_RETRY_INTERVAL_SECONDS=1)
    def test_execute_retries_upload_without_requerying(self):
        """上传抖动只重试上传本身：不重新查询、不重新压缩，退避按尝试次数递增。"""
        job = create_job(status=ExportJobStatus.RUNNING, end_time=1000)
        part = ExportPart.objects.create(
            job=job, part_no=1, start_time=0, end_time=1000, status=ExportPartStatus.RUNNING
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
            _execute(job, part)

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
            run_part(part.pk)

        self.assertEqual(upload.call_count, 2)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.error_code, "UPLOAD_FAILED")


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
            state.claim_part(part.pk)
            state.complete_part(
                part.pk,
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
        state.claim_part(part.pk)
        state.fail_part(part.pk, error_code="QUERY_FAILED", retryable=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.task_id, "")

    def test_exhausted_part_fails_the_job(self):
        self.job.policy = {**ExportPolicy().snapshot(), "part_max_attempts": 1}
        self.job.save(update_fields=["policy"])
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        state.claim_part(part.pk)
        state.fail_part(part.pk, error_code="QUERY_FAILED", retryable=True)
        part.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.FAILED)
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)

    @override_settings(ASYNC_EXPORT_PART_TIMEOUT=1)
    def test_recover_stale_parts_requeues_timeout_part(self):
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        state.claim_part(part.pk)
        ExportPart.objects.filter(pk=part.pk).update(started_at=timezone.now() - timedelta(seconds=10))
        self.assertEqual(state.recover_stale_parts(), [part.pk])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.error_code, "PART_TIMEOUT")

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
        state.claim_part(part.pk)

        state.set_stage(part.pk, ExportStage.PACKAGE)
        self.assertEqual(ExportPart.objects.get(pk=part.pk).status, ExportPartStatus.RUNNING)

        state.set_stage(part.pk, ExportStage.UPLOAD)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.UPLOADING)
        self.assertEqual(part.stage, ExportStage.UPLOAD)

    def test_uploading_part_can_still_complete(self):
        """上传阶段仍是可回填结果的运行态，重新进入上传阶段不会让回填失效。"""
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "task")
        state.claim_part(part.pk)
        state.set_stage(part.pk, ExportStage.UPLOAD)

        self.assertIsNotNone(
            state.complete_part(
                part.pk, actual_rows=10, actual_bytes=100, compressed_bytes=50, object_key="object", checksum="sum"
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
        state.claim_part(part.pk)
        state.set_stage(part.pk, ExportStage.UPLOAD)
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
        state.claim_part(part.pk)
        state.fail_part(part.pk, error_code=error_code, error_detail="执行超时", retryable=True)
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

    def test_part_at_time_precision_fails_the_job_with_oversized_error(self):
        job = create_job(end_time=1000, policy={**ExportPolicy().snapshot(), "part_max_attempts": 1})
        state.claim_planning(job.pk)
        state.persist_plan(job.pk, parts=[PartSpec(0, 1000, 40, 4000, oversized=True)], estimated_total=40)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        state.claim_part(part.pk)
        state.fail_part(part.pk, error_code="PART_TIMEOUT", retryable=True)

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
        state.claim_part(part.pk)
        state.fail_part(part.pk, error_code="PART_TIMEOUT", retryable=True)

        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.FAILED)

    def test_children_take_over_the_leaf_scope(self):
        parent = self.fail_first_part()
        for child in self.children_of(parent):
            state.dispatch_part(child.pk, f"task-{child.pk}")
            state.claim_part(child.pk)
            state.complete_part(
                child.pk,
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
                parent.pk, actual_rows=40, actual_bytes=400, compressed_bytes=1, object_key="stale", checksum="c"
            )
        )
        parent.refresh_from_db()
        self.assertEqual(parent.object_key, "")
        self.assertEqual(parent.status, ExportPartStatus.SPLIT)


class ArtifactNameTests(SimpleTestCase):
    """产物名必须是 (job, part_no) 的纯函数，否则重试会留下无人引用的孤儿对象。"""

    def test_artifact_name_is_deterministic_per_job_and_part(self):
        job = SimpleNamespace(index_set_id=7, pk=11)

        first = artifact_name(job, 3)

        self.assertEqual(first, artifact_name(job, 3))
        self.assertTrue(first.endswith("_11_3.tar.gz"))
        self.assertNotEqual(first, artifact_name(job, 4))

    def test_manifest_name_is_deterministic(self):
        job = SimpleNamespace(index_set_id=7, pk=11)

        self.assertEqual(manifest_name(job), manifest_name(job))


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
            patch("apps.log_search.export.api.resolve_time_tick", return_value=1000),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
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
        with (
            patch("apps.log_search.export.api.build_storage") as build_storage,
            patch("apps.log_search.export.api.download_url", return_value="https://cos.example/x") as download_url,
        ):
            return download_link(self.job, artifact_id), build_storage, download_url

    def test_manifest_link_uses_job_storage_config(self):
        result, build_storage, download_url = self.sign("manifest")

        self.assertEqual(result["url"], "https://cos.example/x")
        build_storage.assert_called_once_with(external=True)
        self.assertEqual(download_url.call_args.args[1], "manifest.json")
        self.assertGreater(download_url.call_args.args[2], 0)

    def test_part_link_targets_the_part_object(self):
        part = ExportPart.objects.get(job=self.job)

        _, _, download_url = self.sign(str(part.pk))

        self.assertEqual(download_url.call_args.args[1], "part.tar.gz")
