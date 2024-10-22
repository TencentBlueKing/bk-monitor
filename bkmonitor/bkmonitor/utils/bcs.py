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

import abc
import concurrent
import logging
from urllib.parse import urljoin

import six
from django.conf import settings
from django.utils.functional import cached_property
from kubernetes import client

from core.drf_resource.contrib.api import APIResource

logger = logging.getLogger(__name__)


class BcsApiGatewayBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    def get_headers(self):
        headers = super(BcsApiGatewayBaseResource, self).get_headers()
        headers["Authorization"] = f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"
        return headers


class BcsKubeClient:
    """
    通过 BCS 集群 ID，构造一个类似 k8s 的 client
    """

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

    def client_request(self, client_api, **kwargs):
        """
        带超时时间的请求
        """

        with concurrent.futures.ThreadPoolExecutor() as executor:
            try:
                response = executor.submit(client_api, **kwargs)
                return response.result(self._REQUEST_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"[BcsKubeClient] "
                    f"{client_api.__name__} of cluster_id: {self.cluster_id}(params: {kwargs}) timeout"
                )
            except client.ApiException as e:
                status = getattr(e, "status")
                if status == 404:
                    logger.warning(
                        f"[BcsKubeClient] "
                        f"{client_api.__name__} of cluster_id: {self.cluster_id}(params: {kwargs}) 404"
                    )
                elif status == 403:
                    logger.warning(
                        f"[BcsKubeClient] "
                        f"{client_api.__name__} of cluster_id: {self.cluster_id}(params: {kwargs}) forbidden"
                    )
                else:
                    logger.error(
                        f"[BcsKubeClient] failed to {client_api.__name__} "
                        f"of cluster_id: {self.cluster_id}(params: {kwargs}), error: {e}"
                    )
