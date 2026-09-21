from typing import Any

from .client import (
    add_route_client,
    add_stream_to_client,
    delete_route_client,
    dispatch_message_client,
    query_route_client,
    query_stream_to_client,
    update_route_client,
    update_stream_to_client,
)


def add_route(
    bk_tenant_id: str,
    metadata: dict[str, Any],
    operation: dict[str, Any],
    route: list[dict[str, Any]] | None = None,
    stream_filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    添加路由配置

    Args:
        bk_tenant_id: 租户ID
        metadata: 所属平台的源信息
        operation: 操作人配置
        route: 路由入库配置
        stream_filters: 过滤规则配置

    Returns:
        {"channel_id": 1573293}
    """
    params: dict[str, Any] = {
        "metadata": metadata,
        "operation": operation,
    }
    if route is not None:
        params["route"] = route
    if stream_filters is not None:
        params["stream_filters"] = stream_filters

    return add_route_client(bk_tenant_id=bk_tenant_id, params=params)


def add_stream_to(
    bk_tenant_id: str,
    metadata: dict[str, Any],
    operation: dict[str, Any],
    stream_to: dict[str, Any],
) -> dict[str, Any]:
    """
    新增数据接收端配置

    Args:
        bk_tenant_id: 租户ID
        metadata: 所属平台的源信息
        operation: 操作人配置
        stream_to: 接收端详细配置

    Returns:
        {
            "stream_to_id": 1234,
            "xxxx": xxx
        }
    """
    params: dict[str, Any] = {
        "metadata": metadata,
        "operation": operation,
        "stream_to": stream_to,
    }

    return add_stream_to_client(bk_tenant_id=bk_tenant_id, params=params)


def delete_route(
    bk_tenant_id: str,
    condition: dict[str, Any],
    operation: dict[str, Any],
    specification: dict[str, Any] | None = None,
) -> None:
    """
    删除路由配置

    Args:
        bk_tenant_id: 租户ID
        condition: 条件信息
        operation: 操作配置
        specification: 指定待删除的配置名称

    Returns:
        None
    """
    params: dict[str, Any] = {
        "condition": condition,
        "operation": operation,
    }
    if specification is not None:
        params["specification"] = specification

    return delete_route_client(bk_tenant_id=bk_tenant_id, params=params)


def query_route(
    bk_tenant_id: str,
    condition: dict[str, Any],
    operation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    查询路由配置

    Args:
        bk_tenant_id: 租户ID
        condition: 条件信息
        operation: 操作配置

    Returns:
        [
          {
            "metadata": {
              "channel_id": 1234567,
              "plat_name": "bkmonitor"
            },
            "route":
            [
              {
                "name": "stream_to_bkmonitor_kafka_0bkmonitor_12345670",
                "stream_to": {
                  "stream_to_id": 1234,
                  "kafka": {
                    "topic_name": "0bkmonitor_12345670"
                  }
                },
                "deliver_type": 0
              }
            ]
          }
        ]
    """
    params: dict[str, Any] = {
        "condition": condition,
        "operation": operation,
    }
    return query_route_client(bk_tenant_id=bk_tenant_id, params=params)


def query_stream_to(
    bk_tenant_id: str,
    condition: dict[str, Any],
    operation: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    查询数据接收端配置

    Args:
        bk_tenant_id: 租户ID
        condition: 接口端配置条件
        operation: 操作配置

    Returns:

    """
    params: dict[str, Any] = {
        "condition": condition,
        "operation": operation,
    }
    return query_stream_to_client(bk_tenant_id=bk_tenant_id, params=params)


def update_route(
    bk_tenant_id: str,
    condition: dict[str, Any],
    operation: dict[str, Any],
    specification: dict[str, Any],
) -> dict[str, Any]:
    """
    修改路由配置

    Args:
        bk_tenant_id: 租户ID
        condition: 接口端配置条件
        operation: 操作配置
        specification: 路由信息

    Returns:

    """
    params: dict[str, Any] = {
        "condition": condition,
        "operation": operation,
        "specification": specification,
    }
    return update_route_client(bk_tenant_id=bk_tenant_id, params=params)


def update_stream_to(
    bk_tenant_id: str,
    condition: dict[str, Any],
    operation: dict[str, Any],
    specification: dict[str, Any],
) -> dict[str, Any]:
    """
    修改数据接收端配置

    Args:
        bk_tenant_id: 租户ID
        condition: 接收端配置条件信息
        operation: 操作配置
        specification: 接收端配置信息

    Returns:

    """
    params: dict[str, Any] = {
        "condition": condition,
        "operation": operation,
        "specification": specification,
    }
    return update_stream_to_client(bk_tenant_id=bk_tenant_id, params=params)


def dispatch_message(
    bk_tenant_id: str,
    message_id: str,
    agent_id_list: list[str],
    content: str,
) -> dict[str, Any]:
    """
    修改数据接收端配置

    Args:
        bk_tenant_id: 租户ID
        message_id: 消息ID
        agent_id_list: Agent ID列表
        content: 请求内容

    Returns:

    """
    params: dict[str, Any] = {
        "message_id": message_id,
        "agent_id_list": agent_id_list,
        "content": content,
    }
    return dispatch_message_client(bk_tenant_id=bk_tenant_id, params=params)
