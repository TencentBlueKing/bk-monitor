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
from urllib.parse import urljoin

import six
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from requests.exceptions import HTTPError, ReadTimeout
from rest_framework import serializers

from core.drf_resource.contrib.api import APIResource
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class BcsProjectBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    """项目相关API基类"""

    base_url = urljoin(
        f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
        "/bcsapi/v4/bcsproject/v1",
    )
    module_name = "bcs-project"

    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        return (
            super(BcsProjectBaseResource, self).get_request_url(validated_request_data).format(**validated_request_data)
        )

    def perform_request(self, validated_request_data):
        request_url = self.get_request_url(validated_request_data)
        headers = {
            "Authorization": f"Bearer {settings.BCS_API_GATEWAY_TOKEN}",
            "X-Project-Username": settings.COMMON_USERNAME,
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
            raise BKAPIError(system_name=self.module_name, url=self.action, result=_("接口返回结果超时"))

        try:
            result.raise_for_status()
        except HTTPError as err:
            logger.exception("【模块：{}】请求 BCS Project 服务错误：{}，请求url: {}".format(self.module_name, err, request_url))
            raise BKAPIError(system_name=self.module_name, url=self.action, result=str(err.response.content))

        result_json = result.json()
        data = result_json.get("data", {})

        return data


class GetProjectsResource(BcsProjectBaseResource):
    """查询项目信息"""

    action = "projects"
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
