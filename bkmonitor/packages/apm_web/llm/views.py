"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm_web.decorators import user_visit_record
from apm_web.llm.resources import (
    CalculateByRangeResource,
    ListFlowsResource,
    ListSpansResource,
    ListTracesResource,
    TokenStatisticsResource,
    TimeSeriesResource,
)
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class LLMViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self) -> list[InstanceActionForDataPermission]:
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute(
            "POST",
            ListTracesResource,
            endpoint="list_traces",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute("POST", ListSpansResource, endpoint="list_spans"),
        ResourceRoute(
            "POST",
            ListFlowsResource,
            endpoint="list_flows",
            decorators=[
                user_visit_record,
            ],
        ),
        ResourceRoute("POST", TokenStatisticsResource, endpoint="token_statistics"),
        ResourceRoute("POST", TimeSeriesResource, endpoint="time_series"),
        ResourceRoute(
            "POST",
            CalculateByRangeResource,
            endpoint="calculate_by_range",
            decorators=[
                user_visit_record,
            ],
        ),
    ]
