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
from django.http import JsonResponse, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.translation import gettext_lazy as _
from opentelemetry import trace
from rest_framework.views import APIView

logger = logging.getLogger("apm")
tracer = trace.get_tracer(__name__)


class BkLogForwardingView(APIView):
    """转发请求到日志平台"""

    # 需要忽略的头部
    ignore_headers = ["host", "content-length"]

    @classmethod
    def _is_attachment_response(cls, response: requests.Response) -> bool:
        """
        判断是否为携带附件响应
        - `Content-Disposition` 头部包含 `attachment` 时，表示响应为附件。
        - 参考：https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Disposition。
        """
        content_disposition = response.headers.get("Content-Disposition", "")
        return "attachment" in content_disposition

    @classmethod
    def _construct_attachment_response(cls, response: requests.Response) -> HttpResponse:
        """构造附件响应"""
        return HttpResponse(
            response.content,
            headers={
                "Content-Type": response.headers.get("Content-Type"),
                "Content-Disposition": response.headers.get("Content-Disposition"),
            },
            status=response.status_code,
        )

    @classmethod
    def _construct_json_response(cls, response: requests.Response) -> JsonResponse:
        """构造 JSON 响应"""
        return JsonResponse(response.json(), status=response.status_code)

    @classmethod
    def _construct_response(cls, response: requests.Response) -> HttpResponseBase:
        """构造请求响应"""
        if cls._is_attachment_response(response):
            return cls._construct_attachment_response(response)
        return cls._construct_json_response(response)

    def dispatch(self, request, *args, **kwargs):
        if not str(request.path).replace("/", "").replace("_", "").isalnum():
            return JsonResponse(
                {
                    "message": _("请求路径不在日志平台接口范围"),
                    "code": 500,
                    "data": None,
                    "result": False,
                },
                status=500,
            )

        target_url = urljoin(settings.BKLOGSEARCH_INNER_HOST, request.path.split("bklog")[-1])
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
                response = requests.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    params=params,
                    data=body,
                    allow_redirects=False,
                    verify=False,
                )
                return self._construct_response(response)
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
