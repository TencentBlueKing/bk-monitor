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


from django.conf import settings
from bkmonitor.utils.request import get_request, get_app_code_by_request


def get_source_app_code():
    """
    获取来源APP_CODE
    """
    try:
        request = get_request()
        bk_app_code = get_app_code_by_request(request)
    except Exception:
        bk_app_code = settings.APP_CODE

    if not bk_app_code:
        bk_app_code = settings.APP_CODE

    return bk_app_code
