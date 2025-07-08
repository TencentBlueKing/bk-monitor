import logging

from bkm_ipchooser.constants import ScopeType
from core.drf_resource import api

logger = logging.getLogger("bkm_ipchooser")


def fill_agent_status(cc_hosts: list[dict], bk_biz_id: int) -> list[dict]:
    """填充主机agent状态"""
    if not cc_hosts:
        return cc_hosts

    host_map = {}
    for index, cc_host in enumerate(cc_hosts):
        host_map[cc_host["bk_host_id"]] = index

    meta = {"scope_type": ScopeType.BIZ.value, "scope_id": str(bk_biz_id), "bk_biz_id": bk_biz_id}
    host_list = [{"host_id": host["bk_host_id"], "meta": meta} for host in cc_hosts]
    scope_list = [{"scope_type": ScopeType.BIZ.value, "scope_id": str(bk_biz_id)}]
    # 添加no_request参数, 多线程调用时，保证用户信息不漏传
    request_params = {
        "no_request": True,
        "host_list": host_list,
        "scope_list": scope_list,
        "agent_realtime_state": True,
    }
    try:
        host_info = api.node_man.ipchooser_host_detail(request_params)
    except Exception as e:
        logger.error("获取主机agent状态失败: %s", e)
        return cc_hosts

    for status in host_info:
        host_id = status.get("host_id")
        if host_id in host_map and "alive" in status:
            # status["alive"]为 1 时表示 ALIVE，为 0 时表示 NO_ALIVE
            cc_hosts[host_map[host_id]]["status"] = status["alive"]
    return cc_hosts
