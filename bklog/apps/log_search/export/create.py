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

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import IAMPermission
from apps.log_search.constants import ExportJobStatus
from apps.log_search.export.config import current_policy, is_enabled
from apps.log_search.export.models import ExportJob
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import AsyncTask, LogIndexSet, Space
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.utils.local import (
    get_request,
    get_request_app_code,
    get_request_external_username,
    get_request_tenant_id,
    get_request_username,
)


TIME_TICK_BY_UNIT = {"second": 1000, "millisecond": 1}


def resolve_time_tick(index_set_id):
    """时间字段的最小精度，决定分片递归的下界。"""
    _, _, unit = SearchHandler.init_time_field(index_set_id)
    tick = TIME_TICK_BY_UNIT.get(unit)
    if not tick:
        raise ValidationError({"detail": "暂不支持该索引集的时间字段精度"})
    return tick


def create_export_job(data):
    """
    创建分片导出任务。

    创建阶段只做权限校验和查询条件冻结，不做统计查询，也不发布任何 broker 消息；
    真正的规划由周期调度器发现 PENDING 任务后异步完成。
    """
    username = get_request_username(default="")
    if not username or get_request_external_username():
        raise PermissionDenied("仅支持 Web 用户创建分片导出任务")
    space = get_object_or_404(Space, space_uid=data["space_uid"], bk_tenant_id=get_request_tenant_id())
    if not is_enabled(space.bk_biz_id):
        raise ValidationError({"detail": "分片导出未启用"})
    index = get_object_or_404(LogIndexSet, pk=data["index_set_id"], space_uid=space.space_uid)
    if index.is_group:
        raise ValidationError({"detail": "暂不支持索引集组导出"})
    IAMPermission([ActionEnum.SEARCH_LOG], [ResourceEnum.INDICES.create_instance(index.pk)]).has_permission(
        get_request(), None
    )

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
