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
from datetime import datetime
from ipaddress import IPv6Address, ip_address

from opentelemetry.semconv.trace import SpanAttributes

from api.cmdb.client import list_biz_hosts
from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.models import HostInstance
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class HostDiscover(DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    PAGE_LIMIT = 100
    DEFAULT_BK_CLOUD_ID = -1
    model = HostInstance

    def list_exists(self):
        res = {}
        instances = HostInstance.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for i in instances:
            res.setdefault((i.bk_cloud_id, i.bk_host_id, i.ip, i.topo_node_key), set()).add(i.id)

        return res

    def discover(self, origin_data):
        """
        Discover host IP if user fill resource.net.host.ip when define resource in OT SDK
        """
        find_ips = set()

        exists_hosts = self.list_exists()

        for span in origin_data:

            service_name = self.get_service_name(span)
            ip = extract_field_value((OtlpKey.RESOURCE, SpanAttributes.NET_HOST_IP), span)

            if not ip or not service_name:
                continue

            find_ips.add((service_name, ip))

        # try to get bk_cloud_id if register in bk_cmdb
        cloud_id_mapping = self.list_bk_cloud_id([i[-1] for i in find_ips])
        need_update_instance_ids = set()
        need_create_instances = set()

        for service_name, ip in find_ips:

            found_key = (*(cloud_id_mapping.get(ip, (self.DEFAULT_BK_CLOUD_ID, None))), ip, service_name)
            if found_key in exists_hosts:
                need_update_instance_ids |= exists_hosts[found_key]
            else:
                need_create_instances.add(found_key)

        # only update update_time
        HostInstance.objects.filter(id__in=need_update_instance_ids).update(updated_at=datetime.now())

        # create
        HostInstance.objects.bulk_create(
            [
                HostInstance(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    bk_cloud_id=i[0],
                    bk_host_id=i[1],
                    ip=i[2],
                    topo_node_key=i[3],
                )
                for i in need_create_instances
            ]
        )

        self.clear_if_overflow()
        self.clear_expired()

    def list_bk_cloud_id(self, ips):

        ipv4 = []
        ipv6 = []

        for i in ips:
            (ipv4, ipv6)[isinstance(ip_address(i), IPv6Address)].append(i)

        params = {
            "fields": ["bk_cloud_id", "bk_host_innerip", "bk_host_id"],
            "bk_biz_id": self.bk_biz_id,
            "host_property_filter": {
                "condition": "AND",
                "rules": [],
            },
        }

        ipv4_res = self._search_ips(
            params, [{"field": "bk_host_innerip", "operator": "in", "value": ipv4}], key_field="bk_host_innerip"
        )
        ipv6_res = self._search_ips(
            params, [{"field": "bk_host_innerip_v6", "operator": "in", "value": ipv6}], key_field="bk_host_innerip_v6"
        )

        return {**ipv4_res, **ipv6_res}

    def _search_ips(self, base_params, rule_extra_params, key_field):
        offset = 0
        page_params = {"start": offset, "limit": self.PAGE_LIMIT}

        base_params["page"] = page_params
        base_params["host_property_filter"]["rules"] += rule_extra_params

        result = list_biz_hosts(base_params)
        if not result or (result and result["count"] == 0):
            return {}

        res = self.convert_result(result["info"], key_field)
        count = result["count"] // self.PAGE_LIMIT
        for i in range(1, count):
            base_params["page"]["start"] = i * self.PAGE_LIMIT
            temp_result = list_biz_hosts(base_params)
            res.update(self.convert_result(temp_result["info"], key_field))

        return res

    def convert_result(self, content, key_field):
        res = {}
        for i in content:
            res[i[key_field]] = (i["bk_cloud_id"], i["bk_host_id"])

        return res
