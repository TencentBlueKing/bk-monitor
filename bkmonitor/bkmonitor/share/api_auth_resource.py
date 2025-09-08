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

from django.db import models
from django.utils.translation import gettext as _

from bkmonitor.share.utils import check_api_permission
from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.tools import format_serializer_errors

logger = logging.getLogger(__name__)


class ApiAuthResource(Resource):
    """
    api鉴权resource
    """

    def perform_request(self, validated_request_data):
        pass

    def validate_request_data(self, request_data):
        """
        校验请求数据,增加鉴权参数校验
        """
        self._request_serializer = None
        if not self.RequestSerializer:
            check_api_permission(get_request(peaceful=True), request_data)
            return request_data

        # model类型的数据需要特殊处理
        if isinstance(request_data, (models.Model, models.QuerySet)):
            request_serializer = self.RequestSerializer(request_data, many=self.many_request_data)
            self._request_serializer = request_serializer
            validated_request_data = request_serializer.data
        else:
            request_serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
            self._request_serializer = request_serializer
            is_valid_request = request_serializer.is_valid()
            if not is_valid_request:
                logger.error(
                    "Resource[{}] 请求参数格式错误：%s".format(self.get_resource_name()),
                    format_serializer_errors(request_serializer),
                )
                raise CustomException(
                    _("Resource[{}] 请求参数格式错误：{}").format(
                        self.get_resource_name(), format_serializer_errors(request_serializer)
                    )
                )
            validated_request_data = request_serializer.validated_data

        # api携带token模式进行参数校验
        check_api_permission(get_request(peaceful=True), request_data)
        return validated_request_data
