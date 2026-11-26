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

from opentelemetry.trace import Span, Status, StatusCode
from requests import PreparedRequest, Response

from bkmonitor.trace.utils import MAX_PARAMS_SIZE, jsonify


def requests_response_hook(span: Span, request: PreparedRequest, response: Response) -> None:
    """将 requests 的请求和返回中的有用信息记录在 span 中"""
    # 非流式请求的响应体已由 Session.send 读取。埋点不能提前读取流式响应。
    if not response or not response._content_consumed:
        return

    try:
        json_result = response.json()
    except Exception:  # pylint: disable=broad-except # noqa
        return

    if not isinstance(json_result, dict):
        return

    code = json_result.get("code", 0)
    errors = str(json_result.get("errors", ""))
    if errors:
        span.set_attribute("http.response.errors", errors)

    request_id = (
        response.headers.get("x-bkapi-request-id")
        or response.headers.get("x-request-id")
        or json_result.get("request_id", "")
    )
    if request_id:
        span.set_attribute("request_id", request_id)

    if str(code) in ["0", "00", "200"]:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR))

    span.set_attribute("http.response.code", code)
    span.set_attribute("http.response.message", json_result.get("message", ""))

    # 重定向时使用实际产生该响应的请求。
    req = response.request or request
    body = req.body

    try:
        authorization = json.loads(req.headers.get("x-bkapi-authorization") or "{}")
    except (TypeError, ValueError):
        try:
            authorization = json.loads(body) if body else {}
        except (TypeError, ValueError):
            authorization = {}

    username = authorization.get("bk_username") if isinstance(authorization, dict) else None
    if username:
        span.set_attribute("user.username", username)

    span.set_attribute("request.body", jsonify(body)[:MAX_PARAMS_SIZE])
