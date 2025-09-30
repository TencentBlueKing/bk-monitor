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

from blueapps.utils import get_request as _get_request
from django.utils.deprecation import MiddlewareMixin

from audit.instance import push_event
from bkmonitor.utils.common_utils import fetch_biz_id_from_request
from bkmonitor.utils.local import local
from bkmonitor.utils.request import is_ajax_request

logger = logging.getLogger(__name__)


class RequestProvider(MiddlewareMixin):
    """
    @summary: request事件接收者
    """

    def process_request(self, request):
        local.current_request = _get_request()
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        biz_id = fetch_biz_id_from_request(request, view_kwargs)
        request.biz_id = biz_id
        # 记录非monitor_api未获取到biz_id的请求
        if biz_id and request.resolver_match.namespace == "monitor_web":
            request.session["bk_biz_id"] = biz_id
            return None

        if request.resolver_match.namespace == "monitor_adapter":
            if request.method == "GET":
                if not is_ajax_request(request) and "CSRF_COOKIE" in request.META:
                    # 用户请求GET方法时生成csrf cookie
                    request.META["CSRF_COOKIE_USED"] = True
            if not biz_id:
                # 切换业务
                request.session["bk_biz_id"] = None
            return None

    def process_response(self, request, response):
        push_event(request)
        local.clear()
        response["X-Content-Type-Options"] = "nosniff"
        return response
