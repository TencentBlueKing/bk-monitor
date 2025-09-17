"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import logging

from alarm_backends.core.storage.redis import Cache
from bkmonitor.utils.bcs import BcsKubeClient
from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig
from constants.bk_collector import BkCollectorComp

logger = logging.getLogger("apm")


class BkCollectorInstaller:
    def __init__(self, cache, cluster_id, related_bk_biz_ids):
        self.cluster_id = cluster_id
        self.bcs_client = BcsKubeClient(self.cluster_id)
        self.cache = cache
        self.related_bk_biz_ids = related_bk_biz_ids

    def check_installed(self):
        """
        检查集群是否安装了 bk-collector
        """
        deploy = self.bcs_client.client_request(
            self.bcs_client.api.read_namespaced_deployment,
            name=BkCollectorComp.DEPLOYMENT_NAME,
            namespace=BkCollectorClusterConfig.bk_collector_namespace(self.cluster_id),
        )
        if deploy:
            # 将集群添加进缓存中 由 apm.tasks 中定时任务来继续执行
            self.cache.sadd(BkCollectorComp.CACHE_KEY_CLUSTER_IDS, self._generate_value)
            logger.info(f"[BkCollectorInstaller] add {self.cluster_id} to cache")

    @classmethod
    def generator(cls):
        # 避免重复创建连接
        # fixme: 优化缓存, 考虑使用metadata的redis
        # from metadata.utils.redis_tools import RedisTools
        # cache = RedisTools().client
        cache = Cache("cache")
        while True:
            yield functools.partial(cls, cache=cache)

    @property
    def _generate_value(self):
        related_bk_biz_id_str = ",".join(map(str, self.related_bk_biz_ids))
        return f"{self.cluster_id}:{related_bk_biz_id_str}"
