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

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.log_search.constants import (
    NON_SPLITTABLE_ERROR_CODES,
    ExportJobStatus,
    ExportPartStatus,
    ExportPlanStatus,
    ExportStage,
)
from apps.log_search.export.config import policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan


@dataclass(frozen=True)
class PartFence:
    """分片状态写入的身份令牌：task_id 标识投递，attempts 标识认领。"""

    task_id: str
    attempts: int

    @classmethod
    def of(cls, part):
        """从分片实例取出当前栅栏令牌。"""
        return cls(task_id=part.task_id, attempts=part.attempts)


def _fenced(part, fence):
    return part.task_id == fence.task_id and part.attempts == fence.attempts


def leaf_parts(job):
    """叶子分片：有效分片口径的唯一来源。"""
    return ExportPart.objects.filter(job=job).exclude(status__in=ExportPartStatus.NON_LEAF)


def leaf_stats(job):
    """叶子分片的数量与已导出条数。"""
    return leaf_parts(job).aggregate(
        total=Count("pk"),
        success=Count("pk", filter=Q(status=ExportPartStatus.SUCCESS)),
        rows=Coalesce(Sum("actual_rows"), 0),
    )


def leaf_counts_annotation():
    """列表页共用的叶子计数注解。"""
    return {
        "leaf_total": Count("parts", filter=~Q(parts__status__in=ExportPartStatus.NON_LEAF), distinct=True),
        "leaf_success": Count("parts", filter=Q(parts__status=ExportPartStatus.SUCCESS), distinct=True),
    }


def sync_actual_total(job):
    """把导出总量对齐到叶子聚合值。"""
    return _save(job, actual_total=leaf_stats(job)["rows"])


def _split_step(job):
    """分片可继续细分的最小步长。"""
    return policy_from_snapshot(job.policy).split_step_ms


def _validate_parts(job, parts):
    """分片必须无重叠、无遗漏地覆盖整个任务区间。"""
    if not parts:
        raise ValueError("计划不能为空")
    step = _split_step(job)
    cursor = job.start_time
    for part in parts:
        if part.start_time != cursor or part.end_time <= cursor or part.end_time > job.end_time:
            raise ValueError("分片必须连续覆盖任务时间范围")
        if part.oversized and part.end_time - part.start_time > step:
            raise ValueError("oversized 分片不能超过切分步长")
        cursor = part.end_time
    if cursor != job.end_time:
        raise ValueError("分片必须连续覆盖任务时间范围")


def _save(record, **changes):
    for field, value in changes.items():
        setattr(record, field, value)
    record.save(update_fields=[*changes, "updated_at"])
    return record


def _finish_job(job, status, error_code="", error_detail=""):
    """任务进入终态后，未投递和已投递但尚未开始的分片直接作废。"""
    now = timezone.now()
    _save(
        job,
        status=status,
        error_code=error_code,
        error_detail=error_detail or "",
        completed_at=now,
    )
    ExportPart.objects.filter(job=job, status__in=[ExportPartStatus.WAITING, ExportPartStatus.DISPATCHED]).update(
        status=ExportPartStatus.CANCELED, stage="", finished_at=now, updated_at=now
    )
    return job


def _claim_plan_record(job, policy, now):
    """
    认领当前计划版本行；失败的尝试复用同一版本，不虚增版本号。

    当前只有 0 -> 1 一条路径（规划成功后任务进入 READY 即不再规划），ExportPlan 的多版本
    能力是给后续"重新规划"入口预留的，不要据此认为已经有重规划流程。
    """
    plan, _ = ExportPlan.objects.update_or_create(
        job=job,
        plan_version=job.plan_version + 1,
        defaults={
            "status": ExportPlanStatus.PLANNING,
            "target_rows": policy.target_rows,
            "target_bytes": policy.target_bytes,
            "started_at": now,
        },
    )
    return plan


def _finish_plan(job, version, plan_result, planned_parts):
    defaults = {"status": ExportPlanStatus.SUCCESS, "planned_parts": planned_parts, "finished_at": timezone.now()}
    if plan_result is not None:
        defaults.update(
            total_rows=plan_result.total_rows,
            avg_row_bytes=plan_result.avg_row_bytes,
            initial_interval_ms=plan_result.initial_interval_ms,
        )
    return ExportPlan.objects.update_or_create(job=job, plan_version=version, defaults=defaults)


def claim_planning(job_id):
    """
    认领初始规划。

    规划一次只会进行一个：未超时的 PLANNING 由其他实例持有，超时后允许重新认领。
    """
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status not in (ExportJobStatus.PENDING, ExportJobStatus.PLANNING):
            return None
        policy = policy_from_snapshot(job.policy)
        now = timezone.now()
        if (
            job.status == ExportJobStatus.PLANNING
            and job.planning_started_at
            and now - job.planning_started_at < timedelta(seconds=settings.ASYNC_EXPORT_PLANNING_TIMEOUT)
        ):
            return None
        plan = _claim_plan_record(job, policy, now)
        if job.planning_attempts >= policy.planning_attempts:
            _save(plan, status=ExportPlanStatus.FAILED, finished_at=now)
            return _finish_job(job, ExportJobStatus.FAILED, "PLANNING_RETRIES_EXHAUSTED", "规划重试次数已耗尽")
        return _save(
            job,
            status=ExportJobStatus.PLANNING,
            planning_started_at=now,
            planning_attempts=job.planning_attempts + 1,
        )


def persist_plan(job_id, *, parts, estimated_total, plan_result=None):
    """把完整计划落库，并把任务推进到可调度状态。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING:
            return None
        _validate_parts(job, parts)
        version = job.plan_version + 1
        ExportPart.objects.bulk_create(
            [
                ExportPart(
                    job=job,
                    part_no=index + 1,
                    plan_version=version,
                    start_time=part.start_time,
                    end_time=part.end_time,
                    oversized=part.oversized,
                    estimated_rows=part.estimated_rows,
                    estimated_bytes=part.estimated_bytes,
                    status=ExportPartStatus.WAITING,
                )
                for index, part in enumerate(parts)
            ]
        )
        _finish_plan(job, version, plan_result, planned_parts=len(parts))
        job = _save(
            job,
            status=ExportJobStatus.READY,
            plan_version=version,
            estimated_total=estimated_total,
            error_code="",
            error_detail="",
        )
        return sync_actual_total(job)


def fail_planning(job_id, code, detail="", retryable=False):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING:
            return None
        now = timezone.now()
        ExportPlan.objects.filter(job=job, plan_version=job.plan_version + 1, status=ExportPlanStatus.PLANNING).update(
            status=ExportPlanStatus.FAILED, finished_at=now, updated_at=now
        )
        if retryable and job.planning_attempts < policy_from_snapshot(job.policy).planning_attempts:
            # 交回调度器重新规划，保留失败原因便于排查
            return _save(job, status=ExportJobStatus.PENDING, error_code=code, error_detail=(detail or "")[:2000])
        return _finish_job(job, ExportJobStatus.FAILED, code, (detail or "")[:2000])


def dispatch_part(part_id, task_id):
    """在真正投递到 broker 之前占用分片，避免重复投递。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if part.status != ExportPartStatus.WAITING or job.status not in (
            ExportJobStatus.READY,
            ExportJobStatus.RUNNING,
        ):
            return None
        _save(
            part,
            status=ExportPartStatus.DISPATCHED,
            task_id=task_id,
            stage="",
            started_at=None,
            finished_at=None,
            error_code="",
            error_detail="",
        )
        now = timezone.now()
        changes = {"last_dispatched_at": now}
        if job.status == ExportJobStatus.READY:
            changes.update(status=ExportJobStatus.RUNNING, started_at=now)
        _save(job, **changes)
        return part


def claim_part(part_id, task_id):
    """
    Worker 开始执行时占分片；已取消、已细分或属于其它投递的消息不会发起查询。

    同一次投递被重发（worker 崩溃后由 broker 重投递）时允许重新认领，不必干等分片超时回收：
    投递身份未变不会串投递，旧执行会被递增后的 attempts 挡在门外。
    """
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if (
            part.task_id != task_id
            or part.status not in ExportPartStatus.INFLIGHT
            or job.status != ExportJobStatus.RUNNING
        ):
            return None
        if part.attempts >= policy_from_snapshot(job.policy).part_max_attempts:
            _fail_locked(job, part, "PART_RETRIES_EXHAUSTED", "执行次数已耗尽", retryable=False)
            return None
        return _save(
            part,
            status=ExportPartStatus.RUNNING,
            stage=ExportStage.DOWNLOAD_LOG,
            attempts=part.attempts + 1,
            started_at=timezone.now(),
        )


def set_stage(part_id, fence, stage):
    """
    推进分片执行阶段；进入上传阶段时一并把状态推进到 UPLOADING。
    返回更新行数，0 表示本次执行已经出局。
    """
    changes = {"stage": stage, "updated_at": timezone.now()}
    if stage == ExportStage.UPLOAD:
        changes["status"] = ExportPartStatus.UPLOADING
    return ExportPart.objects.filter(
        pk=part_id,
        task_id=fence.task_id,
        attempts=fence.attempts,
        status__in=ExportPartStatus.EXECUTING,
    ).update(**changes)


def complete_part(part_id, fence, *, actual_rows, actual_bytes, compressed_bytes, object_key, checksum):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if part.status not in ExportPartStatus.EXECUTING or not _fenced(part, fence):
            # 已被超时回收并重新投递，本次结果作废
            return None
        now = timezone.now()
        if job.status != ExportJobStatus.RUNNING:
            return _save(part, status=ExportPartStatus.CANCELED, stage="", finished_at=now)
        _save(
            part,
            status=ExportPartStatus.SUCCESS,
            stage="",
            actual_rows=actual_rows,
            actual_bytes=actual_bytes,
            compressed_bytes=compressed_bytes,
            object_key=object_key,
            checksum=checksum,
            finished_at=now,
            error_code="",
            error_detail="",
        )
        sync_actual_total(job)
        return part


def fail_part(part_id, fence, *, error_code, error_detail="", retryable=True):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if not _fenced(part, fence):
            return None
        return _fail_locked(job, part, error_code, error_detail, retryable=retryable)


def _fail_locked(job, part, error_code, error_detail, retryable=True):
    if part.status not in ExportPartStatus.INFLIGHT:
        return None
    now = timezone.now()
    changes = {"error_code": error_code, "error_detail": (error_detail or "")[:2000], "finished_at": now}
    if job.status == ExportJobStatus.CANCELED:
        return _save(part, status=ExportPartStatus.CANCELED, stage="", **changes)
    if (
        retryable
        and job.status in (ExportJobStatus.READY, ExportJobStatus.RUNNING)
        and part.attempts < policy_from_snapshot(job.policy).part_max_attempts
    ):
        return _save(part, status=ExportPartStatus.WAITING, stage="", task_id="", **changes)
    if _can_split(job, part, error_code):
        return _split_locked(job, part, error_code, error_detail)
    # 不再重试：让任务明确失败，避免用户拿到不完整的清单
    _save(part, status=ExportPartStatus.FAILED, stage="", **changes)
    if job.status in (ExportJobStatus.READY, ExportJobStatus.RUNNING):
        job_error = "OVERSIZED_PART_FAILED" if part.oversized else "PART_EXECUTION_FAILED"
        _finish_job(job, ExportJobStatus.FAILED, job_error, f"分片 {part.part_no} 执行失败：{error_code}")
    return part


def _can_split(job, part, error_code):
    """重试耗尽后是否能按时间继续细分。"""
    policy = policy_from_snapshot(job.policy)
    if job.status not in (ExportJobStatus.READY, ExportJobStatus.RUNNING):
        return False
    if error_code in NON_SPLITTABLE_ERROR_CODES:
        return False
    if part.end_time - part.start_time <= _split_step(job):
        return False
    return leaf_stats(job)["total"] < policy.max_parts


def _split_locked(job, part, error_code, error_detail):
    """把父分片标记为 SPLIT 并生成两个相邻子分片，由调度器重新投递。"""
    span = part.end_time - part.start_time
    middle = (part.start_time + part.end_time) // 2
    if middle <= part.start_time or middle >= part.end_time:
        return None

    next_no = (ExportPart.objects.filter(job=job).aggregate(Max("part_no"))["part_no__max"] or 0) + 1
    estimated_rows = part.estimated_rows or 0
    estimated_bytes = part.estimated_bytes or 0
    left_rows = estimated_rows * (middle - part.start_time) // span
    left_bytes = estimated_bytes * (middle - part.start_time) // span
    ExportPart.objects.bulk_create(
        [
            ExportPart(
                job=job,
                part_no=next_no,
                plan_version=part.plan_version,
                parent_part=part,
                start_time=part.start_time,
                end_time=middle,
                estimated_rows=left_rows,
                estimated_bytes=left_bytes,
                status=ExportPartStatus.WAITING,
            ),
            ExportPart(
                job=job,
                part_no=next_no + 1,
                plan_version=part.plan_version,
                parent_part=part,
                start_time=middle,
                end_time=part.end_time,
                estimated_rows=estimated_rows - left_rows,
                estimated_bytes=estimated_bytes - left_bytes,
                status=ExportPartStatus.WAITING,
            ),
        ]
    )
    _save(
        part,
        status=ExportPartStatus.SPLIT,
        stage="",
        task_id="",
        finished_at=timezone.now(),
        error_code=error_code,
        error_detail=(error_detail or "")[:2000],
    )
    sync_actual_total(job)
    return part


def _is_stale(part, cutoff):
    """分片是否已超过执行超时；口径需与 recover_stale_parts 的候选查询保持一致。"""
    if part.status in ExportPartStatus.EXECUTING:
        return part.started_at is not None and part.started_at < cutoff
    if part.status == ExportPartStatus.DISPATCHED:
        return part.updated_at < cutoff
    return False


def recover_part(part_id, cutoff=None):
    """回收单个超时未完成的分片；在行锁内重判，避免误回收候选查询之后刚被认领或重新投递的分片。"""
    cutoff = cutoff or timezone.now() - timedelta(seconds=settings.ASYNC_EXPORT_PART_TIMEOUT)
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if not _is_stale(part, cutoff):
            return None
        return _fail_locked(job, part, "PART_TIMEOUT", "分片执行超时，已重新调度", retryable=True)


def recover_stale_parts(limit=None):
    """
    回收超时未完成的分片。

    一期不做租约心跳：Worker 有明确的分片超时（ASYNC_EXPORT_PART_TIMEOUT），
    超过这个时间仍未回填结果的分片一律交回调度器重试。
    """
    limit = limit or settings.ASYNC_EXPORT_COORDINATE_BATCH
    cutoff = timezone.now() - timedelta(seconds=settings.ASYNC_EXPORT_PART_TIMEOUT)
    candidates = (
        ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT)
        .filter(
            Q(status=ExportPartStatus.DISPATCHED, updated_at__lt=cutoff)
            | Q(status__in=ExportPartStatus.EXECUTING, started_at__lt=cutoff)
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )
    recovered = []
    for part_id in list(candidates):
        if recover_part(part_id, cutoff):
            recovered.append(part_id)
    return recovered


def finalize_job(job_id, *, manifest_object_key, manifest_bytes, manifest_checksum):
    """只有全部叶子分片成功、边界连续且数量自洽时才允许任务成功。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.RUNNING:
            return None
        parts = list(leaf_parts(job).order_by("start_time", "part_no"))
        if not parts or any(part.status != ExportPartStatus.SUCCESS for part in parts):
            return None
        cursor = job.start_time
        total = 0
        for part in parts:
            if part.start_time != cursor or part.end_time <= cursor:
                raise ValueError("分片时间边界不连续")
            cursor = part.end_time
            total += part.actual_rows or 0
        if cursor != job.end_time:
            raise ValueError("分片未覆盖完整任务时间范围")
        if total != job.actual_total:
            raise ValueError(f"分片实际条数 {job.actual_total} 与清单条数 {total} 不一致")
        now = timezone.now()
        return _save(
            job,
            status=ExportJobStatus.SUCCESS,
            manifest_object_key=manifest_object_key,
            manifest_bytes=manifest_bytes,
            manifest_checksum=manifest_checksum,
            completed_at=now,
            expires_at=now + timedelta(seconds=policy_from_snapshot(job.policy).artifact_retention_seconds),
            error_code="",
            error_detail="",
        )


def fail_job(job_id, error_code, error_detail=""):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status in ExportJobStatus.TERMINAL:
            return job
        return _finish_job(job, ExportJobStatus.FAILED, error_code, (error_detail or "")[:2000])


def cancel_job(job_id):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status in ExportJobStatus.TERMINAL:
            return job
        return _finish_job(job, ExportJobStatus.CANCELED)


def _job_id_of(part_id):
    return ExportPart.objects.values_list("job_id", flat=True).get(pk=part_id)
