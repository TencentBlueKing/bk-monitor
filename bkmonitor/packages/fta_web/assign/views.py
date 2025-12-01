"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging

from rest_framework import permissions, viewsets

from bkmonitor.action import serializers
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission, IAMPermission
from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.action import GLOBAL_BIZ_ID
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

logger = logging.getLogger("root")


class AssignGroupViewSet(viewsets.ModelViewSet):
    """告警分派规则组"""

    queryset = AlertAssignGroup.objects.all().order_by("-priority")
    serializer_class = serializers.AssignGroupSlz

    filterset_fields = {
        "name": ["exact", "icontains"],
        "priority": ["exact"],
    }
    pagination_class = None

    def check_object_permissions(self, request, obj):
        if (
            int(obj.bk_biz_id) == GLOBAL_BIZ_ID
            and get_request_tenant_id() != DEFAULT_TENANT_ID
            and self.request.method not in permissions.SAFE_METHODS
        ):
            permission = IAMPermission([ActionEnum.MANAGE_GLOBAL_SETTING])
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(request, message=getattr(permission, "message", None))
        else:
            super().check_object_permissions(request, obj)

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]

    def list(self, request, *args, **kwargs):
        request_biz_id = request.query_params.get("bk_biz_id", 0)
        if request_biz_id:
            self.queryset = self.queryset.filter(bk_biz_id__in=[GLOBAL_BIZ_ID, request_biz_id])
        response = super().list(request, *args, **kwargs)
        return response

    def perform_destroy(self, instance):
        AlertAssignRule.objects.filter(assign_group_id=instance.id).delete()
        super().perform_destroy(instance)


class AssignRuleViewSet(viewsets.ModelViewSet):
    queryset = AlertAssignRule.objects.all()
    serializer_class = serializers.AssignRuleSlz

    filterset_fields = {
        "assign_group_id": ["exact"],
    }

    def check_object_permissions(self, request, obj):
        # 如果请求的业务ID为0且进行变更，则需要检查全局配置管理权限，且必须是运营租户
        if (
            int(obj.bk_biz_id) == GLOBAL_BIZ_ID
            and get_request_tenant_id() != DEFAULT_TENANT_ID
            and self.request.method not in permissions.SAFE_METHODS
        ):
            permission = IAMPermission([ActionEnum.MANAGE_GLOBAL_SETTING])
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(request, message=getattr(permission, "message", None))
        else:
            super().check_object_permissions(request, obj)

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]

    def get_queryset(self):
        queryset = super().get_queryset()
        request = get_request(peaceful=True)
        biz_list = [request.biz_id, GLOBAL_BIZ_ID] if request.biz_id else [GLOBAL_BIZ_ID]
        queryset = queryset.filter(bk_biz_id__in=biz_list)
        assign_group_ids = self.request.query_params.get("assign_group_ids")
        if assign_group_ids and isinstance(assign_group_ids, str):
            assign_group_ids = json.loads(assign_group_ids)
        if assign_group_ids or self.request.query_params.get("assign_group_id"):
            self.pagination_class = None
            if assign_group_ids:
                queryset = queryset.filter(assign_group_id__in=assign_group_ids)
        return queryset


class RuleOperateViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["batch_update", "match_debug"]:
            return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]
        return [BusinessActionPermission([ActionEnum.VIEW_RULE])]

    resource_routes = [
        ResourceRoute("POST", resource.assign.batch_update, endpoint="batch_update"),
        ResourceRoute("POST", resource.assign.match_debug, endpoint="match_debug"),
        ResourceRoute("GET", resource.assign.get_assign_condition_keys, endpoint="get_assign_condition_keys"),
    ]


class CmdbObjectAttributeViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.assign.search_object_attribute, endpoint="search_object_attribute")
    ]
