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
from io import StringIO
from typing import Any, Dict
from urllib import parse

from django.http import HttpResponse
from rest_framework.decorators import action

from apm_web.event import resources
from apm_web.event.serializers import EventTopKRequestSerializer
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.data_explorer.event.mock_data import API_TOPK_RESPONSE


class EventViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self):
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", resources.EventLogsResource, endpoint="logs"),
        ResourceRoute("POST", resources.EventTopKResource, endpoint="topk"),
        ResourceRoute("POST", resources.EventTotalResource, endpoint="total"),
        ResourceRoute("POST", resources.EventViewConfigResource, endpoint="view_config"),
        ResourceRoute("POST", resources.EventTimeSeriesResource, endpoint="time_series"),
        ResourceRoute("POST", resources.EventTagsResource, endpoint="tags"),
    ]

    @action(methods=["POST"], detail=False, url_path="download_topk")
    def download_topk(self, request, *args, **kwargs):
        # TODO 和数据探索侧的事件逻辑重合，这里需要抽象公共逻辑。
        s = EventTopKRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        validated_data: Dict[str, Any] = s.validated_data

        output = StringIO()
        for item in API_TOPK_RESPONSE[0]["list"]:
            output.write(f"{item['value']},{item['count']},{item['proportions']:.2f}%\n")

        table: str = validated_data["query_configs"][0]["table"]
        file_name = f"{table}_{validated_data['fields'][0]}.txt"
        file_name = parse.quote(file_name, encoding="utf8")
        file_name = parse.unquote(file_name, encoding="ISO8859_1")

        response = HttpResponse(output.getvalue())
        response["Content-Type"] = "application/x-msdownload"
        response["Content-Disposition"] = 'attachment;filename="{}"'.format(file_name)
        return response
