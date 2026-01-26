"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
import os

from bk_notice_sdk import config as notice_config
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import re_path
from django.views import static
from version_log import config

urlpatterns = [
    re_path(r"^bklog_manage/", admin.site.urls),
    re_path(r"^account/", include("blueapps.account.urls")),
    re_path(r"^console/", include("console.urls")),
    # 通用
    re_path(r"^api/v1/", include("apps.log_commons.urls")),
    # 接口
    re_path(r"^api/v1/iam/", include("apps.iam.urls")),
    re_path(r"^api/v1/databus/", include("apps.log_databus.urls")),
    # trace
    re_path(r"^api/v1/trace/", include("apps.log_trace.urls")),
    re_path(r"^api/v1/", include("apps.log_search.urls")),
    re_path(r"^api/v1/", include("apps.log_esquery.urls")),
    re_path(r"^api/v1/", include("apps.esb.urls")),
    re_path(r"^api/v1/", include("apps.bk_log_admin.urls")),
    re_path(r"^api/v1/", include("apps.log_bcs.urls")),
    re_path(r"^api/v1/", include("apps.log_clustering.urls")),
    re_path(r"^api/v1/", include("apps.log_desensitize.urls")),
    re_path(r"^api/v1/", include("apps.ai_assistant.urls")),
    re_path(r"^api/v1/", include("apps.log_unifyquery.urls")),
    re_path(r"^", include("apps.grafana.urls")),
    re_path(r"^", include("log_adapter.urls")),
    # 前端页面
    re_path(r"^", include("home_application.urls")),
    # celery flower
    re_path(r"^flower/", include("flower_proxy.urls")),
    re_path(rf"^{config.ENTRANCE_URL}", include("version_log.urls")),
    re_path(r"^api/v1/log_extract/", include("apps.log_extract.urls")),
    re_path(r"^api/v1/", include("apps.log_measure.urls")),
    re_path(r"^api/v1/ipchooser/", include("bkm_ipchooser.urls")),
    re_path(r"^api/v1/search_module/", include("bkm_search_module.urls")),
    re_path(rf"^{notice_config.ENTRANCE_URL}", include(("bk_notice_sdk.urls", "notice"), namespace="notice")),
]

if os.environ.get("BKAPP_FEATURE_TGPA_TASK", "off") == "on":
    urlpatterns.extend(
        [re_path(r"^api/v1/", include("apps.tgpa.urls"))]
    )

if settings.IS_K8S_DEPLOY_MODE:
    urlpatterns.extend(
        [re_path(r"^static/(?P<path>.*)$", static.serve, {"document_root": settings.STATIC_ROOT}, name="static")]
    )
