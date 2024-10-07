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
import concurrent
import gzip
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.utils.functional import cached_property
from kubernetes import client
from kubernetes.client import ApiException

from alarm_backends.core.storage.redis import Cache
from constants.apm import BkCollectorComp

logger = logging.getLogger("apm")


class BcsKubeClient:
    # 请求超时时间
    _REQUEST_TIMEOUT = 10

    def __init__(self, cluster_id):
        self.cluster_id = cluster_id

    @property
    def auth(self):
        host = urljoin(
            f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
            f"/clusters/{self.cluster_id}",
        )
        return client.Configuration(
            host=host,
            api_key={"authorization": settings.BCS_API_GATEWAY_TOKEN},
            api_key_prefix={"authorization": "Bearer"},
        )

    @cached_property
    def api(self):
        return client.AppsV1Api(client.ApiClient(self.auth))

    @cached_property
    def core_api(self):
        return client.CoreV1Api(client.ApiClient(self.auth))

    @classmethod
    def request(cls, client_api, **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            try:
                response = executor.submit(client_api, **kwargs)
                return response.result(cls._REQUEST_TIMEOUT)
            except (concurrent.futures.TimeoutError, ApiException) as e:
                logger.error(f"[BcsKubeClient] request api: {client_api} failed(params: {kwargs}), error: {e}")


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
    def deploy_platform_config(cls, cluster_id, platform_config):
        gzip_content = gzip.compress(platform_config.encode())
        b64_content = base64.b64encode(gzip_content)
        sec = client.V1Secret(
            type="Opaque",
            metadata=client.V1ObjectMeta(
                name=BkCollectorComp.SECRET_PLATFORM_NAME,
                labels={
                    "component": "bk-collector",
                    "type": "platform",
                    "template": "false",
                },
            ),
            data={BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME: b64_content},
        )
        bcs_client = BcsKubeClient(cluster_id)
        BcsKubeClient.request(
            bcs_client.core_api.create_namespaced_secret,
            namespace=BkCollectorComp.NAMESPACE,
            body=sec,
        )

    @classmethod
    def platform_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = BcsKubeClient.request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=BkCollectorComp.NAMESPACE,
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
        config_maps = BcsKubeClient.request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=BkCollectorComp.NAMESPACE,
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
