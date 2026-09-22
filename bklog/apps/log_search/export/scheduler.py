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
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from blueapps.core.celery.celery import app
from django.conf import settings
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.log_search.constants import ExportJobStatus, ExportPartStatus
from apps.log_search.export import state
from apps.log_search.export.config import (
    FINALIZE_TASK_NAME,
    PART_TASK_NAME,
    PLAN_TASK_NAME,
    current_policy,
    policy_from_snapshot,
)
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.storage import (
    artifact_name,
    build_storage,
    manifest_name,
    remove_local_artifact,
    supports_artifact_cleanup,
    upload,
)
from apps.utils.log import logger


def _send(task_name, *args, **kwargs):
    queue = kwargs.pop("queue", settings.ASYNC_EXPORT_CONTROL_QUEUE)
    return app.send_task(task_name, args=list(args), queue=queue, retry=False, **kwargs)


def planning_jobs(limit):
    """待规划的任务：新建的，或规划超时的；尝试次数由 claim_planning 按任务策略判定。"""
    timeout = timedelta(seconds=settings.ASYNC_EXPORT_PLANNING_TIMEOUT)
    return list(
        ExportJob.objects.filter(status__in=[ExportJobStatus.PENDING, ExportJobStatus.PLANNING])
        .filter(Q(status=ExportJobStatus.PENDING) | Q(planning_started_at__lt=timezone.now() - timeout))
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )


def enqueue_planning(limit):
    job_ids = planning_jobs(limit)
    for job_id in job_ids:
        _send(PLAN_TASK_NAME, job_id)
    return job_ids


def _inflight_by_index_set():
    rows = (
        ExportPart.objects.filter(status__in=ExportPartStatus.INFLIGHT)
        .values("job__index_set_id")
        .annotate(total=Count("pk"))
    )
    return {row["job__index_set_id"]: row["total"] for row in rows}


def dispatch_ready_parts():
    """
    按公平顺序投递分片。

    并行额度只来自 FeatureConfig：单 Job 上限、单索引集上限、环境全局上限三者取小。
    一期不引入分布式令牌：在途分片本身就是预算账本，直接按数据库计数判断是否还有额度；
    并发投递由「先占用分片状态、再发布消息」和行锁兜底，极端情况下可能略微超出全局上限。
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
        # 环境容量没有配置就不投递：宁可任务停在 READY，也不要多 Pod 各自按本地预算相乘
        logger.warning("[dispatch_ready_parts] 环境全局并行度未配置，%s 个任务已跳过投递", len(jobs))
        return []

    index_limit, global_limit = policy.index_parallelism, policy.global_parallelism
    index_inflight = _inflight_by_index_set()
    global_inflight = sum(index_inflight.values())
    dispatched = []
    for job in jobs:
        job_inflight = ExportPart.objects.filter(job=job, status__in=ExportPartStatus.INFLIGHT).count()
        index_used = index_inflight.get(job.index_set_id, 0)
        while True:
            capacity = min(
                job.requested_parallelism - job_inflight,
                index_limit - index_used,
                global_limit - global_inflight,
            )
            if capacity <= 0:
                break
            part = ExportPart.objects.filter(job=job, status=ExportPartStatus.WAITING).order_by("part_no").first()
            if part is None:
                break
            part = state.dispatch_part(part.pk, uuid4().hex)
            if part is None:
                break
            try:
                _send(PART_TASK_NAME, part.pk, task_id=part.task_id, queue=settings.ASYNC_EXPORT_PART_QUEUE)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception("[dispatch_ready_parts] part=%s publish failed: %s", part.pk, error)
                state.fail_part(
                    part.pk, error_code="DISPATCH_FAILED", error_detail="投递到 Celery 失败", retryable=True
                )
                break
            dispatched.append(part.pk)
            job_inflight += 1
            index_used += 1
            global_inflight += 1
    return dispatched


def finalizing_jobs(limit):
    return list(
        ExportJob.objects.filter(
            status=ExportJobStatus.RUNNING,
            part_total__gt=0,
            part_success=F("part_total"),
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )


def enqueue_finalization(limit):
    job_ids = finalizing_jobs(limit)
    for job_id in job_ids:
        _send(FINALIZE_TASK_NAME, job_id)
    return job_ids


def manifest_snapshot(job, parts):
    """清单只汇总成功分片，边界与条数由状态流转在提交时再次校验。"""
    return {
        "schema_version": 1,
        "job_id": job.pk,
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


def finalize_export(job_id):
    """任务的全部有效分片都成功后，生成清单并让任务进入成功态。"""
    job = ExportJob.objects.filter(pk=job_id).first()
    if job is None or job.status != ExportJobStatus.RUNNING:
        return None
    parts = list(ExportPart.objects.filter(job=job).order_by("start_time", "part_no"))
    if not parts or any(part.status != ExportPartStatus.SUCCESS for part in parts):
        return None
    try:
        content = json.dumps(
            manifest_snapshot(job, parts), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        with tempfile.TemporaryDirectory(prefix=f"bklog-export-manifest-{job.pk}-") as directory:
            path = Path(directory) / "manifest.json"
            path.write_bytes(content)
            upload(build_storage(), path, manifest_name(job))
        return state.finalize_job(job_id, manifest_object_key=manifest_name(job), manifest_bytes=len(content))
    except Exception as error:  # pylint: disable=broad-except
        # 分片产物都已成功，清单失败不能让调度器无限重投，直接给出明确错误
        logger.exception("[finalize_export] job=%s manifest failed: %s", job.pk, error)
        state.fail_job(job_id, "FINALIZATION_FAILED", type(error).__name__)
        return None


def artifact_names(job):
    """
    任务可能产生的全部产物名。

    分片产物名是 (job, part_no) 的纯函数，所以重试、重复投递和超时回收竞态里写出去、
    但没有成功回填的分片也能被枚举到；同时并入已记录的对象名，兜住升级前随机命名的产物。
    """
    names = {manifest_name(job)}
    for part_no, object_key in ExportPart.objects.filter(job=job).values_list("part_no", "object_key"):
        names.add(artifact_name(job, part_no))
        if object_key:
            names.add(object_key)
    return names


def cleanup_artifacts(limit):
    """清理已过期或已终止任务的产物；仍在途的分片会让任务延后到下一轮。"""
    now = timezone.now()
    candidates = ExportJob.objects.filter(artifacts_cleaned_at__isnull=True).filter(
        Q(status=ExportJobStatus.SUCCESS, expires_at__lte=now)
        | Q(status__in=[ExportJobStatus.FAILED, ExportJobStatus.CANCELED])
    )
    cleaned = []
    storage = None
    for job in candidates.order_by("pk")[:limit]:
        if ExportPart.objects.filter(job=job, status__in=ExportPartStatus.INFLIGHT).exists():
            continue
        if storage is None:
            storage = build_storage()
        if not supports_artifact_cleanup(storage):
            # 对象存储一期没有删除接口，产物交给桶的生命周期策略回收；
            # 标记后不再重复扫描，但不计入"已清理"
            logger.info("[cleanup_artifacts] job=%s 产物依赖对象存储生命周期策略回收", job.pk)
            state.mark_artifacts_cleaned(job.pk)
            continue
        failed = False
        for name in artifact_names(job):
            try:
                remove_local_artifact(storage, name)
            except OSError as error:
                logger.exception("[cleanup_artifacts] job=%s name=%s remove failed: %s", job.pk, name, error)
                failed = True
        if failed:
            continue
        state.mark_artifacts_cleaned(job.pk)
        cleaned.append(job.pk)
    return cleaned


def coordinate(limit=None):
    """周期控制入口：回收超时分片、补投规划/收尾消息、按额度投递分片、清理过期产物。"""
    limit = limit or settings.ASYNC_EXPORT_COORDINATE_BATCH
    started = time.monotonic()
    recovered = state.recover_stale_parts(limit)
    planned = enqueue_planning(limit)
    dispatched = dispatch_ready_parts()
    finalized = enqueue_finalization(limit)
    cleaned = cleanup_artifacts(limit)
    result = {
        "recovered": len(recovered),
        "planned": len(planned),
        "dispatched": len(dispatched),
        "finalized": len(finalized),
        "cleaned": len(cleaned),
    }
    logger.info("[coordinate] %s cost=%.3fs", result, time.monotonic() - started)
    return result
