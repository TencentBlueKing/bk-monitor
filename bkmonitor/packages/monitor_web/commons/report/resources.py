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
import time

import requests
from django.conf import settings
from rest_framework import serializers

from core.drf_resource import Resource


class FrontendReportEventResource(Resource):
    """
    前端事件上报
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        dimensions = serializers.DictField(label="维度信息", required=False, default={})
        event_name = serializers.CharField(label="事件名称", required=True)
        event_content = serializers.CharField(label="事件内容", allow_blank=True, default="")
        timestamp = serializers.IntegerField(label="事件时间戳(ms)", required=False)

    def perform_request(self, params):
        # 上报数据ID不存在则不上报
        if not settings.FRONTEND_REPORT_DATA_ID or not settings.FRONTEND_REPORT_DATA_TOKEN:
            return

        # 获取上报地址
        if not settings.FRONTEND_REPORT_DATA_HOST:
            if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
                host = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN[0]
            elif settings.CUSTOM_REPORT_DEFAULT_PROXY_IP:
                host = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP[0]
            else:
                return
            host = f"{host}:10205"
        else:
            host = settings.FRONTEND_REPORT_DATA_HOST

        url = f"http://{host}/v2/push/"

        params["dimensions"]["app_code"] = settings.APP_CODE
        params["target"] = settings.ENVIRONMENT_CODE
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
        return r.json()
