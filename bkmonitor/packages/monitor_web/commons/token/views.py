# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from monitor_web.grafana.permissions import GrafanaWritePermission

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class TokenManagerViewSet(ResourceViewSet):
    """
    API 调用凭证管理
    """

    def get_permissions(self):
        return [
            GrafanaWritePermission(BusinessActionPermission([ActionEnum.MANAGE_RULE, ActionEnum.VIEW_BUSINESS])),
        ]

    resource_routes = [
        ResourceRoute("GET", resource.commons.get_api_token, endpoint="get_api_token"),
    ]
