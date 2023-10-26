# -*- coding: utf-8 -*-


import abc

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource.contrib.api import APIResource


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
