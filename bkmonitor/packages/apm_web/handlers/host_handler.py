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
import time
from collections import defaultdict
from ipaddress import IPv6Address, ip_address

from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.trace import SpanAttributes

from api.cmdb.client import list_biz_hosts
from apm_web.constants import HostAddressType
from apm_web.models import CMDBServiceRelation
from apm_web.topo.handle.relation.define import (
    SourceK8sPod,
    SourceService,
    SourceServiceInstance,
    SourceSystem,
)
from apm_web.topo.handle.relation.query import RelationQ
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey
from core.drf_resource import api

logger = logging.getLogger("apm")


class HostHandler:
    class SourceType:
        """主机来源类型"""

        CMDB_RELATION = "cmdb_relation"
        TOPO = "topo"
        RELATION = "relation"
        FIELD = "field"

        @classmethod
        def get_label(cls, key):
            return {
                cls.CMDB_RELATION: _("通过服务模版 - CMDB 模版集关联"),
                cls.TOPO: _("通过上报数据发现"),
                cls.RELATION: _("通过上报数据发现"),
                cls.FIELD: _("通过 Span 中包含 IP 字段发现"),
            }.get(key, key)

    PAGE_LIMIT = 100
    ONE_HOUR_SECONDS = 3600

    @classmethod
    def get_hosts_from_trace_relation(cls, bk_biz_id, app_name, service_name):
        """获取从 Trace 数据中上报的字段中发现的主机信息"""
        discover_host_instances = api.apm_api.query_host_instance(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        )

        apm_host_instances = []
        # 需要查询 CMDB 获取信息的 ip 列表
        query_ips = []
        for i in discover_host_instances:
            if not i["bk_host_id"]:
                # 兼容旧拓扑数据没有host_id情况
                query_ips.append(i["ip"])
            else:
                apm_host_instances.append(
                    {
                        "bk_host_innerip": i["ip"],
                        "bk_cloud_id": str(i["bk_cloud_id"]),
                        "bk_host_id": str(i["bk_host_id"]),
                        "source_type": cls.SourceType.TOPO,
                    }
                )
        query_host_instances = cls.list_host_by_ips(bk_biz_id, query_ips)
        return apm_host_instances + query_host_instances

    @classmethod
    def get_hosts_from_service_relation(cls, bk_biz_id, app_name, service_name):
        """获取从 用户配置的服务关联 CMDB 服务模板"""
        relation = CMDBServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        cmdb_host_instances = []
        if relation:
            response = batch_request(
                api.cmdb.find_host_by_service_template,
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_service_template_ids": [relation.first().template_id],
                    "fields": ["bk_host_innerip", "bk_cloud_id", "bk_host_id", "bk_host_innerip_v6"],
                },
            )
            if response:
                for item in response:
                    if item["bk_host_innerip"]:
                        ip = item["bk_host_innerip"].split(",")[0]
                        cmdb_host_instances.append(
                            {
                                "bk_host_innerip": ip,
                                "bk_cloud_id": str(item["bk_cloud_id"]),
                                "bk_host_id": str(item["bk_host_id"]),
                                "source_type": cls.SourceType.CMDB_RELATION,
                            }
                        )
                    elif item.get("bk_host_innerip_v6"):
                        ip = item["bk_host_innerip_v6"].split(",")[0]
                        cmdb_host_instances.append(
                            {
                                "bk_host_innerip": ip,
                                "bk_cloud_id": str(item["bk_cloud_id"]),
                                "bk_host_id": str(item["bk_host_id"]),
                                "source_type": cls.SourceType.CMDB_RELATION,
                            }
                        )
            return cmdb_host_instances

    @classmethod
    def get_hosts_from_auto_relation(cls, bk_biz_id, app_name, service_name, start_time=None, end_time=None):
        """获取通过服务自动关联POD与主机的自动关联"""
        query_ips = []
        extra_ip_info = defaultdict(dict)
        relation_qs = RelationQ.generate_q(
            bk_biz_id=bk_biz_id,
            source_info=SourceService(
                apm_application_name=app_name,
                apm_service_name=service_name,
            ),
            target_type=SourceSystem,
            start_time=start_time,
            end_time=end_time,
            path_resource=[SourceService, SourceServiceInstance, SourceSystem],
        )

        relation_qs += RelationQ.generate_q(
            bk_biz_id=bk_biz_id,
            source_info=SourceService(
                apm_application_name=app_name,
                apm_service_name=service_name,
            ),
            target_type=SourceSystem,
            start_time=start_time,
            end_time=end_time,
            path_resource=[SourceService, SourceServiceInstance, SourceK8sPod],
        )
        system_relations = RelationQ.query(relation_qs)
        for r in system_relations:
            for n in r.nodes:
                source_info = n.source_info.to_source_info()
                if source_info.get("bk_target_ip"):
                    query_ips.append(source_info["bk_target_ip"])
                    extra_ip_info[source_info["bk_target_ip"]]["source_type"] = cls.SourceType.RELATION

        return cls.list_host_by_ips(bk_biz_id, query_ips, ip_info_mapping=extra_ip_info)

    @classmethod
    def has_hosts_relation(cls, bk_biz_id, app_name, service_name, start_time=None, end_time=None):
        """
        是否存在主机关联
        """
        host_instances = (
            api.apm_api.query_host_instance(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name) or []
        )
        hosts_in_cmdb = [h for h in host_instances if h.get("bk_host_id")]
        if hosts_in_cmdb:
            return True

        if CMDBServiceRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        ).exists():
            return True

        if not start_time or not end_time:
            end_time = int(time.time())
            start_time = end_time - cls.ONE_HOUR_SECONDS
        if cls.get_hosts_from_auto_relation(bk_biz_id, app_name, service_name, start_time, end_time):
            return True

        return False

    @classmethod
    def list_application_hosts(cls, bk_biz_id, app_name, service_name, start_time=None, end_time=None):
        """
        获取应用的主机列表
        主机来源:
        1. 通过CMDB服务模版关联
        2. 通过topo发现
        3. 通过关联查询
        """

        if not start_time or not end_time:
            end_time = int(time.time())
            start_time = end_time - cls.ONE_HOUR_SECONDS

        dt_start = (start_time // 300) * 300
        dt_end = (end_time // 300) * 300
        cache_key = f"apm:{bk_biz_id}-{app_name}-{service_name}-{dt_start}-{dt_end}-list_hosts"
        hosts_cache = using_cache(CacheType.APM(60 * 5))
        res = hosts_cache.get_value(cache_key)
        if res:
            return res

        futures = []
        pool = ThreadPool()
        futures.append(pool.apply_async(cls.get_hosts_from_trace_relation, args=(bk_biz_id, app_name, service_name)))
        futures.append(pool.apply_async(cls.get_hosts_from_service_relation, args=(bk_biz_id, app_name, service_name)))
        futures.append(
            pool.apply_async(
                cls.get_hosts_from_auto_relation, args=(bk_biz_id, app_name, service_name, start_time, end_time)
            )
        )

        res = []
        host_ids = []
        for future in futures:
            try:
                result = future.get() or []
                for i in result:
                    if i["bk_host_id"] in host_ids:
                        continue
                    res.append(i)
                    host_ids.append(i["bk_host_id"])
            except Exception as e:  # pylint: disable=broad-except
                logger.info(f"batch_list_application_hosts, {e}")

        hosts_cache.set_value(cache_key, res)
        return res

    @classmethod
    def find_host_in_span(cls, bk_biz_id, app_name, span_id, span=None):
        """
        从span中寻找主机
        来源:
        1. 字段 net.host.ip
        """

        if not span:
            span = api.apm_api.query_span_detail(bk_biz_id=bk_biz_id, app_name=app_name, span_id=span_id)
        if not span:
            return []

        ip_mapping = {}
        # 尝试从 net.host.ip / host.ip 字段中找主机 IP 地址
        for f in [SpanAttributes.NET_HOST_IP, "host.ip"]:
            ip = span[OtlpKey.RESOURCE].get(f)
            if ip:
                ip_mapping[ip] = {"source_type": cls.SourceType.FIELD}
                break

        # 从容器字段中获取关联的 IP 地址
        bcs_cluster_id = span[OtlpKey.RESOURCE].get("k8s.bcs.cluster.id")
        namespace = span[OtlpKey.RESOURCE].get("k8s.namespace.name")
        pod = span[OtlpKey.RESOURCE].get("k8s.pod.name")

        if bcs_cluster_id and namespace and pod:
            # 字段齐全才查询关联数据
            system_relations = RelationQ.query(
                RelationQ.generate_q(
                    bk_biz_id=bk_biz_id,
                    source_info=SourceK8sPod(
                        bcs_cluster_id=bcs_cluster_id,
                        namespace=namespace,
                        pod=pod,
                    ),
                    target_type=SourceSystem,
                    start_time=int(span["start_time"] / 1e6),
                    end_time=int(span["end_time"] / 1e6),
                    step="1s",
                )
            )
            for r in system_relations:
                found = False
                for n in r.nodes:
                    source_info = n.source_info.to_source_info()
                    if source_info.get("bk_target_ip"):
                        ip_mapping[source_info["bk_target_ip"]] = {"source_type": cls.SourceType.RELATION}
                        found = True
                        break
                if found:
                    break

        if not ip_mapping:
            return []

        infos = cls.list_host_by_ips(bk_biz_id, list(ip_mapping.keys()), ip_mapping)
        return infos

    @classmethod
    def list_host_by_ips(cls, bk_biz_id, ips, ip_info_mapping=None):
        """根据 IP 列表请求 CMDB 获取主机信息列表"""
        if not ip_info_mapping:
            ip_info_mapping = defaultdict(dict)
        res = []
        rules = []
        for ip in ips:
            try:
                if isinstance(ip_address(ip), IPv6Address):
                    rules.append({"field": "bk_host_innerip_v6", "operator": "equal", "value": ip})
                    ip_info_mapping[ip]["address_type"] = HostAddressType.IPV6
                else:
                    rules.append({"field": "bk_host_innerip", "operator": "equal", "value": ip})
                    ip_info_mapping[ip]["address_type"] = HostAddressType.IPV4
            except ValueError:
                logger.warning(f"retrieve invalid ip: {ip}")

        if not rules:
            return res

        params = {
            "page": {"start": 0, "limit": len(ips)},
            "fields": ["bk_cloud_id", "bk_host_innerip", "bk_host_id"],
            "bk_biz_id": bk_biz_id,
            "host_property_filter": {
                "condition": "OR",
                "rules": rules,
            },
        }
        response = list_biz_hosts(params)
        if response and response.get("count"):
            for i in response["info"]:
                ip = i.get("bk_host_innerip") or i.get("bk_host_innerip_v6")
                res.append(
                    {
                        **ip_info_mapping.get(ip, {}),
                        "bk_cloud_id": i["bk_cloud_id"],
                        "bk_host_id": str(i["bk_host_id"]),
                        "bk_host_innerip": i["bk_host_innerip"],
                    }
                )
        return res
