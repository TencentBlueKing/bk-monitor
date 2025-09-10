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
import functools
import json
from typing import Collection

from django.http import HttpRequest, StreamingHttpResponse
from django.urls import Resolver404, resolve
from opentelemetry.context import attach, detach, get_current
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import Span, Status, StatusCode

from bkmonitor.trace.utils import MAX_PARAMS_SIZE, jsonify
from core.errors import Error


def request_hook(span: Span, request: HttpRequest):
    """将请求中的 GET、BODY 参数记录在 span 中"""

    if not request:
        return
    try:
        if getattr(request, "FILES", None) and request.method.upper() == "POST":
            # 请求中如果包含了文件 不取 Body 内容
            carrier = jsonify(request.POST)
        else:
            carrier = request.body.decode("utf-8")
    except Exception:  # noqa
        carrier = ""

    param_str = jsonify(dict(request.GET)) if request.GET else ""

    span.set_attribute("request.body", carrier[:MAX_PARAMS_SIZE])
    span.set_attribute("request.params", param_str[:MAX_PARAMS_SIZE])


def response_hook(span, request, response):
    # Set user information as an attribute on the span
    if not request or not response:
        return

    user = getattr(request, "user", None)
    username = getattr(user, "username", "") if user else ""
    span.set_attribute("user.username", username)

    if hasattr(response, "data"):
        result = response.data
    else:
        try:
            result = json.loads(response.content)
        except (TypeError, ValueError, AttributeError):
            return
    if not isinstance(result, dict):
        return

    res_result = result.get("result", True)
    span.set_attribute("http.response.code", result.get("code", 0))
    span.set_attribute("http.response.message", result.get("message", ""))
    span.set_attribute("http.response.result", str(res_result))
    if res_result:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(exception=Error(result.get("message")))


def get_span_name(_, request):
    """获取 django instrument 生成的 span 的 span_name 返回 Resource的路径"""
    try:
        match = resolve(request.path)
    except Resolver404:
        if request.path.endswith("/"):
            # 如果无法解析 直接返回 path
            return request.path
        try:
            match = resolve(f"{request.path}/")
        except Resolver404:
            return request.path

    if hasattr(match, "func"):
        resource_path = _get_resource_clz_path(match, request)
        if resource_path:
            return resource_path

    if hasattr(match, "_func_name"):
        return match._func_name  # pylint: disable=protected-access # noqa

    return match.view_name


def _get_resource_clz_path(match, request):
    """寻找 resource 类并返回路径"""
    try:
        resource_mapping = match.func.cls().resource_mapping
        view_set_path = f"{match.func.cls.__module__}.{match.func.cls.__name__}"
        resource_clz = resource_mapping.get(
            (request.method, f"{view_set_path}-{match.func.actions.get(request.method.lower())}")
        )
        if resource_clz:
            return f"{resource_clz.__module__}.{resource_clz.__qualname__}"

        return None
    except Exception:  # noqa
        return None


class BKDjangoStreamingHttpResponseInstrumentor(BaseInstrumentor):
    """
    Instrumentation for django StreamingHttpResponse

    因为 StreamingHttpResponse 的内容是在 DjangoInstrumentor 的 span 关闭后才开始迭代的
    导致可迭代对象里的 span 父级没有关联到 StreamingHttpResponse 初始化时存在的 span。所以这里需要:
    1. hook __init__ 方法，将 StreamingHttpResponse 初始化时的 Otel 上下文保存下来
    1. hook __iter__ 方法，在 StreamingHttpResponse 迭代内容前，将保存下来的 Otel 上下文 attch 到当前上下文
    3. hook _set_streaming_content 方法，将 Otel 上下文重置为上一个
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        return tuple()

    def _instrument(self, **kwargs):
        """Instruments django StreamingHttpResponse

        Args:
            **kwargs: Optional arguments
                ``tracer_provider``: a TracerProvider, defaults to global
        """

        wrapped__init__ = StreamingHttpResponse.__init__
        wrapped__iter__ = StreamingHttpResponse.__iter__
        wrapped_set_streaming_content = StreamingHttpResponse._set_streaming_content

        @functools.wraps(wrapped__init__)
        def instrumented__init__(self, *args, **kwargs):
            self.bk_opentelemetry_instrumentation_previous_token = None
            self.bk_opentelemetry_instrumentation_context = get_current()
            return wrapped__init__(self, *args, **kwargs)

        @functools.wraps(wrapped__iter__)
        def instrumented__iter__(self):
            if self.bk_opentelemetry_instrumentation_context:
                self.bk_opentelemetry_instrumentation_previous_token = attach(
                    self.bk_opentelemetry_instrumentation_context
                )
                self.bk_opentelemetry_instrumentation_context = None
            return wrapped__iter__(self)

        @functools.wraps(wrapped_set_streaming_content)
        def instrumented_set_streaming_content(self, value):
            if self.bk_opentelemetry_instrumentation_previous_token:
                self._resource_closers.append(
                    functools.partial(detach, self.bk_opentelemetry_instrumentation_previous_token)
                )
                self.bk_opentelemetry_instrumentation_previous_token = None
            return wrapped_set_streaming_content(self, value)

        instrumented__init__.bk_opentelemetry_instrumentation_streamhttpresponse_applied = True
        StreamingHttpResponse.__init__ = instrumented__init__

        instrumented__iter__.bk_opentelemetry_instrumentation_streamhttpresponse_applied = True
        StreamingHttpResponse.__iter__ = instrumented__iter__

        instrumented_set_streaming_content.bk_opentelemetry_instrumentation_streamhttpresponse_applied = True
        StreamingHttpResponse._set_streaming_content = instrumented_set_streaming_content

    def _uninstrument(self, **kwargs):
        """Uninstruments django StreamingHttpResponse"""
        for instr_func_name in ("__init__", "__iter__", "_set_streaming_content"):
            instr_func = getattr(StreamingHttpResponse, instr_func_name)
            if not getattr(
                instr_func,
                "bk_opentelemetry_instrumentation_streamhttpresponse_applied",
                False,
            ):
                continue

            original = instr_func.__wrapped__  # pylint:disable=no-member
            setattr(StreamingHttpResponse, instr_func_name, original)
