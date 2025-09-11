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
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

from alarm_backends.core.cache.cmdb.host import HostManager
from api.cmdb.define import ServiceInstance, TopoTree
from core.drf_resource import api

from .base import CMDBCacheManager


class ServiceInstanceManager(CMDBCacheManager):
    """
    CMDB 服务实例缓存
    """

    cache_type = "service_instance"

    @classmethod
    def get_host_to_service_instance_id_cache_key(cls, bk_tenant_id: str) -> str:
        return f"{cls._get_cache_key_prefix(bk_tenant_id)}.host_to_service_instance_id"

    @classmethod
    def get(cls, *, bk_tenant_id: str, service_instance_id: str | int, **kwargs) -> ServiceInstance | None:
        """
        获取单个服务实例
        :param bk_tenant_id: 租户ID
        :param service_instance_id: 服务实例ID
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, str(service_instance_id)))
        if not result:
            return None
        return ServiceInstance(**json.loads(result))

    @classmethod
    def mget(cls, *, bk_tenant_id: str, service_instance_ids: Sequence[int]) -> dict[int, ServiceInstance]:
        """
        批量获取服务实例
        :param bk_tenant_id: 租户ID
        :param service_instance_ids: 服务实例ID列表
        """
        service_instance_id_list: list[str] = list(
            str(service_instance_id) for service_instance_id in service_instance_ids
        )

        if not service_instance_id_list:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        results: list[str | None] = cast(
            list[str | None],
            cls.cache.hmget(cache_key, service_instance_id_list),
        )
        return {
            service_instance_id: ServiceInstance(**json.loads(result))
            for service_instance_id, result in zip(service_instance_ids, results)
            if result
        }

    @classmethod
    def get_service_instance_id_by_host(cls, *, bk_tenant_id: str, bk_host_id: int) -> list[int]:
        """
        获取主机下的服务实例id列表
        :param bk_tenant_id: 租户ID
        :param bk_host_id: 主机ID
        """
        cache_key = cls.get_host_to_service_instance_id_cache_key(bk_tenant_id)
        result = cast(str | None, cls.cache.hget(cache_key, str(bk_host_id)))
        if not result:
            return []
        return [int(service_instance_id) for service_instance_id in json.loads(result)]

    @classmethod
    def refresh_by_biz(cls, *, bk_tenant_id: str, bk_biz_id: int) -> list[ServiceInstance]:
        """
        按业务ID刷新缓存
        """
        instances: list[ServiceInstance] = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id)
        topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)

        # 填充拓扑链
        topo_link_dict = topo_tree.convert_to_topo_link()
        host_to_service_instance = defaultdict(list)

        for instance in instances:
            key = f"module|{instance.bk_module_id}"
            instance.topo_link = {key: topo_link_dict.get(key, [])}

            # 从缓存中补全主机IP信息
            host = HostManager.get_by_id(bk_tenant_id=bk_tenant_id, bk_host_id=instance.bk_host_id)
            if host:
                host_to_service_instance[str(host.bk_host_id)].append(instance.service_instance_id)
                instance.ip = host.ip  # type: ignore
                instance.bk_cloud_id = host.bk_cloud_id  # type: ignore

        # 刷新服务实例缓存
        cache_key = cls.get_cache_key(bk_tenant_id)
        pipeline = cls.cache.pipeline()
        for i in range(0, len(instances), 1000):
            pipeline.hmset(
                cache_key,
                {
                    str(instance.service_instance_id): json.dumps(instance.to_dict(), ensure_ascii=False)
                    for instance in instances[i : i + 1000]
                },
            )
        pipeline.execute()

        # 刷新主机与服务实例的映射关系
        cache_key = cls.get_host_to_service_instance_id_cache_key(bk_tenant_id)
        pipeline = cls.cache.pipeline()
        for host_id, service_instance_ids in host_to_service_instance.items():
            pipeline.hset(cache_key, host_id, json.dumps(service_instance_ids))
        pipeline.execute()

        return instances
