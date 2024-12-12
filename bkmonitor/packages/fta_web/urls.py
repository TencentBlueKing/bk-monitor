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

from django.urls import include, re_path

from fta_web.views import home

app_name = "fta_web"

urlpatterns = [
    re_path(r"^$", home),
    re_path(r"^plugin/", include("fta_web.event_plugin.urls")),
    re_path(r"^alert/", include("fta_web.alert.urls")),
    re_path(r"^action/", include("fta_web.action.urls")),
    re_path(r"^assign/", include("fta_web.assign.urls")),
    re_path(r"^home/", include("fta_web.home.urls")),
]
