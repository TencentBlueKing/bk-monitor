"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from itertools import chain
import logging

from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import ApmCacheType
from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.models import HostInstance
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class HostDiscover(CachedDiscoverMixin, DiscoverBase):
    """
    Host 发现类
    使用多继承: CachedDiscoverMixin 提供缓存功能, DiscoverBase 提供基础发现功能
    """

    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    PAGE_LIMIT = 100
    DEFAULT_BK_CLOUD_ID = -1
    HOST_ID_SPLIT = ":"
    model = HostInstance

    # ========== 实现 CachedDiscoverMixin 的抽象方法 ==========

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.HOST

    @classmethod
    def _to_instance_key(cls, instance: dict) -> str:
        """从实例字典生成 host 缓存 key"""
        bk_cloud_id = instance.get("bk_cloud_id")
        bk_host_id = instance.get("bk_host_id")
        ip = instance.get("ip")
        topo_node_key = instance.get("topo_node_key")
        return cls.HOST_ID_SPLIT.join([str(bk_cloud_id), str(bk_host_id), str(ip), str(topo_node_key)])

    @staticmethod
    def _build_instance_dict(host_obj):
        """构建主机字典的辅助方法"""
        return {
            "id": CachedDiscoverMixin._get_attr_value(host_obj, "id"),
            "bk_cloud_id": CachedDiscoverMixin._get_attr_value(host_obj, "bk_cloud_id"),
            "bk_host_id": CachedDiscoverMixin._get_attr_value(host_obj, "bk_host_id"),
            "ip": CachedDiscoverMixin._get_attr_value(host_obj, "ip"),
            "topo_node_key": CachedDiscoverMixin._get_attr_value(host_obj, "topo_node_key"),
            "updated_at": CachedDiscoverMixin._get_attr_value(host_obj, "updated_at"),
        }

    def list_exists(self):
        """
        获取已存在的 host 数据
        返回元组: (查询字典, 实例数据列表)
        """
        instances = HostInstance.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        # 使用 Mixin 提供的通用方法处理重复数据
        return self._process_duplicate_records(instances)

    def discover(self, origin_data, exists_hosts):
        """
        Discover host IP if user fill resource.net.host.ip when define resource in OT SDK
        """
        find_ips = set()

        for span in origin_data:
            service_name = self.get_service_name(span)
            ip = extract_field_value((OtlpKey.RESOURCE, SpanAttributes.NET_HOST_IP), span) or extract_field_value(
                (OtlpKey.ATTRIBUTES, SpanAttributes.NET_HOST_NAME), span
            )

            if not ip or not service_name:
                continue

            find_ips.add((service_name, ip))

        # try to get bk_cloud_id if register in bk_cmdb
        cloud_id_mapping = self.list_bk_cloud_id([i[-1] for i in find_ips])
        need_update_instances = list()
        need_create_instances = set()

        for service_name, ip in find_ips:
            found_key_tuple = (*(cloud_id_mapping.get(ip, (self.DEFAULT_BK_CLOUD_ID, None))), ip, service_name)
            # 转换为字符串格式以匹配 exists_hosts 的键格式
            found_key = self.HOST_ID_SPLIT.join([str(x) for x in found_key_tuple])
            if found_key in exists_hosts:
                need_update_instances.append(exists_hosts[found_key])
            else:
                need_create_instances.add(found_key_tuple)

        created_instances = [
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
        HostInstance.objects.bulk_create(created_instances)

        # 使用抽象方法处理缓存刷新
        self.handle_cache_refresh_after_create(
            instance_data=list(exists_hosts.values()),
            need_create_instances=created_instances,
            need_update_instances=need_update_instances,
        )

    def list_bk_cloud_id(self, ips: list[str]) -> dict[str, tuple[int, int]]:
        from alarm_backends.core.cache.cmdb.host import HostManager, HostIPManager

        # 获取ip对应的host_key
        host_keys = HostIPManager.mget(bk_tenant_id=self.bk_tenant_id, ips=ips)
        if not host_keys:
            return {}

        # 获取host_key对应的host信息
        hosts = HostManager.mget(bk_tenant_id=self.bk_tenant_id, host_keys=list(chain(*host_keys.values())))

        # 返回ip对应的host信息，并且过滤掉非当前业务下的host
        return {
            host.ip: (host.bk_cloud_id, host.bk_host_id) for host in hosts.values() if host.bk_biz_id == self.bk_biz_id
        }
