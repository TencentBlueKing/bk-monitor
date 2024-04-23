# -*- coding: utf-8 -*-


import abc
import json
from typing import List

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType
from core.drf_resource import api
from core.drf_resource.base import Resource
from core.drf_resource.contrib.api import APIResource


class BcsCcBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    cache_type = CacheType.BCS
    # 注意这里的系统名字是bcs-cc，查询的方法是在https://{settings.BK_PAAS_INNER_HOST}/admin/apigw/api/查询
    # 这是apigw查询系统的方式，目前由于apigw没有页面，所以只能在这里查询
    base_url = settings.BCS_CC_API_URL
    module_name = "bcs-cc"

    def before_request(self, kwargs):
        bkssm_access_token = api.bkssm.get_access_token()
        access_token = bkssm_access_token["access_token"]
        kwargs["headers"]["X-BKAPI-AUTHORIZATION"] = json.dumps({"access_token": access_token})
        return kwargs


class GetClusterList(BcsCcBaseResource):
    """
    获取所有集群信息
    可以通过这个接口，从集群ID查询得到对应的项目ID
    返回数据格式:
    [{'id': 1,
      'created_at': '2021-07-02T09:12:20+08:00',
      'updated_at': '2021-07-02T09:23:11+08:00',
      'deleted_at': None,
      'extra': '',
      'name': 'first',
      'creator': 'admin',
      'description': 'first',
      'project_id': 'f2e651a2b44a4eabb918d079d0da04c8',
      'related_projects': '',
      'cluster_id': 'BCS-K8S-40000',
      'cluster_num': 40000,
      'status': 'normal',
      'disabled': False,
      'type': 'k8s',
      'environment': 'prod',
      'area_id': 1,
      'config_svr_count': 0,
      'master_count': 0,
      'node_count': 0,
      'ip_resource_total': 0,
      'ip_resource_used': 0,
      'artifactory': '',
      'total_mem': 0,
      'remain_mem': 0,
      'total_cpu': 0,
      'remain_cpu': 0,
      'total_disk': 0,
      'remain_disk': 0,
      'capacity_updated_at': '2021-07-02T09:23:11+08:00',
      'not_need_nat': False,
      'extra_cluster_id': '',
      'state': 'bcs_new'}]
    """

    action = "projects/null/clusters_list"
    method = "GET"
    backend_cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        cluster_ids = serializers.ListField(label="集群ID列表")

    def request(self, request_data=None, **kwargs):
        if not settings.BCS_CC_API_URL:
            return []
        return super(GetClusterList, self).request(request_data, **kwargs)


class GetAreaList(BcsCcBaseResource):
    action = "areas"
    method = "GET"
    backend_cache_type = CacheType.BCS

    def request(self, request_data=None, **kwargs):
        if not settings.BCS_CC_API_URL:
            return {"results": []}
        return super(GetAreaList, self).request(request_data, **kwargs)

    def render_response_data(self, validated_request_data, response_data):
        response_data["results"].append(
            {"id": 0, "name": "default", "chinese_name": "默认", "configuration": "", "description": ""}
        )
        return response_data


class GetProjectList(BcsCcBaseResource):
    action = "projects"
    method = "GET"
    backend_cache_type = CacheType.BCS
    _blueking_biz_id = None

    @property
    def blueking_biz_id(self):
        if not self._blueking_biz_id:
            self._blueking_biz_id = api.cmdb.get_blueking_biz()
        return self._blueking_biz_id

    def request(self, request_data=None, **kwargs):
        if not settings.BCS_CC_API_URL:
            return {"results": []}
        return super(GetProjectList, self).request(request_data, **kwargs)

    def render_response_data(self, validated_request_data, response_data):
        response_data["results"].append(
            {
                "approval_status": 2,
                "approval_time": "1970-01-01T00:00:00+00:00",
                "approver": "",
                "bg_id": 0,
                "bg_name": "",
                "bgid": 0,
                "cc_app_id": self.blueking_biz_id,
                "center_id": 0,
                "center_name": "",
                "created_at": "1970-01-01T00:00:00+00:00",
                "creator": "admin",
                "data_id": 0,
                "deploy_type": "null",
                "dept_id": 0,
                "dept_name": "",
                "description": "",
                "english_name": "default",
                "id": 1,
                "is_offlined": False,
                "is_secrecy": False,
                "kind": 1,
                "logo_addr": "",
                "name": "test",
                "project_id": "default",
                "project_name": "默认",
                "project_type": 0,
                "remark": "",
                "updated_at": "1970-01-01T00:00:00+00:00",
                "updator": "admin",
                "use_bk": False,
            }
        )
        return response_data


class GetSharedClusterNamespaces(BcsCcBaseResource):
    """查询共享集群下的命名空间"""

    action = "shared_clusters/{cluster_id}/"
    method = "GET"
    cache_type = None

    def get_request_url(self, validated_request_data):
        return (
            super(GetSharedClusterNamespaces, self)
            .get_request_url(validated_request_data)
            .format(**validated_request_data)
        )

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(label="集群 ID")
        project_id = serializers.CharField(label="项目 ID", default="")
        desire_all_data = serializers.CharField(label="查询全量数据", default="1", help_text="根据服务方提供，字符串`1`为拉取全量数据标识")

    def render_response_data(self, validated_request_data, response_data):
        # 过滤项目下的空间
        if validated_request_data.get("project_id"):
            return [
                {"project_id": n["project_id"], "cluster_id": n["cluster_id"], "namespace": n["name"]}
                for n in (response_data.get("results") or [])
                if n["project_id"] == validated_request_data["project_id"]
            ]

        return [
            {"project_id": n["project_id"], "cluster_id": n["cluster_id"], "namespace": n["name"]}
            for n in (response_data.get("results") or [])
        ]


class GetProjects(BcsCcBaseResource):
    action = "projects"
    method = "GET"
    backend_cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        limit = serializers.IntegerField(required=False, default=1000)
        offset = serializers.IntegerField(required=False, default=0)
        desire_all_data = serializers.IntegerField(required=False, default=0)


class BatchGetProjects(Resource):
    """批量查询项目信息"""

    class RequestSerializer(serializers.Serializer):
        limit = serializers.IntegerField(required=False, default=2000)
        desire_all_data = serializers.BooleanField(required=False, default=False, label="是否拉取全量")
        filter_k8s_kind = serializers.BooleanField(required=False, default=True, label="是否过滤 k8s 类型项目")

    def perform_request(self, validated_request_data):
        def get_data(data):
            # 数组时，直接返回数据
            if isinstance(data, list):
                return data
            return data.get("results") or []

        # 转换参数
        params = {"desire_all_data": 1 if validated_request_data["desire_all_data"] else 0}

        # 批量请求
        project_list = batch_request(
            GetProjects().__call__,
            params,
            get_data=get_data,
            limit=validated_request_data["limit"],
            app="bcs_cc",
        )

        return self._refine_projects(project_list, validated_request_data["filter_k8s_kind"])

    def _refine_projects(self, project_list: List, filter_k8s_kind: bool) -> List:
        """过滤数据，返回必要信息"""
        data = []
        for p in project_list:
            # 是否过滤掉非 k8s 类型数据
            if filter_k8s_kind and str(p["kind"]) != "1":
                continue
            data.append(
                {
                    "project_id": p["project_id"],
                    "name": p["project_name"],
                    "project_code": p["english_name"],
                    "bk_biz_id": str(p["cc_app_id"]),
                }
            )
        return data
