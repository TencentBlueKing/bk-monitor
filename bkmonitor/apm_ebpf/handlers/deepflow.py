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
import operator
from dataclasses import dataclass

import requests

from apm_ebpf.apps import logger
from apm_ebpf.constants import DeepflowComp
from apm_ebpf.handlers.kube import BcsKubeClient
from apm_ebpf.handlers.workload import WorkloadContent, WorkloadHandler
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkmonitor.utils.cache import CacheType, using_cache
from core.drf_resource import api


@dataclass
class DeepflowDatasourceInfo:
    bk_biz_id: str = None
    name: str = None
    request_url: str = None
    # tracingUrl为可选项
    tracing_url: str = None

    @property
    def is_valid(self):
        if not self.bk_biz_id or not self.name or not self.request_url:
            return False

        # 尝试访问url判断是否失效
        if self.tracing_url:
            try:
                requests.get(self.tracing_url, timeout=10)
            except requests.exceptions.RequestException:
                logger.warning(f"fail to request: {self.tracing_url} in {self.name}, tracing may be abnormal.")

        try:
            requests.get(self.request_url, timeout=10)
        except requests.exceptions.RequestException:
            logger.warning(f"fail to request: {self.request_url} in {self.name}")
            return False

        return True


class DeepflowHandler:
    _required_deployments = [
        DeepflowComp.DEPLOYMENT_SERVER,
        DeepflowComp.DEPLOYMENT_GRAFANA,
        DeepflowComp.DEPLOYMENT_APP,
    ]
    _required_services = [
        DeepflowComp.SERVICE_SERVER,
        DeepflowComp.SERVICE_GRAFANA,
        DeepflowComp.SERVICE_APP,
    ]

    _scheme = "http"

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id

    @classmethod
    def check_installed(cls, cluster_id):
        """
        检查集群是否安装了ebpf
        """

        k8s_client = BcsKubeClient(cluster_id)

        # 获取Deployment
        deployments = k8s_client.api.list_namespaced_deployment(namespace=DeepflowComp.NAMESPACE)
        for deployment in deployments.items:
            content = WorkloadContent.deployment_to(deployment)
            if content.name in cls._required_deployments:
                WorkloadHandler.upsert(cluster_id, DeepflowComp.NAMESPACE, content)

        # 获取Service
        services = k8s_client.core_api.list_namespaced_service(namespace=DeepflowComp.NAMESPACE)
        for service in services.items:
            content = WorkloadContent.service_to(service)
            if content.name in cls._required_services:
                WorkloadHandler.upsert(cluster_id, DeepflowComp.NAMESPACE, content)

    def list_datasources(self):
        """
        获取业务下可用的数据源
        """
        res = []

        deployments = WorkloadHandler.list_deployments(self.bk_biz_id, DeepflowComp.NAMESPACE)

        from apm_web.utils import group_by

        cluster_deploy_mapping = group_by(deployments, operator.attrgetter("cluster_id"))

        valid_cluster_ids = []
        # Step1: 过滤出有效的Deployment
        for cluster_id, items in cluster_deploy_mapping.items():
            cluster_deploys = [i for i in deployments if i.name in self._required_deployments]

            if len(deployments) != len(self._required_deployments):
                diff = set(self._required_deployments) - set(cluster_deploys)
                logger.warning(
                    f"there is no complete deployment in cluster: {cluster_id} of bk_biz_id: {self.bk_biz_id}"
                    f"(missing: {','.join(diff)}). this cluster will be ignored."
                )
                continue

            invalid_item = next((i for i in items if not i.is_normal), None)
            if invalid_item:
                logger.warning(f"an abnormal deployment({invalid_item.name}) was found, this cluster will be ignored.")
                continue

            valid_cluster_ids.append(cluster_id)

        # Step2: 过滤出有效的Service
        for cluster_id in valid_cluster_ids:
            services = WorkloadHandler.list_services(self.bk_biz_id, DeepflowComp.NAMESPACE, cluster_id)
            service_name_mapping = {i.name: i for i in services if i.name in self._required_services}
            if len(service_name_mapping) != len(self._required_services):
                diff = set(self._required_services) - set(service_name_mapping.keys())
                logger.warning(
                    f"there is no complete service in cluster: {cluster_id} of bk_biz_id: {self.bk_biz_id}"
                    f"(missing: {','.join(diff)}). this cluster will be ignored."
                )
                continue

            info = DeepflowDatasourceInfo(bk_biz_id=self.bk_biz_id, name=f"DeepFlow-{cluster_id}")

            for service in services:
                if service.name == DeepflowComp.SERVICE_SERVER:
                    # 从deepflow-server获取RequestUrl
                    info.request_url = self.get_server_access(cluster_id, service.content)
                if service.name == DeepflowComp.SERVICE_APP:
                    # 从deepflow-app获取TracingUrl
                    info.tracing_url = self.get_app_access(cluster_id, service.content)

            if info.is_valid:
                res.append(info)

        return res

    def _get_cluster_access_ip(self, cluster_id):
        """
        获取集群某个节点的访问IP
        """
        k8s_client = BcsKubeClient(cluster_id)
        nodes = k8s_client.core_api.list_node()

        for node in nodes.items:
            if node.status.addresses:
                for addr in node.status.addresses:
                    if addr.type == "InternalIP":
                        return addr.address

        return None

    @property
    @using_cache(CacheType.APM_EBPF(60 * 30))
    def _clusters(self):
        """
        获取业务下所有集群列表
        """
        if not self.bk_biz_id:
            logger.warning(f"unable to get cluster list because bk_biz_id is empty")
            return []

        space_info = SpaceApi.get_space_detail(bk_biz_id=self.bk_biz_id)
        space_type = space_info.space_type_id

        if space_type == SpaceTypeEnum.BKCC.value:
            params = {"businessID": self.bk_biz_id}
        elif space_type == SpaceTypeEnum.BCS.value:
            params = {"projectID": space_info.space_id}
        elif space_type == SpaceTypeEnum.BKCI.value and space_info.space_code:
            params = {"projectID": space_info.space_code}
        else:
            logger.warning(f"can not obtained cluster info from " f"bk_biz_id: {self.bk_biz_id}(type: {space_type})")
            return []

        clusters = api.bcs_cluster_manager.fetch_clusters(**params)
        logger.info(f"{len(clusters)} clusters with bk_biz_id: {self.bk_biz_id} are obtained")

        # 过滤共享集群
        return [i for i in clusters if not i["is_shared"]]

    @property
    def server_addresses(self):
        """
        获取业务下所有集群的service: deepflow-server访问地址
        """
        res = {}
        for cluster in self._clusters:
            u = self.get_server_access(cluster["clusterID"])
            if u:
                res[cluster["clusterID"]] = u

        return res

    @property
    def app_addresses(self):
        """
        获取业务下所有集群的service: deepflow-app访问地址
        """
        res = {}
        for cluster in self._clusters:
            u = self.get_app_access(cluster["clusterID"])
            if u:
                res[cluster["clusterID"]] = u

        return res

    def get_server_access(self, cluster_id, service_content=None):
        """
        获取DeepFlow-server访问地址
        """
        return self._get_access(
            cluster_id,
            service_content,
            DeepflowComp.SERVICE_SERVER,
            DeepflowComp.SERVICE_SERVER_PORT_QUERY,
        )

    def get_app_access(self, cluster_id, service_content=None):
        """
        获取DeepFlow-app访问地址
        """
        return self._get_access(
            cluster_id,
            service_content,
            DeepflowComp.SERVICE_APP,
            DeepflowComp.SERVICE_APP_PORT_QUERY,
        )

    @using_cache(CacheType.APM_EBPF(60 * 30))
    def _get_access(self, cluster_id, service_content, comp_name, port_name):
        node_ip = self._get_cluster_access_ip(cluster_id)
        if not node_ip:
            return None

        if not service_content:
            services = WorkloadHandler.list_services(self.bk_biz_id, DeepflowComp.NAMESPACE, cluster_id)
            server_service = next((i for i in services if i.name == comp_name), None)
            if not server_service:
                raise ValueError(f"业务Id: {self.bk_biz_id} 集群Id: {cluster_id}下无法找到{comp_name}服务")

            service_content = server_service.content

        port = WorkloadContent.extra_port(service_content, port_name)
        url = f"{self._scheme}://{node_ip}:{port}"

        return url
