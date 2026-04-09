"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.metric.resources import RumAlertQueryResource
from bkmonitor.iam.drf import ViewBusinessPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetricViewSet(ResourceViewSet):
    """RUM 指标查询接口"""

    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        # 1.19 告警时间带查询
        ResourceRoute("POST", RumAlertQueryResource, endpoint="alert_query"),
    ]
