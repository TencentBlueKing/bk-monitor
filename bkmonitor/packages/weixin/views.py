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


from django.conf import settings
from django.shortcuts import render

from common.decorators import track_site_visit


@track_site_visit
def home(request):
    return render(request, "weixin/index.html", {"ENABLE_CONSOLE": settings.ENABLE_CONSOLE})


def service_worker(request):
    return render(request, "weixin/service-worker.js", content_type="application/javascript")


def manifest(request):
    return render(request, "weixin/manifest.json", content_type="application/json")
