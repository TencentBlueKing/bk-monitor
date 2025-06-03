"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections import defaultdict

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager
from alarm_backends.core.storage.redis import Cache
from api.cmdb.define import Host, TopoTree
from bkmonitor.utils.local import local
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

setattr(local, "host_cache", {})


class HostAgentIDManager:
    """
    CMDB 主机Agent缓存
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.agent_id"
        return f"{bk_tenant_id}.{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.agent_id"

    @classmethod
    def get(cls, *, bk_tenant_id: str = None, bk_agent_id: str) -> tuple[str, int]:
        """
        :rtype: tuple[str, int]
        return (bk_tenant_id, bk_host_id)
        """

        cache_key = cls.get_cache_key(bk_tenant_id)

        # 如果传入租户则只查询该租户，否则查询所有租户
        if bk_tenant_id:
            bk_tenant_ids = [bk_tenant_id]
        else:
            bk_tenant_ids = [tenant["id"] for tenant in api.bk_login.list_tenant()]

        # 遍历租户缓存
        for bk_tenant_id in bk_tenant_ids:
            result = cls.cache.hget(cache_key, bk_agent_id)

            try:
                result = int(result)
            except (ValueError, TypeError):
                continue

            if result:
                return bk_tenant_id, result

        return "", 0


class HostIPManager:
    """
    CMDB 主机IP 缓存
    缓存格式: ip -> [ip:bk_cloud_id1, ip:bk_cloud_id2, ...]
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        return f"{bk_tenant_id}.{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.host_ip"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, ips: list[str], skip_empty: bool = False) -> dict[str, list[str]]:
        cache_key = cls.get_cache_key(bk_tenant_id)
        result = cls.cache.hmget(cache_key, ips)
        return {ip: json.loads(result) if result else [] for ip, result in zip(ips, result) if result or not skip_empty}

    @classmethod
    def to_kv(cls, host_keys: list[str] | None = None) -> dict[str, list[str]]:
        """
        将主机key列表转换为ip到key列表的映射
        """
        host_keys_gby_ip: dict[str, set[str]] = defaultdict(set)
        if host_keys is None:
            host_keys = HostManager.keys()

        for host_key in host_keys:
            if not host_key:
                continue

            ip_or_host_id = host_key.split("|")[0]

            if not ip_or_host_id:
                continue

            host_keys_gby_ip[ip_or_host_id].add(host_key)

        return {ip: list(partial_host_keys) for ip, partial_host_keys in host_keys_gby_ip.items()}


class HostManager:
    """
    CMDB 主机缓存
    """

    cache = Cache("cache-cmdb")

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.host"
        return f"{bk_tenant_id}.{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.host"

    @classmethod
    def get_host_key(cls, ip: str, bk_cloud_id: int) -> str:
        return f"{ip}|{bk_cloud_id}"

    @classmethod
    def _get(cls, *, bk_tenant_id: str, ip: str, bk_cloud_id: int) -> Host | None:
        """
        获取主机信息
        :param bk_tenant_id: 租户ID
        :param ip: 主机IP
        :param bk_cloud_id: 云区域ID
        :return: 主机信息
        """
        host_key = cls.get_host_key(ip, bk_cloud_id)
        cache_key = cls.get_cache_key(bk_tenant_id)
        host = cls.cache.hget(cache_key, host_key)
        if not host:
            return None
        return Host(**json.loads(host))

    @classmethod
    def get(
        cls, *, bk_tenant_id: str, ip: str, bk_cloud_id: int = 0, using_mem: bool = False, using_api: bool = False
    ) -> Host | None:
        """
        :rtype: Host
        """
        if not (using_mem or using_api):
            return cls._get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)

        host_key = cls.get_host_key(ip, bk_cloud_id)
        if using_mem:
            # 如果使用本地内存，那么在逻辑结束后，需要调用clear_mem_cache函数清理
            host = local.host_cache.get(host_key, None)
            if host is not None:
                return host

        host = cls._get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)
        if host is None and using_api:
            # 打印日志以便查看穿透请求情况
            cls.logger.info("[HostManager] get host(%s) by api start", host_key)
            try:
                host_page = api.cmdb.get_host_without_biz_v2(ips=[ip], bk_cloud_id=[bk_cloud_id], limit=1)
                host = Host(host_page["hosts"][0])
                cls.fill_attr_to_hosts(host.bk_biz_id, [host])
            except IndexError:
                cls.logger.info("[HostManager] get host(%s) by api failed: empty data", host_key)
            except Exception as e:  # noqa
                cls.logger.info("[HostManager] get host(%s) by api failed: err -> %s", host_key, str(e))

        if using_mem and host:
            local.host_cache[host_key] = host
        return host

    @classmethod
    def get_by_agent_id(cls, *, bk_tenant_id: str = None, bk_agent_id: str) -> Host | None:
        if not bk_agent_id:
            return None

        # 根据AgentID获取主机ID
        bk_tenant_id, bk_host_id = HostAgentIDManager.get(bk_tenant_id=bk_tenant_id, bk_agent_id=bk_agent_id)
        if not bk_host_id:
            return None

        # 根据主机ID获取主机信息
        host = cls.get_by_id(bk_host_id, bk_tenant_id=bk_tenant_id)
        if host and getattr(host, "bk_agent_id", "") == bk_agent_id:
            return host

    @classmethod
    def get_by_id(cls, *, bk_tenant_id: str, bk_host_id: int, using_mem=False) -> Host | None:
        """
        :rtype: Host
        """
        bk_host_id = str(bk_host_id)

        # 尝试从本地缓存中获取
        if using_mem:
            host = local.host_cache.get(bk_host_id, None)
            if host:
                return host

        # 尝试使用bk_host_id获取主机信息
        cache_key = cls.get_cache_key(bk_tenant_id)
        host = cls.cache.hget(cache_key, bk_host_id)
        if not host:
            return None

        host = Host(**json.loads(host))
        # 本地缓存主机信息
        if using_mem:
            local.host_cache[bk_host_id] = host

        return host

    @classmethod
    def fill_attr_to_hosts(cls, bk_biz_id: int, hosts: list[Host], with_world_ids: bool = False):
        topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
        topo_link_dict: dict[str, list] = topo_tree.convert_to_topo_link()
        biz_sets: list = []
        if with_world_ids:
            biz_sets: list = api.cmdb.get_set(bk_biz_id=bk_biz_id)

        for host in hosts:
            host.topo_link = {}
            for module_id in host.bk_module_ids:
                key = f"module|{module_id}"
                host.topo_link[key] = topo_link_dict.get(key, [])
            host.bk_world_ids = []

            for biz_set in biz_sets:
                if biz_set.bk_inst_id in host.bk_set_ids and hasattr(biz_set, "bk_world_id"):
                    host.bk_world_ids.append(biz_set.bk_world_id)
            host.bk_world_id = host.bk_world_ids[0] if host.bk_world_ids else ""

    @classmethod
    def to_kv(cls, hosts: list[Host], contains_host_id_key: bool = False) -> dict[str, Host]:
        """
        将主机列表转换为字典
        """
        host_key__obj_map: dict[str, Host] = {}
        for host in hosts:
            host_key__obj_map[cls.get_host_key(host.bk_host_innerip, host.bk_cloud_id)] = host
            if contains_host_id_key:
                host_key__obj_map[str(host.bk_host_id)] = host
        return host_key__obj_map
