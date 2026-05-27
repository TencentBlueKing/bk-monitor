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
    PAGE_LIST_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from kubernetes import client as k8s_client

from metadata import config, models

FUNC_BCS_CLUSTER_LIST = "admin.bcs_cluster.list"
FUNC_BCS_CLUSTER_DETAIL = "admin.bcs_cluster.detail"
FUNC_BCS_CLUSTER_DATA_ID_LIST = "admin.bcs_cluster.data_id_list"
FUNC_BCS_CLUSTER_DATA_ID_DETAIL = "admin.bcs_cluster.data_id_detail"
INSPECT_SAFETY_LEVEL = "inspect"

BCS_CLUSTER_FIELDS = [
    "cluster_id",
    "bk_tenant_id",
    "bcs_api_cluster_id",
    "bk_biz_id",
    "bk_cloud_id",
    "project_id",
    "status",
    "domain_name",
    "port",
    "server_address_path",
    "api_key_type",
    "api_key_prefix",
    "is_skip_ssl_verify",
    "K8sMetricDataID",
    "CustomMetricDataID",
    "K8sEventDataID",
    "CustomEventDataID",
    "SystemLogDataID",
    "CustomLogDataID",
    "bk_env",
    "operator_ns",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
    "is_deleted_allow_view",
]

SENSITIVE_BCS_FIELDS = {
    "api_key_content": "has_api_key",
    "cert_content": "has_cert",
}

ORDERING_FIELDS = {
    "cluster_id",
    "bcs_api_cluster_id",
    "bk_biz_id",
    "status",
    "create_time",
    "last_modify_time",
}

DATA_ID_FIELD_NAMES = [
    "K8sMetricDataID",
    "CustomMetricDataID",
    "K8sEventDataID",
    "CustomEventDataID",
    "SystemLogDataID",
    "CustomLogDataID",
]


def _mark_inspect_response(response: dict[str, Any]) -> dict[str, Any]:
    response["meta"]["safety_level"] = INSPECT_SAFETY_LEVEL
    response["meta"]["requested_safety_level"] = INSPECT_SAFETY_LEVEL
    return response


def _normalize_bk_data_id(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_data_id 必须是整数") from error


def _require_cluster_id(params: dict[str, Any]) -> str:
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    return str(cluster_id).strip()


def _get_bcs_cluster_or_raise(bk_tenant_id: str, cluster_id: str) -> models.BCSClusterInfo:
    try:
        return models.BCSClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.BCSClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 BCSClusterInfo: cluster_id={cluster_id}") from error


def _serialize_bcs_cluster(bcs_cluster: models.BCSClusterInfo) -> dict[str, Any]:
    item = {field: serialize_value(getattr(bcs_cluster, field, None)) for field in BCS_CLUSTER_FIELDS}
    for sensitive_field, flag_field in SENSITIVE_BCS_FIELDS.items():
        raw_value = getattr(bcs_cluster, sensitive_field, None)
        item[flag_field] = bool(raw_value)
    return item


def _build_bcs_cluster_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(models.BCSClusterInfo.objects.all(), bk_tenant_id)

    if params.get("bk_biz_id") not in (None, ""):
        try:
            queryset = queryset.filter(bk_biz_id=int(params["bk_biz_id"]))
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_biz_id 必须是整数") from error

    if params.get("bk_data_id") not in (None, ""):
        bk_data_id = _normalize_bk_data_id(params["bk_data_id"])
        if bk_data_id <= 0:
            return queryset.none()

        data_id_query = Q()
        for field_name in DATA_ID_FIELD_NAMES:
            data_id_query |= Q(**{field_name: bk_data_id})
        queryset = queryset.filter(data_id_query)

    if params.get("cluster_id") not in (None, ""):
        queryset = queryset.filter(cluster_id__contains=str(params["cluster_id"]).strip())

    status = params.get("status")
    if status not in (None, ""):
        if isinstance(status, str):
            status_values = [item.strip() for item in status.split(",") if item.strip()]
        elif isinstance(status, list | tuple | set):
            status_values = [str(item).strip() for item in status if str(item).strip()]
        else:
            status_values = [str(status).strip()]

        if status_values:
            queryset = queryset.filter(status__in=status_values)

    return queryset


def _read_nested_dict_value(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _normalize_label_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value == "true":
            return True
        if normalized_value == "false":
            return False
    return None


def _normalize_optional_data_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_bcs_data_id_resource(resource: dict[str, Any]) -> dict[str, Any]:
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    metadata_labels = metadata.get("labels") if isinstance(metadata.get("labels"), dict) else {}
    spec = resource.get("spec") if isinstance(resource.get("spec"), dict) else {}
    spec_labels = spec.get("labels") if isinstance(spec.get("labels"), dict) else {}
    status = resource.get("status") if isinstance(resource.get("status"), dict) else {}

    return {
        "name": metadata.get("name"),
        "data_id": _normalize_optional_data_id(spec.get("dataID") or spec.get("data_id")),
        "usage": metadata_labels.get("usage"),
        "is_common": _normalize_label_bool(metadata_labels.get("isCommon")),
        "is_system": _normalize_label_bool(metadata_labels.get("isSystem")),
        "monitor_resource": spec.get("monitorResource") if isinstance(spec.get("monitorResource"), dict) else None,
        "labels": spec_labels,
        "phase": status.get("phase"),
        "created_at": metadata.get("creationTimestamp"),
        "resource_version": metadata.get("resourceVersion"),
    }


def _get_bcs_data_id_custom_client(cluster: models.BCSClusterInfo) -> k8s_client.CustomObjectsApi:
    return k8s_client.CustomObjectsApi(cluster.api_client)


def _list_bcs_data_id_resources(cluster: models.BCSClusterInfo) -> list[dict[str, Any]]:
    try:
        resource_list = _get_bcs_data_id_custom_client(cluster).list_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        )
    except k8s_client.exceptions.ApiException as error:
        raise CustomException(message=f"查询 BCS DataID 列表失败: {error}") from error

    items = resource_list.get("items") if isinstance(resource_list, dict) else []
    if not isinstance(items, list):
        return []

    return sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda item: str(_read_nested_dict_value(item, "metadata", "name") or ""),
    )


def _get_bcs_data_id_resource(cluster: models.BCSClusterInfo, name: str) -> dict[str, Any]:
    try:
        resource = _get_bcs_data_id_custom_client(cluster).get_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
            name=name,
        )
    except k8s_client.exceptions.ApiException as error:
        if getattr(error, "status", None) == 404:
            raise CustomException(message=f"未找到 BCS DataID 资源: name={name}") from error
        raise CustomException(message=f"查询 BCS DataID 资源失败: {error}") from error

    if not isinstance(resource, dict):
        raise CustomException(message=f"BCS DataID 资源返回格式异常: name={name}")

    return resource


def _paginate_list(items: list[dict[str, Any]], *, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_LIST,
    summary="Admin 查询 BCSClusterInfo 列表",
    description="只读查询 BCSClusterInfo 列表，支持受控过滤、白名单排序和分页。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "bk_biz_id": "可选，业务 ID 精确匹配",
        "bk_data_id": "可选，DataID 精确匹配；匹配 K8sMetricDataID、CustomMetricDataID、K8sEventDataID、CustomEventDataID、SystemLogDataID、CustomLogDataID 任一字段",
        "cluster_id": "可选，集群 ID 包含匹配",
        "status": "可选，集群状态原始值精确匹配，支持字符串、逗号分隔字符串或列表；不传则不过滤",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}，默认 cluster_id",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010, "page": 1, "page_size": 20},
)
def list_bcs_clusters(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="cluster_id")

    queryset = _build_bcs_cluster_queryset(params, bk_tenant_id).order_by(ordering, "cluster_id")
    clusters, total = paginate_queryset(queryset, page=page, page_size=page_size)

    items = [_serialize_bcs_cluster(c) for c in clusters]

    return build_response(
        operation="bcs_cluster.list",
        func_name=FUNC_BCS_CLUSTER_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DETAIL,
    summary="Admin 查询 BCSClusterInfo 详情",
    description="只读查询 BCSClusterInfo 详情及关联的 DataSource 摘要信息。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，集群 ID",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000"},
)
def get_bcs_cluster_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    data: dict[str, Any] = {"cluster": _serialize_bcs_cluster(cluster)}

    data_ids = sorted({getattr(cluster, field, 0) for field in DATA_ID_FIELD_NAMES if getattr(cluster, field, 0) > 0})

    if data_ids:
        datasources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids).only(
            "bk_data_id", "data_name", "type_label", "source_label", "is_enable"
        )
        datasource_summaries = [
            {
                "bk_data_id": ds.bk_data_id,
                "data_name": ds.data_name,
                "type_label": ds.type_label,
                "source_label": ds.source_label,
                "is_enable": ds.is_enable,
            }
            for ds in datasources.order_by("bk_data_id")
        ]
    else:
        datasource_summaries = []

    data["datasource_summaries"] = datasource_summaries

    return build_response(
        operation="bcs_cluster.detail",
        func_name=FUNC_BCS_CLUSTER_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DATA_ID_LIST,
    summary="Admin 实时查询 BCS 集群 DataID CRD 列表",
    description="inspect 级别能力，通过 Kubernetes CustomObjectsApi 实时读取目标 BCS 集群中的 DataID CRD 列表，只读不写。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "page": 1, "page_size": 20},
)
def list_bcs_cluster_data_ids(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    page, page_size = normalize_pagination(params)
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    resources = _list_bcs_data_id_resources(cluster)
    page_resources, total = _paginate_list(resources, page=page, page_size=page_size)
    items = [_serialize_bcs_data_id_resource(resource) for resource in page_resources]

    response = build_response(
        operation="bcs_cluster.data_id_list",
        func_name=FUNC_BCS_CLUSTER_DATA_ID_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )
    return _mark_inspect_response(response)


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_DATA_ID_DETAIL,
    summary="Admin 实时查询 BCS 集群 DataID CRD 详情",
    description="inspect 级别能力，通过 Kubernetes CustomObjectsApi 实时读取目标 BCS 集群中的单个 DataID CRD 原始详情，只读不写。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "cluster_id": "必填，BCSClusterInfo.cluster_id",
        "name": "必填，DataID CRD metadata.name",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "name": "k8smetricdataid"},
)
def get_bcs_cluster_data_id_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    cluster_id = _require_cluster_id(params)
    name = params.get("name")
    if name in (None, ""):
        raise CustomException(message="name 为必填项")
    name = str(name).strip()
    cluster = _get_bcs_cluster_or_raise(bk_tenant_id, cluster_id)

    resource = _get_bcs_data_id_resource(cluster, name)
    data = {**_serialize_bcs_data_id_resource(resource), "resource": resource}
    response = build_response(
        operation="bcs_cluster.data_id_detail",
        func_name=FUNC_BCS_CLUSTER_DATA_ID_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )
    return _mark_inspect_response(response)
