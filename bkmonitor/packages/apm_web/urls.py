# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf.urls import include, url

from apm_web.views import apm_home

app_name = "apm_web"

urlpatterns = [
    url(r"^$", apm_home),
    url(r"meta/", include("apm_web.meta.urls")),
    url(r"^trace_api/", include("apm_web.trace.urls")),
    url(r"^profile_api/", include("apm_web.profile.urls")),
    url(r"^metric/", include("apm_web.metric.urls")),
    url(r"^topo/", include("apm_web.topo.urls")),
    url(r"^service/", include("apm_web.service.urls")),
    url(r"^service_log/", include("apm_web.log.urls")),
    url(r"^service_db/", include("apm_web.db.urls")),
]
