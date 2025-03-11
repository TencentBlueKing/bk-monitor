# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from collections import defaultdict
from ipaddress import IPv6Address, ip_address

from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.trace import SpanAttributes

from api.cmdb.client import list_biz_hosts
from apm_web.constants import HostAddressType
from apm_web.models import Application, CMDBServiceRelation
from apm_web.topo.handle.relation.define import (
    SourceK8sPod,
    SourceService,
    SourceSystem,
)
from apm_web.topo.handle.relation.query import RelationQ
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey
from core.drf_resource import api

logger = logging.getLogger("apm")

TIME_OUT = 60


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

    @classmethod
    @using_cache(CacheType.APM(TIME_OUT))
    def list_application_hosts(cls, bk_biz_id, app_name, service_name, start_time=None, end_time=None):
        """
        获取应用的主机列表
        主机来源:
        1. 通过CMDB服务模版关联
        2. 通过topo发现
        3. 通过关联查询
        """

        if not start_time or not end_time:
            app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if app is None:
                logger.exception(f"[HostHandler] 业务({bk_biz_id})下的app({app_name}) 不存在.")
                return []
            start_time, end_time = app.list_retention_time_range()

        global TIME_OUT
        # 使用end_time和start_time的时间差作为过期时间，保证在同个时间区间查询时，直接从缓存获取
        TIME_OUT = end_time - start_time

        # step1: 从主机发现取出 和 拓扑关联中取出主机
        def get_hosts_from_cmdb_and_topo(bk_biz_id, app_name, service_name):
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
            extra_ip_info = defaultdict(dict)
            relation_qs = []
            for path_item in [SourceSystem, SourceK8sPod]:
                relation_qs += RelationQ.generate_q(
                    bk_biz_id=bk_biz_id,
                    source_info=SourceService(
                        apm_application_name=app_name,
                        apm_service_name=service_name,
                    ),
                    target_type=SourceSystem,
                    start_time=start_time,
                    end_time=end_time,
                    path_resource=[path_item],
                )

            system_relations = RelationQ.query(relation_qs)
            for r in system_relations:
                for n in r.nodes:
                    source_info = n.source_info.to_source_info()
                    if source_info.get("bk_target_ip"):
                        query_ips.append(source_info["bk_target_ip"])
                        extra_ip_info[source_info["bk_target_ip"]]["source_type"] = cls.SourceType.RELATION

            query_host_instances = cls.list_host_by_ips(bk_biz_id, query_ips, ip_info_mapping=extra_ip_info)
            return apm_host_instances + query_host_instances

        # step2: 从关联cmdb取出主机
        def get_from_cmdb_hosts(bk_biz_id, app_name, service_name):
            relation = CMDBServiceRelation.objects.filter(
                bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
            )
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

        query_apm_host_instances = cls.list_ignore_exception(
            get_hosts_from_cmdb_and_topo, (bk_biz_id, app_name, service_name)
        )
        cmdb_host_instances = cls.list_ignore_exception(get_from_cmdb_hosts, (bk_biz_id, app_name, service_name))

        res = []
        host_ids = []
        for i in query_apm_host_instances + cmdb_host_instances:  # noqa
            if i["bk_host_id"] in host_ids:
                continue
            res.append(i)
            host_ids.append(i["bk_host_id"])
        return res

    @classmethod
    def list_ignore_exception(cls, func, params):
        pool = ThreadPool()
        result = pool.apply_async(func, params)
        try:
            query_list = result.get()
        except Exception:
            return []
        return query_list if query_list else []

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
    @using_cache(CacheType.APM(60 * 10))
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
        if response.get("count"):
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
