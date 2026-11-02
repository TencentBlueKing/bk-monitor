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
from collections.abc import Sequence
from typing import cast

from api.cmdb.define import ServiceInstance
from bkmonitor.utils.local import local

from .base import CMDBCacheManager

setattr(local, "service_instance_cache", {})


class ServiceInstanceManager(CMDBCacheManager):
    """
    CMDB 服务实例缓存
    """

    cache_type = "service_instance"

    @classmethod
    def get_host_to_service_instance_id_cache_key(cls, bk_tenant_id: str) -> str:
        return f"{cls._get_cache_key_prefix(bk_tenant_id)}.host_to_service_instance_id"

    @classmethod
    def get(
        cls,
        *,
        bk_tenant_id: str,
        service_instance_id: str | int,
        using_mem: bool = False,
        **kwargs,
    ) -> ServiceInstance | None:
        """
        获取单个服务实例
        :param bk_tenant_id: 租户ID
        :param service_instance_id: 服务实例ID
        :param using_mem: 是否使用内存缓存（如果使用，需要在逻辑结束后调用clear_mem_cache清理）
        """
        cache_key = cls.get_cache_key(bk_tenant_id)
        mem_cache_key = f"{cache_key}.{service_instance_id}"

        # 如果使用内存缓存，先查询内存缓存
        if using_mem:
            instance = local.service_instance_cache.get(mem_cache_key)
            if instance is not None:
                return instance

        # 查询 Redis 缓存
        result = cast(str | None, cls.cache.hget(cache_key, str(service_instance_id)))
        if not result:
            return None

        instance = ServiceInstance(**json.loads(result))

        # 如果使用内存缓存，写入内存缓存
        if using_mem:
            local.service_instance_cache[mem_cache_key] = instance

        return instance

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
