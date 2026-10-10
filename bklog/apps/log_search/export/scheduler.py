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
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from blueapps.core.celery.celery import app
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.log_search.constants import ExportErrorCode, ExportJobStatus, ExportPartStatus, ExportSearchType
from apps.log_search.export import state
from apps.log_search.export.config import (
    FINALIZE_QUEUE,
    FINALIZE_TASK_NAME,
    PART_QUEUE,
    PART_TASK_NAME,
    PLAN_QUEUE,
    PLAN_TASK_NAME,
    current_policy,
    policy_from_snapshot,
)
from apps.log_search.export.merger import merge_export_parts
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.storage import build_storage, manifest_name
from apps.utils.log import logger


def _send(task_name, *args, **kwargs):
    queue = kwargs.pop("queue", PLAN_QUEUE)
    return app.send_task(task_name, args=list(args), queue=queue, retry=False, **kwargs)


def _lease_expired(field, now):
    """还没入队，或上次入队已经超过一个租约窗口。"""
    lease = timedelta(seconds=settings.ASYNC_EXPORT_ENQUEUE_LEASE_SECONDS)
    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__lt": now - lease})


def _enqueue(job_ids, field, statuses, task_name, queue=PLAN_QUEUE):
    """条件更新抢占入队租约以防重复发布；发布失败释放租约，崩溃或消息丢失由租约到期恢复。"""
    sent = []
    for job_id in job_ids:
        now = timezone.now()
        claimed = (
            ExportJob.objects.filter(pk=job_id, status__in=statuses)
            .filter(_lease_expired(field, now))
            .update(**{field: now})
        )
        if not claimed:
            continue
        try:
            message = _send(task_name, job_id, queue=queue)
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("[%s] job=%s publish failed: %s", task_name, job_id, error)
            ExportJob.objects.filter(pk=job_id).update(**{field: None})
            continue
        sent.append(job_id)
        logger.info(
            "[sharded_export_job_enqueued] job_id=%s task_name=%s task_id=%s queue=%s",
            job_id,
            task_name,
            getattr(message, "id", None),
            queue,
        )
    return sent


def planning_jobs(limit):
    """待规划且未入队的任务：新建的，或规划超时的；尝试次数由 claim_planning 按任务策略判定。"""
    now = timezone.now()
    timeout = timedelta(seconds=settings.ASYNC_EXPORT_PLANNING_TIMEOUT)
    return list(
        ExportJob.objects.filter(status__in=[ExportJobStatus.PENDING, ExportJobStatus.PLANNING])
        .filter(Q(status=ExportJobStatus.PENDING) | Q(planning_started_at__lt=now - timeout))
        .filter(_lease_expired("planning_enqueued_at", now))
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )


def enqueue_planning(limit):
    return _enqueue(
        planning_jobs(limit),
        "planning_enqueued_at",
        [ExportJobStatus.PENDING, ExportJobStatus.PLANNING],
        PLAN_TASK_NAME,
    )


def _quota_keys(job):
    """额度维度键：索引集检索按索引集，场景化检索退化为按空间（无固定索引集）。"""
    return job.index_set_ids or [f"scene:{job.space_uid}"]


def _inflight_by_index_set():
    rows = list(
        ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT).values("job_id").annotate(total=Count("pk"))
    )
    jobs = ExportJob.objects.in_bulk(row["job_id"] for row in rows)
    counts = {}
    for row in rows:
        for key in _quota_keys(jobs[row["job_id"]]):
            counts[key] = counts.get(key, 0) + row["total"]
    return counts


def dispatch_ready_parts(deadline=None):
    """
    按公平顺序投递分片。

    额度取单 Job、单索引集、环境全局三者取小；在途分片按数据库全表计数，本身就是预算账本，
    轮次之间由调度任务的共享锁保证不会同时算出两份额度。多任务同时等待时按剩余任务数依次切分
    （两个任务即 2+2），用不完的份额当轮让给后面的任务。
    oversized 分片另受单 Job 和环境上限约束，额度不足时先投同一个任务的普通分片。
    轮次有单调时钟预算：用尽后在两次写库之间收尾，避免单轮活过调度锁租约后与下一轮重叠放量。
    """
    jobs = list(
        ExportJob.objects.filter(status__in=[ExportJobStatus.READY, ExportJobStatus.RUNNING]).order_by(
            F("last_dispatched_at").asc(nulls_first=True), "pk"
        )[: settings.ASYNC_EXPORT_COORDINATE_BATCH]
    )
    if not jobs:
        return []

    policy = current_policy()
    if policy.global_parallelism <= 0:
        # 显式配成 0 表示停投：宁可任务停在 READY，也不要绕过环境容量约束继续放量
        logger.warning("[dispatch_ready_parts] 环境全局并行度已停投，%s 个任务已跳过投递", len(jobs))
        return []

    index_limit, global_limit = policy.index_parallelism, policy.global_parallelism
    index_inflight = _inflight_by_index_set()
    global_inflight = ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT).count()
    oversized_limit = policy.oversized_global_parallelism
    oversized_inflight = ExportPart.objects.filter(oversized=True, status__in=ExportPartStatus.INFLIGHT).count()
    # 本轮还有待投递分片的任务；份额按剩余额度动态切分，空出的额度当轮就让给后面的任务
    waiting_rows = (
        ExportPart.objects.filter(status=ExportPartStatus.WAITING, job__in=jobs)
        .values("job_id", "oversized")
        .annotate(total=Count("pk"))
    )
    waiting_jobs = {row["job_id"] for row in waiting_rows}
    # 有 oversized 分片在排队的任务，供额度不足时判断谁被挡下
    oversized_waiting_jobs = {row["job_id"] for row in waiting_rows if row["oversized"]}
    remaining_jobs = len(waiting_jobs)
    # 本轮因 oversized 额度不足而没投出超大分片的任务，按轮汇总告警
    held_oversized_jobs = set()
    # 轮次时间预算用尽：不再开始新的投递，剩余分片等下一个调度周期
    deadline_reached = False
    dispatched = []
    for job in jobs:
        if deadline_reached:
            break
        if job.pk not in waiting_jobs:
            continue
        shared_limit = max(1, (global_limit - global_inflight) // max(1, remaining_jobs))
        remaining_jobs -= 1
        job_inflight_counts = ExportPart.objects.filter(job=job, status__in=ExportPartStatus.INFLIGHT).aggregate(
            total=Count("pk"), oversized=Count("pk", filter=Q(oversized=True))
        )
        job_inflight = job_inflight_counts["total"]
        job_oversized_inflight = job_inflight_counts["oversized"]
        index_set_ids = _quota_keys(job)
        # 任务自身的期望并行度仍是上限，切分只用于在任务之间分配全局额度
        job_limit = min(job.requested_parallelism, shared_limit)
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                # 只在两次写库之间收尾：不会留下已占额度但没投出去的分片
                deadline_reached = True
                break
            index_capacity = min(index_limit - index_inflight.get(index_set_id, 0) for index_set_id in index_set_ids)
            capacity = min(job_limit - job_inflight, index_capacity, global_limit - global_inflight)
            if capacity <= 0:
                break
            waiting_parts = ExportPart.objects.filter(job=job, status=ExportPartStatus.WAITING)
            if oversized_inflight >= oversized_limit or job_oversized_inflight >= policy.oversized_parallelism:
                # 额度不足：把 oversized 分片从候选里剔除，先投递同一个任务后面的普通分片
                waiting_parts = waiting_parts.filter(oversized=False)
                if job.pk in oversized_waiting_jobs:
                    held_oversized_jobs.add(job.pk)
            part = waiting_parts.order_by("start_time", "part_no").first()
            if part is None:
                break
            part = state.dispatch_part(part.pk, uuid4().hex)
            if part is None:
                break
            try:
                # 投递身份由 Celery 消息 id 承载，消息体只带 part_id
                _send(PART_TASK_NAME, part.pk, task_id=part.task_id, queue=PART_QUEUE)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception("[dispatch_ready_parts] part=%s publish failed: %s", part.pk, error)
                state.fail_part(
                    part.pk,
                    state.PartFence.of(part),
                    error_code=ExportErrorCode.DISPATCH_FAILED,
                    error_detail="投递到 Celery 失败",
                    retryable=True,
                )
                break
            dispatched.append(part.pk)
            logger.info(
                "[sharded_export_part_enqueued] job_id=%s part_id=%s part_no=%s plan_version=%s task_id=%s queue=%s",
                job.pk,
                part.pk,
                part.part_no,
                part.plan_version,
                part.task_id,
                PART_QUEUE,
            )
            job_inflight += 1
            for index_set_id in index_set_ids:
                index_inflight[index_set_id] = index_inflight.get(index_set_id, 0) + 1
            global_inflight += 1
            oversized_inflight += int(part.oversized)
            job_oversized_inflight += int(part.oversized)
    if deadline_reached:
        logger.warning("[dispatch_ready_parts] 轮次时间预算用尽，剩余分片交由下一个调度周期投递")
    if held_oversized_jobs:
        logger.info(
            "[dispatch_ready_parts] oversized 额度不足（单 Job %s / 环境 %s），%s 个任务的 oversized 分片本轮未投递",
            policy.oversized_parallelism,
            oversized_limit,
            len(held_oversized_jobs),
        )
    return dispatched


def finalizing_jobs(limit):
    """叶子分片全部成功、且尚未入队收尾（或入队租约已过期）的任务。"""
    now = timezone.now()
    cutoff = now - state.finalization_window()
    return list(
        ExportJob.objects.filter(
            Q(status=ExportJobStatus.RUNNING)
            | Q(status=ExportJobStatus.FINALIZING, finalization_started_at__lt=cutoff),
            plan_version__gt=0,
        )
        .filter(_lease_expired("finalization_enqueued_at", now))
        .annotate(**state.leaf_counts_annotation())
        .filter(leaf_total__gt=0, leaf_success=F("leaf_total"))
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )


def enqueue_finalization(limit):
    return _enqueue(
        finalizing_jobs(limit),
        "finalization_enqueued_at",
        [ExportJobStatus.RUNNING, ExportJobStatus.FINALIZING],
        FINALIZE_TASK_NAME,
        queue=FINALIZE_QUEUE,
    )


def manifest_snapshot(job, parts, *, merged_object_key="", merged_bytes=None, merged_checksum=""):
    """清单只汇总成功叶子分片，边界与条数在提交时再次校验。"""
    snapshot = {
        "schema_version": 1,
        "job_id": job.pk,
        "search_type": job.search_type,
        "index_set_ids": job.index_set_ids,
        "consistency": "weak_snapshot",
        "interval": "[start_time, end_time)",
        "estimated_total": job.estimated_total,
        "actual_total": job.actual_total,
        "expires_after_success_seconds": policy_from_snapshot(job.policy).artifact_retention_seconds,
        "parts": [
            {
                "part_id": part.pk,
                "part_no": part.part_no,
                "start_time": part.start_time,
                "end_time": part.end_time,
                "oversized": part.oversized,
                "actual_rows": part.actual_rows,
                "actual_bytes": part.actual_bytes,
                "compressed_bytes": part.compressed_bytes,
                "object_key": part.object_key,
                "checksum": part.checksum,
                "checksum_algorithm": "sha256",
            }
            for part in parts
        ],
    }
    if merged_object_key:
        snapshot["merged"] = {
            "object_key": merged_object_key,
            "compressed_bytes": merged_bytes,
            "checksum": merged_checksum,
            "checksum_algorithm": "sha256",
        }
    if job.search_type == ExportSearchType.SCENE:
        snapshot["table_id_conditions"] = job.search_params.get("table_id_conditions")
    return snapshot


def finalize_export(job_id):
    """任务的叶子分片都成功后，合并成整包并生成清单，再让任务进入成功态。"""
    job = state.claim_finalization(job_id)
    if job is None:
        return None
    parts = list(state.leaf_parts(job).order_by("start_time", "part_no"))
    if not parts or any(part.status != ExportPartStatus.SUCCESS for part in parts):
        state.fail_finalization(job_id, job.finalization_attempts, "分片尚未全部成功")
        return None
    try:
        merged_key, merged_bytes, merged_checksum = merge_export_parts(job, parts)
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("[finalize_export] job=%s merge failed: %s", job.pk, error)
        state.fail_finalization(
            job_id, job.finalization_attempts, type(error).__name__, code=ExportErrorCode.MERGE_FAILED
        )
        return None
    logger.info(
        "[sharded_export_merge_completed] job_id=%s finalization_attempts=%s merged_bytes=%s",
        job.pk,
        job.finalization_attempts,
        merged_bytes,
    )
    try:
        content = json.dumps(
            manifest_snapshot(
                job, parts, merged_object_key=merged_key, merged_bytes=merged_bytes, merged_checksum=merged_checksum
            ),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with tempfile.TemporaryDirectory(prefix=f"bklog-export-manifest-{job.pk}-") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(content)
            logger.info(
                "[sharded_export_manifest_upload] job_id=%s finalization_attempts=%s manifest_bytes=%s",
                job.pk,
                job.finalization_attempts,
                len(content),
            )
            build_storage(external=job.is_external).export_upload(file_path=str(path), file_name=manifest_name(job))
        return state.finalize_job(
            job_id,
            job.finalization_attempts,
            manifest_object_key=manifest_name(job),
            manifest_bytes=len(content),
            manifest_checksum=hashlib.sha256(content).hexdigest(),
            merged_object_key=merged_key,
            merged_bytes=merged_bytes,
            merged_checksum=merged_checksum,
        )
    except Exception as error:  # pylint: disable=broad-except
        logger.exception("[finalize_export] job=%s manifest failed: %s", job.pk, error)
        state.fail_finalization(job_id, job.finalization_attempts, type(error).__name__)
        return None


def coordinate(limit=None):
    """周期控制入口：回收超时分片、补投规划/收尾消息、按额度投递分片。"""
    limit = limit or settings.ASYNC_EXPORT_COORDINATE_BATCH
    started = time.monotonic()
    # 轮次时间预算必须早于调度锁租约到期：超时的轮次会和下一轮重叠，按旧快照重复发放额度
    deadline = started + settings.ASYNC_EXPORT_COORDINATE_DEADLINE_SECONDS
    recovered = state.recover_stale_parts(limit)
    planned = enqueue_planning(limit)
    dispatched = dispatch_ready_parts(deadline)
    finalized = enqueue_finalization(limit)
    result = {
        "recovered": len(recovered),
        "planned": len(planned),
        "dispatched": len(dispatched),
        "finalized": len(finalized),
    }
    logger.info("[coordinate] %s cost=%.3fs", result, time.monotonic() - started)
    return result
