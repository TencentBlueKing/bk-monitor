"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from datetime import datetime

from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.models import HostInstance
from bkmonitor.utils.common_utils import safe_int
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
        from alarm_backends.core.cache.cmdb.host import HostManager

        host_keys = HostManager.cache.hget(HostManager.get_biz_cache_key(), str(self.bk_biz_id))
        if host_keys is None:
            return {}

        try:
            host_keys = json.loads(host_keys) or []
        except Exception:  # pylint: disable=broad-except
            return {}

        ip_to_host_key = {}
        for host_key in host_keys:
            if not host_key:
                continue

            split_keys = host_key.split("|")
            if len(split_keys) == 2:
                ip_to_host_key[split_keys[0]] = safe_int(split_keys[1], 0)

        ret = {}
        for ip in ips:
            if ip in ip_to_host_key:
                bk_cloud_id = ip_to_host_key[ip]
                host = HostManager.get(ip, bk_cloud_id)
                ret[ip] = (bk_cloud_id, host.bk_host_id)

        return ret
