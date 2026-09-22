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

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportStage
from apps.log_search.export.config import policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart


def _validate_parts(job, parts):
    """分片必须对齐时间精度，并且无重叠、无遗漏地覆盖整个任务区间。"""
    if not parts:
        raise ValueError("计划不能为空")
    cursor = job.start_time
    for part in parts:
        if part.start_time % job.time_tick or part.end_time % job.time_tick:
            raise ValueError("分片边界必须对齐时间字段精度")
        if part.start_time != cursor or part.end_time <= cursor or part.end_time > job.end_time:
            raise ValueError("分片必须连续覆盖任务时间范围")
        if part.oversized and part.end_time - part.start_time != job.time_tick:
            raise ValueError("oversized 分片必须是时间字段最小精度")
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


def claim_planning(job_id):
    """
    认领初始规划。

    规划一次只会进行一个：未超时的 PLANNING 由其他实例持有，超时后允许重新认领。
    """
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status not in (ExportJobStatus.PENDING, ExportJobStatus.PLANNING):
            return None
        attempts = policy_from_snapshot(job.policy).planning_attempts
        now = timezone.now()
        if (
            job.status == ExportJobStatus.PLANNING
            and job.planning_started_at
            and now - job.planning_started_at < timedelta(seconds=settings.ASYNC_EXPORT_PLANNING_TIMEOUT)
        ):
            return None
        if job.planning_attempts >= attempts:
            return _finish_job(job, ExportJobStatus.FAILED, "PLANNING_RETRIES_EXHAUSTED", "规划重试次数已耗尽")
        return _save(
            job,
            status=ExportJobStatus.PLANNING,
            planning_started_at=now,
            planning_attempts=job.planning_attempts + 1,
        )


def persist_plan(job_id, *, parts, estimated_total):
    """把完整计划落库，并把任务推进到可调度状态。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING:
            return None
        _validate_parts(job, parts)
        ExportPart.objects.bulk_create(
            [
                ExportPart(
                    job=job,
                    part_no=index + 1,
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
        return _save(
            job,
            status=ExportJobStatus.READY,
            part_total=len(parts),
            estimated_total=estimated_total,
            error_code="",
            error_detail="",
        )


def fail_planning(job_id, code, detail="", retryable=False):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING:
            return None
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


def claim_part(part_id):
    """Worker 开始执行时占分片；重复投递、已取消或已回收的投递不会发起查询。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if part.status != ExportPartStatus.DISPATCHED or job.status != ExportJobStatus.RUNNING:
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


def set_stage(part_id, stage):
    """更新展示阶段；分片已被回收或取消时不做任何事。"""
    return ExportPart.objects.filter(pk=part_id, status=ExportPartStatus.RUNNING).update(
        stage=stage, updated_at=timezone.now()
    )


def complete_part(part_id, *, actual_rows, actual_bytes, compressed_bytes, object_key, checksum):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if part.status != ExportPartStatus.RUNNING:
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
        _save(
            job,
            part_success=job.part_success + 1,
            actual_total=job.actual_total + actual_rows,
        )
        return part


def fail_part(part_id, *, error_code, error_detail="", retryable=True):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        return _fail_locked(job, part, error_code, error_detail, retryable=retryable)


def _fail_locked(job, part, error_code, error_detail, retryable=True):
    if part.status not in (ExportPartStatus.DISPATCHED, ExportPartStatus.RUNNING):
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
    # 不再重试：让任务明确失败，避免用户拿到不完整的清单
    _save(part, status=ExportPartStatus.FAILED, stage="", **changes)
    if job.status in (ExportJobStatus.READY, ExportJobStatus.RUNNING):
        _finish_job(
            job,
            ExportJobStatus.FAILED,
            "PART_EXECUTION_FAILED",
            f"分片 {part.part_no} 执行失败：{error_code}",
        )
    return part


def recover_stale_parts(limit=None):
    """
    回收超时未完成的分片。

    一期不做租约心跳：Worker 有明确的分片超时（ASYNC_EXPORT_PART_TIMEOUT），
    超过这个时间仍未回填结果的分片一律交回调度器重试。
    """
    limit = limit or settings.ASYNC_EXPORT_COORDINATE_BATCH
    cutoff = timezone.now() - timedelta(seconds=settings.ASYNC_EXPORT_PART_TIMEOUT)
    stale = (
        ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT)
        .filter(
            Q(status=ExportPartStatus.DISPATCHED, updated_at__lt=cutoff)
            | Q(status=ExportPartStatus.RUNNING, started_at__lt=cutoff)
        )
        .values_list("pk", flat=True)[:limit]
    )
    recovered = []
    for part_id in list(stale):
        if fail_part(part_id, error_code="PART_TIMEOUT", error_detail="分片执行超时，已重新调度", retryable=True):
            recovered.append(part_id)
    return recovered


def finalize_job(job_id, *, manifest_object_key, manifest_bytes):
    """只有全部分片成功、边界连续且数量自洽时才允许任务成功。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.RUNNING:
            return None
        parts = list(ExportPart.objects.filter(job=job).order_by("start_time", "part_no"))
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
