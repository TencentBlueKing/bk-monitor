"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rest_framework.decorators import action

from apm_web.decorators import user_visit_record
from apm_web.event import resources
from apm_web.event.serializers import EventDownloadTopKRequestSerializer
from apm_web.models import Application
from apm_web.utils import generate_csv_file_download_response
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


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
        ResourceRoute(
            "POST", resources.EventTimeSeriesResource, endpoint="time_series", decorators=[user_visit_record]
        ),
        ResourceRoute("POST", resources.EventTagDetailResource, endpoint="tag_detail", decorators=[user_visit_record]),
        ResourceRoute("POST", resources.EventGetTagConfigResource, endpoint="get_tag_config"),
        ResourceRoute(
            "POST", resources.EventUpdateTagConfigResource, endpoint="update_tag_config", decorators=[user_visit_record]
        ),
        ResourceRoute("POST", resources.EventStatisticsInfoResource, endpoint="statistics_info"),
        ResourceRoute("POST", resources.EventStatisticsGraphResource, endpoint="statistics_graph"),
    ]

    @action(methods=["POST"], detail=False, url_path="download_topk")
    def download_topk(self, request, *args, **kwargs):
        serializer = EventDownloadTopKRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data: dict[str, Any] = serializer.validated_data
        api_topk_response = resources.EventTopKResource().perform_request(validated_data)
        return generate_csv_file_download_response(
            f"bkmonitor_{validated_data['query_configs'][0]['table']}_{validated_data['fields'][0]}.csv",
            ([item["value"], item["count"], f"{item['proportions']}%"] for item in api_topk_response[0]["list"]),
        )
