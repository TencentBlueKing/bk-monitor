"""CMDB 主机 Agent 状态辅助函数。"""

import logging
from datetime import datetime
from typing import Any, cast

from bk_monitor_base.infras.third_party_api.nodeman.api import (
    IpchooserHostDetail,
    IpchooserHostDetailsHost,
    IpchooserHostDetailsHostMeta,
    IpchooserHostDetailsParams,
    IpchooserHostDetailsScope,
)

logger = logging.getLogger(__name__)

IPCHOOSER_HOST_DETAILS_BATCH_SIZE = 1000


def get_host_agent_status_map(
    bk_tenant_id: str,
    hosts: list[dict[str, Any]],
) -> dict[str, IpchooserHostDetail]:
    """批量查询主机 Agent 状态。

    Args:
        bk_tenant_id: 蓝鲸租户 ID。
        hosts: 主机列表，支持 ``bk_host_innerip``、``ip``、``bk_cloud_id``、
            ``bk_agent_id`` 等字段。

    Returns:
        以 ``bk_host_id`` 为键的 Agent 状态映射。
    """
    if not hosts:
        return {}

    from bk_monitor_base.infras.third_party_api import node_man

    query_hosts: list[IpchooserHostDetailsHost] = []
    scope_list: list[IpchooserHostDetailsScope] = []
    existed_host_ids: set[int] = set()
    existed_scopes: set[tuple[str, str]] = set()

    for host in hosts:
        bk_host_id = host.get("bk_host_id") or host.get("host_id")
        if not bk_host_id:
            continue

        raw_meta = host.get("meta")
        meta: dict[str, Any] = cast(dict[str, Any], raw_meta) if isinstance(raw_meta, dict) else {}
        bk_biz_id = meta.get("bk_biz_id", host.get("bk_biz_id"))
        if bk_biz_id is None:
            continue

        try:
            host_id = int(bk_host_id)
            biz_id = int(bk_biz_id)
        except (TypeError, ValueError):
            continue

        if host_id in existed_host_ids:
            continue

        scope_type = str(meta.get("scope_type") or "biz")
        raw_scope_id = meta.get("scope_id")
        scope_id = str(raw_scope_id) if raw_scope_id is not None else str(biz_id)
        host_meta: IpchooserHostDetailsHostMeta = {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "bk_biz_id": biz_id,
        }

        query_hosts.append(
            {
                "host_id": host_id,
                "meta": host_meta,
            }
        )
        existed_host_ids.add(host_id)

        scope_key = (scope_type, scope_id)
        if scope_key in existed_scopes:
            continue
        scope_list.append(
            {
                "scope_type": scope_type,
                "scope_id": scope_id,
            }
        )
        existed_scopes.add(scope_key)

    if not query_hosts:
        return {}

    try:
        status_map: dict[str, IpchooserHostDetail] = {}
        for start in range(0, len(query_hosts), IPCHOOSER_HOST_DETAILS_BATCH_SIZE):
            params: IpchooserHostDetailsParams = {
                "host_list": query_hosts[start : start + IPCHOOSER_HOST_DETAILS_BATCH_SIZE],
                "scope_list": scope_list,
                "agent_realtime_state": True,
            }
            response = node_man.get_ipchooser_host_details(
                bk_tenant_id=bk_tenant_id,
                params=params,
            )
            for host_detail in response:
                status_map[str(host_detail["bk_host_id"])] = host_detail
        return status_map
    except Exception as error:
        logger.warning("get_host_agent_status_map failed: %s", error)
        return {}


def enrich_host_instances_with_agent_status(
    bk_tenant_id: str,
    host_instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """为主机实例补充 Agent 状态字段。

    Args:
        bk_tenant_id: 蓝鲸租户 ID。
        host_instances: 主机实例列表。

    Returns:
        已附加 ``bk_agent_alive``、``error`` 和 ``agent_status_sync_time`` 的主机实例列表。
    """
    if not host_instances:
        return host_instances

    status_map = get_host_agent_status_map(bk_tenant_id=bk_tenant_id, hosts=host_instances)
    current_time = datetime.now()

    enriched_instances: list[dict[str, Any]] = []
    for host in host_instances:
        host_key = str(host.get("bk_host_id") or host.get("host_id") or "")
        is_alive = bool(status_map.get(host_key, {}).get("bk_agent_alive", 0))
        enriched_instances.append(
            {
                **host,
                "bk_agent_alive": is_alive,
                "error": not is_alive,
                "agent_status_sync_time": current_time,
            }
        )

    return enriched_instances
