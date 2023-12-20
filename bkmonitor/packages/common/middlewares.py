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


import datetime

import pytz
from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from bkmonitor.utils.common_utils import fetch_biz_id_from_request
from common.log import logger
from monitor_web.extend_account.models import UserAccessRecord


class TimeZoneMiddleware(MiddlewareMixin):
    """
    时区处理中间件
    """

    def process_view(self, request, view_func, view_args, view_kwargs):

        timezone_exempt: bool = getattr(view_func, "timezone_exempt", False)
        if timezone_exempt:
            return

        biz_id: int = fetch_biz_id_from_request(request, view_kwargs)
        if biz_id:
            try:
                from core.drf_resource import resource

                tz_name = resource.cc.get_app_by_id(biz_id)["TimeZone"]
            except Exception:
                tz_name = settings.TIME_ZONE
            request.session[settings.TIMEZONE_SESSION_KEY] = tz_name

        tz_name = request.session.get(settings.TIMEZONE_SESSION_KEY)
        if tz_name:
            timezone.activate(pytz.timezone(tz_name))
        else:
            timezone.deactivate()


class ActiveBusinessMiddleware(MiddlewareMixin):
    """
    活跃业务中间件（用来记录活跃业务以及业务的最后访问者）
    """

    def process_view(self, request, view_func, view_args, view_kwargs):

        track_site_visit: bool = getattr(view_func, "track_site_visit", False)
        if not track_site_visit:
            return

        request.biz_id = fetch_biz_id_from_request(request, view_kwargs)
        if request.biz_id:
            try:
                from utils import business

                business.activate(int(request.biz_id), request.user.username)
            except Exception as e:
                logger.error("活跃业务激活失败, biz_id:{biz_id}, error:{error}".format(biz_id=request.biz_id, error=e))


class RecordLoginUserMiddleware(MiddlewareMixin):
    """
    记录用户访问时间中间件
    """

    def process_view(self, request, view_func, view_args, view_kwargs):

        track_site_visit: bool = getattr(view_func, "track_site_visit", False)
        if not track_site_visit:
            return

        user = request.user
        if not user:
            return
        try:
            user.last_login = datetime.datetime.now()
            user.save()

            UserAccessRecord.objects.update_or_create_by_request(request)
        except Exception:
            pass


class DisableCSRFCheck(MiddlewareMixin):
    """本地开发，去掉django rest framework强制的csrf检查"""

    def process_request(self, request):
        setattr(request, "_dont_enforce_csrf_checks", True)
        return None
