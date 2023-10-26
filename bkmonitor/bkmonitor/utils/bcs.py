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
import logging

import six
from django.conf import settings
from django.utils.translation import ugettext as _
from requests.exceptions import HTTPError, ReadTimeout

from core.drf_resource.contrib.api import APIResource
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class BcsApiGatewayBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    def perform_request(self, validated_request_data):
        request_url = self.get_request_url(validated_request_data)
        headers = {"Authorization": f"Bearer {settings.BCS_API_GATEWAY_TOKEN}"}
        try:
            result = self.session.get(
                params=validated_request_data,
                url=request_url,
                headers=headers,
                verify=False,
                timeout=self.TIMEOUT,
            )
        except ReadTimeout:
            raise BKAPIError(system_name=self.module_name, url=self.action, result=_("接口返回结果超时"))

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception("【模块：%s】请求BCS APIGW错误：%s，请求url: %s " % (self.module_name, err, request_url))
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        result_json = result.json()
        return result_json
