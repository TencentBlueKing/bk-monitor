"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

from bkmonitor.models.bcs_cluster import BCSCluster
from bkmonitor.models.metric_list_cache import MetricListCache
from core.drf_resource.exceptions import CustomException
from django.core import signing
from django.db.models import Q
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from metadata.models.bcs.cluster import BCSClusterInfo, BcsFederalClusterInfo
from metadata.models.space.constants import SpaceTypes
from metadata.models.space.space import Space, SpaceResource

DEFAULT_LIMIT = 50
FEDERAL_NAMESPACE_LIMIT = 200
FEDERAL_MAX_PAGE_SIZE = 50
FEDERAL_CURSOR_SALT = "bkm-cli.inspect-bcs-metadata.federal-cursor"


def inspect_bcs_metadata(params: dict[str, Any]) -> dict[str, Any]:
    cluster_id = str(params.get("cluster_id") or "").strip()
    if not cluster_id:
        raise CustomException(message="inspect-bcs-metadata 必须提供 cluster_id")

    bk_biz_id = _optional_int(params.get("bk_biz_id"), "bk_biz_id")
    space_uid = str(params.get("space_uid") or "").strip()
    bk_tenant_id = str(params.get("bk_tenant_id") or "").strip()
    include_metric_cache = bool(params.get("include_metric_cache", False))
    federal_cursor = params.get("federal_cursor")
    federal_cursor_id = _decode_federal_cursor(federal_cursor, cluster_id, bk_tenant_id)
    federal_page_size = _federal_page_size(params.get("federal_page_size"))

    bcs_cluster_info = _query_bcs_cluster_info(cluster_id, bk_biz_id, bk_tenant_id)
    spaces = _query_spaces(bk_biz_id, space_uid, bk_tenant_id)
    space_resources = _query_space_resources(cluster_id, bk_biz_id, space_uid, bk_tenant_id)
    bcs_clusters = _query_bcs_clusters(cluster_id, bk_biz_id, space_uid, bk_tenant_id)
    metric_cache = _query_metric_cache(bk_biz_id, bk_tenant_id) if include_metric_cache else []

    # 先用同租户的目标集群建立授权锚点，再在联邦关系查询中重复施加租户条件。
    # BKCC 空间可直接用 BCSClusterInfo.bk_biz_id 证明归属；项目空间则还需
    # SpaceResource 或 BCSCluster 关系。
    federal_scope_allowed = bool(
        bk_tenant_id
        and bcs_cluster_info
        and _space_scope_matches_cluster(space_uid, bcs_cluster_info, space_resources, bcs_clusters)
    )
    federal_cluster_info = (
        _query_federal_cluster_info(
            cluster_id,
            bk_tenant_id,
            cursor=federal_cursor,
            cursor_id=federal_cursor_id,
            page_size=federal_page_size,
        )
        if federal_scope_allowed
        else _empty_federal_cluster_info(
            "not_found_in_scope",
            cursor=federal_cursor,
            page_size=federal_page_size,
        )
    )

    return {
        "cluster_id": cluster_id,
        "bk_biz_id": bk_biz_id,
        "space_uid": space_uid or None,
        "bcs_cluster_info": bcs_cluster_info,
        "spaces": spaces,
        "space_resources": space_resources,
        "bcs_clusters": bcs_clusters,
        "metric_list_cache": metric_cache,
        "federal_cluster_info": federal_cluster_info,
    }


def _query_bcs_cluster_info(cluster_id: str, bk_biz_id: int | None, bk_tenant_id: str) -> list[dict[str, Any]]:
    queryset = BCSClusterInfo.objects.filter(cluster_id=cluster_id)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    if bk_tenant_id:
        queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
    return [
        _serialize(
            row,
            [
                "cluster_id",
                "bcs_api_cluster_id",
                "bk_biz_id",
                "project_id",
                "status",
                "K8sMetricDataID",
                "K8sEventDataID",
                "CustomMetricDataID",
                "CustomEventDataID",
                "bk_env",
                "bk_env_label",
                "bk_tenant_id",
            ],
        )
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_spaces(bk_biz_id: int | None, space_uid: str, bk_tenant_id: str) -> list[dict[str, Any]]:
    if bk_biz_id is None and not space_uid:
        return []
    space_filter = _space_filter(bk_biz_id, space_uid, bk_tenant_id)
    queryset = Space.objects.filter(**space_filter)
    return [
        _serialize(row, ["space_type_id", "space_id", "space_uid", "space_name", "is_bcs_valid", "bk_tenant_id"])
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_space_resources(
    cluster_id: str, bk_biz_id: int | None, space_uid: str, bk_tenant_id: str
) -> list[dict[str, Any]]:
    if bk_biz_id is None and not space_uid:
        return []
    space_filter = _space_filter(bk_biz_id, space_uid, bk_tenant_id)
    queryset = SpaceResource.objects.filter(
        resource_type=SpaceTypes.BCS.value,
        resource_id=space_filter["space_id"],
    ).filter(**space_filter)
    return [
        _serialize(
            row,
            ["space_type_id", "space_id", "resource_type", "resource_id", "dimension_values", "bk_tenant_id"],
        )
        for row in queryset[:DEFAULT_LIMIT]
        if _space_resource_contains_cluster(row, cluster_id)
    ]


def _query_bcs_clusters(
    cluster_id: str, bk_biz_id: int | None, space_uid: str, bk_tenant_id: str
) -> list[dict[str, Any]]:
    queryset = BCSCluster.objects.filter(bcs_cluster_id=cluster_id)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    if space_uid:
        queryset = queryset.filter(space_uid=space_uid)
    if bk_tenant_id:
        queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
    return [
        _serialize(row, ["bk_biz_id", "bcs_cluster_id", "name", "environment", "space_uid", "bk_tenant_id"])
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_metric_cache(bk_biz_id: int | None, bk_tenant_id: str) -> list[dict[str, Any]]:
    if bk_biz_id is None:
        return []
    queryset = MetricListCache.objects.filter(bk_biz_id=bk_biz_id)
    if bk_tenant_id:
        queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
    return [
        _serialize(
            row,
            ["bk_biz_id", "result_table_id", "metric_field", "metric_field_name", "data_label", "bk_tenant_id"],
        )
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_federal_cluster_info(
    cluster_id: str,
    bk_tenant_id: str,
    *,
    cursor: str | None,
    cursor_id: int | None,
    page_size: int,
) -> dict[str, Any]:
    queryset = BcsFederalClusterInfo.objects.filter(
        Q(fed_cluster_id=cluster_id) | Q(host_cluster_id=cluster_id) | Q(sub_cluster_id=cluster_id)
    ).filter(bk_tenant_id=bk_tenant_id)
    total_count = queryset.count()
    if total_count == 0:
        return _empty_federal_cluster_info("not_federal", cursor=cursor, page_size=page_size)

    page_queryset = queryset.order_by("id")
    if cursor_id is not None:
        page_queryset = page_queryset.filter(id__gt=cursor_id)
    rows = list(page_queryset[: page_size + 1])
    truncated = len(rows) > page_size
    page_rows = rows[:page_size]

    items = [_serialize_federal_cluster_info(row) for row in page_rows]
    next_cursor = None
    if truncated:
        last_row = page_rows[-1]
        last_id = int(getattr(last_row, "pk", None) or getattr(last_row, "id"))
        next_cursor = _encode_federal_cursor(last_id, cluster_id, bk_tenant_id)
    return {
        "status": "found",
        "total_count": total_count,
        "returned_count": len(items),
        "truncated": truncated,
        "cursor": cursor,
        "page_size": page_size,
        "next_cursor": next_cursor,
        "items": items,
    }


def _serialize_federal_cluster_info(instance: Any) -> dict[str, Any]:
    raw_namespaces = getattr(instance, "fed_namespaces", None)
    namespaces = list(raw_namespaces) if isinstance(raw_namespaces, (list, tuple)) else []
    returned_namespaces = namespaces[:FEDERAL_NAMESPACE_LIMIT]
    return {
        **_serialize(
            instance,
            [
                "fed_cluster_id",
                "host_cluster_id",
                "sub_cluster_id",
                "is_deleted",
            ],
        ),
        "fed_namespaces": returned_namespaces,
        "fed_namespaces_total_count": len(namespaces),
        "fed_namespaces_returned_count": len(returned_namespaces),
        "fed_namespaces_truncated": len(namespaces) > len(returned_namespaces),
        **_serialize(
            instance,
            ["fed_builtin_metric_table_id", "fed_builtin_event_table_id"],
        ),
    }


def _empty_federal_cluster_info(
    status: str,
    *,
    cursor: str | None = None,
    page_size: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    return {
        "status": status,
        "total_count": 0,
        "returned_count": 0,
        "truncated": False,
        "cursor": cursor,
        "page_size": page_size,
        "next_cursor": None,
        "items": [],
    }


def _space_scope_matches_cluster(
    space_uid: str,
    bcs_cluster_info: list[dict[str, Any]],
    space_resources: list[dict[str, Any]],
    bcs_clusters: list[dict[str, Any]],
) -> bool:
    if not space_uid:
        return True
    space_type_id, space_id = space_uid.split("__", 1)
    if space_type_id == SpaceTypes.BKCC.value:
        return any(str(item.get("bk_biz_id")) == space_id for item in bcs_cluster_info)
    return bool(space_resources or bcs_clusters)


def _space_resource_contains_cluster(instance: Any, cluster_id: str) -> bool:
    dimension_values = getattr(instance, "dimension_values", None)
    if not isinstance(dimension_values, (list, tuple)):
        return False
    return any(
        isinstance(item, dict) and str(item.get("cluster_id") or "").strip() == cluster_id for item in dimension_values
    )


def _space_filter(bk_biz_id: int | None, space_uid: str, bk_tenant_id: str) -> dict[str, str]:
    filters = {"bk_tenant_id": bk_tenant_id} if bk_tenant_id else {}
    if space_uid:
        if "__" not in space_uid:
            raise CustomException(message=f"space_uid 格式不正确: {space_uid}")
        space_type_id, space_id = space_uid.split("__", 1)
        return {**filters, "space_type_id": space_type_id, "space_id": space_id}
    if bk_biz_id is not None:
        return {**filters, "space_type_id": "bkcc", "space_id": str(bk_biz_id)}
    return filters


def _optional_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise CustomException(message=f"{field_name} 必须是整数: {value}")
    try:
        normalized = int(value)
    except ValueError as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error
    if normalized is not None and normalized < 1:
        raise CustomException(message=f"{field_name} 必须大于等于 1")
    return normalized


def _federal_page_size(value: Any) -> int:
    page_size = _optional_positive_int(value, "federal_page_size") or DEFAULT_LIMIT
    if page_size > FEDERAL_MAX_PAGE_SIZE:
        raise CustomException(message=f"federal_page_size 超过硬上限 {FEDERAL_MAX_PAGE_SIZE}: {page_size}")
    return page_size


def _encode_federal_cursor(last_id: int, cluster_id: str, bk_tenant_id: str) -> str:
    return signing.dumps(
        {
            "version": 1,
            "last_id": last_id,
            "cluster_id": cluster_id,
            "bk_tenant_id": bk_tenant_id,
        },
        salt=FEDERAL_CURSOR_SALT,
    )


def _decode_federal_cursor(value: Any, cluster_id: str, bk_tenant_id: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CustomException(message="federal_cursor 无效、已被篡改或与当前租户/集群范围不匹配，请从第一页重新读取")

    try:
        payload = signing.loads(value, salt=FEDERAL_CURSOR_SALT)
    except (signing.BadSignature, TypeError, ValueError):
        raise CustomException(
            message="federal_cursor 无效、已被篡改或与当前租户/集群范围不匹配，请从第一页重新读取"
        ) from None

    last_id = payload.get("last_id") if isinstance(payload, dict) else None
    valid = (
        isinstance(payload, dict)
        and payload.get("version") == 1
        and isinstance(last_id, int)
        and not isinstance(last_id, bool)
        and last_id > 0
        and payload.get("cluster_id") == cluster_id
        and payload.get("bk_tenant_id") == bk_tenant_id
    )
    if not valid:
        raise CustomException(message="federal_cursor 无效、已被篡改或与当前租户/集群范围不匹配，请从第一页重新读取")
    return last_id


def _serialize(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {field_name: getattr(instance, field_name, None) for field_name in fields}


KernelRPCRegistry.register_function(
    func_name="bkm_cli.inspect_bcs_metadata",
    summary="核对 BCS metadata DB 记录",
    description="bkm-cli inspect-bcs-metadata 后端函数，仅通过 ORM 读取 BCS metadata 与联邦拓扑相关记录。",
    handler=inspect_bcs_metadata,
    params_schema={
        "cluster_id": "string",
        "bk_biz_id": "integer",
        "space_uid": "string",
        "include_metric_cache": "boolean",
        "federal_cursor": "string",
        "federal_page_size": "integer",
    },
    example_params={
        "cluster_id": "BCS-K8S-00001",
        "bk_biz_id": 1001,
        "space_uid": "bkcc__1001",
        "include_metric_cache": True,
        "federal_page_size": 50,
    },
)

BkmCliOpRegistry.register(
    op_id="inspect-bcs-metadata",
    func_name="bkm_cli.inspect_bcs_metadata",
    summary="核对 BCS metadata DB 记录",
    description=(
        "通过 monitor-api 服务桥纯 DB / ORM 核对 BCSClusterInfo、BcsFederalClusterInfo、Space、"
        "SpaceResource、BCSCluster 与 MetricListCache。"
    ),
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["db", "bcs", "metadata", "inspect"],
    params_schema={
        "cluster_id": "string",
        "bk_biz_id": "integer",
        "space_uid": "string",
        "include_metric_cache": "boolean",
        "federal_cursor": "string",
        "federal_page_size": "integer",
    },
    example_params={
        "cluster_id": "BCS-K8S-00001",
        "bk_biz_id": 1001,
        "space_uid": "bkcc__1001",
        "include_metric_cache": True,
        "federal_page_size": 50,
    },
)
