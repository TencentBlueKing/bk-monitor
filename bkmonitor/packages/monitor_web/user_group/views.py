# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework import permissions, viewsets

from bkmonitor.action import serializers
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import DutyRule, UserGroup
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class UserGroupPermissionViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        """
        获取权限
        """
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_NOTIFY_TEAM])]
        return [BusinessActionPermission([ActionEnum.MANAGE_NOTIFY_TEAM])]


class UserGroupViewSet(UserGroupPermissionViewSet):
    """用户组配置视图"""

    queryset = UserGroup.objects.all()
    serializer_class = serializers.UserGroupDetailSlz

    filter_fields = {"bk_biz_id": ["exact", "in"], "name": ["exact", "icontains"]}
    pagination_class = None

    def get_queryset(self):
        """
        增加对轮值规则的过滤
        """
        queryset = super(UserGroupViewSet, self).get_queryset()
        if self.request.query_params.get("duty_rules"):
            queryset = queryset.filter(duty_rules__contains=self.request.query_params["duty_rules"])
        return queryset

    def get_serializer_class(self):
        """
        根据不同的action获取
        """
        if self.action == "list":
            return serializers.UserGroupSlz
        return self.serializer_class


class DutyRuleViewSet(UserGroupPermissionViewSet):
    """用户组配置视图"""

    queryset = DutyRule.objects.all()
    serializer_class = serializers.DutyRuleDetailSlz

    filter_fields = {"bk_biz_id": ["exact", "in"], "name": ["exact", "icontains"]}
    pagination_class = None

    def get_serializer_class(self):
        """
        根据不同的action获取
        """
        if self.action == "list":
            return serializers.DutyRuleSlz
        return self.serializer_class

    def get_queryset(self):
        """
        增加对轮值标签的过滤
        """
        queryset = super(DutyRuleViewSet, self).get_queryset()
        if self.request.query_params.get("labels"):
            queryset = queryset.filter(labels__contains=self.request.query_params["labels"])
        return queryset


class BkchatGroupViewSet(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", resource.user_group.get_bkchat_group, endpoint="get_bkchat_group")]


class DutyPlanViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.user_group.preview_duty_rule_plan, endpoint="preview_duty_rule_plan"),
        ResourceRoute("POST", resource.user_group.preview_user_group_plan, endpoint="preview_user_group_plan"),
    ]
