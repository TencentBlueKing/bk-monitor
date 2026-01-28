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
import time
from datetime import datetime

import pytz
from opentelemetry.semconv.trace import SpanAttributes

from apm.core.discover.base import DiscoverBase, extract_field_value
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.models import HostInstance
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class HostDiscover(DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    PAGE_LIMIT = 100
    DEFAULT_BK_CLOUD_ID = -1
    HOST_ID_SPLIT = ":"
    model = HostInstance

    @classmethod
    def to_host_key(cls, object_pk_id, bk_cloud_id, bk_host_id, ip):
        """生成 host 缓存 key"""
        return cls.HOST_ID_SPLIT.join([str(object_pk_id), str(bk_cloud_id), str(bk_host_id), str(ip)])

    @classmethod
    def to_id_and_key(cls, hosts: list) -> tuple[set, set]:
        """
        数据提取转化
        :param hosts: host 实例列表
        :return: (ids, keys)
        """
        ids, keys = set(), set()
        for host in hosts:
            host_id = host.get("id")
            host_key = cls.to_host_key(host_id, host.get("bk_cloud_id"), host.get("bk_host_id"), host.get("ip"))
            keys.add(host_key)
            ids.add(host_id)
        return ids, keys

    @classmethod
    def merge_data(cls, hosts: list, cache_data: dict) -> list:
        """
        更新 updated_at 字段
        :param hosts: host 数据
        :param cache_data: 缓存数据
        :return: 合并后的数据
        """
        merge_data = []
        for host in hosts:
            key = cls.to_host_key(host.get("id"), host.get("bk_cloud_id"), host.get("bk_host_id"), host.get("ip"))
            if key in cache_data:
                host["updated_at"] = datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(host)
        return merge_data

    def host_clear_if_overflow(self, hosts: list) -> tuple[list, list]:
        """
        数据量大于100000时, 清除数据
        :param hosts: host 数据
        :return: (删除的数据, 保留的数据)
        """
        overflow_delete_data = []
        count = len(hosts)
        if count > self.MAX_COUNT:
            delete_count = count - self.MAX_COUNT
            # 按照updated_at排序，从小到大
            hosts.sort(key=lambda item: item.get("updated_at"))
            overflow_delete_data = hosts[:delete_count]
            remain_host_data = hosts[delete_count:]
        else:
            remain_host_data = hosts
        return overflow_delete_data, remain_host_data

    def host_clear_expired(self, hosts: list) -> tuple[list, list]:
        """
        清除过期数据
        :param hosts: host 数据
        :return: (过期的数据, 保留的数据)
        """
        # mysql 中的 updated_at 时间字段, 它的时区是 UTC, 跟数据库保持一致
        from datetime import timedelta

        boundary = datetime.now(tz=pytz.UTC) - timedelta(days=self.application.trace_datasource.retention)
        # 按照时间进行过滤
        expired_delete_data = []
        remain_host_data = []
        for host in hosts:
            if host.get("updated_at") <= boundary:
                expired_delete_data.append(host)
            else:
                remain_host_data.append(host)
        return expired_delete_data, remain_host_data

    def list_exists(self):
        res = {}
        instances = HostInstance.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for i in instances:
            res.setdefault((i.bk_cloud_id, i.bk_host_id, i.ip, i.topo_node_key), set()).add(i.id)

        return res

    def query_cache_and_host_data(self) -> tuple[dict, list]:
        """
        缓存数据及 host 数据查询
        :return: (cache_data, host_data)
        """
        # 查询应用下的缓存数据
        name = ApmCacheHandler.get_host_cache_key(self.bk_biz_id, self.app_name)
        cache_data = ApmCacheHandler().get_cache_data(name)

        # 查询应用下的 host 数据
        filter_params = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name}
        host_data = list(
            HostInstance.objects.filter(**filter_params).values("id", "bk_cloud_id", "bk_host_id", "ip", "updated_at")
        )

        return cache_data, host_data

    def clear_data(self, cache_data: dict, host_data: list) -> set:
        """
        数据清除
        :param cache_data: 缓存数据
        :param host_data: mysql 数据
        :return: 需要删除的 host keys
        """
        merge_data = self.merge_data(host_data, cache_data)
        # 过期数据
        expired_delete_data, remain_host_data = self.host_clear_expired(merge_data)
        # 超量数据
        overflow_delete_data, remain_host_data = self.host_clear_if_overflow(remain_host_data)
        delete_data = expired_delete_data + overflow_delete_data

        delete_ids, delete_keys = self.to_id_and_key(delete_data)
        if delete_ids:
            self.model.objects.filter(pk__in=delete_ids).delete()

        return delete_keys

    def refresh_cache_data(
        self,
        old_cache_data: dict,
        create_host_keys: set,
        update_host_keys: set,
        delete_host_keys: set,
    ):
        """
        刷新缓存数据
        :param old_cache_data: 旧的缓存数据
        :param create_host_keys: 新创建的 host keys
        :param update_host_keys: 更新的 host keys
        :param delete_host_keys: 删除的 host keys
        """
        from apm.constants import DEFAULT_HOST_EXPIRE

        now = int(time.time())
        old_cache_data.update({i: now for i in (create_host_keys | update_host_keys)})
        cache_data = {i: old_cache_data[i] for i in (set(old_cache_data.keys()) - delete_host_keys)}
        name = ApmCacheHandler.get_host_cache_key(self.bk_biz_id, self.app_name)
        ApmCacheHandler().refresh_data(name, cache_data, DEFAULT_HOST_EXPIRE)

    def get_remain_data(self):
        return self.list_exists()

    def discover_with_remain_data(self, origin_data, remain_data):
        """
        Discover host IP if user fill resource.net.host.ip when define resource in OT SDK
        """
        exists_hosts = remain_data
        self._do_discover(exists_hosts, origin_data)

    def discover(self, origin_data):
        """
        Discover host IP if user fill resource.net.host.ip when define resource in OT SDK
        """
        exists_hosts = self.list_exists()
        self._do_discover(exists_hosts, origin_data)

    def _do_discover(self, exists_hosts, origin_data):
        find_ips = set()

        for span in origin_data:
            service_name = self.get_service_name(span)
            ip = extract_field_value((OtlpKey.RESOURCE, SpanAttributes.NET_HOST_IP), span)

            if not ip or not service_name:
                continue

            find_ips.add((service_name, ip))

        # try to get bk_cloud_id if register in bk_cmdb
        cloud_id_mapping = self.list_bk_cloud_id([i[-1] for i in find_ips])
        need_update_host_ids = set()
        need_create_hosts = set()

        for service_name, ip in find_ips:
            found_key = (*(cloud_id_mapping.get(ip, (self.DEFAULT_BK_CLOUD_ID, None))), ip, service_name)
            if found_key in exists_hosts:
                need_update_host_ids |= exists_hosts[found_key]
            else:
                need_create_hosts.add(found_key)

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
                for i in need_create_hosts
            ]
        )

        # query cache data and database data(with object_pk_id)
        cache_data, host_data = self.query_cache_and_host_data()

        # delete database data
        delete_host_keys = self.clear_data(cache_data, host_data)

        # refresh cache data
        # 找出新创建的 host 对应的 keys
        create_host_dict = {(h[0], h[1], h[2]): h for h in need_create_hosts}
        create_host_data = [
            h for h in host_data if (h.get("bk_cloud_id"), h.get("bk_host_id"), h.get("ip")) in create_host_dict
        ]
        _, create_host_keys = self.to_id_and_key(create_host_data)

        # 找出更新的 host 对应的 keys
        update_host_data = [h for h in host_data if h.get("id") in need_update_host_ids]
        _, update_host_keys = self.to_id_and_key(update_host_data)

        self.refresh_cache_data(
            old_cache_data=cache_data,
            create_host_keys=create_host_keys,
            update_host_keys=update_host_keys,
            delete_host_keys=delete_host_keys,
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
