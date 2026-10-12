from typing import Any

from bk_monitor_base.infras.third_party_api.errors import BkApiError

from .client import get_app_cluster_namespace_client


def get_app_cluster_namespace(bk_tenant_id: str, app_code: str) -> list[dict[str, Any]]:
    """
    获取蓝鲸应用对应的集群数据

    Args:
        bk_tenant_id: 租户ID
        app_code: 蓝鲸应用

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    try:
        clusters: list[dict[str, Any]] = get_app_cluster_namespace_client(
            bk_tenant_id=bk_tenant_id,
            params={"app_code": app_code},
        )
        return clusters
    except BkApiError:
        return [{app_code: f"{bk_tenant_id}-{app_code}"}, {bk_tenant_id: f"{bk_tenant_id}-{app_code}"}]
