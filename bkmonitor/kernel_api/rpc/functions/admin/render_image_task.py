"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import uuid
from datetime import datetime, time
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from bkmonitor.models.report import RenderImageTask
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)

FUNC_LIST = "admin.render_image_task.list"
FUNC_DETAIL = "admin.render_image_task.detail"

STATUS_LABEL_MAP = dict(RenderImageTask.STATUS)
STATUS_VALUES = set(STATUS_LABEL_MAP)
ORDERING_FIELDS = {"create_time", "start_time", "finish_time", "status", "task_id"}


def _normalize_options_bk_biz_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="options__bk_biz_id 必须是整数") from error


def _normalize_datetime(value: Any, field_name: str, *, end_of_day: bool = False):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise CustomException(message=f"{field_name} 必须是日期时间字符串")

    raw_value = value.strip()
    parsed_datetime = parse_datetime(raw_value)
    if parsed_datetime is None:
        parsed_date = parse_date(raw_value)
        if parsed_date is not None:
            parsed_datetime = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if parsed_datetime is None:
        raise CustomException(message=f"{field_name} 必须是合法日期时间字符串")
    if timezone.is_naive(parsed_datetime):
        parsed_datetime = timezone.make_aware(parsed_datetime, timezone.get_current_timezone())
    return parsed_datetime


def _validate_choice(value: Any, field_name: str, allowed_values: set[str]) -> str | None:
    if value in (None, ""):
        return None
    normalized_value = str(value).strip()
    if normalized_value not in allowed_values:
        allowed_text = ", ".join(sorted(allowed_values))
        raise CustomException(message=f"不支持的 {field_name}: {normalized_value}，可选值: {allowed_text}")
    return normalized_value


def _extract_options(task: RenderImageTask) -> dict[str, Any]:
    return task.options if isinstance(task.options, dict) else {}


def _extract_bk_biz_id(options: dict[str, Any]) -> int | None:
    value = options.get("bk_biz_id")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_image_info(task: RenderImageTask) -> dict[str, Any]:
    if not task.image:
        return {"name": "", "url": "", "size": 0}
    try:
        return {
            "name": task.image.name,
            "url": task.image.url,
            "size": task.image.size,
        }
    except Exception:
        return {"name": str(getattr(task.image, "name", "") or ""), "url": "", "size": 0}


def _calculate_duration_seconds(task: RenderImageTask) -> int | None:
    if not task.start_time:
        return None

    finish_time = task.finish_time
    if finish_time is None and task.status == RenderImageTask.Status.RENDERING:
        finish_time = timezone.now()
    if finish_time is None:
        return None

    duration = int((finish_time - task.start_time).total_seconds())
    return max(duration, 0)


def _serialize_render_image_task(task: RenderImageTask, *, include_detail: bool = False) -> dict[str, Any]:
    options = _extract_options(task)
    item = {
        "id": task.id,
        "task_id": str(task.task_id),
        "bk_tenant_id": task.bk_tenant_id,
        "bk_biz_id": _extract_bk_biz_id(options),
        "dashboard_uid": options.get("dashboard_uid") or "",
        "status": task.status,
        "status_label": STATUS_LABEL_MAP.get(task.status, task.status),
        "username": task.username,
        "duration_seconds": _calculate_duration_seconds(task),
        "created_at": serialize_value(task.create_time),
        "start_time": serialize_value(task.start_time),
        "finish_time": serialize_value(task.finish_time),
    }
    if include_detail:
        item.update(
            {
                "image": _get_image_info(task),
                "options": options,
                "error": task.error,
            }
        )
    return item


def _build_queryset(params: dict[str, Any], bk_tenant_id: str | None) -> Any:
    queryset = filter_by_bk_tenant_id(RenderImageTask.objects.all(), bk_tenant_id)

    task_id = params.get("task_id")
    if task_id not in (None, ""):
        try:
            queryset = queryset.filter(task_id=uuid.UUID(str(task_id)))
        except (TypeError, ValueError) as error:
            raise CustomException(message="task_id 必须是合法 UUID") from error

    options_bk_biz_id = _normalize_options_bk_biz_id(params.get("options__bk_biz_id"))
    if options_bk_biz_id is not None:
        queryset = queryset.filter(options__bk_biz_id=options_bk_biz_id)

    dashboard_uid = params.get("options__dashboard_uid")
    if dashboard_uid not in (None, ""):
        queryset = queryset.filter(options__dashboard_uid=str(dashboard_uid).strip())

    status = _validate_choice(params.get("status"), "status", STATUS_VALUES)
    if status:
        queryset = queryset.filter(status=status)

    username = params.get("username")
    if username not in (None, ""):
        queryset = queryset.filter(username__icontains=str(username).strip())

    created_after = _normalize_datetime(params.get("created_after"), "created_after")
    if created_after is not None:
        queryset = queryset.filter(create_time__gte=created_after)

    created_before = _normalize_datetime(params.get("created_before"), "created_before", end_of_day=True)
    if created_before is not None:
        queryset = queryset.filter(create_time__lte=created_before)

    return queryset


@KernelRPCRegistry.register(
    FUNC_LIST,
    summary="Admin 查询 RenderImageTask 列表",
    description=(
        "分页查询渲染图片任务，支持按 task_id、options__bk_biz_id、options__dashboard_uid、状态和创建时间过滤。"
        "列表默认按 create_time 倒序，自动返回 start_time/finish_time 计算出的 duration_seconds，"
        "不返回图片内容和内部渲染类型。"
    ),
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "task_id": "可选，任务 UUID，精确匹配",
        "options__bk_biz_id": "可选，业务 ID，精确匹配 RenderImageTask.options.bk_biz_id",
        "options__dashboard_uid": "可选，仪表盘 UID，精确匹配 RenderImageTask.options.dashboard_uid",
        "status": f"可选，任务状态: {', '.join(sorted(STATUS_VALUES))}",
        "username": "可选，创建用户名，包含匹配",
        "created_after": "可选，创建时间起点，日期时间字符串",
        "created_before": "可选，创建时间终点，日期时间字符串",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={
        "bk_tenant_id": "system",
        "task_id": "b916e23d-5328-44a2-a6aa-af3d0c1b5c64",
        "options__bk_biz_id": 2,
        "options__dashboard_uid": "dashboard-demo",
        "created_after": "2026-05-26 00:00:00",
        "created_before": "2026-05-27 23:59:59",
        "page": 1,
        "page_size": 20,
        "ordering": "-create_time",
    },
)
def list_render_image_tasks(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="-create_time")

    queryset = _build_queryset(params, bk_tenant_id).order_by(ordering, "id")
    tasks, total = paginate_queryset(queryset, page=page, page_size=page_size)

    return build_response(
        operation="render_image_task.list",
        func_name=FUNC_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_render_image_task(task) for task in tasks],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_DETAIL,
    summary="Admin 查询 RenderImageTask 详情",
    description="查询单个渲染图片任务详情，返回完整 options、错误信息、图片下载地址和自动计算的耗时。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID；传入时按租户过滤",
        "task_id": "必填，任务 UUID",
    },
    example_params={"bk_tenant_id": "system", "task_id": "b916e23d-5328-44a2-a6aa-af3d0c1b5c64"},
)
def get_render_image_task_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    task_id = params.get("task_id")
    if task_id in (None, ""):
        raise CustomException(message="task_id 为必填项")

    try:
        normalized_task_id = uuid.UUID(str(task_id))
    except (TypeError, ValueError) as error:
        raise CustomException(message="task_id 必须是合法 UUID") from error

    try:
        task = filter_by_bk_tenant_id(RenderImageTask.objects.all(), bk_tenant_id).get(task_id=normalized_task_id)
    except RenderImageTask.DoesNotExist as error:
        raise CustomException(message=f"任务不存在: task_id={task_id}") from error

    return build_response(
        operation="render_image_task.detail",
        func_name=FUNC_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"task": _serialize_render_image_task(task, include_detail=True)},
    )
