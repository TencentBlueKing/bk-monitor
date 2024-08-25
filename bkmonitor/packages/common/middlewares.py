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
import logging
from typing import Any, Dict, List

import pytz
from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from bkm_space.api import SpaceApi
from bkmonitor.utils.common_utils import fetch_biz_id_from_request, safe_int
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from monitor_web.tasks import active_business, record_login_user

logger = logging.getLogger(__name__)


class TimeZoneMiddleware(MiddlewareMixin):
    """
    时区处理中间件
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        timezone_exempt: bool = getattr(view_func, "timezone_exempt", False)
        if timezone_exempt:
            return

        biz_id: int = safe_int(fetch_biz_id_from_request(request, view_kwargs))
        if biz_id:
            try:
                tz_name = SpaceApi.get_space_detail(bk_biz_id=biz_id).time_zone
            except Exception:
                tz_name = settings.TIME_ZONE
            request.session[settings.TIMEZONE_SESSION_KEY] = tz_name

        tz_name = request.session.get(settings.TIMEZONE_SESSION_KEY)
        if tz_name:
            timezone.activate(pytz.timezone(tz_name))
        else:
            timezone.deactivate()


class TrackSiteVisitMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if settings.ENVIRONMENT == "development":
            return

        track_site_visit: bool = getattr(view_func, "track_site_visit", False)
        if not track_site_visit:
            return

        # 如果参数不带业务ID也不统计，节省用户直接返回站点的耗时
        request.biz_id = fetch_biz_id_from_request(request, view_kwargs)
        if not request.biz_id:
            return

        username: str = request.user.username
        source: str = getattr(request, "source", "web")
        space_info: Dict[str, Any] = {"bk_biz_id": request.biz_id}
        base_params: Dict[str, Any] = {"username": username, "space_info": space_info}

        def _run_task(_task, kwargs):
            try:
                _task.delay(**kwargs)
            except Exception:  # noqa
                logger.exception("[TrackSiteVisitMiddleware] failed to run task: task -> %s", _task)

        th_list: List[InheritParentThread] = [
            InheritParentThread(target=_run_task, args=(active_business, base_params)),
            InheritParentThread(
                target=_run_task,
                args=(record_login_user, {"source": source, "last_login": datetime.datetime.now(), **base_params}),
            ),
        ]
        run_threads(th_list)


class DisableCSRFCheck(MiddlewareMixin):
    """本地开发，去掉django rest framework强制的csrf检查"""

    def process_request(self, request):
        setattr(request, "_dont_enforce_csrf_checks", True)
        return None
