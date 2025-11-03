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
from collections import defaultdict
from typing import cast

from api.cmdb.define import Host, Set, TopoTree
from bkmonitor.utils.local import local
from core.drf_resource import api

from .base import CMDBCacheManager

setattr(local, "host_cache", {})

logger = logging.getLogger(__name__)


class HostAgentIDManager(CMDBCacheManager):
    """
    CMDB 主机Agent缓存
    """

    cache_type = "agent_id"

    @classmethod
    def get(cls, *, bk_tenant_id: str, bk_agent_id: str, **kwargs) -> int | None:
        """
        根据AgentID获取主机ID
        :param bk_tenant_id: 租户ID
        :param bk_agent_id: 主机AgentID
        :return: 主机ID
        """
        result: str | None = cast(str | None, cls.cache.hget(cls.get_cache_key(bk_tenant_id), bk_agent_id))
        if not result:
            return None

        try:
            return int(result)
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_without_tenant(cls, *, bk_agent_id: str) -> tuple[str, int]:
        """
        根据AgentID获取主机ID（不指定租户）
        :param bk_agent_id: 主机AgentID
        :return: 租户ID, 主机ID
        """
        # 查询租户列表
        bk_tenant_ids: list[str] = [tenant["id"] for tenant in api.bk_login.list_tenant()]

        # 查询所有租户缓存
        pipeline = cls.cache.pipeline()
        for bk_tenant_id in bk_tenant_ids:
            pipeline.hget(cls.get_cache_key(bk_tenant_id), bk_agent_id)
        results = pipeline.execute()

        # 返回第一个匹配的租户ID和主机ID
        for bk_tenant_id, result in zip(bk_tenant_ids, results):
            if not result:
                continue

            try:
                return bk_tenant_id, int(result)
            except (ValueError, TypeError):
                continue

        return "", 0


class HostIPManager(CMDBCacheManager):
    """
    CMDB 主机IP 缓存
    缓存格式: ip -> [ip:bk_cloud_id1, ip:bk_cloud_id2, ...]
    """

    cache_type = "host_ip"

    @classmethod
    def mget(cls, *, bk_tenant_id: str, ips: list[str]) -> dict[str, list[str]]:
        if not ips:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        result: list[str | None] = cast(list[str | None], cls.cache.hmget(cache_key, ips))
        return {ip: json.loads(result) if result else [] for ip, result in zip(ips, result) if result}

    @classmethod
    def to_kv(cls, host_keys: list[str]) -> dict[str, list[str]]:
        """
        将主机key列表转换为ip到key列表的映射
        """
        host_keys_gby_ip: dict[str, set[str]] = defaultdict(set)
        for host_key in host_keys:
            if not host_key:
                continue

            ip_or_host_id = host_key.split("|")[0]

            if not ip_or_host_id:
                continue

            host_keys_gby_ip[ip_or_host_id].add(host_key)

        return {ip: list(partial_host_keys) for ip, partial_host_keys in host_keys_gby_ip.items()}


class HostManager(CMDBCacheManager):
    """
    CMDB 主机缓存
    """

    cache_type = "host"

    @classmethod
    def get_host_key(cls, ip: str, bk_cloud_id: int | str) -> str:
        return f"{ip}|{bk_cloud_id}"

    @classmethod
    def all(cls, *, bk_tenant_id: str) -> list[Host]:
        result: dict[str, str] = cast(dict[str, str], cls.cache.hgetall(cls.get_cache_key(bk_tenant_id)))
        return [Host(**json.loads(host)) for host in result.values()]

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
        host = cast(str | None, cls.cache.hget(cache_key, host_key))
        if not host:
            return None
        return Host(**json.loads(host))

    @classmethod
    def get(
        cls,
        *,
        bk_tenant_id: str,
        ip: str,
        bk_cloud_id: int = 0,
        using_mem: bool = False,
        using_api: bool = False,
        **kwargs,
    ) -> Host | None:
        """
        :rtype: Host
        """
        if not ip:
            return None

        if not (using_mem or using_api):
            return cls._get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)

        host_key = cls.get_host_key(ip, bk_cloud_id)
        cache_key = f"{cls.get_cache_key(bk_tenant_id=bk_tenant_id)}.{host_key}"
        if using_mem:
            # 如果使用本地内存，那么在逻辑结束后，需要调用clear_mem_cache函数清理
            host = local.host_cache.get(cache_key, None)
            if host is not None:
                return host

        host = cls._get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id)
        if host is None and using_api:
            # 打印日志以便查看穿透请求情况
            logger.info("[HostManager] get host(%s) by api start", host_key)
            try:
                host_page = api.cmdb.get_host_without_biz_v2(ips=[ip], bk_cloud_id=[bk_cloud_id], limit=1)
                host = Host(host_page["hosts"][0])
                cls.fill_attr_to_hosts(host.bk_biz_id, [host])
            except IndexError:
                logger.info("[HostManager] get host(%s) by api failed: empty data", host_key)
            except Exception as e:  # noqa
                logger.info("[HostManager] get host(%s) by api failed: err -> %s", host_key, str(e))

        if using_mem and host:
            local.host_cache[cache_key] = host
        return host

    @classmethod
    def mget(cls, *, bk_tenant_id: str, host_keys: list[str]) -> dict[str, Host]:
        """
        批量获取主机信息
        """
        if not host_keys:
            return {}

        cache_key = cls.get_cache_key(bk_tenant_id)
        result: list[str | None] = cast(list[str | None], cls.cache.hmget(cache_key, host_keys))
        return {host_key: Host(**json.loads(r)) for host_key, r in zip(host_keys, result) if r}

    @classmethod
    def get_by_agent_id(cls, *, bk_tenant_id: str, bk_agent_id: str) -> Host | None:
        if not bk_agent_id:
            return None

        # 根据AgentID获取主机ID
        bk_host_id = HostAgentIDManager.get(bk_tenant_id=bk_tenant_id, bk_agent_id=bk_agent_id)
        if not bk_host_id:
            return None

        # 根据主机ID获取主机信息
        host = cls.get_by_id(bk_tenant_id=bk_tenant_id, bk_host_id=bk_host_id)
        if host and getattr(host, "bk_agent_id", "") == bk_agent_id:
            return host

    @classmethod
    def get_by_id(cls, *, bk_tenant_id: str, bk_host_id: int | str | None, using_mem=False) -> Host | None:
        """
        :rtype: Host
        """
        if not bk_host_id:
            return None

        bk_host_id = str(bk_host_id)

        # 尝试从本地缓存中获取
        if using_mem:
            host: Host | None = local.host_cache.get(bk_host_id, None)
            if host:
                return host

        # 尝试使用bk_host_id获取主机信息
        cache_key = cls.get_cache_key(bk_tenant_id)
        host_str: str | None = cast(str | None, cls.cache.hget(cache_key, bk_host_id))
        if not host_str:
            return None

        host_dict: dict = json.loads(host_str)
        host_dict["bk_tenant_id"] = bk_tenant_id
        host = Host(**host_dict)

        # 本地缓存主机信息
        if using_mem:
            local.host_cache[bk_host_id] = host

        return host

    @classmethod
    def fill_attr_to_hosts(cls, bk_biz_id: int, hosts: list[Host], with_world_ids: bool = False):
        topo_tree: TopoTree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
        topo_link_dict: dict[str, list] = topo_tree.convert_to_topo_link()
        biz_sets: list[Set] = []
        if with_world_ids:
            biz_sets = api.cmdb.get_set(bk_biz_id=bk_biz_id)

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

    @classmethod
    def refresh_by_biz(cls, bk_tenant_id: str, bk_biz_id: int) -> dict[str, Host]:
        hosts: list[Host] = api.cmdb.get_host_by_topo_node(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        cls.fill_attr_to_hosts(bk_biz_id, hosts, with_world_ids=True)
        # 返回主机key到主机对象的映射
        return {HostManager.get_host_key(host.bk_host_innerip, host.bk_cloud_id): host for host in hosts}
