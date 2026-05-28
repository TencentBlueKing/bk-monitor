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

from django.db.models import Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    SAFETY_LEVEL_DESTRUCTIVE,
    SAFETY_LEVEL_WRITE,
    build_response,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    get_scoped_map_value,
    instance_tenant_resource_key,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
)
from metadata import models
from metadata.service.vm_short_link import (
    apply_vm_short_links,
    delete_vm_short_links,
    switch_vm_short_links,
    update_vm_short_links,
)

FUNC_LIST = "admin.vm_short_link.list"
FUNC_DETAIL = "admin.vm_short_link.detail"
FUNC_CREATE = "admin.vm_short_link.create"
FUNC_UPDATE = "admin.vm_short_link.update"
FUNC_SWITCH = "admin.vm_short_link.switch"
FUNC_DELETE = "admin.vm_short_link.delete"

OPERATION_LIST = "vm_short_link.list"
OPERATION_DETAIL = "vm_short_link.detail"
OPERATION_CREATE = "vm_short_link.create"
OPERATION_UPDATE = "vm_short_link.update"
OPERATION_SWITCH = "vm_short_link.switch"
OPERATION_DELETE = "vm_short_link.delete"

ORDERING_FIELDS = {"table_id", "vm_result_table_id", "space_id", "vm_cluster_id", "create_time", "update_time"}
VM_SHORT_LINK_FIELDS = [
    "id",
    "bk_tenant_id",
    "space_type",
    "space_id",
    "table_id",
    "vm_result_table_id",
    "vm_result_table_name",
    "vm_cluster_id",
    "data_labels",
    "query_router_config",
    "is_global",
    "is_enabled",
    "is_deleted",
    "creator",
    "create_time",
    "updater",
    "update_time",
]


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _normalize_text(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    text = str(value).strip()
    if not text:
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    return text


def _normalize_string_list(value: Any, field_name: str, *, required: bool = False) -> list[str] | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    if isinstance(value, str):
        raw_values = value.replace("\n", ",").replace(" ", ",").split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = value
    else:
        raise CustomException(message=f"{field_name} 必须是字符串列表")

    values = list(dict.fromkeys(str(item).strip() for item in raw_values if str(item).strip()))
    if required and not values:
        raise CustomException(message=f"{field_name} 不能为空")
    return values


def _normalize_query_router_config(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise CustomException(message="query_router_config 必须是 JSON 对象")
    return value


def _normalize_data_labels(value: Any, *, default: list[str] | None = None) -> list[str] | None:
    if value is None:
        return default
    if isinstance(value, list | tuple):
        return [str(item).strip() for item in value]
    raise CustomException(message="data_labels 必须是字符串列表")


def _service_call(fn, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except ValueError as error:
        raise CustomException(message=str(error)) from error


def _build_vm_cluster_name_map(
    records: list[models.VMShortLinkRecord],
    bk_tenant_id: str | None,
) -> dict[Any, str]:
    cluster_ids = {record.vm_cluster_id for record in records if record.vm_cluster_id}
    if not cluster_ids:
        return {}
    queryset = filter_by_bk_tenant_id(
        models.ClusterInfo.objects.filter(cluster_id__in=cluster_ids, cluster_type=models.ClusterInfo.TYPE_VM),
        bk_tenant_id,
    )
    if bk_tenant_id is None:
        return {instance_tenant_resource_key(cluster, "cluster_id"): cluster.cluster_name for cluster in queryset}
    return {cluster.cluster_id: cluster.cluster_name for cluster in queryset}


def _serialize_short_link(
    record: models.VMShortLinkRecord,
    vm_cluster_names: dict[int, str] | None = None,
) -> dict[str, Any]:
    item = serialize_model(record, VM_SHORT_LINK_FIELDS)
    item["bk_biz_id"] = int(record.space_id) if record.space_type == "bkcc" and record.space_id.isdigit() else None
    item["data_label"] = ",".join(record.data_labels or [])
    item["vm_cluster_name"] = (
        get_scoped_map_value(vm_cluster_names or {}, record.bk_tenant_id, record.vm_cluster_id) or ""
    )
    item["normalized_query_router_config"] = record.normalized_query_router_config
    return item


def _build_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.VMShortLinkRecord.objects.all(), bk_tenant_id)
    include_deleted = normalize_optional_bool(params.get("include_deleted"), "include_deleted") or False
    if not include_deleted:
        queryset = queryset.filter(is_deleted=False)

    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id")
    if bk_biz_id is not None:
        queryset = queryset.filter(space_type="bkcc", space_id=str(bk_biz_id))
    table_id = _normalize_text(params.get("table_id"), "table_id")
    if table_id:
        queryset = queryset.filter(Q(table_id=table_id) | Q(table_id__contains=table_id))
    vmrt = _normalize_text(params.get("vmrt") or params.get("vm_result_table_id"), "vmrt")
    if vmrt:
        queryset = queryset.filter(Q(vm_result_table_id=vmrt) | Q(vm_result_table_id__contains=vmrt))
    is_global = normalize_optional_bool(params.get("is_global"), "is_global")
    if is_global is not None:
        queryset = queryset.filter(is_global=is_global)
    is_enabled = normalize_optional_bool(params.get("is_enabled"), "is_enabled")
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled)
    is_deleted = normalize_optional_bool(params.get("is_deleted"), "is_deleted")
    if is_deleted is not None:
        queryset = queryset.filter(is_deleted=is_deleted)
    return queryset


def _get_record_or_raise(params: dict[str, Any], bk_tenant_id: str) -> models.VMShortLinkRecord:
    table_id = _normalize_text(params.get("table_id"), "table_id")
    vmrt = _normalize_text(params.get("vmrt") or params.get("vm_result_table_id"), "vmrt")
    if not table_id and not vmrt:
        raise CustomException(message="table_id 或 vmrt 至少需要提供一个")

    queryset = models.VMShortLinkRecord.objects.filter(bk_tenant_id=bk_tenant_id)
    if table_id:
        queryset = queryset.filter(table_id=table_id)
    if vmrt:
        queryset = queryset.filter(vm_result_table_id=vmrt)
    try:
        return queryset.get()
    except models.VMShortLinkRecord.DoesNotExist as error:
        raise CustomException(message="VM 短链路不存在") from error
    except models.VMShortLinkRecord.MultipleObjectsReturned as error:
        raise CustomException(message="匹配到多条 VM 短链路，请使用精确 table_id") from error


def _build_target_params(params: dict[str, Any]) -> tuple[list[str] | None, list[str] | None]:
    table_ids = _normalize_string_list(params.get("table_ids"), "table_ids")
    vmrts = _normalize_string_list(params.get("vmrts"), "vmrts")
    if not table_ids and not vmrts:
        table_id = _normalize_text(params.get("table_id"), "table_id")
        vmrt = _normalize_text(params.get("vmrt") or params.get("vm_result_table_id"), "vmrt")
        table_ids = [table_id] if table_id else None
        vmrts = [vmrt] if vmrt else None
    if not table_ids and not vmrts:
        raise CustomException(message="table_ids 和 vmrts 不能同时为空")
    return table_ids, vmrts


@KernelRPCRegistry.register(
    FUNC_LIST,
    summary="Admin 查询 VM 短链路列表",
    description="分页查询 VMShortLinkRecord，支持按业务、虚拟结果表、VMRT、全局、启用和删除态过滤。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，BKCC 业务 ID",
        "table_id": "可选，虚拟结果表 ID，支持包含匹配",
        "vmrt": "可选，VM 结果表 ID，支持包含匹配",
        "is_global": "可选，是否全局",
        "is_enabled": "可选，是否启用",
        "is_deleted": "可选，是否已删除；需要配合 include_deleted=true 查询已删除记录",
        "include_deleted": "可选，是否包含已删除记录，默认 false",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 315, "page": 1, "page_size": 20},
)
def list_vm_short_links(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="-update_time")
    queryset = _build_queryset(params, bk_tenant_id).order_by(ordering, "table_id")
    records, total = paginate_queryset(queryset, page=page, page_size=page_size)
    vm_cluster_names = _build_vm_cluster_name_map(records, bk_tenant_id)
    return build_response(
        operation=OPERATION_LIST,
        func_name=FUNC_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_short_link(record, vm_cluster_names) for record in records],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_DETAIL,
    summary="Admin 查询 VM 短链路详情",
    description="按虚拟结果表 ID 或 VMRT 查询单条 VMShortLinkRecord。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "table_id": "可选", "vmrt": "可选"},
    example_params={"bk_tenant_id": "system", "table_id": "315_demo.__default__"},
)
def get_vm_short_link_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    record = _get_record_or_raise(params, bk_tenant_id)
    vm_cluster_names = _build_vm_cluster_name_map([record], bk_tenant_id)
    return build_response(
        operation=OPERATION_DETAIL,
        func_name=FUNC_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={"short_link": _serialize_short_link(record, vm_cluster_names)},
    )


@KernelRPCRegistry.register(
    FUNC_CREATE,
    summary="Admin 接入 VM 短链路",
    description="按 bk_biz_id + VMRT 列表接入短链路，不查询 BKData 候选列表；默认遇到已接入 VMRT 会失败。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "必填，BKCC 业务 ID",
        "vmrts": "必填，VM 结果表 ID 列表",
        "is_global": "可选，是否全局",
        "query_router_config": "可选，查询路由配置",
        "data_labels": "可选，数据标签列表",
        "overwrite": "可选，是否覆盖已存在短链路配置，默认 false",
        "operator": "可选，操作者",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 315, "vmrts": ["315_demo_vmrt"]},
)
def create_vm_short_link(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    vmrts = _normalize_string_list(params.get("vmrts"), "vmrts", required=True)
    results = _service_call(
        apply_vm_short_links,
        vmrts=vmrts,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        is_global=normalize_optional_bool(params.get("is_global"), "is_global") or False,
        query_router_config=_normalize_query_router_config(params.get("query_router_config")) or {},
        operator=_normalize_text(params.get("operator"), "operator") or "system",
        refresh_router=normalize_optional_bool(params.get("refresh_router"), "refresh_router") is not False,
        overwrite=normalize_optional_bool(params.get("overwrite"), "overwrite") or False,
        data_labels=_normalize_data_labels(params.get("data_labels"), default=[]),
    )
    return build_response(
        operation=OPERATION_CREATE,
        func_name=FUNC_CREATE,
        bk_tenant_id=bk_tenant_id,
        data={"items": results},
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_UPDATE,
    summary="Admin 修改 VM 短链路配置",
    description="修改已存在短链路的全局状态和查询路由配置；默认不从 BKBase 刷新元信息。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "必填，BKCC 业务 ID",
        "table_ids": "可选，虚拟结果表 ID 列表",
        "vmrts": "可选，VM 结果表 ID 列表",
        "is_global": "可选，是否全局",
        "query_router_config": "可选，查询路由配置",
        "data_labels": "可选，数据标签列表；传空列表可清空，未传则不修改",
        "refresh_bkbase": "可选，是否从 BKBase 刷新配置，默认 false",
        "operator": "可选，操作者",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 315, "table_ids": ["315_demo.__default__"]},
)
def update_vm_short_link(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    table_ids, vmrts = _build_target_params(params)
    results = _service_call(
        update_vm_short_links,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        table_ids=table_ids,
        vmrts=vmrts,
        is_global=normalize_optional_bool(params.get("is_global"), "is_global"),
        query_router_config=_normalize_query_router_config(params.get("query_router_config")),
        refresh_bkbase=normalize_optional_bool(params.get("refresh_bkbase"), "refresh_bkbase") or False,
        operator=_normalize_text(params.get("operator"), "operator") or "system",
        refresh_router=normalize_optional_bool(params.get("refresh_router"), "refresh_router") is not False,
        data_labels=_normalize_data_labels(params.get("data_labels")) if "data_labels" in params else None,
    )
    return build_response(
        operation=OPERATION_UPDATE,
        func_name=FUNC_UPDATE,
        bk_tenant_id=bk_tenant_id,
        data={"items": results},
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_SWITCH,
    summary="Admin 启停 VM 短链路",
    description="启用或停用 VM 短链路，不改变删除态。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "必填，BKCC 业务 ID",
        "table_ids": "可选，虚拟结果表 ID 列表",
        "vmrts": "可选，VM 结果表 ID 列表",
        "is_enabled": "必填，是否启用",
        "operator": "可选，操作者",
    },
    example_params={
        "bk_tenant_id": "system",
        "bk_biz_id": 315,
        "table_ids": ["315_demo.__default__"],
        "is_enabled": False,
    },
)
def switch_vm_short_link(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    is_enabled = normalize_optional_bool(params.get("is_enabled"), "is_enabled")
    if is_enabled is None:
        raise CustomException(message="is_enabled 为必填项")
    table_ids, vmrts = _build_target_params(params)
    result = _service_call(
        switch_vm_short_links,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        table_ids=table_ids,
        vmrts=vmrts,
        is_enabled=is_enabled,
        operator=_normalize_text(params.get("operator"), "operator") or "system",
        refresh_router=normalize_optional_bool(params.get("refresh_router"), "refresh_router") is not False,
    )
    return build_response(
        operation=OPERATION_SWITCH,
        func_name=FUNC_SWITCH,
        bk_tenant_id=bk_tenant_id,
        data=result,
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_DELETE,
    summary="Admin 软删除 VM 短链路",
    description="软删除 VM 短链路，并同步禁用关联 ResultTable 和 TimeSeriesGroup。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "必填，BKCC 业务 ID",
        "table_ids": "可选，虚拟结果表 ID 列表",
        "vmrts": "可选，VM 结果表 ID 列表",
        "operator": "可选，操作者",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 315, "table_ids": ["315_demo.__default__"]},
)
def delete_vm_short_link(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_int(params.get("bk_biz_id"), "bk_biz_id", required=True)
    table_ids, vmrts = _build_target_params(params)
    result = _service_call(
        delete_vm_short_links,
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        table_ids=table_ids,
        vmrts=vmrts,
        operator=_normalize_text(params.get("operator"), "operator") or "system",
        refresh_router=normalize_optional_bool(params.get("refresh_router"), "refresh_router") is not False,
    )
    return build_response(
        operation=OPERATION_DELETE,
        func_name=FUNC_DELETE,
        bk_tenant_id=bk_tenant_id,
        data=result,
        safety_level=SAFETY_LEVEL_DESTRUCTIVE,
    )
