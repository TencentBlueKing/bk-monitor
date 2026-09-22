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

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.reverse import reverse

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import IAMPermission
from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportStage
from apps.log_search.export import state
from apps.log_search.export.config import policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.storage import build_storage, download_url
from apps.log_search.models import Space
from apps.utils.local import get_request_app_code, get_request_tenant_id, get_request_username


TERMINAL = ExportJobStatus.TERMINAL
INFLIGHT = ExportPartStatus.INFLIGHT
# 进度展示时取最靠后的阶段
STAGE_ORDER = [ExportStage.DOWNLOAD_LOG, ExportStage.PACKAGE, ExportStage.UPLOAD]


class ExportConflict(APIException):
    status_code = 409
    default_detail = "当前任务状态不允许该操作"
    default_code = "EXPORT_INVALID_STATE"


class ExportExpired(APIException):
    status_code = 410
    default_detail = "导出产物已过期"
    default_code = "EXPORT_FILE_EXPIRED"


class ExportStorageUnavailable(APIException):
    status_code = 503
    default_detail = "导出产物存储暂不可用"
    default_code = "EXPORT_STORAGE_UNAVAILABLE"


def authorized_job(request, job_id, space_uid, *, operate=False):
    """按空间、来源应用和索引集检索权限三重校验任务可见性。"""
    username = get_request_username(default="")
    if not username:
        raise PermissionDenied("缺少用户身份")
    job = get_object_or_404(ExportJob, pk=job_id, space_uid=space_uid, source_app_code=get_request_app_code())
    if not Space.objects.filter(space_uid=job.space_uid, bk_tenant_id=get_request_tenant_id()).exists():
        raise Http404
    IAMPermission([ActionEnum.SEARCH_LOG], [ResourceEnum.INDICES.create_instance(job.index_set_id)]).has_permission(
        request, None
    )
    if operate and job.created_by != username:
        raise PermissionDenied("只有任务创建者可以操作该任务")
    return job


def job_detail(job):
    """任务进度：预计条数与实际条数分开，完成度按已成功的分片数计算。"""
    stages = list(ExportPart.objects.filter(job=job, status__in=INFLIGHT).values_list("stage", flat=True))
    total, success = job.part_total, job.part_success
    if job.status == ExportJobStatus.SUCCESS:
        percent = 100
    elif not total:
        percent = 0
    else:
        percent = min(99, success * 100 // total)
    stage = ""
    if job.status not in TERMINAL:
        if total and success >= total:
            stage = ExportStage.FINALIZING
        else:
            stage = next((value for value in reversed(STAGE_ORDER) if value in stages), "")
    expired = job.status == ExportJobStatus.SUCCESS and job.expires_at is not None and job.expires_at <= timezone.now()
    return {
        "job_id": job.pk,
        "status": "EXPIRED" if expired else job.status,
        "stage": stage,
        "estimated_total": job.estimated_total,
        "actual_total": job.actual_total,
        "parts_total": total,
        "parts_completed": success,
        "percent": percent,
        "percent_basis": "completed_parts",
        "requested_parallelism": job.requested_parallelism,
        "inflight_parts": len(stages),
        "error_code": job.error_code,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "expires_at": job.expires_at,
        "poll_after": None if job.status in TERMINAL else 3,
        "can_operate": job.created_by == get_request_username(default="") and job.status not in TERMINAL,
    }


def job_results(job):
    if job.status != ExportJobStatus.SUCCESS:
        raise ExportConflict("导出尚未完成")
    if job.expires_at is None or job.expires_at <= timezone.now():
        raise ExportExpired()
    parts = list(ExportPart.objects.filter(job=job, status=ExportPartStatus.SUCCESS).order_by("start_time", "part_no"))
    if not parts or not job.manifest_object_key:
        raise ExportConflict("导出产物不完整")
    return {
        "job_id": job.pk,
        "estimated_total": job.estimated_total,
        "actual_total": job.actual_total,
        "expires_at": job.expires_at,
        "manifest": {
            "artifact_id": "manifest",
            "compressed_bytes": job.manifest_bytes,
        },
        "parts": [
            {
                "artifact_id": str(part.pk),
                "part_id": part.pk,
                "part_no": part.part_no,
                "start_time": part.start_time,
                "end_time": part.end_time,
                "oversized": part.oversized,
                "actual_rows": part.actual_rows,
                "actual_bytes": part.actual_bytes,
                "compressed_bytes": part.compressed_bytes,
                "checksum": part.checksum,
            }
            for part in parts
        ],
    }


def download_link(request, job, artifact_id):
    """按需签发下载链接，有效期不超过产物的剩余保留时间。"""
    job_results(job)
    if artifact_id == "manifest":
        name = job.manifest_object_key
    else:
        part = get_object_or_404(ExportPart, pk=int(artifact_id), job=job, status=ExportPartStatus.SUCCESS)
        name = part.object_key
    if not name:
        raise ExportConflict("导出产物不存在")
    remaining = int((job.expires_at - timezone.now()).total_seconds())
    ttl = min(remaining, policy_from_snapshot(job.policy).signed_url_seconds)
    if ttl <= 0:
        raise ExportExpired()
    try:
        storage = build_storage()
        url = download_url(storage, reverse("tasks-download-file", request=request), name, ttl=ttl)
    except Exception as error:  # pylint: disable=broad-except
        raise ExportStorageUnavailable() from error
    return {"url": url, "expires_at": timezone.now() + timedelta(seconds=ttl)}


def cancel_job(job_id):
    return job_detail(state.cancel_job(job_id))


def set_parallelism(job_id, value):
    job = ExportJob.objects.filter(pk=job_id).first()
    if job is None:
        raise Http404
    if job.status in TERMINAL:
        raise ExportConflict("任务已结束，无法调整并行度")
    maximum = policy_from_snapshot(job.policy).max_parallelism
    if value > maximum:
        raise ExportConflict(f"并行度不能超过任务创建时的上限 {maximum}")
    return job_detail(state.set_parallelism(job_id, value))
