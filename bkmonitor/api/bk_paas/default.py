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
import abc
import logging

import six
from django.conf import settings
from rest_framework import serializers

from core.drf_resource import APIResource

logger = logging.getLogger(__name__)


class BkPaaSAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.PAASV3_APIGW_BASE_URL or "%s/api/c/compapi/v2/bk_paas/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "bk_paas"

    def get_request_url(self, validated_request_data):
        return super(BkPaaSAPIGWResource, self).get_request_url(validated_request_data).format(**validated_request_data)


class GetAppClusterNamespaceResource(BkPaaSAPIGWResource):
    """获取蓝鲸应用对应的集群数据"""

    action = "/system/bkapps/applications/{app_code}/cluster_namespaces/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        app_code = serializers.CharField(required=True, label="蓝鲸应用")

    def perform_request(self, validated_request_data):
        try:
            resp = super(GetAppClusterNamespaceResource, self).perform_request(validated_request_data)
        except Exception:
            resp = []

        return resp
