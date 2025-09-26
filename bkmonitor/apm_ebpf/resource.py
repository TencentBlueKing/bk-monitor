# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging

import requests
from rest_framework import serializers
from six.moves.urllib.parse import urljoin

from apm_ebpf.handlers.deepflow import DeepflowHandler
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource
from core.errors.api import BKAPIError

logger = logging.getLogger("apm_ebpf")


class TraceQueryResource(Resource):
    """
    查询eBPF数据
    """

    method = "POST"
    path = "/v1/query/"

    class RequestSerializer(serializers.Serializer):
        trace_id = serializers.CharField(label="TraceID", max_length=255, required=False)
        sql = serializers.CharField(label="sql语句", max_length=5000)
        db = serializers.CharField(label="查询数据库", max_length=50)
        bk_biz_id = serializers.IntegerField(label="业务id")

    @classmethod
    def build_param(cls, params):
        sql = params["sql"]
        if params.get("trace_id"):
            sql += " WHERE trace_id = '{}' ".format(params.get("trace_id"))
        return {"db": params["db"], "sql": sql}

    @classmethod
    def query_ebpf_data(cls, base_url, params):
        url = urljoin(base_url, cls.path.format(**params))
        requests_params = {"method": cls.method, "url": url, "json": params}
        r = requests.request(timeout=60, **requests_params)
        result = r.status_code in [200]
        if not result:
            raise BKAPIError(system_name="deep-flow", url=url, result=r.text)

        # 数据解析
        response = r.json()
        result = response.get("result", {})
        values = result.get("values", [])
        columns = result.get("columns", [])
        if not values or not columns:
            return []
        ebpf_data = [{columns[idx]: value for idx, value in enumerate(row)} for row in values]
        return ebpf_data

    @classmethod
    def batch_query_ebpf(cls, deep_flow_server_base_urls: list, params: dict):
        def inner(base_url, ebpf_param):
            return cls.query_ebpf_data(base_url, ebpf_param)

        futures = []
        pool = ThreadPool()
        for url in deep_flow_server_base_urls:
            futures.append(pool.apply_async(inner, args=(url, params)))

        ebpf_data = []
        for future in futures:
            try:
                ebpf_data.extend(future.get())
            except Exception as e:
                logger.info("batch_query_ebpf, {}".format(e))
        return ebpf_data

    def perform_request(self, params):
        query_params = self.build_param(params)
        deep_flow_server_base_urls = list(DeepflowHandler(params["bk_biz_id"]).server_addresses.values())
        return self.batch_query_ebpf(deep_flow_server_base_urls, query_params)


class AppServiceQueryResource(Resource):
    """
    查询 deepflow 集群信息-app_service 信息映射
    """

    method = "POST"
    path = "/v1/query/"

    @classmethod
    def batch_query_deepflow_service(
        cls, deepflow_server_clusters: dict, deepflow_server_clusters_mapping: dict, params: dict
    ):
        def inner(base_url, ebpf_param):
            # 借用 TraceQueryResource 封装的用于请求 deepflow server 的方法
            return TraceQueryResource.query_ebpf_data(base_url, ebpf_param)

        futures = {}
        pool = ThreadPool()

        # 遍历集群信息列表
        for cluster_id in deepflow_server_clusters.keys():
            # 获取对应的 server 地址
            base_url = deepflow_server_clusters_mapping.get(cluster_id)
            if base_url:
                # 如果找到了对应的 base_url，则创建异步请求
                futures[cluster_id] = pool.apply_async(inner, args=(base_url, params))
            else:
                logger.info(f"No base URL found for cluster ID: {cluster_id}")

        serivce_data = []
        # 批量查询使用字典来保存最后结果 因为需要得到映射关系
        for cluster_id, future in futures.items():
            try:
                services_list = future.get()
                cluster_service = {}
                # 需要将 deepflow 的查询结果伪装成 application 的格式
                cluster_service["application_id"] = "epbf-" + cluster_id
                cluster_service["bk_biz_id"] = params["bk_biz_id"]
                cluster_name = deepflow_server_clusters.get(cluster_id).get("clusterName", "")
                cluster_service["app_name"] = "epbf-" + cluster_name
                cluster_service["app_alias"] = "epbf-" + cluster_name
                cluster_service["description"] = deepflow_server_clusters.get(cluster_id).get("description", "")
                services = []
                for app_service in services_list:
                    service = {"name": app_service.get("app_service", "")}
                    services.append(service)
                cluster_service["services"] = services
                serivce_data.append(cluster_service)
            except Exception as e:
                logger.error(f"batch_query_deepflow error, cluster ID {cluster_id}, {e}")
        return serivce_data

    def perform_request(self, params):
        deepflow_server_info = DeepflowHandler(params["bk_biz_id"])
        deepflow_server_clusters = list(deepflow_server_info._clusters)
        deepflow_server_clusters = {cluster["clusterID"]: cluster for cluster in deepflow_server_clusters}
        deepflow_server_clusters_mapping = deepflow_server_info.app_addresses
        # 根据集群列表和集群 - deepflow-server 地址映射关系 查询对应的 app_service 层级关系对应为 集群 -> app_service

        return self.batch_query_deepflow_service(deepflow_server_clusters, deepflow_server_clusters_mapping, params)


class DeepFlowProfileQueryResource(Resource):
    """
    查询 deepflow profile 数据
    """

    method = "POST"
    path = "/v1/profile/ProfileTracing"

    @classmethod
    def query_profile_data(cls, base_url, params):
        url = urljoin(base_url, cls.path.format(**params))
        requests_params = {"method": cls.method, "url": url, "json": params}
        r = requests.request(timeout=60, **requests_params)
        result = r.status_code in [200]
        if not result:
            raise BKAPIError(system_name="deepflow", url=url, result=r.text)

        # 数据解析 profile data 是平铺的列表结果
        response = r.json()
        results = response.get("result", [])
        return results

    def perform_request(self, params):
        """
        向目标 deepflow server 请求对应的 profile 数据
        """
        deepflow_server_info = DeepflowHandler(params["bk_biz_id"])
        deepflow_server_clusters_mapping = deepflow_server_info.app_addresses
        deepflow_server_addr = deepflow_server_clusters_mapping.get(params["cluster_id"], "")
        if not deepflow_server_addr:
            return []
        return self.query_profile_data(deepflow_server_addr, params)
