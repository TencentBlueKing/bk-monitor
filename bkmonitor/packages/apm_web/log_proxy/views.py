# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from opentelemetry import trace
from rest_framework.views import APIView

logger = logging.getLogger("apm")
tracer = trace.get_tracer(__name__)


class BkLogForwardingView(APIView):
    """转发请求到日志平台"""

    # 需要忽略的头部
    ignore_headers = ["host", "content-length"]

    def dispatch(self, request, *args, **kwargs):
        target_url = urljoin(settings.BKLOGSEARCH_INNER_HOST, request.path.split('bklog')[-1])

        try:
            params = {key: request.GET.get(key) for key in request.GET}
            body = request.body if request.body else None
            headers = {k: v for k, v in dict(request.headers).items() if k.lower() not in self.ignore_headers}
            # 添加监控平台标识 在日志平台中走特殊权限
            headers.update({"X-SOURCE-APP-CODE": settings.APP_CODE})
            with tracer.start_as_current_span(
                "log_forward",
                attributes={
                    "target_url": target_url,
                    "headers": json.dumps(headers),
                    "params": params,
                    "body": body,
                },
            ):
                logger.info(
                    f"[APMLogForward] {request.method} - "
                    f"target_url: {target_url} headers: {json.dumps(headers)} "
                    f"params: {params} body: {body}"
                )

                response = requests.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    params=params,
                    data=body,
                    allow_redirects=False,
                    verify=False,
                )
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:  # noqa
            return JsonResponse(
                {
                    "message": _("请求日志平台接口错误: ") + str(e),
                    "code": 500,
                    "data": None,
                    "result": False,
                },
                status=500,
            )
