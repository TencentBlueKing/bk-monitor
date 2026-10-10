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

import copy
import gzip
import hashlib
import io
import itertools
import json
import tempfile
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from blueapps.core.celery.celery import app
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from qcloud_cos.streambody import StreamBody
from redis.exceptions import RedisError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.api.exception import DataAPIException
from apps.constants import RemoteStorageType
from apps.utils.cos import QcloudCos
from apps.iam import ActionEnum
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_search.constants import (
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    WORKLOAD_ERROR_CODES,
    ExportErrorCode,
    ExportJobStatus,
    ExportPlanStatus,
    ExportPartStatus,
    ExportStage,
    ExportSearchType,
    ExportStatus,
    ExportType,
    IndexSetType,
)
from apps.log_search.exceptions import (
    AsyncExportRequestBusyException,
    ConcurrentExportLimitException,
    PreCheckAsyncExportException,
)
from apps.log_search.export import state
from apps.log_search.export.config import (
    COORDINATOR_QUEUE,
    FINALIZE_QUEUE,
    PART_QUEUE,
    PART_TASK_NAME,
    PLAN_QUEUE,
    ExportPolicy,
)
from apps.log_search.export.api import create_export_job, download_link
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.models import AsyncTask, LogIndexSet, Scenario, Space
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_search.views.export_views import ExportJobIndexSearchPermission, ExportJobViewSet
from apps.log_search.views.search_views import SearchViewSet
from apps.log_search.views.scene_search_views import SceneSearchViewSet
from apps.log_search.export.worker import PartError, _execute, _pack, _write_rows, run_part
from apps.log_search.export.planner import (
    INTERVAL_LADDER_MS,
    PlanError,
    PartSpec,
    build_handler,
    build_parts,
    choose_interval,
    choose_refine_interval,
    merge_adjacent,
    plan_hot_segment,
    refine,
    run_planning,
)
from apps.log_search.export.scheduler import (
    _inflight_by_index_set,
    _send,
    coordinate,
    dispatch_ready_parts,
    enqueue_finalization,
    enqueue_planning,
    finalize_export,
    finalizing_jobs,
)
from apps.log_search.export.merger import merge_export_parts
from apps.log_search.export.storage import (
    UnsupportedExportStorage,
    artifact_name,
    build_storage,
    job_object_prefix,
    manifest_name,
    merged_name,
)
from apps.log_search.tasks.sharded_export import (
    coordinate_sharded_exports,
    execute_sharded_export_part,
    finalize_sharded_export,
    plan_sharded_export,
)


def build_policy(**overrides):
    """按测试需要覆盖 ExportPolicy 的默认值。"""
    return replace(ExportPolicy(), **overrides)


def create_job(**overrides):
    index_set_id = overrides.pop("index_set_id", None)
    index_set_ids = overrides.get("index_set_ids") or overrides.get("search_params", {}).get("index_set_ids")
    index_set_ids = index_set_ids or [index_set_id or 1]
    values = {
        "space_uid": "bkcc__2",
        "created_by": "tester",
        "index_set_ids": index_set_ids,
        "search_params": {"index_set_ids": index_set_ids},
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

    # 复用真实 Handler 的导出原语，让 mock 目标与生产调用路径保持一致
    export_result_window = UnifyQueryHandler.export_result_window
    project_export_rows = UnifyQueryHandler.project_export_rows
    export_scroll_batch = UnifyQueryHandler.export_scroll_batch

    def _deal_query_result(self, result):
        return {"origin_log_list": [{"value": row} for row in result["list"]]}


class PolicyBoundsTests(SimpleTestCase):
    """FeatureConfig 没有 Schema，_BOUNDS 是唯一的字段白名单。"""

    def test_every_policy_field_is_registered_in_bounds(self):
        """漏登记的字段会被 _validated_policy 静默丢弃，运维配的值不生效也不报错。"""
        from apps.log_search.export import config

        self.assertEqual(set(ExportPolicy().snapshot()), set(config._BOUNDS))

    def test_default_policy_is_dispatchable_without_extra_config(self):
        """部署后只配灰度业务即可投递：环境容量默认值为正，空配置也不会退回停投。"""
        from apps.log_search.export import config

        self.assertGreater(config.ExportPolicy().global_parallelism, 0)
        for raw in (None, {}):
            self.assertGreater(config._validated_policy(raw).global_parallelism, 0)

    def test_oversized_limit_rejects_an_unusable_value(self):
        """0 会让 oversized 分片永远投不出去，非法值必须回落到默认额度。"""
        from apps.log_search.export import config

        for field in ("oversized_parallelism", "oversized_global_parallelism"):
            default = getattr(ExportPolicy(), field)
            for invalid in (0, "many"):
                policy = config._validated_policy({field: invalid})
                self.assertEqual(getattr(policy, field), default)
            self.assertEqual(getattr(config._validated_policy({field: 3}), field), 3)


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


class HotSegmentTests(SimpleTestCase):
    def test_refine_interval_follows_the_density_of_the_segment(self):
        policy = build_policy(target_rows=1000, max_buckets=500)

        # 段内 5000 条、跨度 100 秒：按每片目标 1000 条反推，约 20 秒一个桶
        interval = choose_refine_interval(5000, 100_000, 1, 1000, policy)

        self.assertEqual(interval, 20_000)

    def test_refine_interval_is_bounded_by_the_bucket_limit(self):
        policy = build_policy(target_rows=1000, max_buckets=10)

        interval = choose_refine_interval(1_000_000, 100_000, 1, 1000, policy)

        self.assertEqual(interval, 10_000)
        self.assertLessEqual(100_000 // interval, policy.max_buckets)

    def test_refine_interval_uses_the_stricter_byte_target(self):
        policy = build_policy(target_rows=1000, target_bytes=1000)

        self.assertEqual(choose_refine_interval(1000, 100_000, 10, 1000, policy), 10_000)

    def test_segment_at_the_step_is_handed_to_binary_split(self):
        """段宽已到最小步长时没有更细的粒度可统计，直接交给二分而不是发出非法统计窗口。"""
        policy = build_policy(target_rows=100, split_factor=2.0)

        parts = plan_hot_segment(None, [(0, 1000, 1000)], 1, policy, 1000)

        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 1000)])
        self.assertTrue(parts[0].oversized)

    def test_unsupported_finer_window_uses_binary_split_directly(self):
        policy = build_policy(target_rows=100, split_factor=2.0, split_step_ms=100)
        with (
            patch("apps.log_search.export.planner.histogram") as histogram,
            patch("apps.log_search.export.planner.count_rows", side_effect=[100, 100]) as count_rows_mock,
        ):
            parts = plan_hot_segment(None, [(0, 1000, 200)], 1, policy, 1000)

        histogram.assert_not_called()
        self.assertEqual(count_rows_mock.call_count, 2)
        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 500), (500, 1000)])

    def test_consecutive_buckets_at_the_step_reuse_initial_counts(self):
        policy = build_policy(target_rows=100, target_bytes=10**9)
        segment = [(start, start + 1000, 200) for start in range(0, 4000, 1000)]
        with (
            patch("apps.log_search.export.planner.histogram") as histogram_mock,
            patch("apps.log_search.export.planner.count_rows") as count_rows_mock,
        ):
            parts = plan_hot_segment(None, segment, 1, policy, 1000)

        histogram_mock.assert_not_called()
        count_rows_mock.assert_not_called()
        self.assertEqual([(part.start_time, part.end_time, part.estimated_rows) for part in parts], segment)
        self.assertTrue(all(part.oversized for part in parts))

    def test_bucket_limit_falls_back_to_each_initial_bucket(self):
        policy = build_policy(target_rows=100, target_bytes=10**9, max_buckets=2)
        with (
            patch("apps.log_search.export.planner.histogram") as histogram_mock,
            patch("apps.log_search.export.planner.count_rows", return_value=100) as count_rows_mock,
        ):
            parts = plan_hot_segment(None, [(0, 2000, 200), (2000, 4000, 200)], 1, policy, 2000)

        histogram_mock.assert_not_called()
        self.assertCountEqual(
            [call.args[1:] for call in count_rows_mock.call_args_list],
            [(1000, 2000), (0, 1000), (3000, 4000), (2000, 3000)],
        )
        self.assertEqual(
            [(part.start_time, part.end_time) for part in parts],
            [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000)],
        )

    def test_empty_refined_histogram_is_retryable(self):
        policy = build_policy(target_rows=100)
        with patch("apps.log_search.export.planner.histogram", return_value={}):
            with self.assertRaises(PlanError) as context:
                plan_hot_segment(None, [(0, 4000, 400)], 1, policy, 4000)

        self.assertEqual(context.exception.code, "STATISTICS_FAILED")
        self.assertTrue(context.exception.retryable)

    def test_residual_hot_bucket_returns_to_binary_split(self):
        policy = build_policy(target_rows=100, target_bytes=10**9)
        with patch("apps.log_search.export.planner.histogram", return_value={0: 300}):
            parts = plan_hot_segment(None, [(0, 3000, 300)], 1, policy, 3000)

        self.assertEqual((parts[0].start_time, parts[0].end_time), (0, 1000))
        self.assertTrue(parts[0].oversized)
        self.assertEqual(parts[-1].end_time, 3000)

    def test_residual_hot_bucket_queries_binary_halves(self):
        policy = build_policy(target_rows=100, target_bytes=10**9)
        with (
            patch("apps.log_search.export.planner.histogram", return_value={0: 250, 2000: 50}) as histogram_mock,
            patch("apps.log_search.export.planner.count_rows", return_value=125) as count_rows_mock,
        ):
            parts = plan_hot_segment(None, [(0, 6000, 300)], 1, policy, 6000)

        histogram_mock.assert_called_once_with(None, 0, 6000, 2000)
        self.assertCountEqual([call.args[1:] for call in count_rows_mock.call_args_list], [(1000, 2000), (0, 1000)])
        self.assertEqual(
            [(part.start_time, part.end_time, part.estimated_rows) for part in parts],
            [(0, 1000, 125), (1000, 2000, 125), (2000, 4000, 50), (4000, 6000, 0)],
        )
        self.assertTrue(all(not part.oversized for part in parts))


class PlannerFlowTests(SimpleTestCase):
    def plan(self, initial, refined, policy, *, interval, end, total):
        job = SimpleNamespace(start_time=0, end_time=end)
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=total),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"x"]),
            patch("apps.log_search.export.planner.choose_interval", return_value=interval),
            patch("apps.log_search.export.planner.histogram", side_effect=[initial, *refined]) as histogram_mock,
        ):
            parts, _, _ = build_parts(job, policy)
        return parts, histogram_mock

    def test_consecutive_hot_buckets_use_one_refined_histogram(self):
        policy = build_policy(target_rows=100, target_bytes=10**9)
        parts, histogram_mock = self.plan(
            {0: 10, 2000: 200, 4000: 200, 6000: 10},
            [{2000: 100, 3000: 100, 4000: 100, 5000: 100}],
            policy,
            interval=2000,
            end=8000,
            total=420,
        )

        self.assertEqual(histogram_mock.call_count, 2)
        self.assertEqual(histogram_mock.call_args.args[1:3], (2000, 6000))
        self.assertEqual(sum(part.estimated_rows for part in parts), 420)
        self.assertEqual(parts[0].start_time, 0)
        self.assertEqual(parts[-1].end_time, 8000)
        self.assertTrue(all(left.end_time == right.start_time for left, right in zip(parts, parts[1:])))

    def test_normal_bucket_between_hot_runs_is_not_queried_twice(self):
        policy = build_policy(target_rows=100, target_bytes=10**9)
        parts, histogram_mock = self.plan(
            {0: 200, 2000: 10, 4000: 200},
            [{0: 100, 1000: 100}, {4000: 100, 5000: 100}],
            policy,
            interval=2000,
            end=6000,
            total=410,
        )

        self.assertEqual(
            [call.args[1:3] for call in histogram_mock.call_args_list], [(0, 6000), (0, 2000), (4000, 6000)]
        )
        self.assertEqual(sum(part.estimated_rows for part in parts), 410)
        self.assertTrue(all(left.end_time == right.start_time for left, right in zip(parts, parts[1:])))

    def test_part_limit_is_checked_after_adjacent_merge(self):
        policy = build_policy(target_rows=100, target_bytes=10**9, max_parts=2)
        parts, _ = self.plan(
            {0: 10, 2000: 200},
            [{2000: 100, 3000: 100}],
            policy,
            interval=2000,
            end=4000,
            total=210,
        )

        self.assertEqual(len(parts), 2)
        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 3000), (3000, 4000)])

    def test_part_limit_stops_before_querying_later_hot_segments(self):
        policy = build_policy(target_rows=100, target_bytes=10**9, max_parts=2)
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=610),
            patch("apps.log_search.export.planner.sample_rows", return_value=[b"x"]),
            patch("apps.log_search.export.planner.choose_interval", return_value=2000),
            patch(
                "apps.log_search.export.planner.histogram",
                side_effect=[
                    {0: 200, 2000: 200, 4000: 10, 6000: 200},
                    {0: 100, 1000: 100, 2000: 100, 3000: 100},
                ],
            ) as histogram_mock,
        ):
            with self.assertRaises(PlanError) as context:
                build_parts(SimpleNamespace(start_time=0, end_time=8000), policy)

        self.assertEqual(context.exception.code, "PART_LIMIT_EXCEEDED")
        self.assertEqual([call.args[1:3] for call in histogram_mock.call_args_list], [(0, 8000), (0, 4000)])


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

    def test_hot_segment_is_covered_by_a_single_refined_histogram(self):
        """首轮热点桶合并成一段后只再统计一次，段内时间既不被跳过也不被重复切分。"""
        policy = build_policy(target_rows=100, target_bytes=10**9, split_factor=2.0)
        job = create_job(policy=policy.snapshot())
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=400),
            patch("apps.log_search.export.planner.sample_rows", return_value=[]),
            patch("apps.log_search.export.planner.choose_interval", return_value=2000),
            patch(
                "apps.log_search.export.planner.histogram",
                side_effect=[{0: 200, 2000: 200}, {0: 100, 1000: 100, 2000: 100, 3000: 100}],
            ) as histogram_mock,
        ):
            parts, total, _ = build_parts(job, policy)

        self.assertEqual(histogram_mock.call_count, 2)
        self.assertEqual(
            [(part.start_time, part.end_time) for part in parts], [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000)]
        )
        self.assertEqual(total, 400)

    def test_residual_hot_part_falls_back_to_binary_split(self):
        """细化后仍超标的桶交回二分，并带上策略配置的切分步长。"""
        policy = build_policy(target_rows=100, split_factor=2.0, split_step_ms=1000)
        job = create_job(policy=policy.snapshot())
        with (
            patch("apps.log_search.export.planner.build_handler"),
            patch("apps.log_search.export.planner.count_rows", return_value=300),
            patch("apps.log_search.export.planner.sample_rows", return_value=[]),
            patch("apps.log_search.export.planner.choose_interval", return_value=3000),
            patch("apps.log_search.export.planner.histogram", side_effect=[{0: 300}, {0: 300}]),
            patch(
                "apps.log_search.export.planner.refine",
                wraps=refine,
            ) as refine_mock,
        ):
            parts, _, _ = build_parts(job, policy)

        self.assertTrue(refine_mock.call_args_list)
        self.assertTrue(all(call.args[4] == 1000 for call in refine_mock.call_args_list))
        self.assertEqual([(part.start_time, part.end_time) for part in parts], [(0, 1000), (1000, 4000)])
        self.assertTrue(parts[0].oversized)

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

        # 查询侧右端点收窄 1 毫秒
        self.assertEqual((handler.base_dict["start_time"], handler.base_dict["end_time"]), ("1000", "1999"))
        self.assertEqual(handler_cls.call_args.args[0]["start_time"], 0)

    def test_union_part_keeps_all_routes_when_time_is_narrowed(self):
        job = create_job(
            search_params={"index_set_ids": [11, 12], "start_time": 0, "end_time": 4000},
            base_dict={
                "start_time": "0",
                "end_time": "4000",
                "query_list": [{"reference_name": "a"}, {"reference_name": "b"}],
                "metric_merge": "a + b",
            },
        )
        with patch("apps.log_search.export.planner.UnifyQueryHandler") as handler_cls:
            handler = build_handler(job, 1000, 2000)

        self.assertEqual(handler_cls.call_args.args[0]["index_set_ids"], [11, 12])
        self.assertEqual(len(handler.base_dict["query_list"]), 2)
        self.assertEqual(handler.base_dict["metric_merge"], "a + b")
        # 查询侧右端点收窄 1 毫秒
        self.assertEqual((handler.base_dict["start_time"], handler.base_dict["end_time"]), ("1000", "1999"))


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

    @override_settings(ASYNC_EXPORT_PLANNING_TIMEOUT=1)
    def test_run_planning_skips_a_job_that_exhausted_its_attempts(self):
        """认领次数耗尽时任务已被判失败，规划不应再白跑一遍统计查询。"""
        job = create_job(policy={**ExportPolicy().snapshot(), "planning_attempts": 1})
        state.claim_planning(job.pk)
        ExportJob.objects.filter(pk=job.pk).update(planning_started_at=timezone.now() - timedelta(seconds=10))

        with patch("apps.log_search.export.planner.build_parts") as build_parts_mock:
            run_planning(job.pk)

        build_parts_mock.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.FAILED)
        self.assertEqual(job.error_code, ExportErrorCode.PLANNING_RETRIES_EXHAUSTED)
        self.assertFalse(ExportPart.objects.filter(job=job).exists())


class PartRunnerTests(TestCase):
    def test_write_rows_streams_until_done(self):
        responses = [
            {"list": [{"v": 1}, {"v": 2}], "done": False},
            {"list": [{"v": 3}], "done": True},
            {"list": [{"v": 4}], "done": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            payload = Path(directory) / "logs.jsonl"
            with patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api:
                api.query_ts_raw_with_scroll.side_effect = responses
                rows, size = _write_rows(FakeHandler(), payload)
            lines = payload.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(rows, 3)
        self.assertEqual(len(lines), 3)
        self.assertEqual(size, sum(len(line.encode("utf-8")) + 1 for line in lines))
        self.assertEqual(api.query_ts_raw_with_scroll.call_count, 2)

    def test_write_rows_stops_on_empty_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api:
                api.query_ts_raw_with_scroll.side_effect = [{"list": [], "done": False}]
                rows, size = _write_rows(FakeHandler(), Path(directory) / "logs.jsonl")
        self.assertEqual((rows, size), (0, 0))

    def test_pack_puts_single_log_member(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "logs.jsonl").write_bytes(b"{}\n")
            archive = _pack(directory, SimpleNamespace(part_no=7))
            self.assertEqual(archive.name, "part-7.jsonl.gz")
            self.assertGreater(archive.stat().st_size, 0)
            # 分片产物必须是裸 gzip：gzip 多 member 可拼接，是服务端流式合并的前提
            with gzip.open(archive, "rb") as stream:
                self.assertEqual(stream.read(), b"{}\n")

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
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
        ):
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(job, part, fence_of(part))

        build_storage.assert_called_once_with(external=True)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)
        self.assertEqual(part.object_key, artifact_name(job, part, 1))

    def test_execute_retries_upload_without_requerying(self):
        """上传抖动只重试上传本身：不重新查询、不重新压缩，退避按尝试次数递增。"""
        job = create_job(
            policy={**ExportPolicy().snapshot(), "upload_attempts": 3, "upload_retry_interval_seconds": 1},
            status=ExportJobStatus.RUNNING,
            end_time=1000,
        )
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
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
            patch("apps.log_search.export.worker.time.sleep") as sleep,
        ):
            upload = build_storage.return_value.export_upload
            upload.side_effect = [RuntimeError("cos 5xx"), RuntimeError("cos 5xx"), "etag"]
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            _execute(job, part, fence_of(part))

        self.assertEqual(upload.call_count, 3)
        self.assertEqual(api.query_ts_raw_with_scroll.call_count, 1)
        self.assertEqual([item.args[0] for item in sleep.call_args_list], [1, 2])
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.SUCCESS)

    def test_run_part_returns_to_waiting_after_upload_attempts_exhausted(self):
        """上传重试耗尽后整片交回调度器，等待下一轮重新执行。"""
        job = create_job(
            policy={**ExportPolicy().snapshot(), "upload_attempts": 2, "upload_retry_interval_seconds": 0},
            status=ExportJobStatus.RUNNING,
            end_time=1000,
        )
        part = ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.DISPATCHED,
            task_id="task-1",
        )
        with (
            patch("apps.log_search.export.worker.build_storage") as build_storage,
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
            patch("apps.log_search.export.worker.time.sleep"),
        ):
            upload = build_storage.return_value.export_upload
            upload.side_effect = RuntimeError("cos down")
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
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
        ):
            api.query_ts_raw_with_scroll.side_effect = DataAPIException(None, "unify query 5xx")
            run_part(part.pk, "task-1")

        part.refresh_from_db()
        self.assertEqual(part.error_code, ExportErrorCode.UNIFY_QUERY_FAILED)
        self.assertEqual(part.status, ExportPartStatus.WAITING)

    @override_settings(ASYNC_EXPORT_PART_FETCH_TIMEOUT=10)
    def test_write_rows_uses_the_fetch_budget(self):
        """取数只用取数预算，超出后自己按 FETCH_TIMEOUT 退出，而不是拖到回收窗口。"""
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
                patch("apps.log_search.export.worker.time.monotonic", side_effect=[100.0, 100.0, 111.0]),
            ):
                api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": False}]
                with self.assertRaises(PartError) as raised:
                    _write_rows(FakeHandler(), Path(directory) / "logs.jsonl")
        self.assertEqual(raised.exception.code, ExportErrorCode.FETCH_TIMEOUT)
        self.assertEqual(api.query_ts_raw_with_scroll.call_count, 1)

    def test_soft_time_limit_hands_the_part_back(self):
        """软超时时本次执行仍持有栅栏，应自己把分片交回调度器，而不是等回收。"""
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
            patch("apps.log_search.export.worker.build_storage") as build_storage,
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
            patch("apps.log_search.export.worker._sha256", return_value="checksum"),
        ):
            build_storage.return_value.export_upload.side_effect = SoftTimeLimitExceeded()
            api.query_ts_raw_with_scroll.side_effect = [{"list": [{"v": 1}], "done": True}]
            run_part(part.pk, "task-1")

        self.assertEqual(build_storage.return_value.export_upload.call_count, 1)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.error_code, ExportErrorCode.SOFT_TIME_LIMIT_EXCEEDED)


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

        def upload_artifact(file_path, file_name):
            if before_upload is not None:
                before_upload()
            self.objects[file_name] = Path(file_path).read_bytes()
            self.uploaded.append(file_name)

        def delete_file(name):
            if discard_error is not None:
                raise discard_error
            self.deleted.append(name)
            self.objects.pop(name, None)

        with (
            patch(
                "apps.log_search.export.worker.build_storage",
                return_value=MagicMock(export_upload=upload_artifact, delete_file=delete_file),
            ),
            patch("apps.log_search.export.worker.build_handler", return_value=FakeHandler()),
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi") as api,
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
        claimed = state.claim_planning(self.job.pk)
        self.assertIsNotNone(claimed)
        return state.persist_plan(self.job.pk, claimed.planning_attempts, parts=parts, estimated_total=40)

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
        claimed = state.claim_finalization(job.pk)
        self.assertIsNotNone(
            state.finalize_job(
                job.pk,
                claimed.finalization_attempts,
                manifest_object_key="manifest",
                manifest_bytes=10,
                manifest_checksum="manifest-checksum",
            )
        )
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.SUCCESS)
        self.assertIsNotNone(job.expires_at)

    def test_finalize_rejects_broken_leaf_boundaries(self):
        self.plan()
        self.complete_parts(4)
        ExportPart.objects.filter(job=self.job, part_no=3).update(start_time=2500)
        claimed = state.claim_finalization(self.job.pk)
        with self.assertRaises(ValueError):
            state.finalize_job(
                self.job.pk,
                claimed.finalization_attempts,
                manifest_object_key="manifest",
                manifest_bytes=10,
                manifest_checksum="manifest-checksum",
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

    @patch("apps.log_search.export.state.logger")
    def test_failure_log_preserves_stage_and_execution_identity_before_requeue(self, mock_logger):
        self.plan()
        part = ExportPart.objects.filter(job=self.job).order_by("part_no").first()
        state.dispatch_part(part.pk, "upload-task")
        part = state.claim_part(part.pk, "upload-task")
        state.set_stage(part.pk, fence_of(part), ExportStage.UPLOAD)

        state.fail_part(part.pk, fence_of(part), error_code="UPLOAD_FAILED", error_detail="上传失败")

        message, *args = mock_logger.warning.call_args.args
        message %= tuple(args)
        for context in (
            f"job_id={self.job.pk}",
            f"part_id={part.pk}",
            "part_no=1",
            "plan_version=1",
            "attempts=1",
            "task_id=upload-task",
            "stage=UPLOAD",
            "error_code=UPLOAD_FAILED",
            "error_detail=上传失败",
        ):
            self.assertIn(context, message)
        part.refresh_from_db()
        self.assertEqual(part.status, ExportPartStatus.WAITING)
        self.assertEqual(part.stage, "")
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
        self.assertIsNone(state.claim_finalization(self.job.pk))

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
        claimed = state.claim_planning(self.job.pk)
        self.assertIsNotNone(claimed)
        state.fail_planning(self.job.pk, claimed.planning_attempts, "STATISTICS_FAILED", retryable=True)
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
        claimed = state.claim_planning(self.job.pk)
        state.fail_planning(self.job.pk, claimed.planning_attempts, "STATISTICS_FAILED", "统计失败", retryable=True)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.PENDING)

        state.claim_planning(self.job.pk)

        self.assertEqual(ExportPlan.objects.filter(job=self.job).count(), 1)
        plan = ExportPlan.objects.get(job=self.job)
        self.assertEqual(plan.plan_version, 1)
        self.assertEqual(plan.status, ExportPlanStatus.PLANNING)

    @override_settings(ASYNC_EXPORT_PLANNING_TIMEOUT=1)
    def test_stale_attempt_cannot_persist_after_reclaim(self):
        old_claim = state.claim_planning(self.job.pk)
        ExportJob.objects.filter(pk=self.job.pk).update(planning_started_at=timezone.now() - timedelta(seconds=10))
        new_claim = state.claim_planning(self.job.pk)

        parts = [PartSpec(0, 4000, 40, 4000)]
        self.assertIsNone(state.persist_plan(self.job.pk, old_claim.planning_attempts, parts=parts, estimated_total=40))
        self.assertFalse(ExportPart.objects.filter(job=self.job).exists())
        self.assertEqual(ExportPlan.objects.get(job=self.job).status, ExportPlanStatus.PLANNING)

        self.assertEqual(
            state.persist_plan(self.job.pk, new_claim.planning_attempts, parts=parts, estimated_total=40).status,
            ExportJobStatus.READY,
        )

    @override_settings(ASYNC_EXPORT_PLANNING_TIMEOUT=1)
    def test_stale_attempt_cannot_fail_after_reclaim(self):
        old_claim = state.claim_planning(self.job.pk)
        ExportJob.objects.filter(pk=self.job.pk).update(planning_started_at=timezone.now() - timedelta(seconds=10))
        new_claim = state.claim_planning(self.job.pk)

        self.assertIsNone(
            state.fail_planning(self.job.pk, old_claim.planning_attempts, "STATISTICS_FAILED", retryable=False)
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.PLANNING)
        self.assertEqual(self.job.planning_attempts, new_claim.planning_attempts)
        self.assertEqual(ExportPlan.objects.get(job=self.job).status, ExportPlanStatus.PLANNING)

    def test_failed_planning_marks_the_plan_row_failed(self):
        claimed = state.claim_planning(self.job.pk)
        state.fail_planning(self.job.pk, claimed.planning_attempts, "QUOTA_EXCEEDED", "超过单任务上限")

        self.job.refresh_from_db()
        plan = ExportPlan.objects.get(job=self.job, plan_version=1)
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)
        self.assertEqual(plan.status, ExportPlanStatus.FAILED)
        self.assertIsNotNone(plan.finished_at)

    def test_retryable_planning_failure_releases_the_enqueue_lease(self):
        """规划失败交回调度器时清掉入队标记，重试不用干等租约到期。"""
        ExportJob.objects.filter(pk=self.job.pk).update(planning_enqueued_at=timezone.now())
        claimed = state.claim_planning(self.job.pk)

        state.fail_planning(self.job.pk, claimed.planning_attempts, "STATISTICS_FAILED", "统计失败", retryable=True)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.PENDING)
        self.assertIsNone(self.job.planning_enqueued_at)

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
        claimed = state.claim_planning(self.job.pk)
        self.assertIsNotNone(claimed)
        state.persist_plan(
            self.job.pk, claimed.planning_attempts, parts=[PartSpec(0, 4000, 40, 4000)], estimated_total=40
        )

    def fail_first_part(self, error_code="FETCH_TIMEOUT"):
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
        claimed = state.claim_planning(job.pk)
        state.persist_plan(
            job.pk, claimed.planning_attempts, parts=[PartSpec(0, 1000, 40, 4000, oversized=True)], estimated_total=40
        )
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="FETCH_TIMEOUT", retryable=True)

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
        claimed = state.claim_planning(job.pk)
        state.persist_plan(job.pk, claimed.planning_attempts, parts=[PartSpec(0, 4000, 40, 4000)], estimated_total=40)
        part = ExportPart.objects.get(job=job)
        state.dispatch_part(part.pk, "task")
        part = state.claim_part(part.pk, "task")
        state.fail_part(part.pk, fence_of(part), error_code="FETCH_TIMEOUT", retryable=True)

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
        claimed = state.claim_finalization(job.pk)
        self.assertIsNotNone(
            state.finalize_job(
                job.pk,
                claimed.finalization_attempts,
                manifest_object_key="manifest",
                manifest_bytes=1,
                manifest_checksum="manifest-checksum",
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

        self.assertEqual(artifact_name(job, part, 1), "exports/11/parts/3/attempt-1.jsonl.gz")
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

    def test_missing_toggle_is_reported_as_unsupported_storage(self):
        """开关缺失是配置问题：必须给出不可重试的存储错误码，而不是落到兜底异常。"""
        with patch("apps.log_search.export.storage.FeatureToggleObject.toggle", return_value=None):
            with self.assertRaises(UnsupportedExportStorage):
                build_storage(external=False)

    def test_empty_feature_config_is_reported_as_unsupported_storage(self):
        with self.assertRaises(UnsupportedExportStorage):
            self._build(external=False, config=None)


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
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_dispatch_stops_when_the_round_budget_is_exhausted(self, send, _policy):
        """预算已用尽时一个分片都不投，分片保持 WAITING 等下一个调度周期。"""
        self.assertEqual(dispatch_ready_parts(deadline=time.monotonic() - 1), [])
        send.assert_not_called()
        self.assertEqual(ExportPart.objects.filter(status=ExportPartStatus.WAITING).count(), 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler.time.monotonic")
    @patch("apps.log_search.export.scheduler._send")
    def test_dispatch_stops_between_two_dispatches_when_the_budget_runs_out(self, send, monotonic, _policy):
        """预算在投递中间用尽：已投出的分片保留，不会留下占了额度却没发布的分片。"""
        # 第一次检查（100）还没到预算，之后都超过 deadline=150
        monotonic.side_effect = itertools.chain([100.0], itertools.repeat(200.0))

        self.assertEqual(len(dispatch_ready_parts(deadline=150.0)), 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(ExportPart.objects.filter(status=ExportPartStatus.WAITING).count(), 2)

    @override_settings(ASYNC_EXPORT_COORDINATE_DEADLINE_SECONDS=0)
    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=4, global_parallelism=4),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_coordinate_gives_the_round_budget_to_the_dispatch_stage(self, send, _policy):
        """轮次入口把时间预算交给投递阶段：预算为 0 时本轮不投递，但仍走完回收与收尾。"""
        self.assertEqual(coordinate()["dispatched"], 0)
        send.assert_not_called()

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
        return_value=build_policy(
            index_parallelism=4,
            global_parallelism=3,
            oversized_parallelism=1,
            oversized_global_parallelism=2,
        ),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_oversized_slot_limits_dispatch_and_reopens_after_completion(self, send, _policy):
        """同轮只投递一个超大分片；它结束后，后续轮次可以继续投递。"""
        ExportPart.objects.filter(job=self.job, part_no__in=[1, 3]).update(oversized=True)

        self.assertEqual(len(dispatch_ready_parts()), 2)
        self.assertEqual(
            list(
                ExportPart.objects.filter(job=self.job, status=ExportPartStatus.DISPATCHED)
                .order_by("part_no")
                .values_list("part_no", flat=True)
            ),
            [1, 2],
        )
        self.assertEqual(ExportPart.objects.get(job=self.job, part_no=3).status, ExportPartStatus.WAITING)

        ExportPart.objects.filter(job=self.job, part_no=1).update(status=ExportPartStatus.SUCCESS)
        self.assertEqual(len(dispatch_ready_parts()), 1)
        self.assertEqual(ExportPart.objects.get(job=self.job, part_no=3).status, ExportPartStatus.DISPATCHED)
        self.assertEqual(send.call_count, 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(
            index_parallelism=4,
            global_parallelism=4,
            oversized_parallelism=1,
            oversized_global_parallelism=2,
        ),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_oversized_slot_is_global_and_does_not_block_normal_parts(self, send, _policy):
        """环境超大额度已满时，本任务仍可投递普通分片。"""
        ExportPart.objects.filter(job=self.job, part_no=1).update(oversized=True)
        for index_set_id in (12, 13):
            other = create_job(
                index_set_id=index_set_id, base_dict={}, end_time=1000, status=ExportJobStatus.RUNNING, plan_version=1
            )
            ExportPart.objects.create(
                job=other,
                part_no=1,
                plan_version=1,
                start_time=0,
                end_time=1000,
                oversized=True,
                status=ExportPartStatus.UPLOADING,
            )

        self.assertEqual(len(dispatch_ready_parts()), 2)
        self.assertEqual(ExportPart.objects.get(job=self.job, part_no=1).status, ExportPartStatus.WAITING)
        self.assertEqual(ExportPart.objects.filter(job=self.job, status=ExportPartStatus.DISPATCHED).count(), 2)
        self.assertEqual(send.call_count, 2)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(
            index_parallelism=4,
            global_parallelism=4,
            oversized_parallelism=1,
            oversized_global_parallelism=2,
        ),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_oversized_limit_allows_one_part_from_each_of_two_jobs(self, send, _policy):
        """不同任务各占一个超大槽位，环境上限为两个。"""
        ExportPart.objects.filter(job=self.job, part_no=1).update(oversized=True)
        second = create_job(index_set_id=12, base_dict={}, end_time=1000, status=ExportJobStatus.READY, plan_version=1)
        ExportPart.objects.create(job=second, part_no=1, plan_version=1, start_time=0, end_time=1000, oversized=True)

        dispatch_ready_parts()

        self.assertEqual(ExportPart.objects.filter(oversized=True, status=ExportPartStatus.DISPATCHED).count(), 2)
        self.assertEqual(send.call_count, 3)

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(
            index_parallelism=4,
            global_parallelism=4,
            oversized_parallelism=2,
            oversized_global_parallelism=2,
        ),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_oversized_job_limit_allows_two_parts_in_one_round(self, send, _policy):
        """单 Job 额度调大后，同一个任务可以在同一轮并行投递两个超大分片。"""
        ExportPart.objects.filter(job=self.job, part_no__in=[1, 3]).update(oversized=True)

        self.assertEqual(len(dispatch_ready_parts()), 3)
        self.assertEqual(
            ExportPart.objects.filter(job=self.job, oversized=True, status=ExportPartStatus.DISPATCHED).count(), 2
        )

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
        job = create_job(index_set_id=12, status=ExportJobStatus.PENDING)
        self.assertEqual(enqueue_planning(10), [job.pk])
        # 入队租约内不再重复发布：队列积压时消息量不会被周期重扫放大
        self.assertEqual(enqueue_planning(10), [])
        self.assertEqual(send.call_count, 1)

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_planning_republishes_after_the_lease_expires(self, send):
        job = create_job(index_set_id=12, status=ExportJobStatus.PENDING)
        self.assertEqual(enqueue_planning(10), [job.pk])

        ExportJob.objects.filter(pk=job.pk).update(
            planning_enqueued_at=timezone.now() - timedelta(seconds=settings.ASYNC_EXPORT_ENQUEUE_LEASE_SECONDS + 1)
        )

        self.assertEqual(enqueue_planning(10), [job.pk])
        self.assertEqual(send.call_count, 2)

    @patch("apps.log_search.export.scheduler._send", side_effect=RuntimeError("broker down"))
    def test_publish_failure_releases_the_enqueue_lease(self, send):
        job = create_job(index_set_id=12, status=ExportJobStatus.PENDING)

        self.assertEqual(enqueue_planning(10), [])

        self.assertIsNone(ExportJob.objects.get(pk=job.pk).planning_enqueued_at)

    @patch("apps.log_search.export.scheduler._send")
    def test_enqueue_finalization_waits_for_all_parts(self, send):
        self.assertEqual(enqueue_finalization(10), [])
        ExportPart.objects.update(status=ExportPartStatus.SUCCESS)
        self.job.status = ExportJobStatus.RUNNING
        self.job.save(update_fields=["status"])
        self.assertEqual(enqueue_finalization(10), [self.job.pk])
        # 收尾同样受入队租约约束，不会每轮重复发布
        self.assertEqual(enqueue_finalization(10), [])
        self.assertEqual(send.call_count, 1)

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

    @patch(
        "apps.log_search.export.scheduler.current_policy",
        return_value=build_policy(index_parallelism=1, global_parallelism=2),
    )
    @patch("apps.log_search.export.scheduler._send")
    def test_union_part_occupies_each_index_but_only_one_global_slot(self, send, _policy):
        self.job.index_set_ids = [11, 12]
        self.job.search_params = {"index_set_ids": [11, 12]}
        self.job.save(update_fields=["index_set_ids", "search_params"])
        ExportPart.objects.filter(job=self.job, part_no=1).update(status=ExportPartStatus.DISPATCHED)
        blocked = create_job(index_set_id=12, status=ExportJobStatus.READY, plan_version=1, end_time=1000)
        free = create_job(index_set_id=13, status=ExportJobStatus.READY, plan_version=1, end_time=1000)
        ExportPart.objects.create(job=blocked, part_no=1, plan_version=1, start_time=0, end_time=1000)
        free_part = ExportPart.objects.create(job=free, part_no=1, plan_version=1, start_time=0, end_time=1000)

        self.assertEqual(_inflight_by_index_set(), {11: 1, 12: 1})
        self.assertEqual(dispatch_ready_parts(), [free_part.pk])
        self.assertEqual(_inflight_by_index_set(), {11: 1, 12: 1, 13: 1})
        send.assert_called_once()

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
    """规划、收尾、调度轮次、分片四类消息各自独占队列：大合并不阻塞规划，排队再久也不推迟回收投递。"""

    def test_queues_are_distinct(self):
        self.assertEqual(len({PART_QUEUE, PLAN_QUEUE, FINALIZE_QUEUE, COORDINATOR_QUEUE}), 4)

    def test_coordinator_tick_has_its_own_queue(self):
        self.assertEqual(coordinate_sharded_exports.options, {"queue": COORDINATOR_QUEUE})
        self.assertEqual(
            app.conf.beat_schedule[coordinate_sharded_exports.name]["options"], {"queue": COORDINATOR_QUEUE}
        )

    def test_planning_is_bounded_before_the_reclaim_window(self):
        """规划软超时必须早于规划超时窗口，否则 Coordinator 会判定超时并重复投递同一份规划。"""
        self.assertIsNotNone(plan_sharded_export.soft_time_limit)
        self.assertLess(plan_sharded_export.soft_time_limit, settings.ASYNC_EXPORT_PLANNING_TIMEOUT)

    def test_part_execution_is_bounded_by_the_reclaim_window(self):
        """
        分片被回收重投时旧执行必须已经退出，否则它不计入在途数却仍在查询，实际并发会超出额度；
        取数预算还要给打包与上传留出余量。
        """
        soft_limit = execute_sharded_export_part.soft_time_limit
        hard_limit = execute_sharded_export_part.time_limit
        self.assertIsNotNone(soft_limit)
        self.assertIsNotNone(hard_limit)
        self.assertLess(soft_limit, hard_limit)
        self.assertLessEqual(hard_limit, settings.ASYNC_EXPORT_PART_TIMEOUT)
        self.assertLess(settings.ASYNC_EXPORT_PART_FETCH_TIMEOUT, soft_limit)

    def test_finalization_is_bounded_before_the_reclaim_window(self):
        """合并+清单生成软超时必须早于协调器重认领窗口。"""
        self.assertIsNotNone(finalize_sharded_export.soft_time_limit)
        window = settings.ASYNC_EXPORT_MERGE_TIMEOUT + settings.ASYNC_EXPORT_FINALIZATION_TIMEOUT
        self.assertLess(finalize_sharded_export.soft_time_limit, window)

    def test_round_budget_is_bounded_before_the_lock_lease(self):
        """轮次必须先于调度锁租约结束，否则锁过期后旧轮次会与下一轮重叠发放额度。"""
        self.assertIsNotNone(coordinate_sharded_exports.soft_time_limit)
        self.assertGreater(settings.ASYNC_EXPORT_COORDINATE_DEADLINE_SECONDS, 0)
        self.assertLess(
            settings.ASYNC_EXPORT_COORDINATE_DEADLINE_SECONDS, settings.ASYNC_EXPORT_COORDINATE_SOFT_TIME_LIMIT
        )
        self.assertLess(settings.ASYNC_EXPORT_COORDINATE_SOFT_TIME_LIMIT, settings.ASYNC_EXPORT_COORDINATE_LOCK_TIMEOUT)

    def test_supervisord_consumes_every_queue(self):
        """漏部署任一 worker 会让对应链路整体停摆，队列改动必须同步部署配置。"""
        conf_path = Path(__file__).resolve().parents[3] / "support-files" / "supervisord.conf"
        conf = conf_path.read_text(encoding="utf-8")
        for queue in (PART_QUEUE, PLAN_QUEUE, FINALIZE_QUEUE, COORDINATOR_QUEUE):
            with self.subTest(queue=queue):
                self.assertIn(f"-Q {queue} ", conf)


class JobFailureClassificationTests(TestCase):
    """任务级错误码只表达原因；OVERSIZED 仅用于「已到最小时间精度 + 工作量类原因」。"""

    FAILED_CASES = (
        # 工作量类原因且已到最小精度：只有缩小范围才有意义
        (ExportErrorCode.FETCH_TIMEOUT, 1000, 500, ExportErrorCode.OVERSIZED_PART_FAILED),
        # 查询失败、重试耗尽、上传/存储等与数据密度无关，不能被密度文案覆盖
        (ExportErrorCode.UNIFY_QUERY_FAILED, 1000, 500, ExportErrorCode.UNIFY_QUERY_FAILED),
        (ExportErrorCode.PART_RETRIES_EXHAUSTED, 1000, 500, ExportErrorCode.PART_RETRIES_EXHAUSTED),
        (ExportErrorCode.UPLOAD_FAILED, 1000, 500, ExportErrorCode.UPLOAD_FAILED),
        (ExportErrorCode.STORAGE_UNSUPPORTED, 1000, 500, ExportErrorCode.STORAGE_UNSUPPORTED),
        # 未预期异常多为代码或配置问题，已到最小精度也不能报成密度过高
        (ExportErrorCode.PART_EXECUTION_FAILED, 1000, 500, ExportErrorCode.PART_EXECUTION_FAILED),
        # 还能继续细分时保留原始原因，避免把「分片数到上限」误报成密度问题
        (ExportErrorCode.FETCH_TIMEOUT, 4000, 1, ExportErrorCode.FETCH_TIMEOUT),
        # 未登记的码不透给前端，否则前端只能拿到空文案
        ("QUERY_FAILED", 1000, 500, ExportErrorCode.PART_EXECUTION_FAILED),
    )

    def fail_single_part_job(self, error_code, span, max_parts):
        """造一个只含单个分片的任务并让它失败，返回刷新后的任务。"""
        job = create_job(
            end_time=span,
            policy={**ExportPolicy().snapshot(), "part_max_attempts": 1, "max_parts": max_parts},
        )
        claimed = state.claim_planning(job.pk)
        state.persist_plan(job.pk, claimed.planning_attempts, parts=[PartSpec(0, span, 10, 10)], estimated_total=10)
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

    def test_unexpected_failure_fails_the_job_without_splitting(self):
        """兜底错误每次必然复现，重试耗尽后直接失败，不再一路细分到最小精度。"""
        job = self.fail_single_part_job(ExportErrorCode.PART_EXECUTION_FAILED, 4000, 500)

        self.assertEqual(job.status, ExportJobStatus.FAILED)
        self.assertEqual(job.error_code, ExportErrorCode.PART_EXECUTION_FAILED)
        self.assertEqual(list(ExportPart.objects.filter(job=job).values_list("status", flat=True)), ["FAILED"])

    def test_underlying_part_error_stays_in_the_detail(self):
        job = self.fail_single_part_job(ExportErrorCode.STORAGE_UNSUPPORTED, 1000, 500)

        self.assertIn(ExportErrorCode.STORAGE_UNSUPPORTED, job.error_detail)


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
            patch("apps.log_search.export.scheduler.build_storage") as build_storage,
            patch("apps.log_search.export.merger.build_storage") as merge_storage,
        ):
            merge_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(b"part-bytes")
            build_storage.return_value.export_upload.side_effect = lambda file_path, file_name: captured.append(
                Path(file_path).read_bytes()
            )
            finalize_export(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.SUCCESS)
        content = captured[0]
        self.assertEqual(self.job.manifest_bytes, len(content))
        self.assertEqual(self.job.manifest_checksum, hashlib.sha256(content).hexdigest())
        self.assertEqual(self.job.manifest_object_key, manifest_name(self.job))
        # 合并产物也随任务落库
        self.assertEqual(self.job.merged_object_key, merged_name(self.job))
        self.assertEqual(self.job.merged_bytes, len(b"part-bytes"))
        self.assertEqual(self.job.merged_checksum, hashlib.sha256(b"part-bytes").hexdigest())

    def test_transient_upload_failure_retries_without_rerunning_parts(self):
        with (
            patch("apps.log_search.export.scheduler.build_storage") as build_storage,
            patch("apps.log_search.export.merger.build_storage") as merge_storage,
        ):
            merge_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(b"part-bytes")
            upload = build_storage.return_value.export_upload
            upload.side_effect = [OSError("temporary"), None]
            self.assertIsNone(finalize_export(self.job.pk))
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
            self.assertEqual(self.job.finalization_attempts, 1)
            self.assertEqual(finalizing_jobs(10), [self.job.pk])
            self.assertEqual(finalize_export(self.job.pk).status, ExportJobStatus.SUCCESS)

        self.assertEqual(upload.call_count, 2)
        self.assertEqual(ExportPart.objects.get(job=self.job).status, ExportPartStatus.SUCCESS)
        self.job.refresh_from_db()
        self.assertEqual(self.job.finalization_attempts, 2)

    def test_upload_failure_fails_job_after_retry_budget(self):
        self.job.policy = {**self.job.policy, "finalization_attempts": 2}
        self.job.save(update_fields=["policy"])
        with (
            patch("apps.log_search.export.scheduler.build_storage") as build_storage,
            patch("apps.log_search.export.merger.build_storage") as merge_storage,
        ):
            merge_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(b"part-bytes")
            upload = build_storage.return_value.export_upload
            upload.side_effect = OSError("temporary")
            finalize_export(self.job.pk)
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
            finalize_export(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.FAILED)
        self.assertEqual(self.job.error_code, ExportErrorCode.FINALIZATION_FAILED)
        self.assertEqual(self.job.finalization_attempts, 2)
        self.assertEqual(upload.call_count, 2)
        self.assertFalse(finalizing_jobs(10))

    def test_finalization_failure_releases_the_enqueue_lease(self):
        """收尾失败交回调度器时清掉入队标记，重试不用干等租约到期。"""
        ExportJob.objects.filter(pk=self.job.pk).update(finalization_enqueued_at=timezone.now())
        claimed = state.claim_finalization(self.job.pk)

        state.fail_finalization(self.job.pk, claimed.finalization_attempts, "upload failed")

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.RUNNING)
        self.assertIsNone(self.job.finalization_enqueued_at)

    @override_settings(ASYNC_EXPORT_FINALIZATION_TIMEOUT=1, ASYNC_EXPORT_MERGE_TIMEOUT=1)
    def test_stale_finalization_attempt_cannot_commit_or_fail(self):
        old_claim = state.claim_finalization(self.job.pk)
        self.assertIsNone(state.claim_finalization(self.job.pk))
        ExportJob.objects.filter(pk=self.job.pk).update(finalization_started_at=timezone.now() - timedelta(seconds=10))
        self.assertEqual(finalizing_jobs(10), [self.job.pk])
        new_claim = state.claim_finalization(self.job.pk)

        self.assertIsNone(
            state.finalize_job(
                self.job.pk,
                old_claim.finalization_attempts,
                manifest_object_key="old-manifest",
                manifest_bytes=1,
                manifest_checksum="old-checksum",
            )
        )
        self.assertIsNone(state.fail_finalization(self.job.pk, old_claim.finalization_attempts, "late error"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.FINALIZING)
        self.assertEqual(self.job.finalization_attempts, new_claim.finalization_attempts)

    def test_cancel_during_finalization_keeps_the_job_canceled(self):
        def cancel_during_upload(file_path, file_name):
            self.assertEqual(ExportJob.objects.get(pk=self.job.pk).status, ExportJobStatus.FINALIZING)
            state.cancel_job(self.job.pk)

        with (
            patch("apps.log_search.export.scheduler.build_storage") as build_storage,
            patch("apps.log_search.export.merger.build_storage") as merge_storage,
        ):
            merge_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(b"part-bytes")
            build_storage.return_value.export_upload.side_effect = cancel_during_upload
            self.assertIsNone(finalize_export(self.job.pk))

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExportJobStatus.CANCELED)
        self.assertEqual(self.job.finalization_attempts, 1)
        self.assertEqual(self.job.manifest_object_key, "")
        self.assertEqual(ExportPart.objects.get(job=self.job).status, ExportPartStatus.SUCCESS)
        self.assertEqual(finalizing_jobs(10), [])

    def test_manifest_checksum_is_written_after_finalization(self):
        claimed = state.claim_finalization(self.job.pk)
        state.finalize_job(
            self.job.pk,
            claimed.finalization_attempts,
            manifest_object_key="manifest.json",
            manifest_bytes=10,
            manifest_checksum="manifest-checksum",
        )

        self.assertEqual(ExportJob.objects.get(pk=self.job.pk).manifest_checksum, "manifest-checksum")


class MergedArtifactTests(TestCase):
    """整包合并：分片按序字节拼接成单个多 member gzip，并暴露为单文件下载入口。"""

    def setUp(self):
        self.job = create_job(status=ExportJobStatus.RUNNING, plan_version=1, end_time=1000)

    def _add_part(self, part_no, start_time, end_time, content):
        ExportPart.objects.create(
            job=self.job,
            part_no=part_no,
            plan_version=1,
            start_time=start_time,
            end_time=end_time,
            status=ExportPartStatus.SUCCESS,
            actual_rows=1,
            actual_bytes=len(content),
            object_key=f"part-{part_no}.jsonl.gz",
            checksum="ignored",
        )

    def test_merge_concatenates_gzip_members_in_order(self):
        """合并就是按序字节拼接 gzip member，解压后是各分片内容的顺序拼接。"""
        payload = {"part-1.jsonl.gz": gzip.compress(b'{"a":1}\n'), "part-2.jsonl.gz": gzip.compress(b'{"b":2}\n')}
        self._add_part(1, 0, 500, payload["part-1.jsonl.gz"])
        self._add_part(2, 500, 1000, payload["part-2.jsonl.gz"])
        parts = list(state.leaf_parts(self.job).order_by("start_time", "part_no"))

        with patch("apps.log_search.export.merger.build_storage") as build_storage:
            contents = {}
            build_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(payload[key])
            build_storage.return_value.export_upload.side_effect = lambda file_path, file_name: contents.update(
                {file_name: Path(file_path).read_bytes()}
            )
            key, size, checksum = merge_export_parts(self.job, parts)

        self.assertEqual(key, merged_name(self.job))
        self.assertEqual(size, len(payload["part-1.jsonl.gz"]) + len(payload["part-2.jsonl.gz"]))
        self.assertEqual(checksum, hashlib.sha256(payload["part-1.jsonl.gz"] + payload["part-2.jsonl.gz"]).hexdigest())
        self.assertEqual(contents[key], payload["part-1.jsonl.gz"] + payload["part-2.jsonl.gz"])
        # gzip 多 member 拼接后解压仍是合法内容
        self.assertEqual(gzip.decompress(contents[key]), b'{"a":1}\n{"b":2}\n')

    def test_download_link_exposes_full_artifact(self):
        self._add_part(1, 0, 1000, gzip.compress(b'{"a":1}\n'))
        self.job.status = ExportJobStatus.SUCCESS
        self.job.manifest_object_key = "manifest.json"
        self.job.manifest_bytes = 10
        self.job.manifest_checksum = "m"
        self.job.merged_object_key = merged_name(self.job)
        self.job.merged_bytes = 100
        self.job.merged_checksum = "checksum"
        self.job.expires_at = timezone.now() + timedelta(seconds=600)
        self.job.save()

        with patch("apps.log_search.export.api.build_storage") as build_storage:
            build_storage.return_value.generate_download_url.return_value = "https://full-url"
            link = download_link(self.job, "full")
        self.assertEqual(link["url"], "https://full-url")
        self.assertEqual(
            build_storage.return_value.generate_download_url.call_args.kwargs["file_name"], merged_name(self.job)
        )


class ExportErrorCodeTests(SimpleTestCase):
    """错误分类是给前端展示的稳定契约：新增错误码必须同时登记文案。"""

    def test_every_declared_code_has_a_message(self):
        codes = {value for name, value in vars(ExportErrorCode).items() if name.isupper() and isinstance(value, str)}

        self.assertTrue(codes)
        self.assertTrue(codes <= set(ExportErrorCode.MESSAGES))
        self.assertTrue(all(ExportErrorCode.MESSAGES[code] for code in codes))

    def test_only_fetch_timeout_is_splittable(self):
        """只有取数超时才有足够证据说明是读不完，允许时间细分；其余错误码不再细分。"""
        self.assertEqual(WORKLOAD_ERROR_CODES, {ExportErrorCode.FETCH_TIMEOUT})

    def test_query_failure_is_not_split(self):
        """查询失败可能是链路抖动，不应被当作「工作量过大」去时间细分；但仍保留可重试。"""
        self.assertNotIn(ExportErrorCode.UNIFY_QUERY_FAILED, WORKLOAD_ERROR_CODES)

    def test_unknown_or_empty_code_has_no_message(self):
        self.assertEqual(ExportErrorCode.label("NOT_A_CODE"), "")
        self.assertEqual(ExportErrorCode.label(""), "")


class ManifestSnapshotTests(TestCase):
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
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
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

    def test_creator_identity_follows_the_forwarded_external_user(self):
        cases = (("external_a", "external_a", True), ("", "authorizer", False))
        for external_username, expected_creator, expected_external in cases:
            with self.subTest(external_username=external_username):
                job = self.create(external_username)

                self.assertEqual(job.created_by, expected_creator)
                self.assertEqual(job.is_external, expected_external)

    def get_queryset(self):
        view = ExportJobViewSet()
        view.request = SimpleNamespace(data={"space_uid": self.SPACE_UID}, query_params={})
        return view.get_queryset()

    def make_job(self, created_by):
        return create_job(space_uid=self.SPACE_UID, created_by=created_by, source_app_code=settings.APP_CODE)

    def test_queryset_scope_follows_the_forwarded_external_user(self):
        """外部用户只看自己创建的任务，内部用户看整个空间的任务。"""
        own = self.make_job("external_a")
        other = self.make_job("external_b")

        for external_username, expected in (("external_a", [own.pk]), ("", [own.pk, other.pk])):
            with self.subTest(external_username=external_username):
                with patch(
                    "apps.log_search.views.export_views.get_request_external_username", return_value=external_username
                ):
                    self.assertCountEqual(list(self.get_queryset().values_list("pk", flat=True)), expected)


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class ExportJobPermissionTests(TestCase):
    """详情类接口按任务保存的索引集复核检索权限，不能只凭 Job ID 读到别人的产物。"""

    SPACE_UID = "bkcc__21"

    def setUp(self):
        Space.objects.create(
            space_uid=self.SPACE_UID,
            bk_biz_id=21,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="21",
            space_name="biz-21",
            bk_tenant_id="tenant-a",
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=759,
            index_set_name="index-759",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )

    def build_view(self, action):
        view = ExportJobViewSet()
        view.action = action
        view.request = SimpleNamespace(data={"space_uid": self.SPACE_UID}, query_params={}, method="GET")
        return view

    def build_request(self):
        return SimpleNamespace(data={"space_uid": self.SPACE_UID}, query_params={}, headers={}, META={}, method="GET")

    def test_detail_actions_require_the_index_set_permission(self):
        """详情和下载都要在空间校验之外再过一个索引集级检索权限。"""
        for action in ("retrieve", "download_link"):
            kinds = [type(permission) for permission in self.build_view(action).get_permissions()]
            self.assertEqual(kinds, [ViewBusinessPermission, ExportJobIndexSearchPermission], action)

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_retrieve_checks_business_permission_from_space(self, mock_permission_cls):
        mock_permission_cls.return_value.is_allowed.side_effect = PermissionDenied("没有业务访问权限")
        request = self.build_request()
        view = self.build_view("retrieve")

        with self.assertRaisesMessage(PermissionDenied, "没有业务访问权限"):
            view.check_permissions(request)

        called = mock_permission_cls.return_value.is_allowed.call_args
        self.assertEqual(called.kwargs["action"], ActionEnum.VIEW_BUSINESS)
        self.assertEqual(str(called.kwargs["resources"][0].id), "21")
        self.assertTrue(called.kwargs["raise_exception"])

    def test_object_permission_never_gates_admission(self):
        """索引集取自任务对象，准入阶段交给业务权限校验。"""
        permission = ExportJobIndexSearchPermission()

        for action in ("retrieve", "download_link"):
            self.assertTrue(permission.has_permission(self.build_request(), self.build_view(action)))

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_instance_id_comes_from_the_job(self, mock_permission_cls):
        """鉴权实例来自任务保存的索引集，而不是请求参数。"""
        job = create_job(created_by="other_user", space_uid=self.SPACE_UID, index_set_id=self.index_set.pk)
        permission = ExportJobIndexSearchPermission()

        self.assertTrue(permission.has_object_permission(self.build_request(), self.build_view("retrieve"), job))

        called = mock_permission_cls.return_value.is_allowed.call_args
        self.assertEqual(str(called.kwargs["resources"][0].id), str(self.index_set.pk))
        self.assertTrue(called.kwargs["raise_exception"])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_iam_denial_is_not_swallowed(self, mock_permission_cls):
        mock_permission_cls.return_value.is_allowed.side_effect = PermissionDenied("没有该索引集的检索权限")
        job = create_job(created_by="other_user", space_uid=self.SPACE_UID, index_set_id=self.index_set.pk)
        permission = ExportJobIndexSearchPermission()

        with self.assertRaises(PermissionDenied):
            permission.has_object_permission(self.build_request(), self.build_view("download_link"), job)

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_union_job_checks_every_index_set_before_download(self, mock_permission_cls):
        second = LogIndexSet.objects.create(
            index_set_id=760,
            index_set_name="index-760",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )
        job = create_job(
            space_uid=self.SPACE_UID,
            index_set_id=self.index_set.pk,
            search_params={"index_set_ids": [self.index_set.pk, second.pk]},
        )
        permission = ExportJobIndexSearchPermission()

        self.assertTrue(permission.has_object_permission(self.build_request(), self.build_view("download_link"), job))
        checked = [
            str(call.kwargs["resources"][0].id) for call in mock_permission_cls.return_value.is_allowed.call_args_list
        ]
        self.assertEqual(checked, [str(self.index_set.pk), str(second.pk)])

    @override_settings(IGNORE_IAM_PERMISSION=False, BKAPP_IS_BKLOG_API=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_union_create_requires_business_permission_at_legacy_entry(self, mock_permission_cls):
        second = LogIndexSet.objects.create(
            index_set_id=760,
            index_set_name="index-760",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )
        view = SearchViewSet()
        view.action = "union_async_export"
        request = self.build_request()
        request.method = "POST"
        request.data.update(
            bk_biz_id=21,
            union_configs=[{"index_set_id": self.index_set.pk}, {"index_set_id": second.pk}],
        )
        view.request = request
        mock_permission_cls.return_value.is_allowed.side_effect = PermissionDenied("没有业务访问权限")

        with self.assertRaisesMessage(PermissionDenied, "没有业务访问权限"):
            view.check_permissions(request)

        mock_permission_cls.return_value.is_allowed.assert_called_once()
        called = mock_permission_cls.return_value.is_allowed.call_args
        self.assertEqual(called.kwargs["action"], ActionEnum.VIEW_BUSINESS)
        self.assertEqual(str(called.kwargs["resources"][0].id), "21")
        self.assertTrue(called.kwargs["raise_exception"])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.drf.Permission")
    def test_union_job_denies_download_when_second_index_set_is_denied(self, mock_permission_cls):
        second = LogIndexSet.objects.create(
            index_set_id=760,
            index_set_name="index-760",
            space_uid=self.SPACE_UID,
            category_id="application",
            scenario_id=Scenario.LOG,
        )
        job = create_job(search_params={"index_set_ids": [self.index_set.pk, second.pk]})
        mock_permission_cls.return_value.is_allowed.side_effect = [True, PermissionDenied("无权限")]

        with self.assertRaises(PermissionDenied):
            ExportJobIndexSearchPermission().has_object_permission(
                self.build_request(), self.build_view("download_link"), job
            )


class LegacyExportRoutingTests(SimpleTestCase):
    def test_custom_indices_and_quick_exports_keep_the_original_chain(self):
        request = SimpleNamespace(user=SimpleNamespace(is_superuser=False))
        module = "apps.log_search.views.search_views"
        with (
            patch(f"{module}.is_sharded_export_enabled", return_value=True),
            patch(f"{module}.FeatureToggleObject.switch", return_value=False),
            patch(f"{module}.FeatureToggleObject.toggle", return_value=SimpleNamespace(feature_config={})),
            patch(f"{module}._apply_index_set_search_bk_biz_id"),
            patch(f"{module}._reject_platform_index_sets"),
            patch(f"{module}.Permission.get_auth_info", return_value=None),
        ):
            for is_union, custom_indices, is_quick in itertools.product(
                (False, True), ("", "2_bklog.0001"), (False, True)
            ):
                with self.subTest(is_union=is_union, custom_indices=custom_indices, is_quick=is_quick):
                    data = {
                        "bk_biz_id": 2,
                        "export_fields": [],
                        "file_type": "txt",
                    }
                    if is_union:
                        data.update(
                            index_set_ids=[3, 4],
                            union_configs=[
                                {"index_set_id": 3, "custom_indices": ""},
                                {"index_set_id": 4, "custom_indices": custom_indices},
                            ],
                            is_quick_export=is_quick,
                        )
                    else:
                        data["custom_indices"] = custom_indices
                    view = SearchViewSet()
                    view.request = request
                    view.params_valid = Mock(return_value=data)
                    view.get_object = Mock()
                    view._sharded_export_from_data = Mock(return_value=SimpleNamespace(data={"task_id": 19}))
                    handler_name = "UnionAsyncExportHandlers" if is_union else "AsyncExportHandlers"
                    with patch(f"{module}.{handler_name}") as legacy_handler:
                        legacy_handler.return_value.async_export.return_value = (7, 1)
                        if is_union:
                            response = view.union_async_export(request)
                        else:
                            response = view._export(request, index_set_id=3, is_quick_export=is_quick)
                    if custom_indices or is_quick:
                        self.assertEqual(response.data["task_id"], 7)
                        view._sharded_export_from_data.assert_not_called()
                        legacy_handler.return_value.async_export.assert_called_once_with(is_quick_export=is_quick)
                        forwarded = legacy_handler.call_args.kwargs["search_dict"]
                        actual_indices = (
                            forwarded["union_configs"][1]["custom_indices"] if is_union else forwarded["custom_indices"]
                        )
                        self.assertEqual(actual_indices, custom_indices)
                    else:
                        self.assertEqual(response.data["task_id"], 19)
                        view._sharded_export_from_data.assert_called_once()
                        legacy_handler.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class CreateJobRangeTests(TestCase):
    """导出时间区间不再要求对齐索引集时间精度，与旧异步导出链路保持一致。"""

    def setUp(self):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="biz-2",
            bk_tenant_id="tenant-a",
        )
        self.index_set = LogIndexSet.objects.create(
            index_set_id=756,
            index_set_name="index-756",
            space_uid="bkcc__2",
            category_id="application",
            scenario_id=Scenario.LOG,
        )

    def test_range_need_not_align_to_time_precision(self):
        handler = MagicMock(base_dict={"query_list": []}, origin_order_by=[], is_desensitize=True)
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            job = create_export_job(
                {
                    "space_uid": "bkcc__2",
                    "index_set_id": self.index_set.pk,
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

    def test_legacy_routes_preserve_query_scope_time_range_and_retry_params(self):
        conditions = [[{"field_name": "scene", "value": ["host"], "op": "eq"}]]
        cases = (
            (IndexSetType.SINGLE.value, 1500, 3700),
            (IndexSetType.UNION.value, "1970-01-01T00:00:01.500Z", "1970-01-01T00:00:03.700Z"),
            (ExportSearchType.SCENE, "1500", "3700"),
        )
        for index_type, start_time, end_time in cases:
            with self.subTest(index_type=index_type):
                is_scene = index_type == ExportSearchType.SCENE
                data = {
                    "bk_biz_id": 2,
                    "start_time": start_time,
                    "end_time": end_time,
                    "keyword": "",
                    "addition": None,
                    "sort_list": None,
                    "export_fields": ["message"],
                    "is_desensitize": False,
                }
                if is_scene:
                    data.update(space_uid="bkcc__2", table_id_conditions=conditions)
                raw_params = copy.deepcopy(data)
                handler = MagicMock(
                    base_dict={"query_list": []},
                    origin_order_by=[["dtEventTimeStamp", "desc"]],
                    is_desensitize=False,
                )
                handler.pre_get_result.return_value = {"list": [{"message": "log"}]}
                handler_name = "SceneUnifyQueryHandler" if is_scene else "UnifyQueryHandler"
                with (
                    patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
                    patch(f"apps.log_search.export.api.{handler_name}", return_value=handler),
                    patch("apps.log_search.export.api.get_request_username", return_value="tester"),
                    patch("apps.log_search.export.api.get_request_external_username", return_value=""),
                    patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
                ):
                    if is_scene:
                        response = SceneSearchViewSet()._sharded_scene_export(data)
                    elif index_type == IndexSetType.UNION.value:
                        response = SearchViewSet()._sharded_export_from_data(data, index_set_ids=[self.index_set.pk])
                    else:
                        response = SearchViewSet()._sharded_export_from_data(data, index_set_id=self.index_set.pk)

                job = ExportJob.objects.get(pk=response.data["task_id"])
                self.assertEqual(response.data["engine"], "sharded")
                self.assertEqual((job.start_time, job.end_time), (1500, 3701))
                self.assertEqual((job.search_params["start_time"], job.search_params["end_time"]), (1500, 3701))
                self.assertEqual(job.index_set_type, index_type)
                self.assertEqual(job.index_set_ids, [] if is_scene else [self.index_set.pk])
                self.assertEqual(job.raw_params, raw_params)
                self.assertEqual(data, raw_params)
                self.assertEqual(job.search_params["keyword"], "*")
                self.assertEqual(job.search_params["addition"], [])
                self.assertEqual(job.search_params["ip_chooser"], {})
                self.assertEqual(job.search_params["sort_list"], handler.origin_order_by)
                self.assertEqual(job.search_params["export_fields"], ["message"])
                self.assertFalse(job.search_params["is_desensitize"])
                if is_scene:
                    self.assertEqual(job.search_params["space_uid"], "bkcc__2")
                    self.assertEqual(job.search_params["table_id_conditions"], conditions)
                else:
                    self.assertEqual(job.search_params["index_set_ids"], [self.index_set.pk])
                handler.pre_get_result.assert_called_once_with(
                    sorted_fields=handler.origin_order_by, size=1000 if is_scene else 1
                )


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class UnionExportCreateTests(TestCase):
    def setUp(self):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="biz-2",
            bk_tenant_id="tenant-a",
        )
        for index_set_id in (756, 757):
            LogIndexSet.objects.create(
                index_set_id=index_set_id,
                index_set_name=f"index-{index_set_id}",
                space_uid="bkcc__2",
                category_id="application",
                scenario_id=Scenario.LOG,
            )

    def test_creation_freezes_the_combined_query_and_exposes_index_sets(self):
        handler = MagicMock(
            base_dict={"query_list": [{"reference_name": "a"}, {"reference_name": "b"}], "metric_merge": "a + b"},
            origin_order_by=[],
            is_desensitize=True,
        )
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler) as handler_cls,
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch("apps.log_search.export.api.get_request_app_code", return_value="bk_log"),
        ):
            job = create_export_job(
                {
                    "space_uid": "bkcc__2",
                    "index_set_ids": [757, 756],
                    "start_time": 0,
                    "end_time": 2000,
                    "keyword": "*",
                    "addition": [],
                    "ip_chooser": {},
                    "sort_list": [],
                    "export_fields": [],
                }
            )

        self.assertEqual(handler_cls.call_args.args[0]["index_set_ids"], [756, 757])
        self.assertEqual(job.index_set_ids, [756, 757])
        self.assertEqual(job.search_params["index_set_ids"], [756, 757])
        self.assertEqual(len(job.base_dict["query_list"]), 2)

    @patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True)
    def test_union_rejects_platform_index_set(self, _enabled):
        LogIndexSet.objects.filter(index_set_id=757).update(is_platform_index=True)

        with self.assertRaisesMessage(ValidationError, "联合检索暂不支持平台级索引集"):
            create_export_job({"space_uid": "bkcc__2", "index_set_ids": [756, 757]})

    def test_sort_error_from_existence_probe_rejects_creation(self):
        handler = MagicMock(
            base_dict={"query_list": [], "order_by": [["request_time", "desc"]]},
            origin_order_by=[["request_time", "desc"]],
            is_desensitize=True,
        )
        handler.pre_get_result.side_effect = DataAPIException(None, "request_time unsupported")
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
        ):
            with self.assertRaisesMessage(PreCheckAsyncExportException, "request_time unsupported"):
                create_export_job(
                    {
                        "space_uid": "bkcc__2",
                        "index_set_ids": [756, 757],
                        "start_time": 0,
                        "end_time": 2000,
                        "keyword": "*",
                        "addition": [],
                        "ip_chooser": {},
                        "sort_list": [["request_time", "desc"]],
                        "export_fields": [],
                    }
                )
        handler.pre_get_result.assert_called_once_with(sorted_fields=[["request_time", "desc"]], size=1)
        handler.fields.assert_not_called()
        handler.check_sort_list.assert_not_called()
        self.assertFalse(ExportJob.objects.exists())


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="tenant-a")
class EmptyExportPreCheckTests(TestCase):
    """创建前的存在性预检查：空数据和查询失败都拒绝创建。"""

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
        handler.pre_get_result.return_value = {"list": [] if empty else [{"log": "x"}]}
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
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

    def test_empty_range_is_rejected_without_creating_a_job(self):
        with self.assertRaises(PreCheckAsyncExportException):
            self.probe(empty=True)

        self.assertFalse(ExportJob.objects.exists())

    def test_range_with_data_still_creates_the_job(self):
        job = self.probe(empty=False)

        self.assertEqual(job.status, ExportJobStatus.PENDING)
        self.assertEqual(job.index_set_ids, [self.index_set.pk])


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
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
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

    def occupy(self, *statuses):
        """按给定状态占用本用户额度。"""
        for status in statuses:
            create_job(created_by="tester", status=status)

    def occupy_legacy_tasks(self, count):
        for _ in range(count):
            AsyncTask.objects.create(
                created_by="tester",
                scenario_id=Scenario.LOG,
                request_param={"index_set_ids": [1]},
                export_type=ExportType.ASYNC,
                export_status=ExportStatus.DOWNLOAD_LOG,
            )

    def test_full_user_quota_rejects_creation(self):
        """RUNNING、FINALIZING 与旧 AsyncTask 共用同一份额度，占满后新任务被拒且不落库。"""
        cases = (
            (
                "running",
                lambda: self.occupy(ExportJobStatus.RUNNING, ExportJobStatus.RUNNING, ExportJobStatus.RUNNING),
            ),
            (
                "finalizing",
                lambda: self.occupy(ExportJobStatus.RUNNING, ExportJobStatus.RUNNING, ExportJobStatus.FINALIZING),
            ),
            (
                "legacy_async_task",
                lambda: (self.occupy_legacy_tasks(2), self.occupy(ExportJobStatus.PLANNING)),
            ),
        )
        for name, occupy in cases:
            with self.subTest(name=name):
                occupy()
                before = ExportJob.objects.filter(created_by="tester").count()

                with self.assertRaises(ConcurrentExportLimitException):
                    self.create()

                self.assertEqual(ExportJob.objects.filter(created_by="tester").count(), before)

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


class _FakeRawStream:
    """模拟 urllib3 底层流：read/close，记录是否被关闭。"""

    def __init__(self, data):
        self._data = io.BytesIO(data)
        self.closed = False

    def read(self, size=-1):
        return self._data.read(size)

    def close(self):
        self.closed = True


class _FakeHttpResponse:
    """模拟 requests.Response，只暴露 StreamBody 依赖的 headers/raw/iter_content。"""

    def __init__(self, data):
        self.headers = {"Content-Length": str(len(data))}
        self.raw = _FakeRawStream(data)

    def iter_content(self, chunk_size):
        while True:
            chunk = self.raw.read(chunk_size)
            if not chunk:
                break
            yield chunk


class CosDownloadFileobjTests(SimpleTestCase):
    """用真实 StreamBody 类型验证 COS 流式下载：SDK 的 StreamBody 没有 close()，必须关闭底层流。"""

    def test_download_fileobj_reads_content_and_closes_raw_stream(self):
        payload = b'{"a":1}\n{"b":2}\n'
        body = StreamBody(_FakeHttpResponse(payload))

        with patch("apps.utils.cos.CosS3Client") as client_cls:
            client = client_cls.return_value
            client.get_object.return_value = {"Body": body}
            cos = QcloudCos("id", "key", "region", "bucket")
            out = io.BytesIO()
            cos.download_fileobj("exports/1/full.jsonl.gz", out)

        self.assertEqual(out.getvalue(), payload)
        self.assertTrue(body.get_raw_stream().closed)
