"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework.decorators import action

from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from bkmonitor.utils.csv import generate_csv_file_download_response
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from rum_web.models.application import Application
from rum_web.query.resources import (
    RumFieldsOptionValuesResource,
    RumGenerateQueryStringResource,
    RumRecordsResource,
    RumViewConfigResource,
    RumFieldsTopKResource,
    RumFieldStatisticsInfoResource,
    RumFieldStatisticsGraphResource,
)
from rum_web.query.serializers import RumDownloadTopKRequestSerializer


class SearchViewSet(ResourceViewSet):
    """RUM 统一检索接口"""

    INSTANCE_ID = "app_name"

    def get_permissions(self):
        if self.action == "generate_query_string":
            return []
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_RUM_APPLICATION],
                ResourceEnum.RUM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", RumRecordsResource, endpoint="list_records"),
        ResourceRoute("GET", RumViewConfigResource, endpoint="view_config"),
        ResourceRoute("POST", RumFieldsOptionValuesResource, endpoint="get_fields_option_values"),
        ResourceRoute("POST", RumGenerateQueryStringResource, endpoint="generate_query_string"),
        ResourceRoute("POST", RumFieldsTopKResource, endpoint="fields_topk"),
        ResourceRoute("POST", RumFieldStatisticsInfoResource, endpoint="field_statistics_info"),
        ResourceRoute("POST", RumFieldStatisticsGraphResource, endpoint="field_statistics_graph"),
    ]

    @action(methods=["POST"], detail=False, url_path="download_topk")
    def download_topk(self, request, *args, **kwargs):
        s = RumDownloadTopKRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        validated_data: dict = s.validated_data
        topk_data = RumFieldsTopKResource().perform_request(validated_data)

        file_name = f"topk_{validated_data['bk_biz_id']}_{validated_data['app_name']}_{validated_data['fields'][0]}.csv"
        file_content = ([item["value"], item["count"], f"{item['proportions']}%"] for item in topk_data[0]["list"])
        response = generate_csv_file_download_response(file_name, file_content)

        return response
