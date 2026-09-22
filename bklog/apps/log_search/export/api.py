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
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.reverse import reverse

from apps.log_search.constants import ExportJobStatus, ExportPartStatus, ExportStage
from apps.log_search.export import state
from apps.log_search.export.config import current_policy, is_enabled, policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.storage import UnsupportedExportStorage, build_storage, download_url
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import AsyncTask, LogIndexSet, Space
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.local import (
    get_request_app_code,
    get_request_external_username,
    get_request_tenant_id,
    get_request_username,
)


TERMINAL = ExportJobStatus.TERMINAL
INFLIGHT = ExportPartStatus.INFLIGHT
# 进度展示时取最靠后的阶段
STAGE_ORDER = [ExportStage.DOWNLOAD_LOG, ExportStage.PACKAGE, ExportStage.UPLOAD]
TIME_TICK_BY_UNIT = {"second": 1000, "millisecond": 1}


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


def resolve_time_tick(index_set_id):
    """时间字段的最小精度，决定分片递归的下界。"""
    _, _, unit = SearchHandler.init_time_field(index_set_id)
    tick = TIME_TICK_BY_UNIT.get(unit)
    if not tick:
        raise ValidationError({"detail": "暂不支持该索引集的时间字段精度"})
    return tick


def create_export_job(data):
    """创建分片导出任务。"""
    username = get_request_username(default="")
    if not username or get_request_external_username():
        raise PermissionDenied("仅支持 Web 用户创建分片导出任务")
    space = get_object_or_404(Space, space_uid=data["space_uid"], bk_tenant_id=get_request_tenant_id())
    if not is_enabled(space.bk_biz_id):
        raise ValidationError({"detail": "分片导出未启用"})
    # 只支持对象存储；配置不匹配时在创建阶段就失败，避免任务跑到执行阶段才报错
    try:
        build_storage()
    except UnsupportedExportStorage as error:
        raise ValidationError({"detail": str(error)}) from error
    index = get_object_or_404(LogIndexSet, pk=data["index_set_id"], space_uid=space.space_uid)

    tick = resolve_time_tick(index.pk)
    if data["start_time"] % tick or data["end_time"] % tick:
        raise ValidationError({"detail": "导出时间范围必须对齐时间字段精度"})

    # 与旧异步导出共用同一个用户级并发额度
    AsyncTask.check_running_count_by_user(username)

    params = {
        key: copy.deepcopy(data[key]) for key in ("keyword", "addition", "ip_chooser", "sort_list", "export_fields")
    }
    params.update(
        start_time=data["start_time"],
        end_time=data["end_time"],
        index_set_ids=[index.pk],
        bk_biz_id=space.bk_biz_id,
        is_desensitize=True,
        interval="30s",
    )
    handler = UnifyQueryHandler(params)
    if data["sort_list"]:
        handler.check_sort_list(handler.fields()["fields"], data["sort_list"])
    # 冻结解析后的排序与脱敏结论，保证后续所有分片重建出完全一致的查询条件
    params["sort_list"] = copy.deepcopy(handler.origin_order_by)
    params["is_desensitize"] = handler.is_desensitize

    policy = current_policy()
    requested_parallelism = data.get("requested_parallelism", policy.default_parallelism)
    if requested_parallelism > policy.max_parallelism:
        raise ValidationError({"requested_parallelism": f"并行度不能超过 {policy.max_parallelism}"})

    return ExportJob.objects.create(
        space_uid=space.space_uid,
        created_by=username,
        source_app_code=get_request_app_code(),
        index_set_id=index.pk,
        bk_biz_id=space.bk_biz_id,
        search_params=params,
        base_dict=copy.deepcopy(handler.base_dict),
        policy=policy.snapshot(),
        start_time=data["start_time"],
        end_time=data["end_time"],
        time_tick=tick,
        requested_parallelism=requested_parallelism,
        status=ExportJobStatus.PENDING,
    )


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
        "requested_parallelism": job.requested_parallelism,
        "error_code": job.error_code,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "expires_at": job.expires_at,
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
