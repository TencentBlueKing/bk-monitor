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
import concurrent
import functools

from kubernetes.client import ApiException

from apm_ebpf.apps import logger
from apm_ebpf.handlers.kube import BcsKubeClient


class Installer:
    # 请求超时时间
    _REQUEST_TIMEOUT = 10

    def __init__(self, cluster_id):
        self.cluster_id = cluster_id
        self.k8s_client = BcsKubeClient(self.cluster_id)

    def _client_request(self, client_api, **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            try:
                response = executor.submit(client_api, **kwargs)
                return response.result(self._REQUEST_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"[DeepflowInstaller] "
                    f"list deployments of cluster_id: {self.cluster_id}(params: {kwargs}) timeout"
                )
            except ApiException as e:
                status = getattr(e, "status")
                if status == 404:
                    logger.warning(
                        f"[DeepflowInstaller] "
                        f"list deployments of cluster_id: {self.cluster_id}(params: {kwargs}) 404"
                    )
                elif status == 403:
                    logger.warning(
                        f"[DeepflowInstaller] "
                        f"list deployments of cluster_id: {self.cluster_id}(params: {kwargs}) forbidden"
                    )
                else:
                    logger.error(
                        f"[DeepflowInstaller] failed to list deployments "
                        f"of cluster_id: {self.cluster_id}(params: {kwargs}), error: {e}"
                    )

    def list_deployments(self, namespace):
        """获取命名空间下的 deployment"""
        return self._client_request(self.k8s_client.api.list_namespaced_deployment, namespace=namespace)

    def list_services(self, namespace):
        """获取命名空间下的 service"""
        return self._client_request(self.k8s_client.core_api.list_namespaced_service, namespace=namespace)

    @classmethod
    def check_deployment(cls, content, required_deployment):
        """检查 deployment 中镜像名称是否和要求的一致"""
        image_name = cls._exact_image_name(content.image)
        return image_name == required_deployment

    @classmethod
    def _exact_image_name(cls, image):
        return image.split("/")[-1].split(":")[0]

    @classmethod
    def generator(cls):
        while True:
            yield functools.partial(cls)
