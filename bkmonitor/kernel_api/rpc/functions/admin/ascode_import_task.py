"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import ast
from typing import Any

from bkmonitor.models.as_code import AsCodeImportTask
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)

FUNC_LIST = "admin.ascode_import_task.list"
FUNC_DETAIL = "admin.ascode_import_task.detail"

LIST_FIELDS = [
    "id",
    "bk_biz_id",
    "params",
    "create_time",
    "update_time",
]
ORDERING_FIELDS = {"bk_biz_id", "create_time", "update_time"}


def _parse_result(task: AsCodeImportTask) -> dict[str, Any] | None:
    if task.result is None:
        return None
    raw = task.result.strip()
    if not raw or raw in ("{}", "[]", ""):
        return None
    try:
        result_data = ast.literal_eval(raw)
        if isinstance(result_data, dict):
            return result_data
        return None
    except (ValueError, SyntaxError, TypeError):
        return None


def _infer_status(task: AsCodeImportTask) -> str:
    result_data = _parse_result(task)
    if result_data is None:
        return "pending"
    errors = result_data.get("errors")
    if errors and errors != "{}":
        return "failed"
    return "success"


def _get_file_info(task: AsCodeImportTask) -> dict[str, Any]:
    try:
        return {
            "name": task.file.name,
            "url": task.file.url,
            "size": task.file.size,
        }
    except Exception:
        return {"name": "", "url": "", "size": 0}


def _serialize_list_item(task: AsCodeImportTask) -> dict[str, Any]:
    params = task.params or {}
    item = serialize_model(task, LIST_FIELDS)
    item["task_name"] = params.get("app", "")
    item["status"] = _infer_status(task)
    item["file"] = _get_file_info(task)
    item["created_at"] = item.pop("create_time", None)
    item["updated_at"] = item.pop("update_time", None)
    return item


def serialize_model(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {field: serialize_value(getattr(instance, field, None)) for field in fields}


def _build_queryset(params: dict[str, Any]) -> Any:
    queryset = AsCodeImportTask.objects.all()

    bk_biz_id = params.get("bk_biz_id")
    if bk_biz_id is not None and bk_biz_id != "":
        try:
            queryset = queryset.filter(bk_biz_id=int(bk_biz_id))
        except (TypeError, ValueError):
            raise CustomException(message="bk_biz_id 必须是整数")

    return queryset


@KernelRPCRegistry.register(
    FUNC_LIST,
    summary="Admin 查询 AsCode 导入任务列表",
    description="分页查询 AsCode 导入任务，支持按 bk_biz_id 过滤和白名单排序。列表返回推断状态（pending/success/failed），不返回 result 原始值。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "可选，业务 ID，精确匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_biz_id": 2, "page": 1, "page_size": 20, "ordering": "-create_time"},
)
def list_ascode_import_tasks(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="-create_time")

    queryset = _build_queryset(params).order_by(ordering, "id")
    tasks, total = paginate_queryset(queryset, page=page, page_size=page_size)

    items = [_serialize_list_item(task) for task in tasks]

    return build_response(
        operation="ascode_import_task.list",
        func_name=FUNC_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_DETAIL,
    summary="Admin 查询 AsCode 导入任务详情",
    description="查询单个 AsCode 导入任务的完整信息，result 已解析为 JSON 对象。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "task_id": "必填，任务 ID",
    },
    example_params={"task_id": 1},
)
def get_ascode_import_task_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    task_id = params.get("task_id")

    if task_id is None or task_id == "":
        raise CustomException(message="task_id 为必填项")

    try:
        task = AsCodeImportTask.objects.get(id=int(task_id))
    except (TypeError, ValueError):
        raise CustomException(message="task_id 必须是整数")
    except AsCodeImportTask.DoesNotExist:
        raise CustomException(message=f"任务不存在: task_id={task_id}")

    params_data = task.params or {}
    item = {
        "id": task.id,
        "bk_biz_id": task.bk_biz_id,
        "task_name": params_data.get("app", ""),
        "params": params_data,
        "status": _infer_status(task),
        "file": _get_file_info(task),
        "result": _parse_result(task),
        "created_at": serialize_value(task.create_time),
        "updated_at": serialize_value(task.update_time),
    }

    return build_response(
        operation="ascode_import_task.detail",
        func_name=FUNC_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"task": item},
    )
