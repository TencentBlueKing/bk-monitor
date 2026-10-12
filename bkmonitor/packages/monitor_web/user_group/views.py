"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import permissions, serializers as drf_serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bkmonitor.action import serializers
from bkmonitor.action.serializers import DutySwitchSlz
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import DutyPlan, DutyRule, DutyRuleSnap, UserGroup
from bkmonitor.utils.request import get_request
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.permissions import check_notification_group_permission, require_business_id


class PermissionMixin:
    def check_permissions(self, request):
        require_business_id(request)
        super().check_permissions(request)

    def check_object_permissions(self, request, obj):
        action = (
            ActionEnum.VIEW_NOTIFY_TEAM if request.method in permissions.SAFE_METHODS else ActionEnum.MANAGE_NOTIFY_TEAM
        )
        check_notification_group_permission(request, obj.bk_biz_id, action)

    def get_queryset(self):
        queryset = super().get_queryset().filter(bk_biz_id__in=[0, require_business_id(self.request)])
        # bk_biz_id 是请求业务上下文；显式 __in 只进一步收窄可见范围。
        biz_ids = self.request.query_params.get("bk_biz_id__in")
        if biz_ids is not None:
            biz_ids = drf_serializers.ListField(child=drf_serializers.IntegerField()).run_validation(biz_ids.split(","))
            queryset = queryset.filter(bk_biz_id__in=biz_ids)
        return queryset

    def get_serializer(self, *args, **kwargs):
        if "data" in kwargs:
            instance = args[0] if args else kwargs.get("instance")
            kwargs["data"] = kwargs["data"].copy()
            # 请求始终携带真实业务，平台对象的归属由存量记录决定，不允许迁移归属。
            kwargs["data"]["bk_biz_id"] = (
                instance.bk_biz_id if instance is not None else require_business_id(self.request)
            )
        return super().get_serializer(*args, **kwargs)

    def get_permissions(self):
        """
        获取权限
        """
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_NOTIFY_TEAM])]
        return [BusinessActionPermission([ActionEnum.MANAGE_NOTIFY_TEAM])]


class UserGroupViewSet(PermissionMixin, viewsets.ModelViewSet):
    """用户组配置视图"""

    queryset = UserGroup.objects.all()
    serializer_class = serializers.UserGroupDetailSlz

    filterset_fields = {"name": ["exact", "icontains"]}
    pagination_class = None

    def get_queryset(self):
        """
        增加对轮值规则的过滤
        """
        queryset = super().get_queryset()
        if self.request.query_params.get("duty_rules"):
            queryset = queryset.filter(duty_rules__contains=self.request.query_params["duty_rules"])
        return queryset

    def get_serializer_class(self):
        """
        根据不同的action获取
        """
        if self.action == "list":
            return serializers.UserGroupSlz
        if self.action == "retrieve":
            request = get_request(peaceful=True)
            setattr(request, "notice_user_detail", True)
        return self.serializer_class

    @action(detail=False, methods=["post"])
    def bulk_update(self, request, *args, **kwargs):
        params = request.data
        data = resource.user_group.user_group_bulk_update(params)
        return Response(data)


class DutyRuleViewSet(PermissionMixin, viewsets.ModelViewSet):
    """用户组配置视图"""

    queryset = DutyRule.objects.all()
    serializer_class = serializers.DutyRuleDetailSlz

    filterset_fields = {"name": ["exact", "icontains"]}
    pagination_class = None

    def get_serializer_class(self):
        """
        根据不同的action获取
        """
        if self.action == "list":
            return serializers.DutyRuleSlz
        if self.action == "retrieve":
            request = get_request(peaceful=True)
            setattr(request, "notice_user_detail", True)
        return self.serializer_class

    def get_queryset(self):
        """
        增加对轮值标签的过滤
        """
        queryset = super().get_queryset()
        if self.request.query_params.get("labels"):
            queryset = queryset.filter(labels__contains=self.request.query_params["labels"])
        return queryset

    @action(detail=False, methods=["post"])
    def switch(self, request):
        """
        启停开关
        """
        serializer = DutySwitchSlz(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_data = serializer.data
        enabled = request_data.pop("enabled")
        # 过滤出来有效的数据
        rules = DutyRule.objects.filter(id__in=request_data["ids"])
        for biz_id in rules.values_list("bk_biz_id", flat=True).distinct():
            check_notification_group_permission(request, biz_id, ActionEnum.MANAGE_NOTIFY_TEAM)
        rule_ids = list(rules.values_list("id", flat=True))
        if rule_ids:
            rules.update(enabled=enabled)
            if enabled is False:
                # 关闭掉之后，直接关闭掉对应的计划
                DutyRuleSnap.objects.filter(duty_rule_id__in=rule_ids).update(enabled=False)
                DutyPlan.objects.filter(duty_rule_id__in=rule_ids).update(is_effective=False)
        return Response({"rule_ids": rule_ids})


class BkchatGroupViewSet(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", resource.user_group.get_bkchat_group, endpoint="get_bkchat_group")]


class DutyPlanViewSet(ResourceViewSet):
    def get_permissions(self):
        require_business_id(self.request)
        return [BusinessActionPermission([ActionEnum.VIEW_NOTIFY_TEAM])]

    resource_routes = [
        ResourceRoute("POST", resource.user_group.preview_duty_rule_plan, endpoint="preview_duty_rule_plan"),
        ResourceRoute("POST", resource.user_group.preview_user_group_plan, endpoint="preview_user_group_plan"),
    ]
