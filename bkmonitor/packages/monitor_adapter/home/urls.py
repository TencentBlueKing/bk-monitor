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

from monitor_adapter.home import views

urlpatterns = [
    url(r"^$", views.home),
    url(r"^e/$", views.event_center_proxy),
    url(r"^route/$", views.path_route_proxy),
    url(r"^static/monitor/$", views.home),
    url(r"^external/$", views.external),
    url(r"^external_callback/$", views.external_callback),
    url(r"^report_callback/$", views.report_callback),
    url(r"^dispatch_external_proxy/$", views.dispatch_external_proxy),
    url(r"^service-worker.js$", views.service_worker),
    url(r"^manifest.json$", views.manifest),
    url(r"^logout/?$", views.user_exit),
]
