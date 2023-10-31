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
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^$", views.GrafanaSwitchOrgView.as_view()),
    url(r"^home$", views.GrafanaSwitchOrgView.as_view()),
    url(r"^d/[a-zA-Z_0-9]+$", views.GrafanaSwitchOrgView.as_view()),
    url(r"^public/", views.StaticView.as_view()),
    url(r"^avatar/", views.StaticView.as_view()),
    url(r"^api/", views.ApiProxyView.as_view()),
    url("^dashboard$", views.RedirectDashboardView.as_view()),
    url(r"^", views.GrafanaProxyView.as_view()),
]
