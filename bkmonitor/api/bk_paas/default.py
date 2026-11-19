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
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class BkPaaSAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.PAASV3_APIGW_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/bk_paas/"

    # 模块名
    module_name = "bk_paas"

    def get_request_url(self, validated_request_data):
        return super().get_request_url(validated_request_data).format(**validated_request_data)


class GetAppClusterNamespaceResource(BkPaaSAPIGWResource):
    """获取蓝鲸应用对应的集群数据

    返回 [{"bcs_cluster_id": xxx, "namespace": xxx, ...}]；空列表表示应用确实没有使用集群资源。
    调用失败（网关错误、超时、鉴权失败、应用不存在等）或返回结构无法识别时抛出异常，
    调用方据此与"没有集群资源"区分，不能把失败当作空结果写入。
    """

    action = "/system/bkapps/applications/{app_code}/cluster_namespaces/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        app_code = serializers.CharField(required=True, label="蓝鲸应用")

    def perform_request(self, validated_request_data):
        app_code = validated_request_data.get("app_code")
        try:
            resp = super().perform_request(validated_request_data)
        except Exception as e:
            logger.warning("get app cluster namespace failed, app_code: %s, error: %s", app_code, type(e).__name__)
            raise

        if not isinstance(resp, list) or not all(
            isinstance(item, dict) and "bcs_cluster_id" in item and "namespace" in item for item in resp
        ):
            logger.warning(
                "get app cluster namespace returned unrecognized response, app_code: %s, type: %s",
                app_code,
                type(resp).__name__,
            )
            raise BKAPIError(
                system_name=self.module_name,
                url=self.action,
                result=f"unrecognized cluster namespace response, type: {type(resp).__name__}",
            )

        return resp
