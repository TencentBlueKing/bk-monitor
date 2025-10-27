import abc
import json
import logging

import six
from django.conf import settings
from rest_framework import serializers

from core.drf_resource.contrib.api import APIResource

logger = logging.getLogger(__name__)


class BcsApiBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    """BCS API 网关基类"""

    base_url = settings.BCS_APIGW_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bcs-api-gateway/prod/"

    module_name = "bcs-api"

    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        return super().get_request_url(validated_request_data).format(**validated_request_data)

    def get_headers(self):
        headers = super().get_headers()
        headers["Authorization"] = f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"
        return headers

    def render_response_data(self, validated_request_data, response_data):
        code = response_data.get("code")

        # 如果 code 非 0 时，记录对应的 request id，不做异常处理
        if code != 0:
            logger.error(
                "BcsApiBaseResource: request bcs api error, params: %s, response: %s",
                json.dumps(validated_request_data),
                json.dumps(response_data),
            )
        return response_data.get("data", {})


class FetchSharedClusterNamespacesResource(BcsApiBaseResource):
    action = "/bcsproject/v1/projects/{project_code}/clusters/{cluster_id}/native/namespaces"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = serializers.CharField(required=True, label="租户ID")
        # 当为`-`时，为拉取集群下所有的命名空间数据
        project_code = serializers.CharField(required=False, label="project code", default="-")
        cluster_id = serializers.CharField(label="cluster id")

    def render_response_data(self, validated_request_data, response_data):
        # 对响应数据进行额外处理
        data = super().render_response_data(validated_request_data, response_data)
        return self._refine_ns(data, validated_request_data["cluster_id"])

    def _refine_ns(self, ns_list: list, cluster_id: str) -> list:
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
        bk_tenant_id = serializers.CharField(required=True, label="租户ID")
        limit = serializers.IntegerField(required=False, default=1000)
        offset = serializers.IntegerField(required=False, default=0)
        kind = serializers.CharField(required=False, allow_blank=True)
        is_detail = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_request_data):
        projects = super().perform_request(validated_request_data)
        count = projects["total"]
        project_list = projects.get("results") or []
        # 如果每页的数量大于count，则不用继续请求，否则需要继续请求
        if count > self.default_limit:
            max_offset = count // self.default_limit
            start_offset = 1
            while start_offset <= max_offset:
                validated_request_data.update({"limit": self.default_limit, "offset": start_offset})
                resp_data = super().perform_request(validated_request_data)
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
        bk_tenant_id = serializers.CharField(required=True, label="租户ID")
        fed_project_code = serializers.CharField(required=False, allow_blank=True)
        fed_cluster_id = serializers.CharField(required=False, allow_blank=True)
        sub_project_code = serializers.CharField(required=False, allow_blank=True)
        sub_cluster_id = serializers.CharField(required=False, allow_blank=True)

    def full_request_data(self, validated_request_data):
        return validated_request_data

    def perform_request(self, validated_request_data):
        data = self._get_request_data(validated_request_data)
        resp = super().perform_request(data)
        return self._refine_cluster(resp)

    def _refine_cluster(self, resp: list | None = None):
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
