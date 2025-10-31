"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import defaultdict
from itertools import chain

from alarm_backends.core.alert import Event
from alarm_backends.core.cache.cmdb import (
    HostIPManager,
    HostManager,
    ServiceInstanceManager,
)
from alarm_backends.service.alert.enricher.base import BaseEventEnricher
from api.cmdb.define import Host, ServiceInstance
from constants.alert import EventTargetType

logger = logging.getLogger("alert.enricher")


class CMDBEnricher(BaseEventEnricher):
    def __init__(self, events: list[Event]):
        super().__init__(events)

        # 缓存准备，批量查询避免重复请求redis，按租户分组
        tenant_ips: dict[str, set[str]] = defaultdict(set)
        tenant_hosts: dict[str, set[str]] = defaultdict(set)
        tenant_service_instance_ids: dict[str, set[int]] = defaultdict(set)

        for event in self.events:
            if not event.target:
                continue

            if event.target_type == EventTargetType.HOST:
                ip_with_cloud_id = event.target.split("|")
                if not ip_with_cloud_id[0]:
                    continue
                if len(ip_with_cloud_id) == 1:
                    # 如果缺少云区域信息，后续会使用IP进行查询
                    tenant_ips[event.bk_tenant_id].add(ip_with_cloud_id[0])
                else:
                    tenant_hosts[event.bk_tenant_id].add(f"{ip_with_cloud_id[0]}|{ip_with_cloud_id[1]}")
            elif event.target_type == EventTargetType.SERVICE:
                tenant_service_instance_ids[event.bk_tenant_id].add(int(event.target))

        # 根据IP获取IP+云区域ID
        self.ip_cache: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for bk_tenant_id, ips in tenant_ips.items():
            self.ip_cache[bk_tenant_id] = HostIPManager.mget(bk_tenant_id=bk_tenant_id, ips=list(ips))

        # 根据服务实例ID获取服务实例
        self.service_instance_cache: dict[str, dict[int, ServiceInstance]] = {}
        for bk_tenant_id, service_instance_ids in tenant_service_instance_ids.items():
            self.service_instance_cache[bk_tenant_id] = ServiceInstanceManager.mget(
                bk_tenant_id=bk_tenant_id, service_instance_ids=list(service_instance_ids)
            )

        # 根据IP+云区域ID获取主机
        self.hosts_cache: dict[str, dict[str, Host]] = defaultdict(dict)
        for bk_tenant_id in set(tenant_hosts.keys()) | set(self.ip_cache.keys()):
            hosts = list(tenant_hosts.get(bk_tenant_id, [])) + [
                host for host in chain(*list(self.ip_cache[bk_tenant_id].values()))
            ]
            self.hosts_cache[bk_tenant_id] = HostManager.mget(bk_tenant_id=bk_tenant_id, host_keys=hosts)

    def get_host_by_ip(self, bk_tenant_id: str, ip: str):
        keys = self.ip_cache.get(bk_tenant_id, {}).get(ip) or []
        return list({self.hosts_cache[bk_tenant_id][key] for key in keys if self.hosts_cache[bk_tenant_id].get(key)})

    def get_host(self, bk_tenant_id: str, ip: str, bk_cloud_id: int):
        return self.hosts_cache[bk_tenant_id].get(f"{ip}|{bk_cloud_id}")

    def get_service_instance(self, bk_tenant_id: str, service_instance_id: str):
        try:
            _service_instance_id = int(service_instance_id)
        except (ValueError, TypeError):
            return None

        return self.service_instance_cache[bk_tenant_id].get(_service_instance_id)

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
            host = HostManager.get_by_id(bk_tenant_id=event.bk_tenant_id, bk_host_id=bk_host_id)
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
            target_hosts = self.get_host_by_ip(event.bk_tenant_id, ip)
            if len(target_hosts) == 1:
                # 0. 如果 ip 下只有一台机器，则直接匹配成功
                host = target_hosts[0]
            else:
                for h in target_hosts:
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
            host = self.get_host(bk_tenant_id=event.bk_tenant_id, ip=ip, bk_cloud_id=int(bk_cloud_id))

        # 主机信息找不到
        if not host:
            logger.warning("[enrich_host] host not found for event(%s) target(%s)", event.id, event.target)
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
        instance = self.get_service_instance(event.bk_tenant_id, event.target)

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
