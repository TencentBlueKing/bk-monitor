# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import abc
import json
import logging

import six
from django.conf import settings
from requests.exceptions import HTTPError, ReadTimeout
from rest_framework import serializers

from core.drf_resource import APIResource
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class BkPaaSAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.PAASV3_APIGW_BASE_URL or "%s/api/c/compapi/v2/bk_paas/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "bk_paas"

    def get_request_url(self, validated_request_data):
        return super(BkPaaSAPIGWResource, self).get_request_url(validated_request_data).format(**validated_request_data)

    def perform_request(self, validated_request_data):
        request_url = self.get_request_url(validated_request_data)
        headers = {
            "x-bkapi-authorization": json.dumps({"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.APP_TOKEN})
        }
        try:
            result = self.session.get(
                params=validated_request_data,
                url=request_url,
                headers=headers,
                verify=False,
                timeout=self.TIMEOUT,
            )
        except ReadTimeout:
            raise BKAPIError(system_name=self.module_name, url=self.action, result="request timeout")

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception("【模块：{}】请求错误：{}，请求url: {} ".format(self.module_name, err, request_url))
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        return result.json()


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
