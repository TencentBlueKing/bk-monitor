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
import requests
import version_log.config as config
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.decorators.http import require_GET
from django.views.static import serve
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from core.prometheus.tools import get_metric_agg_gateway_url


def wrapped_serve(*args, **kwargs):
    response = serve(*args, **kwargs)
    if response.get("Content-Type") == "application/x-tar" and response.has_header("Content-Encoding"):
        # 删除编码，防止浏览器侧直接对tgz文件解压
        del response["Content-Encoding"]
    return response


schema_view = get_schema_view(
    openapi.Info(
        title="BkMonitor API",
        default_version="v1",
        description="BkMonitor API",
        terms_of_service="https://bk.tencent.com/",
    ),
    public=True,
    permission_classes=(permissions.IsAdminUser,),
)


@require_GET
@login_exempt
def metrics(request):
    gateway_url = get_metric_agg_gateway_url()
    if not gateway_url:
        return HttpResponse("Fetch metrics error: `METRIC_AGG_GATEWAY_URL` is not set, please check!")
    response = requests.get(f"http://{gateway_url.strip('/')}/metrics")
    response.raise_for_status()
    return HttpResponse(response.text, content_type="text/plain")


urlpatterns = [
    re_path(r"^account/", include("blueapps.account.urls")),
    path("admin/", admin.site.urls, name="admin"),
    path("manage/", admin.site.urls, name="manage"),
    path("rest/v1/", include("monitor_api.urls", namespace="monitor_api")),
    re_path(r"^weixin/", include("weixin.urls", namespace="weixin")),
    re_path(r"^", include("monitor_adapter.urls", namespace="monitor_adapter")),
    re_path(r"^", include("calendars.urls", namespace="calendar")),
    re_path(r"^rest/v2/", include("monitor_web.urls", namespace="monitor_web")),
    # 查询专用API路由
    re_path(r"^query-api/rest/v2/", include("monitor_web.urls", namespace="monitor_web")),
    re_path(r"^fta/", include("fta_web.urls", namespace="fta_web")),
    re_path(r"^apm/", include("apm_web.urls", namespace="apm_web")),
    re_path(r"^apm_log_forward/", include("apm_web.log_proxy.urls", namespace="log_proxy")),
    re_path(r"^trace/", include("apm_trace.urls", namespace="apm_trace")),
    re_path(r"^{}".format(config.ENTRANCE_URL), include("version_log.urls")),
    re_path(r"^media/(?P<path>.*)$", wrapped_serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^metrics/$", metrics),
    # env: `BK_API_URL_TMPL` must be set
    re_path(r'^notice/', include(('bk_notice_sdk.urls', 'notice'), namespace='notice')),
]

# 添加API访问子路径
if settings.API_SUB_PATH:
    urlpatterns.append(
        re_path(rf"^{settings.API_SUB_PATH}rest/v2/", include("monitor_web.urls", namespace="monitor_web"))
    )
    urlpatterns.append(
        re_path(rf"^{settings.API_SUB_PATH}query-api/rest/v2/", include("monitor_web.urls", namespace="monitor_web"))
    )

# 正式环境屏蔽swagger访问路径
if settings.ENVIRONMENT != "production":
    urlpatterns += [
        re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
        re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
        re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    ]
