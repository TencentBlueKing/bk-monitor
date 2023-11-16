# -*- coding: utf-8 -*-
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
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import time

import requests
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_commons.exceptions import BaseCommonsException
from apps.log_commons.serializers import FrontendEventSerializer

# 用户白皮书在文档中心的根路径
DOCS_USER_GUIDE_ROOT = "日志平台"

DOCS_LIST = ["产品白皮书", "应用运维文档", "开发架构文档"]

DEFAULT_DOC = DOCS_LIST[0]


@login_exempt
def get_docs_link(request):
    md_path = request.GET.get("md_path", "").strip("/")
    if not md_path:
        e = BaseCommonsException(_("md_path参数不能为空"))
        return JsonResponse({"result": False, "code": e.code, "message": str(e)})

    docs_list = [str(i) for i in DOCS_LIST]
    if md_path.split("/", 1)[0] in docs_list:
        if not md_path.startswith(DOCS_USER_GUIDE_ROOT):
            md_path = "/".join([DOCS_USER_GUIDE_ROOT, md_path])
    else:
        md_path = "/".join([DOCS_USER_GUIDE_ROOT, DEFAULT_DOC, md_path])

    doc_url = f"{settings.BK_DOC_URL.rstrip('/')}/markdown/{md_path.lstrip('/')}"
    return JsonResponse({"result": True, "code": 0, "message": "OK", "data": doc_url})


class FrontendEventViewSet(APIViewSet):
    @action(detail=False, methods=["POST"], url_path="report")
    def report(self, request):
        params = self.params_valid(FrontendEventSerializer)
        if not settings.FRONTEND_REPORT_DATA_ID or not settings.FRONTEND_REPORT_DATA_TOKEN:
            return Response("report config does not set")

        host = settings.FRONTEND_REPORT_DATA_URL or settings.BKMONITOR_CUSTOM_PROXY_IP
        if not host:
            return Response("report config does not set")

        url = f"{host}/v2/push/"

        params["dimensions"]["app_code"] = settings.APP_CODE
        report_data = {
            "data_id": int(settings.FRONTEND_REPORT_DATA_ID),
            "access_token": settings.FRONTEND_REPORT_DATA_TOKEN,
            "data": [
                {
                    "dimension": params["dimensions"],
                    "event_name": params["event_name"],
                    "event": {"content": params["event_content"]},
                    "target": params["target"],
                    "timestamp": params.get("timestamp", int(time.time() * 1000)),
                }
            ],
        }
        r = requests.post(url, json=report_data, timeout=3)
        return Response(r.json())
