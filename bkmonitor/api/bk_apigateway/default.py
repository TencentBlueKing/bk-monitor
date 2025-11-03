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

from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource import APIResource


class BkApiGatewayResource(APIResource, metaclass=abc.ABCMeta):
    base_url_statement = None
    base_url = settings.APIGATEWAY_API_BASE_URL or "%s/api/bk-apigateway/prod/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "bk-apigateway"

    def get_request_url(self, validated_request_data):
        return super().get_request_url(validated_request_data).format(**validated_request_data)


class GetPublicKeyResource(BkApiGatewayResource):
    """
    获取public_key
    """

    action = "/api/v1/apis/{api_name}/public_key/"
    method = "GET"
    cache_type = CacheType.USER

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = serializers.CharField(label="租户ID")
        api_name = serializers.CharField(label="接口名称", max_length=255)
