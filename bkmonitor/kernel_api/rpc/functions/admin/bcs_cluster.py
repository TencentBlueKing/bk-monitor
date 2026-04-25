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
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    get_bk_tenant_id,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from metadata import models

FUNC_BCS_CLUSTER_LIST = "admin.bcs_cluster.list"
FUNC_BCS_CLUSTER_DETAIL = "admin.bcs_cluster.detail"

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


def _serialize_bcs_cluster(bcs_cluster: models.BCSClusterInfo) -> dict[str, Any]:
    item = {field: serialize_value(getattr(bcs_cluster, field, None)) for field in BCS_CLUSTER_FIELDS}
    for sensitive_field, flag_field in SENSITIVE_BCS_FIELDS.items():
        raw_value = getattr(bcs_cluster, sensitive_field, None)
        item[flag_field] = bool(raw_value)
    return item


def _build_bcs_cluster_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("bk_biz_id") not in (None, ""):
        try:
            queryset = queryset.filter(bk_biz_id=int(params["bk_biz_id"]))
        except (TypeError, ValueError) as error:
            raise CustomException(message="bk_biz_id 必须是整数") from error

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


@KernelRPCRegistry.register(
    FUNC_BCS_CLUSTER_LIST,
    summary="Admin 查询 BCSClusterInfo 列表",
    description="只读查询 BCSClusterInfo 列表，支持受控过滤、白名单排序和分页。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_biz_id": "可选，业务 ID 精确匹配",
        "cluster_id": "可选，集群 ID 包含匹配",
        "status": "可选，集群状态原始值精确匹配，支持字符串、逗号分隔字符串或列表；不传则不过滤",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}，默认 cluster_id",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20, "ordering": "cluster_id"},
)
def list_bcs_clusters(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
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
    cluster_id = params.get("cluster_id")
    if cluster_id in (None, ""):
        raise CustomException(message="cluster_id 为必填项")
    cluster_id = str(cluster_id).strip()

    try:
        cluster = models.BCSClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    except models.BCSClusterInfo.DoesNotExist as error:
        raise CustomException(message=f"未找到 BCSClusterInfo: cluster_id={cluster_id}") from error

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
