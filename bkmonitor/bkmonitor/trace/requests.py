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

from blueapps.opentelemetry.instrumentor import requests_callback
from opentelemetry.trace import Span


def requests_span_callback(span: Span, response):
    requests_callback(span, response)
    if not response:
        return

    req = response.request

    body = None
    if req.body:
        try:
            body = req.body.decode() if isinstance(req.body, bytes) else str(body)
            span.set_attribute("request.body", body)
        except Exception:  # noqa
            pass

    try:
        authorization_header = req.headers.get("x-bkapi-authorization")
        if authorization_header:
            username = json.loads(authorization_header).get("bk_username")
            if username:
                span.set_attribute("user.username", username)
    except (TypeError, json.JSONDecodeError):
        if body:
            try:
                username = json.loads(body).get("bk_username")
                if username:
                    span.set_attribute("user.username", username)
            except (TypeError, json.JSONDecodeError):
                pass


def requests_name_callback(method, _):
    return f"REQUESTS.HTTP {method.strip()}"
