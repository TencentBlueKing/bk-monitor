from typing import Any

from .client import fetch_shared_cluster_namespaces_client, get_federation_clusters_client, get_projects_client


def fetch_shared_cluster_namespaces(
    bk_tenant_id: str, cluster_id: str, project_code: str = "-"
) -> list[dict[str, Any]]:
    """
    获取共享集群命名空间列表

    Args:
        bk_tenant_id: 租户ID
        cluster_id: 集群ID
        project_code: 项目code

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    ns_list: list[dict[str, Any]] = fetch_shared_cluster_namespaces_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "cluster_id": cluster_id,
            "project_code": project_code,
        },
    )
    return [
        {
            "project_id": ns["projectID"],
            "project_code": ns["projectCode"],
            "cluster_id": cluster_id,
            "namespace": ns["name"],
        }
        for ns in ns_list
    ]


def get_federation_clusters(
    bk_tenant_id: str,
    fed_project_code: str = "",
    fed_cluster_id: str = "",
    sub_project_code: str = "",
    sub_cluster_id: str = "",
) -> dict[str, Any]:
    """
    查询联邦集群信息

    Args:
        bk_tenant_id: 租户ID
        fed_project_code: fed_project_code
        fed_cluster_id: fed_cluster_id
        sub_project_code: sub_project_code
        sub_cluster_id: sub_cluster_id

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {}
    # 添加联邦集群的查询条件
    if fed_project_code or fed_cluster_id:
        params["conditions"] = {}
        if fed_project_code:
            params["conditions"]["project_code"] = fed_project_code
        if fed_cluster_id:
            params["conditions"]["cluster_id"] = fed_cluster_id
    # 添加子集群的查询条件
    if sub_project_code or sub_cluster_id:
        params["sub_conditions"] = {}
        if sub_project_code:
            params["sub_conditions"]["project_code"] = sub_project_code
        if sub_cluster_id:
            params["sub_conditions"]["sub_cluster_id"] = sub_cluster_id
    """
    cluster_data = {
        "{federation_cluster_id}": {
            "host_cluster_id": "{host_cluster_id}",
            "sub_clusters": {
                "{sub_cluster_id}": [namespace1, namespace2, namespace3]
            }
        }
    }
    """
    cluster_data: list[dict[str, Any]] = get_federation_clusters_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    if not cluster_data:
        return {}
    resp_data: dict[str, Any] = {}
    for data in cluster_data:
        sub_item = {}
        for sub in data["sub_clusters"]:
            sub_item.setdefault(sub["sub_cluster_id"], []).extend(sub.get("federation_namespaces", []))
        resp_data.setdefault(data["federation_cluster_id"], {}).update(
            {
                "host_cluster_id": data["host_cluster_id"],
                "sub_clusters": sub_item,
            }
        )
    return resp_data


def get_projects(
    bk_tenant_id: str, kind: str = "", is_detail: bool = False, limit: int = 1000, offset: int = 0
) -> list[dict[str, Any]]:
    """
    查询项目信息

    Args:
        bk_tenant_id: 租户ID
        kind: 类型
        is_detail: 是否详情
        limit: 查询限制
        offset: 查询偏移量

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    projects: dict[str, Any] = get_projects_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "kind": kind,
            "limit": limit,
            "offset": offset,
        },
    )
    count = projects["total"]
    project_list: list[dict[str, Any]] = projects.get("results") or []
    params = {
        "kind": kind,
        "limit": limit,
        "offset": offset,
    }
    # 如果每页的数量大于count，则不用继续请求，否则需要继续请求
    if count > limit:
        max_offset = count // limit
        start_offset = 1
        while start_offset <= max_offset:
            params.update({"limit": limit, "offset": start_offset})
            resp_data = get_projects_client(
                bk_tenant_id=bk_tenant_id,
                params=params,
            )
            project_list.extend(resp_data.get("results") or [])
            start_offset += 1
    # 因为返回数据内容太多，抽取必要的字段
    if is_detail:
        return project_list

    return [
        {
            "project_id": p["projectID"],
            "name": p["name"],
            "project_code": p["projectCode"],
            "bk_biz_id": p["businessID"],
        }
        for p in project_list
    ]
