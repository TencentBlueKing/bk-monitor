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


from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from api.cmdb.define import ServiceInstance
from core.drf_resource import api


class ServiceInstanceManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 服务实例缓存
    """

    type = "service_instance"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.service_instance"
    HOST_TO_SERVICE_INSTANCE_ID_CACHE_KEY = "{prefix}.cmdb.host_to_service_instance_id".format(
        prefix=CMDBCacheManager.CACHE_KEY_PREFIX
    )
    ObjectClass = ServiceInstance

    @classmethod
    def key_to_internal_value(cls, service_instance_id):
        return str(service_instance_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        return int(origin_key)

    @classmethod
    def get(cls, service_instance_id):
        """
        :param service_instance_id: 服务实例ID
        :rtype: ServiceInstance
        """
        return super().get(service_instance_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        instances = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id)  # type: list[ServiceInstance]
        topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)  # type: TopoTree
        # 填充拓扑链
        topo_link_dict = topo_tree.convert_to_topo_link()
        host_to_service_instance = defaultdict(list)

        for instance in instances:
            key = f"module|{instance.bk_module_id}"
            instance.topo_link = {key: topo_link_dict.get(key, [])}

            # 从缓存中补全主机IP信息
            host = HostManager.get_by_id(instance.bk_host_id)
            if host:
                host_to_service_instance[str(host.bk_host_id)].append(instance.service_instance_id)
                instance.ip = host.ip
                instance.bk_cloud_id = host.bk_cloud_id

        for host_id, service_instance_ids in host_to_service_instance.items():
            cls.cache.hset(cls.HOST_TO_SERVICE_INSTANCE_ID_CACHE_KEY, host_id, json.dumps(service_instance_ids))
        cls.cache.expire(cls.HOST_TO_SERVICE_INSTANCE_ID_CACHE_KEY, cls.CACHE_TIMEOUT)
        return {cls.key_to_internal_value(instance.service_instance_id): instance for instance in instances}

    @classmethod
    def get_service_instance_id_by_host(cls, bk_host_id):
        """
        获取主机下的服务实例id列表
        """
        result = cls.cache.hget(cls.HOST_TO_SERVICE_INSTANCE_ID_CACHE_KEY, str(bk_host_id)) or "[]"
        service_instance_ids = json.loads(result)
        return service_instance_ids
