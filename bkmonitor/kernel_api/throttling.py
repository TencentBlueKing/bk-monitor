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
from django.conf import settings
from django.core.cache import caches, cache
from rest_framework import throttling

from bkmonitor.utils.request import get_app_code_by_request

try:
    mem_cache = caches["locmem"]
except Exception:
    mem_cache = cache


class AppCodeThrottle(throttling.SimpleRateThrottle):
    """ """

    cache = mem_cache
    scope = "app_code"

    # 白名单以外的应用，直接不允许请求
    rate = "0/m"

    def get_cache_key(self, request, view):
        bk_app_code = get_app_code_by_request(request)

        if not bk_app_code or not settings.THROTTLE_APP_WHITE_LIST or bk_app_code in settings.THROTTLE_APP_WHITE_LIST:
            # 3种情况豁免流控
            # 1. 取不到APP_CODE
            # 2. 白名单为空
            # 3. 白名单不为空，且当前请求在白名单内
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": bk_app_code,
        }
