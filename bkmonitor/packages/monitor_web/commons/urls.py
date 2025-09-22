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


from django.urls import include, re_path

from bkm_ipchooser import views as ip_views
from core.drf_resource.routers import ResourceRouter
from monitor_web.commons.biz import views as biz_views
from monitor_web.commons.bkdocs import views as bkdocs_views
from monitor_web.commons.cc import views as cc_views
from monitor_web.commons.context import views as context_views
from monitor_web.commons.data import views as data_views
from monitor_web.commons.html import views as html_views
from monitor_web.commons.report import views as report_views
from monitor_web.commons.robot import views as robot_views
from monitor_web.commons.task import views as task_views
from monitor_web.commons.token import views as token_views
from monitor_web.commons.user import views as user_views

router = ResourceRouter()
router.register_module(biz_views)
router.register_module(cc_views)
router.register_module(data_views)
router.register_module(task_views)
router.register_module(context_views)
router.register_module(bkdocs_views)
router.register_module(html_views)
router.register_module(user_views)
router.register_module(ip_views)
router.register_module(robot_views)
router.register_module(token_views)
router.register_module(report_views)


urlpatterns = [
    re_path(r"^", include(router.urls)),
]
