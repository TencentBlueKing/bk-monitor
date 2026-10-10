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
from rest_framework.exceptions import APIException, ValidationError

from apps.log_search.constants import (
    ExportJobStatus,
    ExportPartStatus,
    ExportSearchType,
    IndexSetType,
)
from apps.log_search.exceptions import PreCheckAsyncExportException
from apps.log_search.export.config import current_policy, is_sharded_export_enabled, policy_from_snapshot
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.storage import build_storage
from apps.log_search.models import AsyncTask, LogIndexSet, Space
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.utils import deal_time_format
from apps.utils.local import (
    get_request_app_code,
    get_request_external_username,
    get_request_username,
)
from apps.utils.log import logger


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


def normalize_legacy_export_params(data, *, search_type=ExportSearchType.INDEX_SET):
    """将旧入口的公共参数转换为分片任务参数。"""
    start_time, end_time = data["start_time"], data["end_time"]
    if search_type == ExportSearchType.SCENE:
        # 场景化时间兼容毫秒数字字符串，与 SceneUnifyQueryHandler 保持一致。
        if isinstance(start_time, str) and start_time.isdigit():
            start_time = int(start_time)
        if isinstance(end_time, str) and end_time.isdigit():
            end_time = int(end_time)
    start_ms, end_ms = deal_time_format(start_time, end_time)
    return {
        "search_type": search_type,
        "start_time": start_ms,
        # 旧入口使用闭区间，分片任务使用左闭右开区间。
        "end_time": end_ms + 1,
        "keyword": data.get("keyword") or "*",
        "addition": data.get("addition") or [],
        "ip_chooser": data.get("ip_chooser", {}),
        "sort_list": data.get("sort_list") or [],
        "export_fields": data.get("export_fields", []),
        "is_desensitize": data.get("is_desensitize", True),
    }


def create_export_job(data, raw_params=None):
    """创建分片导出任务；raw_params 为创建时的原始请求参数，未传时回退用 data 本身。"""
    username = get_request_external_username() or get_request_username(default="")
    space = Space.objects.get(space_uid=data["space_uid"])
    if not is_sharded_export_enabled(space.bk_biz_id):
        raise ValidationError({"detail": "分片导出未启用"})

    search_type = data.get("search_type", ExportSearchType.INDEX_SET)
    is_scene = search_type == ExportSearchType.SCENE
    if is_scene:
        index_set_ids = []
        index_set_type = ExportSearchType.SCENE
    else:
        index_set_ids = sorted(set(data.get("index_set_ids") or [data["index_set_id"]]))
        indexes = list(LogIndexSet.objects.filter(index_set_id__in=index_set_ids))
        if len(indexes) != len(index_set_ids):
            raise ValidationError({"index_set_ids": "索引集不存在"})
        if len(index_set_ids) > 1 and any(index.is_platform_index for index in indexes):
            raise ValidationError({"index_set_ids": "联合检索暂不支持平台级索引集"})

        # 单索引集／联合检索类型由入口明确传递，避免按去重后的 ID 数量误判（联合入口允许只有一项）
        index_set_type = data.get("index_set_type") or (
            IndexSetType.UNION.value if len(index_set_ids) > 1 else IndexSetType.SINGLE.value
        )

    params = copy.deepcopy(
        {
            "keyword": data.get("keyword", "*"),
            "addition": data.get("addition", []),
            "ip_chooser": data.get("ip_chooser", {}),
            "sort_list": data.get("sort_list", []),
            "export_fields": data.get("export_fields", []),
            "bk_biz_id": space.bk_biz_id,
            "is_desensitize": data.get("is_desensitize", True),
            "interval": "30s",
            "start_time": data["start_time"],
            "end_time": data["end_time"],
        }
    )
    if is_scene:
        params.update(space_uid=data["space_uid"], table_id_conditions=data["table_id_conditions"])
        handler = SceneUnifyQueryHandler(params)
    else:
        params.update(index_set_ids=index_set_ids, begin=data.get("begin", 0))
        handler = UnifyQueryHandler(params)

    # 冻结解析后的排序与脱敏结论，保证后续所有分片重建出完全一致的查询条件
    params["sort_list"] = copy.deepcopy(handler.origin_order_by)
    params["is_desensitize"] = handler.is_desensitize

    # 先按当前额度快速拒绝，避免为必然失败的任务发起查询；真正占额度在落库时锁内复检
    AsyncTask.check_running_count_by_user(username, is_scene=is_scene)

    policy = current_policy()
    requested_parallelism = data.get("requested_parallelism", policy.default_parallelism)
    if requested_parallelism > policy.max_parallelism:
        raise ValidationError({"requested_parallelism": f"并行度不能超过 {policy.max_parallelism}"})

    pre_check_size = 1000 if search_type == ExportSearchType.SCENE else 1
    try:
        result = handler.pre_get_result(sorted_fields=handler.origin_order_by, size=pre_check_size)
    except Exception as error:  # pylint: disable=broad-except
        logger.exception(
            "[sharded_export_precheck_failure] space_uid=%s search_type=%s index_set_ids=%s",
            space.space_uid,
            search_type,
            index_set_ids,
        )
        raise PreCheckAsyncExportException(f"导出预检查查询失败：{error}") from error
    if not result.get("list"):
        raise PreCheckAsyncExportException()

    # 额度复检与落库必须在同一把用户级锁内：两个并发请求都通过上面的检查时，
    # 只有一个能在锁内看到对方的任务并真正占住额度
    with AsyncTask.export_create_lock(username, is_scene=is_scene):
        AsyncTask.check_running_count_by_user(username, is_scene=is_scene)
        job = ExportJob.objects.create(
            space_uid=space.space_uid,
            created_by=username,
            source_app_code=get_request_app_code(),
            is_external=bool(get_request_external_username()),
            search_type=search_type,
            index_set_ids=index_set_ids,
            index_set_type=index_set_type,
            bk_biz_id=space.bk_biz_id,
            search_params=params,
            base_dict=copy.deepcopy(handler.base_dict),
            raw_params=raw_params if raw_params is not None else data,
            policy=policy.snapshot(),
            start_time=data["start_time"],
            end_time=data["end_time"],
            requested_parallelism=requested_parallelism,
            status=ExportJobStatus.PENDING,
        )
    logger.info(
        "[sharded_export_job_created] job_id=%s space_uid=%s search_type=%s index_set_ids=%s "
        "start_time=%s end_time=%s requested_parallelism=%s",
        job.pk,
        job.space_uid,
        job.search_type,
        job.index_set_ids,
        job.start_time,
        job.end_time,
        job.requested_parallelism,
    )
    return job


def download_link(job, artifact_id):
    """按需签发下载链接，有效期不超过产物的剩余保留时间。"""
    if job.status != ExportJobStatus.SUCCESS:
        raise ExportConflict("导出尚未完成")
    if job.expires_at is None or job.expires_at <= timezone.now():
        raise ExportExpired()
    if artifact_id == "manifest":
        name = job.manifest_object_key
    elif artifact_id == "full":
        name = job.merged_object_key
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
        storage = build_storage(external=job.is_external)
        url = storage.generate_download_url(file_name=name, expired=ttl)
    except Exception as error:  # pylint: disable=broad-except
        logger.exception(
            "[sharded_export_download_failure] job_id=%s artifact_id=%s is_external=%s",
            job.pk,
            artifact_id,
            job.is_external,
        )
        raise ExportStorageUnavailable() from error
    return {"url": url, "expires_at": timezone.now() + timedelta(seconds=ttl)}
