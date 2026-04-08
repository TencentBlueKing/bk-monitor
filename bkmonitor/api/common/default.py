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

import six
from django.conf import settings

from bkmonitor.utils.template import Jinja2Renderer
from bkmonitor.utils.user import get_global_user
from core.drf_resource.contrib.api import APIResource
from core.errors.api import BKAPIError


class CommonBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = ""
    module_name = "common"
    action = "common"
    method = "GET"

    def __init__(self, *args, **kwargs):
        self.url = kwargs.pop("url", "")
        self.url_path = Jinja2Renderer.render(
            self.url,
            {"bk_paas_inner_host": "", "bk_paas_host": "", "itsm_v4_api_url": ""},
        )
        self.base_url = Jinja2Renderer.render(
            self.url,
            {
                "bk_paas_inner_host": settings.BK_COMPONENT_API_URL.rstrip("/"),
                "bk_paas_host": settings.BK_PAAS_HOST.rstrip("/"),
                "itsm_v4_api_url": settings.BK_ITSM_V4_API_URL.rstrip("/"),
            },
        )
        self.method = kwargs.pop("method", "GET")
        self.plugin_key = self.module_name
        super().__init__(**kwargs)

    def perform_request(self, params):
        self.plugin_key = params.pop("action_plugin_key", None) or self.plugin_key
        params["_origin_user"] = get_global_user()
        try:
            return super().perform_request(params)
        except BKAPIError as api_error:
            # 重新设置异常内容
            error_message = api_error.data.get("message", "第三方系统异常")
            raise BKAPIError(system_name=self.plugin_key, url=self.url_path, result=str(error_message))

    def get_request_url(self, validated_request_data):
        """
        获取最终请求的url，也可以由子类进行重写
        """
        return self.base_url
