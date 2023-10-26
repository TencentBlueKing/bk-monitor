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

import arrow
from blueapps.account.decorators import login_exempt
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from utils import business
from utils.business import human_readable_biz

from bkmonitor.utils.common_utils import DatetimeEncoder


@login_exempt
def status_business(request):
    """
    Business status
    """
    business_info = business.get_all_business()
    all_business_last_visited = [
        (b[0], arrow.get(b[1]).to(timezone.get_current_timezone().zone).format("YYYY-MM-DD HH:mm:ss"))
        for b in business_info
    ]
    active_business_list = business.get_all_activate_business()
    data = {
        "num_of_active_business": len(active_business_list),
        "active_business_list": human_readable_biz(active_business_list),
        "all_business_last_visited": all_business_last_visited,
    }
    return JsonResponse({"data": data})


def status_settings(request):
    """
    获取settings(需管理员权限访问)
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden()

    from django.conf import settings

    ret = {}
    for attr in sorted(dir(settings)):
        val = getattr(settings, attr)
        if not attr.startswith("_") and isinstance(val, (int, str, tuple, list, dict)):
            try:
                _ = json.dumps(val, cls=DatetimeEncoder)
            except Exception:  # noqa
                continue
            ret[attr] = val

    return JsonResponse(ret)
