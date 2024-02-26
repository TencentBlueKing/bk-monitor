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
from itertools import chain
from typing import Dict, List, Optional, Set

from django.utils.translation import ugettext as _

import settings
from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.cmdb import HostIPManager, HostManager
from alarm_backends.service.alert.enricher.base import BaseAlertEnricher
from api.cmdb.define import Host
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import api

logger = logging.getLogger("alert.enricher")


class KubernetesCMDBEnricher(BaseAlertEnricher):
    """
    kubernetes相关的告警补全IP信息
    """

    def __init__(self, alerts: List[Alert]):
        # 缓存准备，批量查询避免重复请求redis
        super(KubernetesCMDBEnricher, self).__init__(alerts)
        self.kubernetes_alerts = defaultdict(list)
        biz_source_info_list = defaultdict(list)
        self.biz_resource_info = {}
        # step1 根据维度信息通过接口获取对应的kubernetes资源信息
        self.get_kubernetes_relations(biz_source_info_list)

        # step2 根据返回的内容统一获取对应的告警IP

        # 解析出告警ip对应的ip信息
        self.alert_relations = {}
        ips = self.get_node_ips()
        # 根据ip获取对应的 ip + 云区域 的组合
        self.ip_cache = HostIPManager.multi_get_with_dict(ips)

        # 根据ip和云区域ID获取对应的主机列表（带业务特性）
        hosts = {host for host in chain(*[ips for ips in self.ip_cache.values() if ips])}
        self.hosts_cache = HostManager.multi_get_with_dict(hosts)

        # 容器场景告警和主机创建时间相近，差量同步不存在主机避免缓存刷新不及时导致维度无法正常补充的问题
        try:
            self.refresh_host_by_increment()
        except Exception:  # noqa
            logger.exception(
                "[KubernetesCMDBEnricher][refresh_by_increment] alerts(%s) error but skip",
                ",".join([alert.id for alert in self.alerts]),
            )

    def refresh_host_by_increment(self):

        total_host_keys: Set[str] = set(self.hosts_cache.keys())
        to_be_refresh_ips_gby_biz_id: Dict[int, Set[str]] = defaultdict(set)
        for alert in self.alerts:
            bk_biz_id: int = int(alert.bk_biz_id)
            if bk_biz_id <= 0:
                continue

            if alert.id not in self.alert_relations:
                continue

            ip_list: List[str] = self.alert_relations[alert.id]["ip_list"]
            for ip in ip_list:
                host_keys: Optional[List[str]] = self.ip_cache.get(ip)
                if not host_keys:
                    # 主机 IP - Host Keys 缓存不存在
                    to_be_refresh_ips_gby_biz_id[bk_biz_id].add(ip)
                elif not set(host_keys) & total_host_keys:
                    # Host Keys 匹配不到任何主机
                    to_be_refresh_ips_gby_biz_id[bk_biz_id].add(ip)

        if not to_be_refresh_ips_gby_biz_id:
            return

        logger.info(
            "[KubernetesCMDBEnricher][refresh_by_increment] alerts(%s) start: to_be_refresh_ips_gby_biz_id -> %s",
            ",".join([alert.id for alert in self.alerts]),
            to_be_refresh_ips_gby_biz_id,
        )

        for bk_biz_id, to_be_refresh_ips in to_be_refresh_ips_gby_biz_id.items():

            try:
                partial_hosts: List = api.cmdb.get_host_by_ip(
                    ips=[{"ip": ip} for ip in to_be_refresh_ips], bk_biz_id=bk_biz_id
                )
                HostManager.fill_attr_to_hosts(bk_biz_id, partial_hosts, with_world_ids=False)
            except Exception:  # noqa
                # 单个业务的更新失败可以不影响整体，记录异常并跳过
                logger.exception(
                    "[KubernetesCMDBEnricher][refresh_by_increment] "
                    "alerts(%s) failed to sync biz(%s)'s ip(%s) but skip.",
                    ",".join([alert.id for alert in self.alerts]),
                    bk_biz_id,
                    to_be_refresh_ips,
                )
                continue

            partial_host_key__obj_map: Dict[str, Host] = HostManager.to_kv(partial_hosts)

            # 补充到主机缓存
            self.hosts_cache.update(partial_host_key__obj_map)
            # 补充 IP - IP Keys 缓存
            partial_host_keys_gby_ip: Dict[str, List[str]] = HostIPManager.to_kv(list(partial_host_key__obj_map.keys()))
            # 不同业务可能存在同 IP 不同管控区域主机的场景
            # 采取在原有基础上合并列表更新的方式，避免上述场景下导致同 IP 的 Host Keys 相互覆盖
            for ip, host_keys in partial_host_keys_gby_ip.items():
                self.ip_cache[ip] = list(set(self.ip_cache.get(ip) or [] + host_keys))
            self.ip_cache.update(HostIPManager.to_kv(list(partial_host_key__obj_map.keys())))

        logger.info(
            "[KubernetesCMDBEnricher][refresh_by_increment] alerts(%s) end.",
            ",".join([alert.id for alert in self.alerts]),
        )

    def get_kubernetes_relations(self, biz_source_info_list):
        """
        获取容器关联关系
        """
        # step1 确定需要获取节点ip的告警
        biz_white_list = settings.KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST

        for alert in self.alerts:
            if not alert.is_new() or "bcs_cluster_id" not in alert.agg_dimensions:
                # 如果当前告警不是新的，不做渲染
                # bcs_cluster_id维度是补全的必要字段，所以当前字段不存在直接忽略
                continue

            if biz_white_list and alert.bk_biz_id not in biz_white_list:
                # 如果业务ID不在容器关联关系丰富白名单内, 忽略
                # 当业务白名单为空，默认全部放开
                continue

            self.kubernetes_alerts[alert.bk_biz_id].append(alert)

            # 获取origin_alarm的维度字典， 原生没有做后期丰富，的比较接近查询的内容
            source_info = alert.get_origin_alarm_dimensions()
            # 1. 容器关联本身也是一个指标，如果查询时间戳使用「首次异常时间」，时间早于「容器指标」最早可查询时间，会出现查询不到关联信息的问题
            # 2. 容器关联指标会跟随时间动态变化，unify query 根据给定时间戳往前找 5min 内第一个点，如果查询时间和 「首次异常时间」如果有较大时间差距，也可能会导致查不到关联关系
            # 3. 此处加一个偏移量用于规避指标收敛窗口周期查的问题，基于 2. 这个偏移量不能过大并且不能是未来时间
            offset = 2 * 60
            source_info["data_timestamp"] = min(int(time.time()), alert.first_anomaly_time + offset)
            biz_source_info_list[alert.bk_biz_id].append(source_info)

        # step2 确定需要获取节点ip的告警
        query_params = []
        for bk_biz_id, source_info_list in biz_source_info_list.items():
            query_params.append({"bk_biz_ids": [bk_biz_id], "source_info_list": source_info_list})

        if not query_params:
            return

        pool = ThreadPool()
        results = pool.map_ignore_exception(
            api.unify_query.get_kubernetes_relation, query_params, return_exception=True
        )
        for index, result in enumerate(results):
            bk_biz_id = query_params[index]["bk_biz_ids"][0]
            if isinstance(result, Exception):
                logger.info(
                    "alerts(%s) resource info enrich failed because "
                    "Get kubernetes resource info for biz(%s) error %s",
                    ",".join([alert.id for alert in self.kubernetes_alerts[bk_biz_id]]),
                    bk_biz_id,
                    str(result),
                )
                continue
            self.biz_resource_info[bk_biz_id] = result["data"]

    def get_node_ips(self):
        """
        通过接口返回的信息解析所有的ip
        """
        ips = []
        for bk_biz_id, biz_results in self.biz_resource_info.items():
            biz_alerts = self.kubernetes_alerts[bk_biz_id]
            for index, result in enumerate(biz_results):
                alert = biz_alerts[index]
                if result["code"] != 200 or len(result["target_list"]) == 0:
                    # 没有查到的内容，直接忽略
                    # 如果返回的ip数量为0，直接忽略
                    # 打印一条日志方便查找
                    logger.info("ignore to enrich alert(%s)'s host info  because empty result(%s)", alert.id, result)
                    continue
                # 将对应告警的信息与告警进行关联
                ip_list = [target["bk_target_ip"] for target in result["target_list"]]
                result["ip_list"] = ip_list
                self.alert_relations[alert.id] = result
                ips.extend(ip_list)
        return set(ips)

    def get_host_by_ip(self, ip):
        keys = self.ip_cache.get(ip) or []
        return [self.hosts_cache[key] for key in keys if self.hosts_cache.get(key)]

    def get_host(self, ip, bk_cloud_id):
        key = HostManager.key_to_internal_value(ip, bk_cloud_id)
        return self.hosts_cache.get(key)

    def enrich_alert(self, alert: Alert):
        if alert.id not in self.alert_relations:
            # 如果当前告警没有对应关系，直接返回
            return alert
        relation_info = self.alert_relations[alert.id]
        alert.add_dimension("target_type", relation_info["source_type"], display_key=_("目标类型"))
        alert.update_key_value_field(
            "assign_tags",
            [
                {
                    "key": "target_type",
                    "value": relation_info["source_type"],
                    "display_key": _("目标类型"),
                    "display_value": relation_info["source_type"],
                }
            ],
        )
        ip_list = relation_info["ip_list"]
        for ip in ip_list:
            host = self.get_host_info(alert, ip)
            if not host:
                # 补偿后仍获取不到主机，打印一条日志
                logger.warning(
                    "[KubernetesCMDBEnricher][enrich_alert] "
                    "ignore to enrich alert(%s) because ip(%s) not found in cache(%s)",
                    alert.id,
                    ip,
                    ("host_ip", "host")[ip in self.ip_cache],
                )
                continue
            self.enrich_host(alert, host)
            break
        return alert

    def enrich_host(self, alert, host):
        # 如果能适配到一台主机，则将其作为当前告警的主机
        topo_nodes = list({node.id for node in chain(*list(host.topo_link.values()))})
        dimensions = [
            {
                "key": "bk_host_id",
                "value": host.bk_host_id,
                "display_key": _("主机ID"),
                "display_value": host.bk_host_id,
            },
            {
                "key": "ip",
                "value": host.bk_host_innerip,
                "display_key": _("主机IP"),
                "display_value": host.bk_host_innerip,
            },
            {
                "key": "bk_cloud_id",
                "value": host.bk_cloud_id,
                "display_key": _("云区域ID"),
                "display_value": host.bk_cloud_id,
            },
            {
                "key": "bk_topo_node",
                "value": topo_nodes,
                "display_key": _("拓扑节点"),
                "display_value": ",".join(topo_nodes),
            },
        ]

        ipv6 = getattr(host, "bk_host_innerip_v6", "")
        if ipv6:
            dimensions.append(
                {
                    "key": "ipv6",
                    "value": ipv6,
                    "display_key": "ipv6",
                    "display_value": ipv6,
                }
            )
        alert.update_key_value_field("dimensions", dimensions)
        # 同时更新到assign_tags，支持前端页面查找
        alert.update_key_value_field("assign_tags", dimensions)

    def get_host_info(self, alert: Alert, ip):
        """
        根据ip信息获取告警对应的主机
        """
        host = None
        for h in self.get_host_by_ip(ip):

            # 1. 如果提供了业务ID，且主机的业务ID跟事件提供的业务ID相同，则匹配成功
            if int(alert.bk_biz_id) > 0 and h.bk_biz_id != alert.bk_biz_id:
                # 告警的业务ID 与 主机的业务ID 不一致，忽略
                continue

            if host:
                # 如果已经有一台机器匹配过了， 表示当前主机存在多个ip，那么就发生冲突，清洗失败
                logger.warning(
                    "[enrich_host] host of alert(%s) conflict for target(%s): (%s) <=> (%s)", alert.id, ip, h, host
                )
                return
            host = h
        return host
