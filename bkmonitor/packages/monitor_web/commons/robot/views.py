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
import os

import requests

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework import status
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from rest_framework.decorators import api_view


class FetchRobotInfoViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]

    resource_routes = [
        ResourceRoute("GET", resource.commons.fetch_robot_info),
    ]


@api_view(["POST"])
def llm(request):
    data = request.data
    headers = {
        "APP-CODE": settings.APP_CODE,
        "APP-SECRET": settings.APP_TOKEN
    }

    target_url = os.getenv("LLM_TARGET_URL")

    try:
        response = requests.post(target_url, json=data, headers=headers, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    def event_stream():
        for line in response.iter_lines(chunk_size=10):
            if line:
                result = line.decode('utf-8') + '\n\n'
                yield result

    # 返回 StreamingHttpResponse
    sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    sr.headers["Cache-Control"] = "no-cache"
    sr.headers["X-Accel-Buffering"] = "no"
    return sr