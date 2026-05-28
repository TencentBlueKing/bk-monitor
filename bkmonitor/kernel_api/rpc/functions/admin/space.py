"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from core.drf_resource.exceptions import CustomException
from django.db.models import Q
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    filter_by_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    require_bk_tenant_id,
    serialize_model,
)
from metadata import models
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes

FUNC_SPACE_LIST = "admin.space.list"
FUNC_SPACE_DETAIL = "admin.space.detail"

SPACE_FIELDS = [
    "id",
    "bk_tenant_id",
    "space_type_id",
    "space_id",
    "space_name",
    "space_code",
    "status",
    "time_zone",
    "language",
    "is_bcs_valid",
    "is_global",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
SPACE_RESOURCE_FIELDS = [
    "id",
    "bk_tenant_id",
    "space_type_id",
    "space_id",
    "resource_type",
    "resource_id",
    "dimension_values",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
SPACE_VM_INFO_FIELDS = [
    "id",
    "space_type",
    "space_id",
    "vm_cluster_id",
    "vm_retention_time",
    "status",
    "creator",
    "create_time",
    "updater",
    "update_time",
]
VM_CLUSTER_SUMMARY_FIELDS = ["cluster_id", "cluster_name", "display_name", "cluster_type"]
ORDERING_FIELDS = {
    "id",
    "space_uid",
    "space_type_id",
    "space_id",
    "space_name",
    "status",
    "is_bcs_valid",
    "is_global",
    "create_time",
    "last_modify_time",
}


def _split_space_uid(value: Any) -> tuple[str, str]:
    space_uid = str(value or "").strip()
    if not space_uid:
        raise CustomException(message="space_uid 为必填项")

    parts = space_uid.split(SPACE_UID_HYPHEN, 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise CustomException(message="space_uid 格式不合法，应为 <space_type_id>__<space_id>")
    return parts[0], parts[1]


def _compose_space_uid(space_type_id: str, space_id: str) -> str:
    return f"{space_type_id}{SPACE_UID_HYPHEN}{space_id}"


def _split_search_space_uid(value: str) -> tuple[str, str] | None:
    if value.count(SPACE_UID_HYPHEN) != 1:
        return None

    space_type_id, space_id = value.split(SPACE_UID_HYPHEN, 1)
    space_type_id = space_type_id.strip()
    space_id = space_id.strip()
    if not space_type_id or not space_id:
        return None
    return space_type_id, space_id


def _build_bk_biz_id(space: models.Space) -> int | None:
    if space.space_type_id == SpaceTypes.BKCC.value:
        try:
            return int(space.space_id)
        except (TypeError, ValueError):
            return None
    return -int(space.id)


def _serialize_space(space: models.Space) -> dict[str, Any]:
    item = serialize_model(space, SPACE_FIELDS)
    item["space_uid"] = _compose_space_uid(space.space_type_id, space.space_id)
    item["bk_biz_id"] = _build_bk_biz_id(space)
    return item


def _serialize_space_resource(resource: models.SpaceResource) -> dict[str, Any]:
    item = serialize_model(resource, SPACE_RESOURCE_FIELDS)
    item["space_uid"] = _compose_space_uid(resource.space_type_id, resource.space_id)
    return item


def _serialize_reverse_space_resource(
    resource: models.SpaceResource,
    spaces_by_key: dict[tuple[str, str], models.Space],
) -> dict[str, Any]:
    item = _serialize_space_resource(resource)
    related_space = spaces_by_key.get((resource.space_type_id, resource.space_id))
    item["space"] = _serialize_space(related_space) if related_space else None
    return item


def _serialize_vm_cluster(cluster: models.ClusterInfo | None) -> dict[str, Any] | None:
    return serialize_model(cluster, VM_CLUSTER_SUMMARY_FIELDS) if cluster else None


def _serialize_space_vm_info(
    space_vm_info: models.SpaceVMInfo,
    vm_clusters_by_id: dict[int, models.ClusterInfo],
) -> dict[str, Any]:
    return {
        "space_vm_info": serialize_model(space_vm_info, SPACE_VM_INFO_FIELDS),
        "vm_cluster": _serialize_vm_cluster(vm_clusters_by_id.get(space_vm_info.vm_cluster_id)),
    }


def _normalize_space_ordering(raw_ordering: Any) -> list[str]:
    ordering = normalize_ordering(raw_ordering, ORDERING_FIELDS, default="space_type_id")
    descending = ordering.startswith("-")
    field_name = ordering[1:] if descending else ordering
    prefix = "-" if descending else ""

    if field_name == "space_uid":
        return [f"{prefix}space_type_id", f"{prefix}space_id", "id"]
    return [ordering, "id"]


def _apply_space_search(queryset, raw_search: Any, raw_search_mode: Any):
    search = str(raw_search or "").strip()
    if not search:
        return queryset

    search_mode = str(raw_search_mode or "fuzzy").strip().lower()
    if search_mode not in {"fuzzy", "exact"}:
        raise CustomException(message="search_mode 仅支持 fuzzy / exact")

    space_uid_parts = _split_search_space_uid(search)
    if space_uid_parts:
        space_type_id, space_id = space_uid_parts
        if search_mode == "exact":
            return queryset.filter(space_type_id=space_type_id, space_id=space_id)
        return queryset.filter(space_type_id__iexact=space_type_id, space_id__icontains=space_id)

    if search_mode == "exact":
        return queryset.filter(Q(space_id=search) | Q(space_name=search))
    return queryset.filter(Q(space_id__icontains=search) | Q(space_name__icontains=search))


def _build_space_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.Space.objects.all(), bk_tenant_id)
    queryset = _apply_space_search(queryset, params.get("search"), params.get("search_mode"))

    if params.get("space_uid"):
        space_type_id, space_id = _split_space_uid(params["space_uid"])
        queryset = queryset.filter(space_type_id=space_type_id, space_id=space_id)
    if params.get("space_type_id"):
        queryset = queryset.filter(space_type_id=str(params["space_type_id"]).strip())
    if params.get("space_id"):
        queryset = queryset.filter(space_id__icontains=str(params["space_id"]).strip())
    if params.get("space_name"):
        queryset = queryset.filter(space_name__icontains=str(params["space_name"]).strip())
    if params.get("status"):
        queryset = queryset.filter(status=str(params["status"]).strip())
    for field in ["is_bcs_valid", "is_global"]:
        field_value = normalize_optional_bool(params.get(field), field)
        if field_value is not None:
            queryset = queryset.filter(**{field: field_value})

    return queryset


@KernelRPCRegistry.register(
    FUNC_SPACE_LIST,
    summary="Admin 查询 Space 列表",
    description="只读查询 Space，支持受控过滤、白名单排序和分页；列表不展开 SpaceResource 或 SpaceDataSource。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID；缺省或空表示全租户查询",
        "search": "可选，统一搜索；匹配 space_uid / space_id / space_name，包含单个 __ 时按 space_uid 拆分",
        "search_mode": "可选，搜索模式 fuzzy / exact，默认 fuzzy",
        "space_uid": "可选，空间 UID，格式为 <space_type_id>__<space_id>",
        "space_type_id": "可选，空间类型精确匹配",
        "space_id": "可选，空间 ID 模糊匹配",
        "space_name": "可选，空间名称模糊匹配",
        "status": "可选，空间状态，例如 normal / disabled",
        "is_bcs_valid": "可选，BCS 是否可用",
        "is_global": "可选，是否跨业务管理可用",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "search": "bkcc__2", "page": 1, "page_size": 20},
)
def list_spaces(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = _normalize_space_ordering(params.get("ordering"))

    queryset = _build_space_queryset(params, bk_tenant_id).order_by(*ordering)
    spaces, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = [_serialize_space(space) for space in spaces]

    return build_response(
        operation="space.list",
        func_name=FUNC_SPACE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_SPACE_DETAIL,
    summary="Admin 查询 Space 详情",
    description=(
        "只读查询 Space 基础信息、该空间下的 SpaceResource，以及基于 resource_type/resource_id "
        "反查到当前 Space 的 SpaceResource；额外按当前 Space 精确查询 SpaceVMInfo 默认 VM 集群映射；"
        "不展开 SpaceDataSource 或场景聚合。"
    ),
    params_schema={
        "bk_tenant_id": "必填，租户 ID",
        "space_uid": "必填，空间 UID，格式为 <space_type_id>__<space_id>",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2"},
)
def get_space_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = require_bk_tenant_id(params)
    space_type_id, space_id = _split_space_uid(params.get("space_uid"))

    try:
        space = models.Space.objects.get(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        )
    except models.Space.DoesNotExist as error:
        raise CustomException(message=f"未找到 Space: space_uid={params.get('space_uid')}") from error

    resources = [
        _serialize_space_resource(resource)
        for resource in models.SpaceResource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        ).order_by("resource_type", "resource_id", "id")
    ]
    reverse_resources = list(
        models.SpaceResource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            resource_type=space_type_id,
            resource_id=space_id,
        ).order_by("space_type_id", "space_id", "id")
    )
    reverse_resource_query = Q()
    for resource in reverse_resources:
        reverse_resource_query |= Q(space_type_id=resource.space_type_id, space_id=resource.space_id)

    reverse_spaces = (
        models.Space.objects.filter(bk_tenant_id=bk_tenant_id).filter(reverse_resource_query)
        if reverse_resources
        else []
    )
    reverse_spaces_by_key = {(space.space_type_id, space.space_id): space for space in reverse_spaces}
    space_vm_infos = list(
        models.SpaceVMInfo.objects.filter(space_type=space.space_type_id, space_id=space.space_id).order_by("id")
    )
    vm_cluster_ids = [info.vm_cluster_id for info in space_vm_infos]
    vm_clusters_by_id = {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=vm_cluster_ids)
    }

    return build_response(
        operation="space.detail",
        func_name=FUNC_SPACE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "space": _serialize_space(space),
            "space_resources": resources,
            "reverse_space_resources": [
                _serialize_reverse_space_resource(resource, reverse_spaces_by_key) for resource in reverse_resources
            ],
            "space_vm_infos": [
                _serialize_space_vm_info(space_vm_info, vm_clusters_by_id) for space_vm_info in space_vm_infos
            ],
        },
    )
