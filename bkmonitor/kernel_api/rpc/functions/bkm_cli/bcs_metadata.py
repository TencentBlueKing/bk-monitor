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
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from metadata.models.bcs.cluster import BCSClusterInfo
from metadata.models.space.space import Space, SpaceResource

DEFAULT_LIMIT = 50


def inspect_bcs_metadata(params: dict[str, Any]) -> dict[str, Any]:
    cluster_id = str(params.get("cluster_id") or "").strip()
    if not cluster_id:
        raise CustomException(message="inspect-bcs-metadata 必须提供 cluster_id")

    bk_biz_id = _optional_int(params.get("bk_biz_id"), "bk_biz_id")
    space_uid = str(params.get("space_uid") or "").strip()
    include_metric_cache = bool(params.get("include_metric_cache", False))

    bcs_cluster_info = _query_bcs_cluster_info(cluster_id, bk_biz_id)
    spaces = _query_spaces(bk_biz_id, space_uid)
    space_resources = _query_space_resources(cluster_id, bk_biz_id, space_uid)
    bcs_clusters = _query_bcs_clusters(cluster_id, bk_biz_id, space_uid)
    metric_cache = _query_metric_cache(bk_biz_id) if include_metric_cache else []

    return {
        "cluster_id": cluster_id,
        "bk_biz_id": bk_biz_id,
        "space_uid": space_uid or None,
        "bcs_cluster_info": bcs_cluster_info,
        "spaces": spaces,
        "space_resources": space_resources,
        "bcs_clusters": bcs_clusters,
        "metric_list_cache": metric_cache,
    }


def _query_bcs_cluster_info(cluster_id: str, bk_biz_id: int | None) -> list[dict[str, Any]]:
    queryset = BCSClusterInfo.objects.filter(cluster_id=cluster_id)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
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
                "bk_tenant_id",
            ],
        )
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_spaces(bk_biz_id: int | None, space_uid: str) -> list[dict[str, Any]]:
    space_filter = _space_filter(bk_biz_id, space_uid)
    if not space_filter:
        return []
    queryset = Space.objects.filter(**space_filter)
    return [
        _serialize(row, ["space_type_id", "space_id", "space_uid", "space_name", "is_bcs_valid", "bk_tenant_id"])
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_space_resources(cluster_id: str, bk_biz_id: int | None, space_uid: str) -> list[dict[str, Any]]:
    queryset = SpaceResource.objects.filter(resource_id=cluster_id)
    space_filter = _space_filter(bk_biz_id, space_uid)
    if space_filter:
        queryset = queryset.filter(**space_filter)
    return [
        _serialize(
            row,
            ["space_type_id", "space_id", "resource_type", "resource_id", "dimension_values", "bk_tenant_id"],
        )
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_bcs_clusters(cluster_id: str, bk_biz_id: int | None, space_uid: str) -> list[dict[str, Any]]:
    queryset = BCSCluster.objects.filter(bcs_cluster_id=cluster_id)
    if bk_biz_id is not None:
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    if space_uid:
        queryset = queryset.filter(space_uid=space_uid)
    return [
        _serialize(row, ["bk_biz_id", "bcs_cluster_id", "name", "environment", "space_uid", "bk_tenant_id"])
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _query_metric_cache(bk_biz_id: int | None) -> list[dict[str, Any]]:
    if bk_biz_id is None:
        return []
    queryset = MetricListCache.objects.filter(bk_biz_id=bk_biz_id)
    return [
        _serialize(
            row,
            ["bk_biz_id", "result_table_id", "metric_field", "metric_field_name", "data_label", "bk_tenant_id"],
        )
        for row in queryset[:DEFAULT_LIMIT]
    ]


def _space_filter(bk_biz_id: int | None, space_uid: str) -> dict[str, str]:
    if space_uid:
        if "__" not in space_uid:
            raise CustomException(message=f"space_uid 格式不正确: {space_uid}")
        space_type_id, space_id = space_uid.split("__", 1)
        return {"space_type_id": space_type_id, "space_id": space_id}
    if bk_biz_id is not None:
        return {"space_type_id": "bkcc", "space_id": str(bk_biz_id)}
    return {}


def _optional_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


def _serialize(instance: Any, fields: list[str]) -> dict[str, Any]:
    return {field_name: getattr(instance, field_name, None) for field_name in fields}


KernelRPCRegistry.register_function(
    func_name="bkm_cli.inspect_bcs_metadata",
    summary="核对 BCS metadata DB 记录",
    description="bkm-cli inspect-bcs-metadata 后端函数，仅通过 ORM 读取 BCS metadata 相关记录。",
    handler=inspect_bcs_metadata,
    params_schema={
        "cluster_id": "string",
        "bk_biz_id": "integer",
        "space_uid": "string",
        "include_metric_cache": "boolean",
    },
    example_params={
        "cluster_id": "BCS-K8S-00001",
        "bk_biz_id": 1001,
        "space_uid": "bkcc__1001",
        "include_metric_cache": True,
    },
)

BkmCliOpRegistry.register(
    op_id="inspect-bcs-metadata",
    func_name="bkm_cli.inspect_bcs_metadata",
    summary="核对 BCS metadata DB 记录",
    description="通过 monitor-api 服务桥纯 DB / ORM 核对 BCSClusterInfo、Space、SpaceResource、BCSCluster 与 MetricListCache。",
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["db", "bcs", "metadata", "inspect"],
    params_schema={
        "cluster_id": "string",
        "bk_biz_id": "integer",
        "space_uid": "string",
        "include_metric_cache": "boolean",
    },
    example_params={
        "cluster_id": "BCS-K8S-00001",
        "bk_biz_id": 1001,
        "space_uid": "bkcc__1001",
        "include_metric_cache": True,
    },
)
