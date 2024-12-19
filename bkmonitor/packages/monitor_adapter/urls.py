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
from blueapps.account.decorators import login_exempt
from django.http import HttpResponse
from django.urls import include, re_path

app_name = "monitor_adapter"


@login_exempt
def ping(request):
    return HttpResponse("pong")


urlpatterns = [
    re_path(r"^", include("monitor_adapter.home.urls")),
    re_path(r"^", include("monitor_adapter.api.urls")),
    re_path(r"^grafana/", include("monitor_adapter.grafana.urls")),
    re_path(r"^", include("healthz.urls")),
    re_path(r"^rest/v1/", include("healthz.urls")),
    re_path(r"^ping$", ping),
]
