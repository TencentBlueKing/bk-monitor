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
    WORKLOAD_ERROR_CODES,
    ExportErrorCode,
    ExportJobStatus,
    ExportPartStatus,
    ExportPlanStatus,
    ExportStage,
)
from apps.log_search.export.config import policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.utils.log import logger


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
    if status == ExportJobStatus.FAILED:
        logger.warning(
            "[sharded_export_job_failure] job_id=%s plan_version=%s status=%s "
            "planning_attempts=%s finalization_attempts=%s error_code=%s error_detail=%s",
            job.pk,
            job.plan_version,
            job.status,
            job.planning_attempts,
            job.finalization_attempts,
            error_code,
            (error_detail or "")[:2000],
        )
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
    """认领当前计划版本行；失败的尝试复用同一版本，不虚增版本号。"""
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
    认领初始规划：未超时的 PLANNING 由其他实例持有，超时后允许重新认领。

    递增后的 planning_attempts 是本次认领的栅栏，必须原样传给 persist_plan / fail_planning：
    规划软超时不保证阻塞中的查询及时退出，旧执行的结果必须作废。
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
            return _finish_job(
                job, ExportJobStatus.FAILED, ExportErrorCode.PLANNING_RETRIES_EXHAUSTED, "规划重试次数已耗尽"
            )
        job = _save(
            job,
            status=ExportJobStatus.PLANNING,
            planning_started_at=now,
            planning_attempts=job.planning_attempts + 1,
        )
        logger.info(
            "[sharded_export_planning_started] job_id=%s plan_version=%s planning_attempts=%s",
            job.pk,
            job.plan_version + 1,
            job.planning_attempts,
        )
        return job


def persist_plan(job_id, planning_attempt, *, parts, estimated_total, plan_result=None):
    """把完整计划落库，并把任务推进到可调度状态；planning_attempt 是认领栅栏，过期执行直接作废。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING or job.planning_attempts != planning_attempt:
            logger.info(
                "[sharded_export_plan_discarded] job_id=%s planning_attempts=%s current_planning_attempts=%s status=%s",
                job.pk,
                planning_attempt,
                job.planning_attempts,
                job.status,
            )
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
        sync_actual_total(job)
        logger.info(
            "[sharded_export_plan_completed] job_id=%s plan_version=%s planning_attempts=%s "
            "planned_parts=%s estimated_total=%s",
            job.pk,
            job.plan_version,
            job.planning_attempts,
            len(parts),
            estimated_total,
        )
        return job


def fail_planning(job_id, planning_attempt, code, detail="", retryable=False):
    """规划失败的提交入口；planning_attempt 是认领栅栏，过期执行不能改动任务状态。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.PLANNING or job.planning_attempts != planning_attempt:
            return None
        now = timezone.now()
        ExportPlan.objects.filter(job=job, plan_version=job.plan_version + 1, status=ExportPlanStatus.PLANNING).update(
            status=ExportPlanStatus.FAILED, finished_at=now, updated_at=now
        )
        if retryable and job.planning_attempts < policy_from_snapshot(job.policy).planning_attempts:
            logger.warning(
                "[sharded_export_planning_retry] job_id=%s plan_version=%s planning_attempts=%s "
                "error_code=%s error_detail=%s",
                job.pk,
                job.plan_version + 1,
                job.planning_attempts,
                code,
                (detail or "")[:2000],
            )
            # 交回调度器重新规划，保留失败原因便于排查；清掉入队标记，下一轮立即重发
            return _save(
                job,
                status=ExportJobStatus.PENDING,
                planning_enqueued_at=None,
                error_code=code,
                error_detail=(detail or "")[:2000],
            )
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

    同一次投递被重发时允许重新认领，不必等分片超时回收；旧执行会被递增后的 attempts 挡在门外。
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
        part = _save(
            part,
            status=ExportPartStatus.RUNNING,
            stage=ExportStage.DOWNLOAD_LOG,
            attempts=part.attempts + 1,
            started_at=timezone.now(),
        )
        logger.info(
            "[sharded_export_part_started] job_id=%s part_id=%s part_no=%s plan_version=%s "
            "attempts=%s task_id=%s start_time=%s end_time=%s",
            job.pk,
            part.pk,
            part.part_no,
            part.plan_version,
            part.attempts,
            part.task_id,
            part.start_time,
            part.end_time,
        )
        return part


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
            logger.info(
                "[sharded_export_part_result_discarded] job_id=%s part_id=%s attempts=%s task_id=%s "
                "current_attempts=%s current_task_id=%s status=%s job_status=%s",
                job.pk,
                part.pk,
                fence.attempts,
                fence.task_id,
                part.attempts,
                part.task_id,
                part.status,
                job.status,
            )
            # 已被超时回收并重新投递，本次结果作废
            return None
        now = timezone.now()
        if job.status != ExportJobStatus.RUNNING:
            logger.info(
                "[sharded_export_part_result_discarded] job_id=%s part_id=%s attempts=%s task_id=%s job_status=%s",
                job.pk,
                part.pk,
                fence.attempts,
                fence.task_id,
                job.status,
            )
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
        logger.info(
            "[sharded_export_part_completed] job_id=%s part_id=%s part_no=%s plan_version=%s "
            "attempts=%s task_id=%s actual_rows=%s actual_bytes=%s compressed_bytes=%s",
            job.pk,
            part.pk,
            part.part_no,
            part.plan_version,
            part.attempts,
            part.task_id,
            actual_rows,
            actual_bytes,
            compressed_bytes,
        )
        return part


def fail_part(part_id, fence, *, error_code, error_detail="", retryable=True):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=_job_id_of(part_id))
        part = ExportPart.objects.select_for_update().get(pk=part_id)
        if not _fenced(part, fence):
            return None
        return _fail_locked(job, part, error_code, error_detail, retryable=retryable)


def _classify_failure(job, part, error_code):
    """
    任务级失败分类：error_code 只表达原因，OVERSIZED_PART_FAILED 表示「已到最小时间精度且原因是工作量」，
    只有这种组合才建议用户缩小范围。是否还能细分与 _can_split 用同一口径，不依赖 oversized 标记。
    """
    if not ExportErrorCode.label(error_code):
        # 未登记的码不透给前端，否则前端只能拿到空文案
        return ExportErrorCode.PART_EXECUTION_FAILED
    if error_code in WORKLOAD_ERROR_CODES and part.end_time - part.start_time <= _split_step(job):
        return ExportErrorCode.OVERSIZED_PART_FAILED
    return error_code


def _fail_locked(job, part, error_code, error_detail, retryable=True):
    if part.status not in ExportPartStatus.INFLIGHT:
        return None
    # 阶段和投递身份随后可能被重置，先记录失败时的上下文以便追踪重试及超时回收。
    logger.warning(
        "[sharded_export_part_failure] job_id=%s part_id=%s part_no=%s plan_version=%s "
        "attempts=%s task_id=%s status=%s stage=%s start_time=%s end_time=%s "
        "retryable=%s error_code=%s error_detail=%s",
        job.pk,
        part.pk,
        part.part_no,
        part.plan_version,
        part.attempts,
        part.task_id,
        part.status,
        part.stage,
        part.start_time,
        part.end_time,
        retryable,
        error_code,
        (error_detail or "")[:2000],
    )
    now = timezone.now()
    changes = {"error_code": error_code, "error_detail": (error_detail or "")[:2000], "finished_at": now}
    if job.status == ExportJobStatus.CANCELED:
        return _save(part, status=ExportPartStatus.CANCELED, stage="", **changes)
    if (
        retryable
        and job.status in (ExportJobStatus.READY, ExportJobStatus.RUNNING)
        and part.attempts < policy_from_snapshot(job.policy).part_max_attempts
    ):
        logger.info(
            "[sharded_export_part_retry] job_id=%s part_id=%s attempts=%s task_id=%s error_code=%s",
            job.pk,
            part.pk,
            part.attempts,
            part.task_id,
            error_code,
        )
        return _save(part, status=ExportPartStatus.WAITING, stage="", task_id="", **changes)
    if _can_split(job, part, error_code):
        return _split_locked(job, part, error_code, error_detail)
    # 不再重试：让任务明确失败，避免用户拿到不完整的清单
    _save(part, status=ExportPartStatus.FAILED, stage="", **changes)
    if job.status in (ExportJobStatus.READY, ExportJobStatus.RUNNING):
        _finish_job(
            job,
            ExportJobStatus.FAILED,
            _classify_failure(job, part, error_code),
            f"分片 {part.part_no} 执行失败：{error_code}",
        )
    return part


def _can_split(job, part, error_code):
    """重试耗尽后是否能按时间继续细分；只有取数超时这类工作量证据才值得细分。"""
    policy = policy_from_snapshot(job.policy)
    if job.status not in (ExportJobStatus.READY, ExportJobStatus.RUNNING):
        return False
    if error_code not in WORKLOAD_ERROR_CODES:
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
    logger.info(
        "[sharded_export_part_split] job_id=%s part_id=%s plan_version=%s "
        "child_part_nos=%s,%s start_time=%s split_time=%s end_time=%s error_code=%s",
        job.pk,
        part.pk,
        part.plan_version,
        next_no,
        next_no + 1,
        part.start_time,
        middle,
        part.end_time,
        error_code,
    )
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
        return _fail_locked(job, part, ExportErrorCode.PART_TIMEOUT, "分片执行超时，已重新调度", retryable=True)


def recover_stale_parts(limit=None):
    """回收超时未完成的分片：一期不做租约心跳，超时未回填结果的一律交回调度器重试。"""
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


def finalization_window():
    """收尾（合并 + 清单生成）的重认领窗口：任务软超时必须早于它，避免旧执行未退出就重认领。"""
    return timedelta(seconds=settings.ASYNC_EXPORT_MERGE_TIMEOUT + settings.ASYNC_EXPORT_FINALIZATION_TIMEOUT)


def claim_finalization(job_id):
    """认领清单生成；超时的执行可重认领，旧尝试不能回填结果。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status not in (ExportJobStatus.RUNNING, ExportJobStatus.FINALIZING):
            return None
        now = timezone.now()
        if job.status == ExportJobStatus.FINALIZING and (
            job.finalization_started_at is None or now - job.finalization_started_at < finalization_window()
        ):
            return None
        stats = leaf_stats(job)
        if not stats["total"] or stats["success"] != stats["total"]:
            return None
        if job.finalization_attempts >= policy_from_snapshot(job.policy).finalization_attempts:
            _finish_job(job, ExportJobStatus.FAILED, ExportErrorCode.FINALIZATION_FAILED, "清单生成重试次数已耗尽")
            return None
        job = _save(
            job,
            status=ExportJobStatus.FINALIZING,
            finalization_started_at=now,
            finalization_attempts=job.finalization_attempts + 1,
        )
        logger.info(
            "[sharded_export_finalization_started] job_id=%s plan_version=%s finalization_attempts=%s "
            "parts_total=%s actual_total=%s",
            job.pk,
            job.plan_version,
            job.finalization_attempts,
            stats["total"],
            job.actual_total,
        )
        return job


def fail_finalization(job_id, finalization_attempt, detail="", code=ExportErrorCode.FINALIZATION_FAILED):
    """本次清单生成失败后交回调度器；达到预算时才让整单失败。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.FINALIZING or job.finalization_attempts != finalization_attempt:
            return None
        detail = (detail or "")[:2000]
        if finalization_attempt >= policy_from_snapshot(job.policy).finalization_attempts:
            return _finish_job(job, ExportJobStatus.FAILED, code, detail)
        logger.warning(
            "[sharded_export_finalization_retry] job_id=%s plan_version=%s finalization_attempts=%s "
            "error_code=%s error_detail=%s",
            job.pk,
            job.plan_version,
            finalization_attempt,
            code,
            detail,
        )
        return _save(
            job,
            status=ExportJobStatus.RUNNING,
            finalization_started_at=None,
            finalization_enqueued_at=None,
            error_code=code,
            error_detail=detail,
        )


def finalize_job(
    job_id,
    finalization_attempt,
    *,
    manifest_object_key,
    manifest_bytes,
    manifest_checksum,
    merged_object_key="",
    merged_bytes=None,
    merged_checksum="",
):
    """只有全部叶子分片成功、边界连续且数量自洽时才允许任务成功。"""
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status != ExportJobStatus.FINALIZING or job.finalization_attempts != finalization_attempt:
            logger.info(
                "[sharded_export_finalization_discarded] job_id=%s finalization_attempts=%s "
                "current_finalization_attempts=%s status=%s",
                job.pk,
                finalization_attempt,
                job.finalization_attempts,
                job.status,
            )
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
        job = _save(
            job,
            status=ExportJobStatus.SUCCESS,
            manifest_object_key=manifest_object_key,
            manifest_bytes=manifest_bytes,
            manifest_checksum=manifest_checksum,
            merged_object_key=merged_object_key,
            merged_bytes=merged_bytes,
            merged_checksum=merged_checksum,
            completed_at=now,
            expires_at=now + timedelta(seconds=policy_from_snapshot(job.policy).artifact_retention_seconds),
            error_code="",
            error_detail="",
        )
        logger.info(
            "[sharded_export_job_completed] job_id=%s plan_version=%s finalization_attempts=%s "
            "parts_total=%s actual_total=%s merged_bytes=%s manifest_bytes=%s",
            job.pk,
            job.plan_version,
            finalization_attempt,
            len(parts),
            total,
            merged_bytes,
            manifest_bytes,
        )
        return job


def cancel_job(job_id):
    with transaction.atomic():
        job = ExportJob.objects.select_for_update().get(pk=job_id)
        if job.status in ExportJobStatus.TERMINAL:
            return job
        return _finish_job(job, ExportJobStatus.CANCELED)


def _job_id_of(part_id):
    return ExportPart.objects.values_list("job_id", flat=True).get(pk=part_id)
