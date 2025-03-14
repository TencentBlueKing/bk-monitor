# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from collections import defaultdict

from django.conf import settings

from alarm_backends.management.hashring import HashRing
from bkmonitor.commons.tools import is_ipv6_biz
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.prometheus import metrics
from metadata.models.custom_report.subscription_config import get_proxy_host_ids
from metadata.models.ping_server import PingServerSubscriptionConfig
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED

logger = logging.getLogger("metadata")


def refresh_ping_server_2_node_man():
    """
    刷新Ping Server配置至节点管理，下发ip列表到proxy机器
    """

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_ping_server_2_node_man", status=TASK_STARTED, process_target=None
    ).inc()
    # 兼容下发proxy
    start_time = time.time()
    logger.info("start refresh ping server to node man")
    refresh_ping_conf("bkmonitorproxy")
    refresh_ping_conf("bk-collector")
    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_ping_server_2_node_man", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="refresh_ping_server_2_node_man", process_target=None
    ).observe(cost_time)
    metrics.report_all()
    logger.info("end refresh ping server to node man, cost time: %s" % cost_time)


def refresh_ping_conf(plugin_name="bkmonitorproxy"):
    """
    刷新Ping Server的ip列表配置

    1. 获取CMDB下的所有主机ip
    2. 获取云区域下的所有ProxyIP
    3. 根据Hash环，将同一云区域下的ip分配到不同的Proxy
    4. 通过节点管理订阅任务将分配好的ip下发到机器
    """
    if not settings.ENABLE_PING_ALARM:
        PingServerSubscriptionConfig.create_subscription(0, {}, [], plugin_name)
        for tenant in api.bk_login.get_tenant():
            for cloud_area in api.cmdb.search_cloud_area(bk_tenant_id=tenant["id"]):
                if cloud_area["bk_cloud_id"] == 0:
                    continue
                PingServerSubscriptionConfig.create_subscription(cloud_area["bk_cloud_id"], {}, [], plugin_name)
        return

    # metadata模块不应该引入alarm_backends下的文件，这里通过函数内引用，避免循环引用问题
    from alarm_backends.core.cache.cmdb.host import HostManager

    # 1. 获取CMDB下的所有主机ip
    try:
        all_hosts = HostManager.all()
    except Exception:  # noqa
        logger.exception("CMDB的主机缓存获取失败。获取不到主机，有可能会导致pingserver不执行")
        return

    exists_host_ids = set()
    cloud_to_hosts = defaultdict(list)
    for h in all_hosts:
        ip = h.bk_host_innerip_v6 if is_ipv6_biz(h.bk_biz_id) else h.bk_host_innerip
        if h.ignore_monitoring or not ip or h.bk_host_id in exists_host_ids:
            continue
        cloud_to_hosts[h.bk_cloud_id].append(
            {"ip": ip, "bk_cloud_id": h.bk_cloud_id, "bk_biz_id": h.bk_biz_id, "bk_host_id": h.bk_host_id}
        )
        exists_host_ids.add(h.bk_host_id)

    del all_hosts

    # 2. 获取云区域下的所有ProxyIP
    for bk_cloud_id, target_ips in cloud_to_hosts.items():
        if int(bk_cloud_id) == 0:
            bk_host_ids = []
            hosts = api.cmdb.get_host_without_biz(
                ips=settings.CUSTOM_REPORT_DEFAULT_PROXY_IP, bk_tenant_id=DEFAULT_TENANT_ID
            )["hosts"]
            proxies = [{"bk_host_id": host.bk_host_id} for host in hosts]
            bk_host_ids.extend([host["bk_host_id"] for host in hosts])
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
                proxy_list = api.node_man.get_proxies(bk_cloud_id=bk_cloud_id)
                proxies = []
                target_hosts = []
                for p in proxy_list:
                    if p["status"] != "RUNNING":
                        logger.warning(
                            "proxy({}) can not be use with pingserver, it's not running".format(p["inner_ip"])
                        )
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
            except Exception:  # noqa
                logger.exception("从节点管理获取云区域({})下的ProxyIP列表失败".format(bk_cloud_id))
                continue
        if not proxies:
            logger.error("云区域({})下无可用proxy节点，相关pingserver服务不可用".format(bk_cloud_id))
            continue
        proxies_host_ids = [p["bk_host_id"] for p in proxies]

        # 3. 根据Hash环，将同一云区域下的ip分配到不同的Proxy。
        proxies_host_ids = get_proxy_host_ids(proxies_host_ids) if plugin_name == "bkmonitorproxy" else proxies_host_ids
        if not proxies_host_ids:
            logger.info(f"云区域({bk_cloud_id})下无可用proxy插件[{plugin_name}]，暂不下发")
            continue
        proxies_host_id_map = {proxy_host_id: 1 for proxy_host_id in proxies_host_ids}
        host_info = defaultdict(list)
        if settings.ENABLE_PING_ALARM:
            # 如果开启了PING服务，则按hash分配给不同的server执行
            host_ring = HashRing(proxies_host_id_map)
            for target in target_ips:
                ip = target["ip"]
                host_id = host_ring.get_node(ip)
                host_info[host_id].append(
                    {"target_ip": ip, "target_cloud_id": target["bk_cloud_id"], "target_biz_id": target["bk_biz_id"]}
                )
        else:
            # 如果关闭了PING服务，则清空目标Proxy上的任务iplist
            host_info = {p["bk_host_id"]: [] for p in proxies}

        # 针对直连区域做一定处理，如果关闭直连区域的PING采集，则清空目标Proxy上的任务iplist
        if int(bk_cloud_id) == 0 and not settings.ENABLE_DIRECT_AREA_PING_COLLECT:
            host_info = {p["bk_host_id"]: [] for p in proxies}

        # 4. 通过节点管理订阅任务将分配好的ip下发到机器
        try:
            PingServerSubscriptionConfig.create_subscription(bk_cloud_id, host_info, target_hosts, plugin_name)
        except Exception:  # noqa
            logger.exception(
                "下发pingserver订阅任务失败，bk_cloud_id({}), proxies_ips({}), plugin({})".format(
                    bk_cloud_id, proxies_host_ids, plugin_name
                )
            )
