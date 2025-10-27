"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
bcs 集群缓存管理器
"""

import json

from alarm_backends.core.cache.base import CacheManager
from core.drf_resource import api


class BcsClusterCacheManager(CacheManager):
    """
    BCS集群缓存
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".bcs_cluster_{}"

    @classmethod
    def refresh(cls):
        for tenant in api.bk_login.list_tenant():
            try:
                cluster_infos = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=tenant["id"])
            except Exception:  # noqa
                return

            pipeline = cls.cache.pipeline()
            for cluster_info in cluster_infos:
                bcs_cluster_id = cluster_info["bcs_cluster_id"]
                name = cluster_info["name"]

                data = {
                    "name": name,
                }
                cache_key = cls.CACHE_KEY_TEMPLATE.format(bcs_cluster_id)
                pipeline.set(
                    cache_key,
                    json.dumps(data),
                    cls.CACHE_TIMEOUT,
                )
            pipeline.execute()

    @classmethod
    def get(cls, bcs_cluster_id: str) -> dict | None:
        """
        获取集群信息
        """
        cache_key = cls.CACHE_KEY_TEMPLATE.format(bcs_cluster_id)
        data = cls.cache.get(cache_key)
        if data:
            return json.loads(data)


def main():
    BcsClusterCacheManager.refresh()
