import logging
from typing import Any, cast

from .client import get_app_cluster_namespace_client

logger = logging.getLogger(__name__)


def get_app_cluster_namespace(bk_tenant_id: str, app_code: str) -> list[dict[str, Any]]:
    """
    获取蓝鲸应用对应的集群数据

    空列表表示应用确实没有使用集群资源；调用失败必须抛出，调用方据此与"没有集群资源"区分，
    不能把失败当作空结果写入。

    Args:
        bk_tenant_id: 租户ID
        app_code: 蓝鲸应用

    Returns:
        集群命名空间列表，元素至少包含 bcs_cluster_id 与 namespace

    Raises:
        BkApiError: 接口调用失败
        ValueError: 返回结构无法识别
    """
    try:
        response: Any = get_app_cluster_namespace_client(
            bk_tenant_id=bk_tenant_id,
            params={"app_code": app_code},
        )
    except Exception as e:
        logger.warning("get app cluster namespace failed, app_code: %s, error: %s", app_code, type(e).__name__)
        raise

    response_type = type(response).__name__
    if not isinstance(response, list) or not all(
        isinstance(item, dict) and "bcs_cluster_id" in item and "namespace" in item
        for item in cast(list[Any], response)
    ):
        logger.warning(
            "get app cluster namespace returned unrecognized response, app_code: %s, type: %s",
            app_code,
            response_type,
        )
        raise ValueError(f"unrecognized cluster namespace response, type: {response_type}")

    return cast(list[dict[str, Any]], response)
