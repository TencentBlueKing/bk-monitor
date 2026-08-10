"""BCS 联邦集群 Admin RPC。"""

from typing import Any

from core.drf_resource.exceptions import CustomException
from django.db.models import Count, Max

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    REQUIRED_TENANT_SCHEMA,
    build_response,
    filter_by_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_pagination,
    paginate_queryset,
    require_bk_tenant_id,
    serialize_value,
)
from metadata import models

FUNC_BCS_FEDERAL_CLUSTER_LIST = "admin.bcs_federal_cluster.list"
FUNC_BCS_FEDERAL_CLUSTER_DETAIL = "admin.bcs_federal_cluster.detail"
FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_LIST = "admin.bcs_federal_cluster.sub_cluster_list"
FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_NAMESPACE_LIST = "admin.bcs_federal_cluster.sub_cluster_namespace_list"


def _require_string(params: dict[str, Any], field_name: str) -> str:
    value = params.get(field_name)
    if value in (None, ""):
        raise CustomException(message=f"{field_name} 为必填项")
    normalized = str(value).strip()
    if not normalized:
        raise CustomException(message=f"{field_name} 为必填项")
    return normalized


def _serialize_cluster_summary(cluster: models.BCSClusterInfo | None) -> dict[str, Any] | None:
    if cluster is None:
        return None
    return {
        "cluster_id": cluster.cluster_id,
        "bk_tenant_id": cluster.bk_tenant_id,
        "bk_biz_id": cluster.bk_biz_id,
        "project_id": cluster.project_id,
        "status": cluster.status,
        "K8sMetricDataID": cluster.K8sMetricDataID,
        "K8sEventDataID": cluster.K8sEventDataID,
        "last_modify_time": serialize_value(cluster.last_modify_time),
    }


def _get_proxy_cluster_or_raise(params: dict[str, Any]) -> tuple[str, str, models.BCSClusterInfo]:
    bk_tenant_id = require_bk_tenant_id(params)
    fed_cluster_id = _require_string(params, "fed_cluster_id")
    try:
        cluster = models.BCSClusterInfo.objects.get(
            bk_tenant_id=bk_tenant_id,
            cluster_id=fed_cluster_id,
        )
    except models.BCSClusterInfo.DoesNotExist as error:
        raise CustomException(
            message=f"未找到租户 {bk_tenant_id} 下的联邦代理集群: fed_cluster_id={fed_cluster_id}"
        ) from error
    return bk_tenant_id, fed_cluster_id, cluster


def _get_active_topology_or_raise(fed_cluster_id: str):
    queryset = models.BcsFederalClusterInfo.objects.filter(
        fed_cluster_id=fed_cluster_id,
        is_deleted=False,
    )
    if not queryset.exists():
        raise CustomException(message=f"未找到有效联邦拓扑: fed_cluster_id={fed_cluster_id}")
    return queryset


def _normalize_namespaces(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


@KernelRPCRegistry.register(
    FUNC_BCS_FEDERAL_CLUSTER_LIST,
    summary="Admin 查询 BCS 联邦集群列表",
    description=(
        "从有效 BcsFederalClusterInfo 提取联邦代理集群 ID，再通过 BCSClusterInfo 完成租户过滤；不加载 Namespace 明细。"
    ),
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "fed_cluster_id": "可选，联邦代理集群 ID 包含匹配",
        "host_cluster_id": "可选，HOST 集群 ID 精确匹配",
        "sub_cluster_id": "可选，子集群 ID 精确匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "fed_cluster_id": "BCS-K8S", "page": 1, "page_size": 20},
)
def list_bcs_federal_clusters(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)

    topology_queryset = models.BcsFederalClusterInfo.objects.filter(is_deleted=False)
    fed_cluster_id = str(params.get("fed_cluster_id") or "").strip()
    host_cluster_id = str(params.get("host_cluster_id") or "").strip()
    sub_cluster_id = str(params.get("sub_cluster_id") or "").strip()
    if fed_cluster_id:
        topology_queryset = topology_queryset.filter(fed_cluster_id__icontains=fed_cluster_id)
    if host_cluster_id:
        topology_queryset = topology_queryset.filter(host_cluster_id=host_cluster_id)
    if sub_cluster_id:
        topology_queryset = topology_queryset.filter(sub_cluster_id=sub_cluster_id)

    candidate_ids = list(topology_queryset.order_by().values_list("fed_cluster_id", flat=True).distinct())
    cluster_queryset = filter_by_bk_tenant_id(
        models.BCSClusterInfo.objects.filter(cluster_id__in=candidate_ids),
        bk_tenant_id,
    ).order_by("cluster_id", "bk_tenant_id")
    clusters, total = paginate_queryset(cluster_queryset, page=page, page_size=page_size)

    page_fed_cluster_ids = [cluster.cluster_id for cluster in clusters]
    topology_summaries = {
        item["fed_cluster_id"]: item
        for item in models.BcsFederalClusterInfo.objects.filter(
            is_deleted=False,
            fed_cluster_id__in=page_fed_cluster_ids,
        )
        .values("fed_cluster_id")
        .annotate(
            host_cluster_id=Max("host_cluster_id"),
            sub_cluster_count=Count("sub_cluster_id", distinct=True),
            topology_updated_at=Max("updated_at"),
        )
    }

    items = []
    for cluster in clusters:
        topology = topology_summaries.get(cluster.cluster_id, {})
        items.append(
            {
                "bk_tenant_id": cluster.bk_tenant_id,
                "fed_cluster_id": cluster.cluster_id,
                "host_cluster_id": topology.get("host_cluster_id"),
                "bk_biz_id": cluster.bk_biz_id,
                "status": cluster.status,
                "sub_cluster_count": topology.get("sub_cluster_count", 0),
                "topology_updated_at": serialize_value(topology.get("topology_updated_at")),
            }
        )

    return build_response(
        operation="bcs_federal_cluster.list",
        func_name=FUNC_BCS_FEDERAL_CLUSTER_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_BCS_FEDERAL_CLUSTER_DETAIL,
    summary="Admin 查询 BCS 联邦集群详情",
    description="校验租户下的代理 BCSClusterInfo 后，返回数据库中的联邦拓扑摘要。",
    params_schema={
        "bk_tenant_id": REQUIRED_TENANT_SCHEMA,
        "fed_cluster_id": "必填，联邦代理集群 ID",
    },
    example_params={"bk_tenant_id": "system", "fed_cluster_id": "BCS-K8S-00000"},
)
def get_bcs_federal_cluster_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id, fed_cluster_id, proxy_cluster = _get_proxy_cluster_or_raise(params)
    topology_queryset = _get_active_topology_or_raise(fed_cluster_id)
    aggregate = topology_queryset.aggregate(
        host_cluster_id=Max("host_cluster_id"),
        sub_cluster_count=Count("sub_cluster_id", distinct=True),
        topology_updated_at=Max("updated_at"),
    )
    topology = topology_queryset.only(
        "fed_builtin_metric_table_id",
        "fed_builtin_event_table_id",
    ).first()
    host_cluster_id = aggregate.get("host_cluster_id")
    host_cluster = (
        models.BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_id=host_cluster_id,
        ).first()
        if host_cluster_id
        else None
    )

    data = {
        "bk_tenant_id": bk_tenant_id,
        "fed_cluster_id": fed_cluster_id,
        "host_cluster_id": host_cluster_id,
        "sub_cluster_count": aggregate.get("sub_cluster_count", 0),
        "topology_updated_at": serialize_value(aggregate.get("topology_updated_at")),
        "proxy_cluster": _serialize_cluster_summary(proxy_cluster),
        "host_cluster": _serialize_cluster_summary(host_cluster),
        "builtin_result_tables": {
            "metric_table_id": getattr(topology, "fed_builtin_metric_table_id", None),
            "event_table_id": getattr(topology, "fed_builtin_event_table_id", None),
        },
    }
    return build_response(
        operation="bcs_federal_cluster.detail",
        func_name=FUNC_BCS_FEDERAL_CLUSTER_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
    )


@KernelRPCRegistry.register(
    FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_LIST,
    summary="Admin 查询 BCS 联邦集群子集群列表",
    description="分页返回联邦子集群及当前页 Namespace 摘要，关联 BCSClusterInfo 使用批量查询。",
    params_schema={
        "bk_tenant_id": REQUIRED_TENANT_SCHEMA,
        "fed_cluster_id": "必填，联邦代理集群 ID",
        "sub_cluster_id": "可选，子集群 ID 包含匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "fed_cluster_id": "BCS-K8S-00000", "page": 1},
)
def list_bcs_federal_sub_clusters(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id, fed_cluster_id, _ = _get_proxy_cluster_or_raise(params)
    page, page_size = normalize_pagination(params)
    queryset = _get_active_topology_or_raise(fed_cluster_id)
    sub_cluster_id = str(params.get("sub_cluster_id") or "").strip()
    if sub_cluster_id:
        queryset = queryset.filter(sub_cluster_id__icontains=sub_cluster_id)
    queryset = queryset.order_by("sub_cluster_id").only(
        "sub_cluster_id",
        "fed_namespaces",
        "updated_at",
    )
    topology_records, total = paginate_queryset(queryset, page=page, page_size=page_size)

    sub_cluster_ids = [record.sub_cluster_id for record in topology_records]
    cluster_map = {
        cluster.cluster_id: cluster
        for cluster in models.BCSClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_id__in=sub_cluster_ids,
        )
    }
    items = []
    for record in topology_records:
        namespaces = _normalize_namespaces(record.fed_namespaces)
        items.append(
            {
                "sub_cluster_id": record.sub_cluster_id,
                "namespace_count": len(namespaces),
                "namespace_preview": namespaces[:3],
                "topology_updated_at": serialize_value(record.updated_at),
                "cluster_info": _serialize_cluster_summary(cluster_map.get(record.sub_cluster_id)),
            }
        )

    return build_response(
        operation="bcs_federal_cluster.sub_cluster_list",
        func_name=FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_NAMESPACE_LIST,
    summary="Admin 查询 BCS 联邦子集群 Namespace 列表",
    description="只展开指定联邦下一个子集群的 Namespace，并在服务端完成搜索和分页。",
    params_schema={
        "bk_tenant_id": REQUIRED_TENANT_SCHEMA,
        "fed_cluster_id": "必填，联邦代理集群 ID",
        "sub_cluster_id": "必填，子集群 ID",
        "namespace": "可选，Namespace 包含匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={
        "bk_tenant_id": "system",
        "fed_cluster_id": "BCS-K8S-00000",
        "sub_cluster_id": "BCS-K8S-00001",
        "page": 1,
    },
)
def list_bcs_federal_sub_cluster_namespaces(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id, fed_cluster_id, _ = _get_proxy_cluster_or_raise(params)
    sub_cluster_id = _require_string(params, "sub_cluster_id")
    page, page_size = normalize_pagination(params)
    topology = (
        _get_active_topology_or_raise(fed_cluster_id)
        .filter(sub_cluster_id=sub_cluster_id)
        .only("fed_namespaces")
        .first()
    )
    if topology is None:
        raise CustomException(
            message=(f"子集群不属于指定联邦: fed_cluster_id={fed_cluster_id}, sub_cluster_id={sub_cluster_id}")
        )

    namespaces = _normalize_namespaces(topology.fed_namespaces)
    namespace = str(params.get("namespace") or "").strip().casefold()
    if namespace:
        namespaces = [item for item in namespaces if namespace in item.casefold()]
    total = len(namespaces)
    offset = (page - 1) * page_size
    items = [{"namespace": item} for item in namespaces[offset : offset + page_size]]

    return build_response(
        operation="bcs_federal_cluster.sub_cluster_namespace_list",
        func_name=FUNC_BCS_FEDERAL_CLUSTER_SUB_CLUSTER_NAMESPACE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )
