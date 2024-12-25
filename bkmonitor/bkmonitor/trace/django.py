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

from django.http import HttpRequest
from django.urls import Resolver404, resolve
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
