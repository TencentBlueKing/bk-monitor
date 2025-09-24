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


import os

import six
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from rest_framework.documentation import include_docs_urls
from six.moves import map

from bk_dataview.views import ProxyView, StaticView, SwitchOrgView
from bkmonitor.utils.common_utils import package_contents
from core.drf_resource.routers import ResourceRouter
from kernel_api import views
from monitor_web.grafana import views as grafana_views

try:
    from kernel_api import extend_views
except ImportError:
    extend_views = None

ROOT_MODULE = "kernel_api.views"
API_NAMESPACE = "api"
DEFAULT_INSTALLED_APIS = [
    "collector",
    "meta",
    "models",
    "query",
]
# 不同模块api 在环境变量设置INSTALLED_APIS
INSTALLED_APIS = [x for x in os.getenv("INSTALLED_APIS", "").split(",") if x] or DEFAULT_INSTALLED_APIS


def register_url(prex, views_module_list, namespace):
    if not isinstance(views_module_list, list):
        views_module_list = [views_module_list]

    views_module_list = [
        __import__(views_module, fromlist=["*"]) if isinstance(views_module, six.string_types) else views_module
        for views_module in views_module_list
    ]

    router = ResourceRouter()
    list(map(router.register_module, views_module_list))
    return re_path(prex, include((router.urls, "kernel_api"), namespace=namespace))


def register_v2():
    views_modules = [views.v2]
    if settings.ALLOW_EXTEND_API and extend_views:
        views_modules.append(extend_views)

    urlpatterns.append(register_url(r"^api/v2/", views_modules, f"{API_NAMESPACE}.v2"))


def register_v3():
    ROOT_MODULE_V3 = ROOT_MODULE + ".v3"
    apis = {m: "{}.{}".format(ROOT_MODULE_V3, m) for m in package_contents(ROOT_MODULE_V3) if m in INSTALLED_APIS}
    if settings.ALLOW_EXTEND_API and extend_views:
        apis["extend"] = extend_views

    for name, sub_module in list(apis.items()):
        urlpattern = register_url(r"^api/v3/%s/" % name, sub_module, namespace="{}.v3.{}".format(API_NAMESPACE, name))
        urlpatterns.append(urlpattern)


def register_v4():
    views_modules = [views.v4]
    if settings.ALLOW_EXTEND_API and extend_views:
        views_modules.append(extend_views)

    urlpatterns.append(register_url(r"^api/v4/", views_modules, f"{API_NAMESPACE}.v4"))


router = ResourceRouter()
router.register_module(grafana_views)


@login_exempt
def ping(request):
    return HttpResponse("pong")


urlpatterns = [
    re_path(r"^ping$", ping),
    re_path(r"^account/", include("blueapps.account.urls")),
    path(r"admin/", admin.site.urls),
    re_path(r"^docs/", include_docs_urls(title="My API title", public=True)),
    re_path(r"^grafana/$", SwitchOrgView.as_view()),
    re_path(r"^grafana/public/", StaticView.as_view()),
    re_path(r"^grafana/", ProxyView.as_view()),
    re_path(r"^o/bk_monitorv3/grafana/$", SwitchOrgView.as_view()),
    re_path(r"^o/bk_monitorv3/grafana/public/", StaticView.as_view()),
    re_path(r"^o/bk_monitorv3/grafana/", ProxyView.as_view()),
    re_path(r"^rest/v2/", include(router.urls)),
    re_path(r"^o/bk_monitorv3/rest/v2/", include(router.urls)),
    re_path(r"^query-api/rest/v2/", include(router.urls)),
    re_path(r"^o/bk_monitorv3/query-api/rest/v2/", include(router.urls)),
    re_path(r"^query-api/o/bk_monitorv3/rest/v2/", include(router.urls)),
    re_path(r"^apm_api/v1/", include("apm.urls")),
]


register_v2()
register_v3()
register_v4()
