from typing import Any

from bk_monitor_base.config.all import get_config

from .client import fetch_clusters_client, get_project_clusters_client


def get_project_clusters(
    bk_tenant_id: str, project_id: str = "", exclude_shared_cluster: bool = False
) -> list[dict[str, Any]]:
    """
    获取项目下的集群信息

    Args:
        bk_tenant_id: 租户ID
        project_id: 项目ID
        exclude_shared_cluster: 是否过滤掉共享集群

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    clusters: list[dict[str, Any]] = get_project_clusters_client(
        bk_tenant_id=bk_tenant_id,
        params={"projectID": project_id},
    )
    if exclude_shared_cluster:
        return [
            {
                "project_id": c["projectID"],
                "cluster_id": c["clusterID"],
                "bk_biz_id": c["businessID"],
                "cluster_type": c["clusterType"],
            }
            for c in clusters or []
            if not c.get("is_shared")
        ]

    return [
        {
            "project_id": c["projectID"],
            "cluster_id": c["clusterID"],
            "bk_biz_id": c["businessID"],
            "is_shared": c.get("is_shared", False),
            "cluster_type": c["clusterType"],
        }
        for c in clusters or []
    ]


def fetch_k8s_cluster_list(bk_tenant_id: str) -> list[dict[str, Any]]:
    """
    从cluster manager获取集群列表

    Args:
        bk_tenant_id: 租户ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    cluster_id_mapping_biz_id = {}

    # 是否只同步指定业务的集群列表
    # DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID 格式: cluster_id_1:biz_id1,cluster_id_2:biz_id2
    cfg = get_config()
    if cfg.metadata.debugging_bcs_cluster_id_mapping_biz_id:
        items = cfg.metadata.debugging_bcs_cluster_id_mapping_biz_id.split(",")
        for item in items:
            mapping = item.split(":")
            if len(mapping) == 2:
                cluster_id_mapping_biz_id[mapping[0]] = mapping[1]

    clusters: list[dict[str, Any]] = fetch_clusters_client(bk_tenant_id=bk_tenant_id)

    for cluster in clusters:
        # 标记需要同步的业务集群列表
        business_id = cluster_id_mapping_biz_id.get(cluster["clusterID"], cluster["businessID"])
        cluster["businessID"] = business_id

    return clusters
