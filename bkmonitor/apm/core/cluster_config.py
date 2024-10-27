# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import base64
import functools
import logging

from django.conf import settings

from alarm_backends.core.storage.redis import Cache
from bkmonitor.utils.bcs import BcsKubeClient
from constants.apm import BkCollectorComp

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
            namespace=ClusterConfig.bk_collector_namespace(self.cluster_id),
        )
        if deploy:
            # 将集群添加进缓存中 由 apm.tasks 中定时任务来继续执行
            self.cache.sadd(BkCollectorComp.CACHE_KEY_CLUSTER_IDS, self._generate_value)
            logger.info(f"[BkCollectorInstaller] add {self.cluster_id} to cache")

    @classmethod
    def generator(cls):
        # 避免重复创建连接
        cache = Cache("cache")
        while True:
            yield functools.partial(cls, cache=cache)

    @property
    def _generate_value(self):
        related_bk_biz_id_str = ','.join(map(str, self.related_bk_biz_ids))
        return f"{self.cluster_id}:{related_bk_biz_id_str}"


class ClusterConfig:
    @classmethod
    def get_cluster_mapping(cls):
        """获取由 apm_ebpf 模块发现的集群 id"""
        cache = Cache("cache")
        with cache.pipeline() as p:
            p.smembers(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)
            p.delete(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)
            values = p.execute()
        cluster_to_bk_biz_ids = values[0]

        res = {}
        for i in cluster_to_bk_biz_ids:
            cluster_id, related_bk_biz_ids = cls._split_value(i)
            if cluster_id and related_bk_biz_ids:
                res[cluster_id] = related_bk_biz_ids

        return res

    @classmethod
    def bk_collector_namespace(cls, cluster_id):
        cluster_namespace = settings.K8S_OPERATOR_DEPLOY_NAMESPACE or {}
        return cluster_namespace.get(cluster_id, BkCollectorComp.NAMESPACE)

    @classmethod
    def platform_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=cls.bk_collector_namespace(cluster_id),
            label_selector="component=bk-collector,template=true,type=platform",
        )
        if len(config_maps.items) == 0:
            return None

        content = config_maps.items[0].data.get(BkCollectorComp.CONFIG_MAP_PLATFORM_TPL_NAME)
        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[ClusterConfig] parse platform_config_tpl failed: cluster({cluster_id}), error({e})")

    @classmethod
    def application_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=cls.bk_collector_namespace(cluster_id),
            label_selector="component=bk-collector,template=true,type=subconfig",
        )
        if len(config_maps.items) == 0:
            return None

        content = config_maps.items[0].data.get(BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME)
        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[ClusterConfig] parse application_config_tpl failed: cluster({cluster_id}), error({e})")

    @classmethod
    def _split_value(cls, value):
        c = value.split(":")
        if len(c) != 2:
            return None, None
        return c[0], c[1].split(",")
