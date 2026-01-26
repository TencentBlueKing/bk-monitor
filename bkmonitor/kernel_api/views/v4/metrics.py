"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.metrics import TimeSeriesGroupListResource, ExecuteRangeQueryResource


class MetricsViewSet(ResourceViewSet):
    """
    指标相关接口
    """

    resource_routes = [
        ResourceRoute("POST", resource.strategies.get_metric_list_v2, endpoint="get_metric_list"),
        ResourceRoute("POST", TimeSeriesGroupListResource, endpoint="list_time_series_groups"),
        ResourceRoute("POST", ExecuteRangeQueryResource, endpoint="execute_range_query"),
    ]
