"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from collections.abc import Iterator
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.http.response import HttpResponseBase
from django.utils.translation import gettext_lazy as _
from opentelemetry import trace
from rest_framework.views import APIView

logger = logging.getLogger("apm")
tracer = trace.get_tracer(__name__)

# # 与 urllib3 默认流读取大小一致，平衡首包延迟、迭代开销和内存占用。
LOG_STREAM_CHUNK_SIZE = 64 * 1024


class _UpstreamResponseIterator:
    """逐块读取上游响应，并在结束或中断时释放连接。"""

    def __init__(self, response: requests.Response) -> None:
        self.response: requests.Response = response

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self.response.iter_content(chunk_size=LOG_STREAM_CHUNK_SIZE)
        finally:
            self.close()

    def close(self) -> None:
        self.response.close()


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
        try:
            return HttpResponse(
                response.content,
                headers={
                    "Content-Type": response.headers.get("Content-Type"),
                    "Content-Disposition": response.headers.get("Content-Disposition"),
                },
                status=response.status_code,
            )
        finally:
            response.close()

    @classmethod
    def _construct_json_response(cls, response: requests.Response) -> JsonResponse:
        """构造 JSON 响应"""
        try:
            return JsonResponse(response.json(), status=response.status_code)
        finally:
            response.close()

    @classmethod
    def _is_streaming_response(cls, response: requests.Response) -> bool:
        """判断上游是否返回 NDJSON 流。"""
        content_type: str = response.headers.get("Content-Type", "")
        return content_type.partition(";")[0].strip().lower() == "application/x-ndjson"

    @classmethod
    def _construct_streaming_response(cls, response: requests.Response) -> StreamingHttpResponse:
        """构造流式透传响应。"""
        response_headers: dict[str, str] = {
            header: response.headers[header]
            # 透传日志平台要求设置的流式依赖请求头：
            # Cache-Control： 避免浏览器缓存 NDJSON 流，确保每次请求都能获取最新数据。
            # X-Accel-Buffering：通知 Nginx 不要缓冲响应，尽快向客户端发送数据。
            for header in ("Cache-Control", "X-Accel-Buffering")
            if header in response.headers
        }
        return StreamingHttpResponse(
            _UpstreamResponseIterator(response),
            content_type=response.headers["Content-Type"],
            headers=response_headers,
            status=response.status_code,
        )

    @classmethod
    def _construct_response(cls, response: requests.Response) -> HttpResponseBase:
        """构造请求响应"""
        if cls._is_attachment_response(response):
            return cls._construct_attachment_response(response)
        if cls._is_streaming_response(response):
            return cls._construct_streaming_response(response)
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
                    # 收到响应头后先返回 Response，不要立刻把响应体全部读入内存，根据真实 Content-Type 决定是否流式返回。
                    stream=True,
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
