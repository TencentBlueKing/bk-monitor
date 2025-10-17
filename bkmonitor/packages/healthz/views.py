"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.shortcuts import render
from rest_framework import permissions

from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.utils.request import get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


def index(request, cc_biz_id):
    return render(request, "/monitor/healthz/dashboard.html", {"cc_biz_id": cc_biz_id})


class AlarmConfig(ResourceViewSet):
    def get_permissions(self):
        # 非运营租户禁止访问全局配置
        if get_request_tenant_id() != DEFAULT_TENANT_ID:
            return [permissions.NOT(permissions.AllowAny())]

        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_GLOBAL_SETTING])]
        return [BusinessActionPermission([ActionEnum.MANAGE_GLOBAL_SETTING])]

    resource_routes = [
        ResourceRoute("GET", resource.healthz.get_alarm_config),
        ResourceRoute("POST", resource.healthz.update_alarm_config),
    ]
