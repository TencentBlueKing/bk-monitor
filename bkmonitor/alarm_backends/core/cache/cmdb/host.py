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

import json
from typing import List

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from api.cmdb.define import Host, TopoTree
from bkmonitor.utils.local import local
from core.drf_resource import api

setattr(local, "host_cache", {})


class HostIDManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 主机ID 缓存
    """

    type = "host_id"
    CACHE_KEY = "{prefix}.cmdb.host_id".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)
    AGENT_CACHE_KEY = "{prefix}.cmdb.agent_host_id".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)

    @classmethod
    def serialize(cls, obj):
        """
        序列化数据
        """
        return obj

    @classmethod
    def deserialize(cls, string):
        """
        反序列化数据
        """
        return string

    @classmethod
    def key_to_internal_value(cls, bk_host_id):
        return "{}".format(bk_host_id)

    @classmethod
    def get(cls, bk_host_id):
        """
        :rtype: str
        """
        return super(HostIDManager, cls).get(bk_host_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        hosts: List[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
        return {
            cls.key_to_internal_value(host.bk_host_id): "{}|{}".format(
                host.bk_host_innerip or host.bk_host_innerip_v6, host.bk_cloud_id
            )
            for host in hosts
        }


class HostAgentIDManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 主机Agent缓存
    """

    type = "agent_id"
    CACHE_KEY = "{prefix}.cmdb.agent_id".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)

    @classmethod
    def key_to_internal_value(cls, bk_host_id):
        return "{}".format(bk_host_id)

    @classmethod
    def get(cls, bk_agent_id):
        """
        :rtype: str
        """
        return super(HostAgentIDManager, cls).get(bk_agent_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        hosts: List[Host] = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
        return {cls.key_to_internal_value(host.bk_agent_id): host.bk_host_id for host in hosts if host.bk_agent_id}


class HostIPManager(CMDBCacheManager):
    """
    CMDB 主机IP 缓存
    """

    type = "host_ip"
    CACHE_KEY = "{prefix}.cmdb.host_ip".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)

    @classmethod
    def serialize(cls, obj):
        return json.dumps(obj or [])

    @classmethod
    def deserialize(cls, string):
        if not string:
            return []
        return json.loads(string)

    @classmethod
    def key_to_internal_value(cls, ip):
        return "{}".format(ip)

    @classmethod
    def get(cls, ip):
        return super(HostIPManager, cls).get(ip)

    @classmethod
    def refresh(cls, host_keys: List[str] = None):
        """
        刷新缓存
        """
        cls.logger.info("refresh host ip data started.")

        # IP对应的可选云区域列表
        # {
        #   "10.0.0.1": ["10.0.0.1|0", "10.0.0.1|1"],
        #   "10.0.0.2": ["10.0.0.2|0"]
        # }
        ip_mapping = {}

        if host_keys is None:
            host_keys = HostManager.keys()

        for host in host_keys:
            if not host:
                continue
            ip = host.split("|")[0]

            if not ip:
                continue

            ip_mapping.setdefault(ip, set()).add(host)

        old_keys = cls.cache.hkeys(cls.CACHE_KEY)
        deleted_keys = set(old_keys) - set(ip_mapping.keys())
        if deleted_keys:
            cls.cache.hdel(cls.CACHE_KEY, *deleted_keys)

        if ip_mapping:
            ip_result = {}
            for index, ip in enumerate(ip_mapping):
                ip_result[ip] = json.dumps(list(ip_mapping[ip]))
                if index % 1000 == 0:
                    cls.cache.hmset(cls.CACHE_KEY, ip_result)
                    ip_result = {}

            if ip_result:
                cls.cache.hmset(cls.CACHE_KEY, ip_result)

        cls.cache.expire(cls.CACHE_KEY, cls.CACHE_TIMEOUT)

        cls.logger.info(
            "cache_key({}) refresh CMDB data finished, amount: updated: {}, removed: {}".format(
                cls.CACHE_KEY, len(ip_mapping), len(deleted_keys)
            )
        )


class HostManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 主机缓存
    """

    type = "host"
    CACHE_KEY = "{prefix}.cmdb.host".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)

    @classmethod
    def key_to_internal_value(cls, ip, bk_cloud_id=0):
        return "{}|{}".format(ip, bk_cloud_id)

    @classmethod
    def get(cls, ip, bk_cloud_id=0, using_mem=False):
        """
        :rtype: Host
        """
        if not using_mem:
            return super(HostManager, cls).get(ip, bk_cloud_id)
        # 如果使用本地内存，那么在逻辑结束后，需要调用clear_mem_cache函数清理
        host_id = f"{ip}|{bk_cloud_id}"
        host = local.host_cache.get(host_id, None)
        if host is None:
            host = cls.get(ip, bk_cloud_id)
            if host is not None:
                local.host_cache[host_id] = host
        return host

    @classmethod
    def get_by_agent_id(cls, bk_agent_id):
        bk_host_id = HostAgentIDManager.get(bk_agent_id)
        if not bk_host_id:
            return None
        return cls.get_by_id(bk_host_id)

    @classmethod
    def get_by_id(cls, bk_host_id, using_mem=False):
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
        host = cls.cache.hget(cls.CACHE_KEY, bk_host_id)
        if not host:
            # 如果没有获取到主机信息，则尝试使用ip获取主机信息
            host_key = HostIDManager.get(bk_host_id)
            if not host_key:
                return
            ip, bk_cloud_id = host_key.split("|")
            host = HostManager.get(ip, bk_cloud_id, using_mem=using_mem)

            if not host:
                return
        else:
            host = cls.deserialize(host)

        # 本地缓存主机信息
        if using_mem:
            local.host_cache[bk_host_id] = host

        return host

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        hosts = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)  # type: list[Host]
        topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)  # type: TopoTree
        biz_sets = api.cmdb.get_set(bk_biz_id=bk_biz_id)
        # 填充拓扑链
        topo_link_dict = topo_tree.convert_to_topo_link()
        for host in hosts:
            host.topo_link = {}
            for module_id in host.bk_module_ids:
                key = "module|{}".format(module_id)
                host.topo_link[key] = topo_link_dict.get(key, [])
            host.bk_world_ids = []
            for biz_set in biz_sets:
                if biz_set.bk_inst_id in host.bk_set_ids and hasattr(biz_set, "bk_world_id"):
                    host.bk_world_ids.append(biz_set.bk_world_id)
            host.bk_world_id = host.bk_world_ids[0] if host.bk_world_ids else ""

        result = {}
        for host in hosts:
            result[cls.key_to_internal_value(host.bk_host_innerip, host.bk_cloud_id)] = host
            result[str(host.bk_host_id)] = host
        return result


def main():
    HostIDManager.refresh()
    HostManager.refresh()
    HostIPManager.refresh()
    HostAgentIDManager.refresh()
