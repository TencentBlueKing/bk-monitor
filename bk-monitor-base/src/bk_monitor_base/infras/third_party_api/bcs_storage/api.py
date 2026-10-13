from typing import Any

from .client import fetch_client


def fetch_k8s_node_list_by_cluster(bk_tenant_id: str, bcs_cluster_id: str = "") -> list[dict[str, Any]]:
    """
    获取集群的Node信息

    Args:
        bk_tenant_id: 租户ID
        bcs_cluster_id: 集群ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """

    node_fields = ",".join(
        [
            "data.metadata.name",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.spec.unschedulable",
            "data.spec.taints",
            "data.status.addresses",
            "data.status.conditions",
        ]
    )

    params: dict[str, Any] = {
        "cluster_id": bcs_cluster_id,
        "type": "Nodes",
        "field": node_fields,
    }

    node_list: list[dict[str, Any]] = []
    offset = 0
    limit = 5000
    while True:
        params["offset"] = offset
        params["limit"] = limit
        data: list[dict[str, Any]] = fetch_client(bk_tenant_id=bk_tenant_id, params=params)
        node_list.extend(data)
        data_len = len(data)
        if data_len == limit:
            offset += limit
            params["offset"] = offset
            continue
        break

    result: list[dict[str, Any]] = []
    for node in node_list:
        node_ip = ""
        for address in node.get("status", {}).get("addresses", []):
            if address.get("type") == "InternalIP":
                node_ip = address.get("address", "")
                break
        result.append(
            {
                "bcs_cluster_id": bcs_cluster_id,
                "node_ip": node_ip,
            }
        )
    return result
