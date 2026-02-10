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
from apm.core.discover.instance_data import HostInstanceData
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

    @classmethod
    def _get_cache_type(cls) -> str:
        """获取缓存类型"""
        return ApmCacheType.HOST

    @classmethod
    def to_cache_key(cls, instance: HostInstanceData) -> str:
        """从实例数据对象生成 host 缓存 key"""
        return cls.HOST_ID_SPLIT.join(map(str, cls._to_found_key(instance)))

    @classmethod
    def build_instance_data(cls, host_obj) -> HostInstanceData:
        return HostInstanceData(
            id=DiscoverBase.get_attr_value(host_obj, "id"),
            bk_cloud_id=DiscoverBase.get_attr_value(host_obj, "bk_cloud_id"),
            bk_host_id=DiscoverBase.get_attr_value(host_obj, "bk_host_id"),
            ip=DiscoverBase.get_attr_value(host_obj, "ip"),
            topo_node_key=DiscoverBase.get_attr_value(host_obj, "topo_node_key"),
            updated_at=DiscoverBase.get_attr_value(host_obj, "updated_at"),
        )

    @classmethod
    def _to_found_key(cls, instance_data: HostInstanceData) -> tuple:
        """从实例数据对象生成业务唯一标识（不包含数据库ID）用于在 discover 过程中匹配已存在的实例"""
        return instance_data.bk_cloud_id, instance_data.bk_host_id, instance_data.ip, instance_data.topo_node_key

    def get_remain_data(self):
        instances = self.model.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        return self.process_duplicate_records(instances, True)

    def discover(self, origin_data, exists_hosts: dict[tuple, HostInstanceData]):
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
            found_key = (*(cloud_id_mapping.get(ip, (self.DEFAULT_BK_CLOUD_ID, None))), ip, service_name)
            if found_key in exists_hosts:
                need_update_instances.append(exists_hosts[found_key])
            else:
                need_create_instances.add(found_key)

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
            existing_instances=list(exists_hosts.values()),
            created_db_instances=created_instances,
            updated_instances=need_update_instances,
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
