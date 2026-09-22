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

import json
import tempfile
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.log_search.constants import ExportJobStatus, ExportPartStatus
from apps.log_search.export import state
from apps.log_search.export.config import ExportPolicy
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.worker import _pack, _write_rows
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
    cleanup_artifacts,
    dispatch_ready_parts,
    enqueue_finalization,
    enqueue_planning,
)
from apps.log_search.export.storage import artifact_name, manifest_name


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
    """build_parts 是规划链路的契约点：返回 (parts, total, interval) 且完整覆盖任务区间。"""

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

    def test_returns_parts_total_and_interval_for_the_whole_range(self):
        parts, total, interval = self.plan_with(total=40, buckets={0: 40}, sample=[b"x" * 20])

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(total, 40)
        self.assertEqual(parts[0].estimated_rows, 40)
        self.assertEqual(parts[0].estimated_bytes, 800)
        self.assertGreaterEqual(interval, self.job.time_tick)
        self.assertEqual(interval % self.job.time_tick, 0)

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
        parts, total, interval = self.plan_with(total=0, buckets={})

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 4000)])
        self.assertEqual(total, 0)
        self.assertGreater(interval, 0)


class RunPlanningTests(TestCase):
    """规划必须真的把任务推进到 READY —— 覆盖 build_parts 返回值契约被破坏的回归场景。"""

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
        self.assertEqual(job.part_total, 1)
        self.assertEqual(job.estimated_total, 40)
        self.assertIsNotNone(job.interval)
        self.assertIsNotNone(job.statistics_at)
        part = ExportPart.objects.get(job=job)
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
        return state.persist_plan(
            self.job.pk,
            parts=parts,
            estimated_total=40,
            interval=30000,
        )

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
        self.assertEqual(job.part_total, 4)
        self.assertEqual(ExportPart.objects.filter(job=job).count(), 4)

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
        self.assertEqual(job.part_success, 4)
        self.assertEqual(job.actual_total, 40)
        self.assertIsNotNone(state.finalize_job(job.pk, manifest_object_key="manifest", manifest_bytes=10))
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.SUCCESS)
        self.assertIsNotNone(job.expires_at)

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
        self.assertIsNone(state.finalize_job(self.job.pk, manifest_object_key="manifest", manifest_bytes=1))

    def test_cancel_job_cancels_waiting_parts(self):
        self.plan()
        state.cancel_job(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.CANCELED)
        self.assertFalse(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.WAITING).exists())

    def test_planning_attempt_budget_is_taken_from_job_policy(self):
        self.job.policy = {**ExportPolicy().snapshot(), "planning_attempts": 1}
        self.job.save(update_fields=["policy"])
        self.assertIsNotNone(state.claim_planning(self.job.pk))
        state.fail_planning(self.job.pk, "STATISTICS_FAILED", retryable=True)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)


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


@override_settings(ASYNC_EXPORT_COORDINATE_BATCH=10)
class SchedulerTests(TestCase):
    def setUp(self):
        self.job = create_job(
            index_set_id=11,
            base_dict={},
            end_time=3000,
            status=ExportJobStatus.READY,
            part_total=3,
        )
        for part_no, (start, end) in enumerate([(0, 1000), (1000, 2000), (2000, 3000)], start=1):
            ExportPart.objects.create(job=self.job, part_no=part_no, start_time=start, end_time=end)

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

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_planning_only_picks_unplanned_jobs(self, send):
        self.assertEqual(enqueue_planning(10), [])
        create_job(index_set_id=12, status=ExportJobStatus.PENDING)
        self.assertEqual(len(enqueue_planning(10)), 1)

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_finalization_waits_for_all_parts(self, send):
        ExportPart.objects.update(status=ExportPartStatus.SUCCESS)
        self.job.part_success = 3
        self.job.status = ExportJobStatus.RUNNING
        self.job.save(update_fields=["part_success", "status"])
        self.assertEqual(enqueue_finalization(10), [self.job.pk])

    def test_cleanup_registers_expired_job_once(self):
        self.job.status = ExportJobStatus.SUCCESS
        self.job.expires_at = timezone.now() + timedelta(seconds=60)
        self.job.save(update_fields=["status", "expires_at"])

        # 未过期不登记
        self.assertEqual(cleanup_artifacts(10), [])
        ExportJob.objects.filter(pk=self.job.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(cleanup_artifacts(10), [self.job.pk])
        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.artifacts_cleaned_at)
        # 已登记的任务不再重复扫描
        self.assertEqual(cleanup_artifacts(10), [])

    def test_cleanup_defers_job_with_inflight_parts(self):
        ExportPart.objects.filter(part_no=1).update(status=ExportPartStatus.RUNNING)
        self.job.status = ExportJobStatus.CANCELED
        self.job.save(update_fields=["status"])

        self.assertEqual(cleanup_artifacts(10), [])
        self.job.refresh_from_db()
        self.assertIsNone(self.job.artifacts_cleaned_at)

    def test_inflight_count_groups_by_index_set(self):
        ExportPart.objects.filter(part_no=1).update(status=ExportPartStatus.DISPATCHED)
        ExportPart.objects.filter(part_no=2).update(status=ExportPartStatus.RUNNING)
        self.assertEqual(_inflight_by_index_set(), {11: 2})


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
