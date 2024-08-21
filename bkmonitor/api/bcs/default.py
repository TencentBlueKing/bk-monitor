# -*- coding: utf-8 -*-


import abc
import json
import logging
from typing import List, Optional

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource.contrib.api import APIResource

logger = logging.getLogger(__name__)


class BcsBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    # 注意这里的系统名字是bcs-api，查询的方法是在https://{settings.BK_PAAS_INNER_HOST}/admin/apigw/api/查询
    # 这是apigw查询系统的方式，目前由于apigw没有页面，所以只能在这里查询
    base_url = "%s/api/apigw/bcs-api/prod/" % settings.BK_COMPONENT_API_URL
    module_name = "bcs-api"
    # backend_cache_type = CacheType.BCS
    # BCS目前是非蓝鲸标准的返回格式，所以需要兼容
    IS_STANDARD_FORMAT = False


class GetClusterApiId(BcsBaseResource):
    """
    获取集群在bcs-api的ID
    主要用于将集群ID从bcs 集群ID转换为bcs-api的集群ID
    返回数据格式: (未确认，从文档获取)
    {
     "id": "bcs-bcs-k8s-40291-xxx",  # bcs api侧的cluster id
     "provider": 2,
     "creator_id": 6430,
     "identifier": "bcs-bcs-k8s-40291-xxx-xxx",
     "created_at": "2021-03-09T15:51:56+08:00"
    }
    """

    action = "/rest/clusters/bcs/query_by_id"
    method = "GET"
    backend_cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        # 注意此处的ID是SaaS的集群ID
        cluster_id = serializers.CharField(label="集群ID")
        project_id = serializers.CharField(label="项目ID", required=False)
        access_token = serializers.CharField(label="ACCESS TOKEN", default="")


class GetClusterToken(BcsBaseResource):
    """
    获取bcs集群的认证token信息
    token信息用于供操作bcs-api（bcs模块，非apigw模块）时作为身份认证信息
    返回数据格式: (未确认，从文档获取)
    {
     "cluster_id": "bcs-bcs-k8s-40291-xxx",  # bcs api侧的cluster id
     # 连接集群时，需要添加bcs api的地址，如:原生k8s的api路径: /version/, 则需要组装为/tunnels/clusters/bcs-bcs-k8s-40291-xxx-xxx/version/
     "server_address_path": "/tunnels/clusters/bcs-bcs-k8s-40291-xxx-xxx/",
     "user_token": "xxx", # user token
     "cacert_data": "-----BEGIN CERTIFICATE-----\nxxx\n-----END CERTIFICATE-----\n"
    }
    """

    action = "/rest/clusters/{cluster_id}/client_credentials"
    method = "GET"
    backend_cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        # 注意此处的ID是bcs-api的集群ID
        cluster_id = serializers.CharField(label="集群ID")
        access_token = serializers.CharField(label="ACCESS TOKEN", default="")

    def get_request_url(self, validated_request_data):
        return super(BcsBaseResource, self).get_request_url(validated_request_data).format(**validated_request_data)


class BcsApiBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    """BCS API 网关基类"""

    base_url = settings.BCS_APIGW_BASE_URL

    module_name = "bcs-api"

    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        return super(BcsApiBaseResource, self).get_request_url(validated_request_data).format(**validated_request_data)

    def get_headers(self):
        headers = super(BcsApiBaseResource, self).get_headers()
        headers["Authorization"] = f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"
        return headers

    def render_response_data(self, validated_request_data, response_data):
        # 如果 code 非 0 时，记录对应的 request id，不做异常处理
        if response_data.get("code") != 0:
            logger.error(
                "request bcs api error, params: %s, response: %s",
                json.dumps(validated_request_data),
                json.dumps(response_data),
            )
        return response_data.get("data", {})


class FetchSharedClusterNamespacesResource(BcsApiBaseResource):
    action = "/bcsproject/v1/projects/{project_code}/clusters/{cluster_id}/native/namespaces"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        # 当为`-`时，为拉取集群下所有的命名空间数据
        project_code = serializers.CharField(required=False, label="project code", default="-")
        cluster_id = serializers.CharField(label="cluster id")

    def render_response_data(self, validated_request_data, response_data):
        # 对响应数据进行额外处理
        data = super(FetchSharedClusterNamespacesResource, self).render_response_data(
            validated_request_data, response_data
        )
        return self._refine_ns(data, validated_request_data["cluster_id"])

    def _refine_ns(self, ns_list: List, cluster_id: str) -> List:
        """处理返回的命名空间"""
        return [
            {
                "project_id": ns["projectID"],
                "project_code": ns["projectCode"],
                "cluster_id": cluster_id,
                "namespace": ns["name"],
            }
            for ns in ns_list
        ]


class GetProjectsResource(BcsApiBaseResource):
    """查询项目信息"""

    action = "/bcsproject/v1/projects"
    method = "GET"
    backend_cache_type = None

    default_limit = 1000

    class RequestSerializer(serializers.Serializer):
        limit = serializers.IntegerField(required=False, default=1000)
        offset = serializers.IntegerField(required=False, default=0)
        kind = serializers.CharField(required=False, allow_blank=True)
        is_detail = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_request_data):
        projects = super(GetProjectsResource, self).perform_request(validated_request_data)
        count = projects["total"]
        project_list = projects.get("results") or []
        # 如果每页的数量大于count，则不用继续请求，否则需要继续请求
        if count > self.default_limit:
            max_offset = count // self.default_limit
            start_offset = 1
            while start_offset <= max_offset:
                validated_request_data.update({"limit": self.default_limit, "offset": start_offset})
                resp_data = super(GetProjectsResource, self).perform_request(validated_request_data)
                project_list.extend(resp_data.get("results") or [])
                start_offset += 1
        # 因为返回数据内容太多，抽取必要的字段
        if validated_request_data.get("is_detail"):
            return project_list

        return self._refine_projects(project_list)

    def _refine_projects(self, project_list):
        return [
            {
                "project_id": p["projectID"],
                "name": p["name"],
                "project_code": p["projectCode"],
                "bk_biz_id": p["businessID"],
            }
            for p in project_list
        ]


class GetFederationClustersResource(BcsApiBaseResource):
    """查询联邦集群信息"""

    action = "/federationmanager/v1/clusters/all/sub_clusters"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        fed_project_code = serializers.CharField(required=False, allow_blank=True)
        fed_cluster_id = serializers.CharField(required=False, allow_blank=True)
        sub_project_code = serializers.CharField(required=False, allow_blank=True)
        sub_cluster_id = serializers.CharField(required=False, allow_blank=True)

    def full_request_data(self, validated_request_data):
        return validated_request_data

    def perform_request(self, validated_request_data):
        data = self._get_request_data(validated_request_data)
        resp = super(GetFederationClustersResource, self).perform_request(data)
        return self._refine_cluster(resp)

    def _refine_cluster(self, resp: Optional[List] = None):
        """处理返回的集群信息
        格式:
        {
            "{federation_cluster_id}": {
                "host_cluster_id": "{host_cluster_id}",
                "sub_clusters": {
                    "{sub_cluster_id}": [namespace1, namespace2, namespace3]
                }
            }
        }
        """
        if resp is None:
            return {}
        resp_data = {}
        for data in resp:
            sub_item = {}
            for sub in data["sub_clusters"]:
                sub_item.setdefault(sub["sub_cluster_id"], []).extend(sub.get("federation_namespaces", []))
            resp_data.setdefault(data["federation_cluster_id"], {}).update(
                {
                    "host_cluster_id": data["host_cluster_id"],
                    "sub_clusters": sub_item,
                }
            )
        return resp_data

    def _get_request_data(self, validated_request_data):
        data = {}
        fed_project_code = validated_request_data.get("fed_project_code")
        fed_cluster_id = validated_request_data.get("fed_cluster_id")
        # 添加联邦集群的查询条件
        if fed_project_code or fed_cluster_id:
            data["conditions"] = {}
            if fed_project_code:
                data["conditions"]["project_code"] = fed_project_code
            if fed_cluster_id:
                data["conditions"]["cluster_id"] = fed_cluster_id
        # 添加子集群的查询条件
        sub_project_code = validated_request_data.get("sub_project_code")
        sub_cluster_id = validated_request_data.get("sub_cluster_id")
        if sub_project_code or sub_cluster_id:
            data["sub_conditions"] = {}
            if sub_project_code:
                data["sub_conditions"]["project_code"] = sub_project_code
            if sub_cluster_id:
                data["sub_conditions"]["sub_cluster_id"] = sub_cluster_id

        return data
