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

from __future__ import absolute_import, unicode_literals

from common.log import logger
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.drf_resource import resource


def home(request):
    """
    首页
    """
    biz_id_list = resource.cc.get_app_ids_by_user(request.user)
    if not biz_id_list:
        cc_biz_id = settings.DEMO_BIZ_ID
        logger.info("用户:%s 没有任何业务权限." % request.user)
    else:
        cc_biz_id = request.GET.get("bizId") or request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
        if cc_biz_id not in biz_id_list:
            cc_biz_id = biz_id_list[0]

    # 校验bk_biz_id是否合法
    try:
        cc_biz_id = int(cc_biz_id)
    except (ValueError, TypeError):
        raise HttpResponseForbidden("error biz id")

    response = render(request, "fta/index.html", {"cc_biz_id": cc_biz_id})

    if biz_id_list:
        response.set_cookie("bk_biz_id", str(cc_biz_id))

    return response
