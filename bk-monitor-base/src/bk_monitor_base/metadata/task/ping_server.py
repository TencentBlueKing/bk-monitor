import logging
import time
from collections import defaultdict
from typing import Any

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.cmdb.api import CloudArea, HostPropertyFilter, format_ip_filter_rule
from bk_monitor_base.infras.third_party_api.user.api import list_tenant
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.models.ping_server import PingServerSubscriptionConfig
from bk_monitor_base.metadata.utils.hashring import HashRing
from bk_monitor_base.metadata.utils.tools import is_ipv6_biz

logger = logging.getLogger("metadata")


def refresh_ping_server_2_node_man():
    """
    刷新Ping Server配置至节点管理，下发ip列表到proxy机器
    """

    # 兼容下发proxy
    start_time = time.time()
    logger.info("start refresh ping server to node man")
    refresh_ping_conf("bk-collector")
    cost_time = time.time() - start_time
    logger.info(f"end refresh ping server to node man, cost time: {cost_time}")


def refresh_ping_conf(plugin_name: str):
    """
    刷新Ping Server的ip列表配置

    1. 获取CMDB下的所有主机ip
    2. 获取云区域下的所有ProxyIP
    3. 根据Hash环，将同一云区域下的ip分配到不同的Proxy
    4. 通过节点管理订阅任务将分配好的ip下发到机器
    """
    if not settings.metadata.enable_ping_alarm:
        for tenant in list_tenant():
            cloud_areas: list[CloudArea] = api.cmdb.search_cloud_area(bk_tenant_id=tenant["id"])
            for cloud_area in cloud_areas:
                PingServerSubscriptionConfig.create_subscription(
                    tenant["id"], cloud_area["bk_cloud_id"], {}, [], plugin_name
                )
        return

    for tenant in list_tenant():
        bk_tenant_id: str = tenant["id"]

        exists_host_ids: set[int] = set()
        cloud_to_hosts: dict[int, list[dict[str, Any]]] = defaultdict(list)

        # 获取CMDB下的所有主机ip
        try:
            _, all_hosts = api.cmdb.list_all_hosts(bk_tenant_id=bk_tenant_id)
        except Exception:  # noqa
            logger.exception("CMDB的主机缓存获取失败。获取不到主机，有可能会导致pingserver不执行")
            continue

        for h in all_hosts:
            ip = h.bk_host_innerip_v6 if is_ipv6_biz(h.bk_biz_id) else h.bk_host_innerip
            # 跳过忽略监控的主机和已经处理过的主机
            if (
                getattr(h, "bk_state", None) in settings.metadata.host_disable_monitor_states
                or not ip
                or h.bk_host_id in exists_host_ids
            ):
                continue

            # 将主机添加到租户ID+云区域对应的列表中
            cloud_to_hosts[h.bk_cloud_id].append(
                {"ip": ip, "bk_cloud_id": h.bk_cloud_id, "bk_biz_id": h.bk_biz_id, "bk_host_id": h.bk_host_id}
            )
            exists_host_ids.add(h.bk_host_id)

        # 释放内存
        del all_hosts

        # 按租户ID+云区域对主机进行分组，并刷新Ping Server的ip列表配置
        for bk_cloud_id, target_ips in cloud_to_hosts.items():
            try:
                _refresh_ping_conf_by_cloud_id(bk_tenant_id, bk_cloud_id, plugin_name, target_ips)
            except Exception as e:
                logger.exception(
                    f"refresh ping server config error, bk_tenant_id({bk_tenant_id}), bk_cloud_id({bk_cloud_id}), error({e})"
                )


def _refresh_ping_conf_by_cloud_id(
    bk_tenant_id: str, bk_cloud_id: int, plugin_name: str, target_ips: list[dict[str, Any]]
):
    """
    刷新Ping Server的ip列表配置

    1. 获取CMDB下的所有主机ip
    2. 获取云区域下的所有ProxyIP
    3. 根据Hash环，将同一云区域下的ip分配到不同的Proxy
    4. 通过节点管理订阅任务将分配好的ip下发到机器
    """
    # 如果云区域小于0，代表未分配云区域，则不进行下发
    if bk_cloud_id < 0:
        return

    if bk_cloud_id == 0:
        # 如果是直连区域，默认使用监控平台内置的proxy ip进行下发，这些ip只能默认租户下的机器
        if not settings.metadata.custom_report_default_proxy_ip:
            return
        ip_filters = format_ip_filter_rule(settings.metadata.custom_report_default_proxy_ip)
        _, hosts = api.cmdb.list_hosts_without_biz(
            bk_tenant_id=DEFAULT_TENANT_ID,
            host_property_filter=HostPropertyFilter(condition="AND", rules=ip_filters),
        )
        proxies = [{"bk_host_id": host.bk_host_id} for host in hosts]
        target_hosts = [
            {
                "ip": host.bk_host_innerip,
                "ipv6": host.bk_host_innerip_v6,
                "bk_cloud_id": 0,
                "bk_supplier_id": 0,
                "bk_host_id": host.bk_host_id,
                "bk_biz_id": host.bk_biz_id,
            }
            for host in hosts
        ]
    else:
        try:
            proxy_list = api.node_man.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)
        except Exception:  # noqa
            logger.exception(f"从节点管理获取云区域({bk_cloud_id})下的ProxyIP列表失败")
            return

        # 过滤掉不可用的proxy
        proxies = []
        target_hosts = []
        for p in proxy_list:
            if p["status"] != "RUNNING":
                logger.warning("proxy({}) can not be use with pingserver, it's not running".format(p["inner_ip"]))
            else:
                proxies.append(p)
                target_hosts.append(
                    {
                        "ip": p["inner_ip"],
                        "ipv6": p.get("inner_ipv6", ""),
                        "bk_host_id": p["bk_host_id"],
                        "bk_cloud_id": p.get("bk_cloud_id", 0),
                        "bk_supplier_id": 0,
                        "bk_biz_id": p["bk_biz_id"],
                    }
                )
    if not proxies:
        logger.error(f"云区域({bk_cloud_id})下无可用proxy节点，相关pingserver服务不可用")
        return

    proxies_host_ids = [p["bk_host_id"] for p in proxies]

    # 3. 根据Hash环，将同一云区域下的ip分配到不同的Proxy。
    host_info: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if not settings.metadata.enable_ping_alarm or (
        int(bk_cloud_id) == 0 and not settings.metadata.enable_direct_area_ping_collect
    ):
        # 如果关闭了PING服务，则清空目标Proxy上的任务iplist
        host_info = {p["bk_host_id"]: [] for p in proxies}
    else:
        # 如果开启了PING服务，则按hash分配给不同的server执行
        host_ring = HashRing({proxy_host_id: 1 for proxy_host_id in proxies_host_ids})
        for target in target_ips:
            ip = target["ip"]
            host_id = host_ring.get_node(ip)
            host_info[host_id].append(
                {"target_ip": ip, "target_cloud_id": target["bk_cloud_id"], "target_biz_id": target["bk_biz_id"]}
            )

    # 针对直连区域做一定处理，如果关闭直连区域的PING采集，则清空目标Proxy上的任务iplist
    if int(bk_cloud_id) == 0 and not settings.metadata.enable_direct_area_ping_collect:
        host_info = {p["bk_host_id"]: [] for p in proxies}

    # 4. 通过节点管理订阅任务将分配好的ip下发到机器
    try:
        PingServerSubscriptionConfig.create_subscription(
            bk_tenant_id, bk_cloud_id, host_info, target_hosts, plugin_name
        )
    except Exception:  # noqa
        logger.exception(
            f"下发pingserver订阅任务失败， bk_tenant_id({bk_tenant_id}), bk_cloud_id({bk_cloud_id}), proxies_ips({proxies_host_ids}), plugin({plugin_name})"
        )
