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
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework.views import APIView


class BkLogForwardingView(APIView):
    """转发请求到日志平台"""

    def dispatch(self, request, *args, **kwargs):

        target_url = urljoin(settings.BKLOGSEARCH_HOST, request.path.split('bklog')[-1])

        try:
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                params={key: request.GET.get(key) for key in request.GET},
                data=request.body if request.body else None,
                allow_redirects=False,
            )
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:  # noqa
            return JsonResponse(
                {
                    "message": _("请求日志平台接口错误: ") + str(e),
                    "code": 500,
                    "data": None,
                    "result": False,
                },
                status=500,
            )
