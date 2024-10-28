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
from itertools import chain
from typing import List

from alarm_backends.core.alert import Event
from alarm_backends.core.cache.cmdb import (
    HostIPManager,
    HostManager,
    ServiceInstanceManager,
)
from alarm_backends.service.alert.enricher.base import BaseEventEnricher
from constants.alert import EventTargetType

logger = logging.getLogger("alert.enricher")


class CMDBEnricher(BaseEventEnricher):
    def __init__(self, events: List[Event]):
        super(CMDBEnricher, self).__init__(events)

        # 缓存准备，批量查询避免重复请求redis
        ips = set()
        hosts = set()
        service_instance_ids = set()

        for event in self.events:
            if not event.target:
                continue

            if event.target_type == EventTargetType.HOST:
                ip_with_cloud_id = event.target.split("|")
                if not ip_with_cloud_id[0]:
                    continue
                if len(ip_with_cloud_id) == 1:
                    ips.add(HostIPManager.key_to_internal_value(ip_with_cloud_id[0]))
                else:
                    hosts.add(HostManager.key_to_internal_value(ip_with_cloud_id[0], ip_with_cloud_id[1]))
            elif event.target_type == EventTargetType.SERVICE:
                service_instance_ids.add(ServiceInstanceManager.key_to_internal_value(event.target))

        self.ip_cache = HostIPManager.multi_get_with_dict(ips)
        self.service_instance_cache = ServiceInstanceManager.multi_get_with_dict(service_instance_ids)

        # 加上从 ip_cache 拿到的 IP 列表
        hosts |= {host for host in chain(*[ips for ips in self.ip_cache.values() if ips])}
        self.hosts_cache = HostManager.multi_get_with_dict(hosts)

    def get_host_by_ip(self, ip):
        keys = self.ip_cache.get(HostIPManager.key_to_internal_value(ip)) or []
        return list({self.hosts_cache[key] for key in keys if self.hosts_cache.get(key)})

    def get_host(self, ip, bk_cloud_id):
        key = HostManager.key_to_internal_value(ip, bk_cloud_id)
        return self.hosts_cache.get(key)

    def get_service_instance(self, service_instance_id):
        key = ServiceInstanceManager.key_to_internal_value(service_instance_id)
        return self.service_instance_cache.get(key)

    def enrich_event(self, event: Event):
        if event.is_dropped():
            return event

        target_type = event.target_type

        if target_type == EventTargetType.HOST:
            return self.enrich_host(event)

        if target_type == EventTargetType.SERVICE:
            return self.enrich_service(event)

        if target_type == EventTargetType.TOPO:
            return self.enrich_topo(event)

        if not event.bk_biz_id:
            event.drop()

        return event

    def enrich_host(self, event: Event):
        if not event.target:
            return event

        ip_with_cloud_id = []
        # 尝试解析bk_host_id
        try:
            bk_host_id = int(event.target)
        except ValueError:
            bk_host_id = 0
            ip_with_cloud_id = event.target.split("|")

        if bk_host_id:
            host = HostManager.get_by_id(bk_host_id)
            if not host:
                ip = ""
                bk_cloud_id = 0
            else:
                ip = host.bk_host_innerip
                bk_cloud_id = host.bk_cloud_id
        elif len(ip_with_cloud_id) == 1:
            # 没有提供云区域ID的情况下，使用 IP 进行模糊匹配
            ip = ip_with_cloud_id[0]
            bk_cloud_id = 0
            host = None
            for h in self.get_host_by_ip(ip):
                if event.bk_biz_id and int(event.bk_biz_id) > 0 and h.bk_biz_id != event.bk_biz_id:
                    continue
                # 1. 如果提供了业务ID，且主机的业务ID跟事件提供的业务ID相同，则匹配成功
                # 2. 如果没有提供业务ID，则直接匹配成功
                if host:
                    # 如果已经有一台机器匹配过了，那么就发生冲突，清洗失败
                    logger.warning(
                        "[enrich_host] host(%s) conflict, multiple cloud regions exist for this IP", event.target
                    )
                    event.drop()
                    return event
                host = h
            event.set("target", f"{ip}|{bk_cloud_id}")
        else:
            # 存在IP和云区域
            ip = ip_with_cloud_id[0]
            bk_cloud_id = ip_with_cloud_id[1]
            host = self.get_host(ip, bk_cloud_id)

        # 主机信息找不到
        if not host:
            if event.bk_biz_id is None:
                # 如果事件也没有提供业务，则丢弃
                logger.warning("[enrich_host] biz is empty for host target(%s)", event.target)
                event.drop()
            return event

        # 主机不在告警业务中，先打日志记录
        if event.bk_biz_id != host.bk_biz_id:
            logger.warning("[enrich_host] ip(%s) not in biz(%s)", ip, event.bk_biz_id)
            # event.drop()
            # return event

        # 丰富主机信息
        if event.bk_biz_id is None:
            # 优先取事件提供的业务ID，没有才使用主机的
            event.set("bk_biz_id", host.bk_biz_id)

        event.set("bk_host_id", host.bk_host_id)
        event.set("ip", host.bk_host_innerip)
        event.set("ipv6", getattr(host, "bk_host_innerip_v6", ""))
        event.set("bk_cloud_id", host.bk_cloud_id)
        event.set("bk_topo_node", list({node.id for node in chain(*list(host.topo_link.values()))}))
        return event

    def enrich_service(self, event: Event):
        instance = self.get_service_instance(event.target)

        if not instance:
            if event.bk_biz_id is None:
                logger.warning("[enrich_service] biz is empty for service target(%s)", event.target)
                event.drop()
                return event

            event.set("bk_service_instance_id", event.target)
            return event

        if event.bk_biz_id is None:
            # 优先取事件提供的业务ID，没有才使用主机的
            event.set("bk_biz_id", instance.bk_biz_id)
        else:
            if event.bk_biz_id != instance.bk_biz_id:
                logger.warning(
                    "[enrich_service] instance(%s) not in biz(%s)", instance.service_instance_id, event.bk_biz_id
                )
                # event.drop()
                # return event
        event.set("target", instance.service_instance_id)
        event.set("bk_service_instance_id", instance.service_instance_id)
        event.set("bk_host_id", instance.bk_host_id)
        event.set("ip", instance.ip)
        event.set("bk_cloud_id", instance.bk_cloud_id)
        event.set("bk_topo_node", list({node.id for node in chain(*list(instance.topo_link.values()))}))
        return event

    def enrich_topo(self, event: Event):
        bk_obj_and_inst = event.target.split("|")

        if len(bk_obj_and_inst) != 2:
            logger.warning("[enrich_topo] topo target(%s) is not a valid topo node", event.target)
            event.drop()
            return event

        # TODO: 补全完成拓扑链
        event.set("bk_topo_node", [event.target])

        if event.bk_biz_id is None:
            logger.warning("[enrich_topo] biz is empty for topo target(%s)", event.target)
            event.drop()
            return event

        return event
