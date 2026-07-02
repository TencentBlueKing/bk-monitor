"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.operation import (
    GetOperationMetricResource,
    GetOperationOverviewResource,
    ListOperationMetricsResource,
)


class OperationViewSet(ResourceViewSet):
    """
    运营数据相关接口 (用于 AI MCP 请求)
    """

    resource_routes = [
        ResourceRoute("POST", ListOperationMetricsResource, endpoint="list_operation_metrics"),
        ResourceRoute("POST", GetOperationMetricResource, endpoint="get_operation_metric"),
        ResourceRoute("POST", GetOperationOverviewResource, endpoint="get_operation_overview"),
    ]
