"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from bkmonitor.iam.drf import ViewBusinessPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class IncidentEventsViewSet(ResourceViewSet):
    query_post_actions = []

    def get_permissions(self):
        if self.action in ["incident_overview"]:
            return []

        # 业务开启故障分析才有权限校验，未开启不需要校验，因为查不出数据
        if self.request.biz_id in settings.AIOPS_INCIDENT_BIZ_WHITE_LIST:
            return [ViewBusinessPermission()]
        return []

    resource_routes = [
        # 故障事件接口 events
        ResourceRoute("POST", resource.incident.incident_events_search, endpoint="search"),
        # 故障事件详情接口
        ResourceRoute("POST", resource.incident.incident_events_detail, endpoint="detail"),
    ]
