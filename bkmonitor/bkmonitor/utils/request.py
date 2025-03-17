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

import json
from typing import Optional

from django.http import HttpRequest

from bkmonitor.utils.local import local
from constants.cmdb import BIZ_ID_FIELD_NAMES
from constants.common import SourceApp


def get_request_tenant_id(peaceful=False) -> Optional[str]:
    """
    获取当前请求的租户id
    """
    request = get_request(peaceful)
    if not request or not hasattr(request, "user") or not getattr(request.user, "tenant_id", None):
        if peaceful:
            return None
        else:
            raise Exception("get_request_tenant_id: cannot get tenant_id from request.")

    return request.user.tenant_id


def get_request(peaceful=False) -> Optional[HttpRequest]:
    if hasattr(local, "current_request"):
        return local.current_request
    elif peaceful:
        return None

    raise Exception("get_request: current thread hasn't request.")


def get_source_app(request=None):
    request = request or get_request(True)
    if not request:
        return SourceApp.MONITOR
    return SourceApp.FTA if request.META.get("HTTP_SOURCE_APP") == SourceApp.FTA else SourceApp.MONITOR


def get_app_code_by_request(request):
    bk_app_code = request.META.get("HTTP_BK_APP_CODE")
    if bk_app_code is None and hasattr(request, "jwt"):
        bk_app_code = request.jwt.app.app_code

    return bk_app_code


def get_x_request_id():
    x_request_id = ""
    http_request = get_request()
    if hasattr(http_request, "META"):
        meta = http_request.META
        x_request_id = meta.get("HTTP_X_REQUEST_ID", "") if isinstance(meta, dict) else ""
    return x_request_id


def fetch_biz_id_from_dict(data, default=None):
    """
    从字典对象中提取出biz_id属性
    """
    if not hasattr(data, "__getitem__"):
        return default

    for field in data:
        if field in BIZ_ID_FIELD_NAMES:
            return data[field]

    return default


def fetch_biz_id_from_request(request, view_kwargs):
    # 业务id解析方式：
    # 1. url带上业务id（monitor_adapter）
    biz_id = fetch_biz_id_from_dict(view_kwargs)
    if not biz_id:
        # 2. request.GET (resource的get方法)
        # 3. request.POST (未改造成resource的ajax的post方法)
        biz_id = fetch_biz_id_from_dict(request.POST) or fetch_biz_id_from_dict(request.GET)

    if not biz_id:
        # 4. request.body(resource的post方法)
        try:
            body_unicode = request.body.decode("utf-8")
            body = json.loads(body_unicode)
            biz_id = fetch_biz_id_from_dict(body)
        except (json.JSONDecodeError, TypeError):
            pass
    return biz_id


def get_request_username(default=""):
    try:
        username = get_request().user.username
    except Exception:
        try:
            username = local.username
        except Exception:
            username = default
    return username


def set_request_username(username):
    request = get_request(peaceful=True)
    if request:
        # 有请求对象，就设置请求对象
        request.user.username = username
    else:
        # 没有请求对象，就设置local
        local.username = username


def is_ajax_request(request):
    """
    断是否是ajax请求
    """
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
