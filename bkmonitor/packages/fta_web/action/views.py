"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from django.utils.translation import gettext as _
from rest_framework import permissions, viewsets

from bkmonitor.action import serializers
from bkmonitor.action.utils import (
    get_action_config_rules,
    get_action_config_strategy_dict,
)
from bkmonitor.documents import ActionInstanceDocument
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission, IAMPermission
from bkmonitor.models import ActionConfig, ActionPlugin, StrategyActionConfigRelation
from constants.action import GLOBAL_BIZ_ID, ActionDisplayStatus
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ActionConfigViewSet(viewsets.ModelViewSet):
    """套餐配置视图"""

    queryset = ActionConfig.objects.exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID).all()
    serializer_class = serializers.ActionConfigDetailSlz

    filterset_fields = {
        "plugin_id": ["exact", "in"],
        "name": ["exact", "icontains"],
    }
    pagination_class = None

    def check_object_permissions(self, request, obj):
        if int(obj.bk_biz_id) == 0 and self.request.method not in permissions.SAFE_METHODS:
            permission = IAMPermission([ActionEnum.MANAGE_PUBLIC_ACTION_CONFIG])
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(request, message=getattr(permission, "message", None))
        else:
            super().check_object_permissions(request, obj)

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.ActionConfigListSlz
        elif self.action == "partial_update":
            return serializers.ActionConfigPatchSlz
        return self.serializer_class

    def list(self, request, *args, **kwargs):
        request_biz_id = request.query_params.get("bk_biz_id", 0)
        if request_biz_id:
            self.queryset = self.queryset.filter(bk_biz_id__in=[GLOBAL_BIZ_ID, request_biz_id])
        response = super().list(request, *args, **kwargs)

        if request.query_params.get("with_advance_fields") == "no":
            # 不需要高级字段直接不做统计
            return response

        config_ids = list(self.queryset.values_list("id", flat=True))

        related_strategy_count = get_action_config_strategy_dict(
            config_ids,
            bk_biz_id=request_biz_id,
        )
        related_rules = get_action_config_rules(config_ids, request_biz_id)
        week_ago = int(time.time()) - 7 * 24 * 60 * 60
        search_object = (
            ActionInstanceDocument.search(start_time=week_ago)
            .filter("range", create_time={"gte": week_ago})
            .filter("term", bk_biz_id=request_biz_id)
            .filter(
                "terms",
                status=[
                    ActionDisplayStatus.RUNNING,
                    ActionDisplayStatus.FAILURE,
                    ActionDisplayStatus.SUCCESS,
                ],
            )
            .filter("terms", action_config_id=[config_data["id"] for config_data in response.data])
            .exclude("term", is_parent_action=True)
        )
        search_object.aggs.bucket("action_config_id", "terms", field="action_config_id", size=10000)
        search_result = search_object.execute()

        latest_execute_count_dict = {}
        if search_result.aggs:
            for bucket in search_result.aggs.action_config_id.buckets:
                latest_execute_count_dict[int(bucket.key)] = bucket.doc_count

        for config_data in response.data:
            config_data["strategy_count"] = related_strategy_count.get(config_data["id"]) or 0
            config_data["delete_allowed"] = (
                config_data["bk_biz_id"] != GLOBAL_BIZ_ID
                and config_data["id"] not in related_strategy_count
                and config_data["id"] not in related_rules
            )
            config_data["edit_allowed"] = config_data["bk_biz_id"] != GLOBAL_BIZ_ID
            config_data["execute_count"] = latest_execute_count_dict.get(config_data["id"]) or 0
            config_data["config_source"] = "YAML" if config_data.get("app") else "UI"
        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        request_biz_id = request.query_params.get("bk_biz_id", GLOBAL_BIZ_ID)
        instance_id = response.data["id"]
        config_strategy_dict = get_action_config_strategy_dict(
            [instance_id],
            bk_biz_id=response.data["bk_biz_id"] or request_biz_id,
        )
        related_rules = get_action_config_rules([instance_id], request_biz_id)

        response.data["strategy_count"] = config_strategy_dict.get(instance_id) or 0
        response.data["delete_allowed"] = (
            response.data["bk_biz_id"] != GLOBAL_BIZ_ID
            and instance_id not in config_strategy_dict
            and instance_id not in related_rules
        )
        response.data["edit_allowed"] = response.data["bk_biz_id"] != GLOBAL_BIZ_ID
        return response

    def perform_destroy(self, instance):
        if StrategyActionConfigRelation.objects.filter(config_id=instance.id).exists():
            raise serializers.ValidationError(_("当前套餐关联了告警策略，无法删除!!"))
        instance.delete()


class ActionPluginCurdViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        return [BusinessActionPermission([ActionEnum.MANAGE_RULE])]

    queryset = ActionPlugin.objects.all()
    serializer_class = serializers.ActionPluginSlz


class ActionPluginViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_RULE])]

    resource_routes = [
        ResourceRoute("GET", resource.action.get_plugins, endpoint="get_plugins"),
        ResourceRoute("GET", resource.action.get_plugin_templates, endpoint="get_plugin_templates"),
        ResourceRoute("GET", resource.action.get_template_detail, endpoint="get_template_detail"),
        ResourceRoute("GET", resource.action.get_dimensions, endpoint="get_dimensions"),
        ResourceRoute("GET", resource.action.get_converge_function, endpoint="get_converge_function"),
        ResourceRoute("GET", resource.action.get_variables, endpoint="get_variables"),
        ResourceRoute("POST", resource.action.render_notice_template, endpoint="render_notice_template"),
        ResourceRoute("GET", resource.action.register_bk_plugin, endpoint="register_bk_plugin"),
        ResourceRoute("GET", resource.action.batch_register_bk_plugin, endpoint="batch_register_bk_plugin"),
    ]


class ActionInstanceViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["get_action_config_by_alerts", "create_chat_group"]:
            return [BusinessActionPermission([ActionEnum.VIEW_EVENT])]
        if self.action in ["create_demo_action", "get_demo_action_detail"]:
            return [BusinessActionPermission([ActionEnum.VIEW_RULE])]
        if self.action in ["get_action_params", "batch_create", "assign_alert"]:
            return [BusinessActionPermission([ActionEnum.MANAGE_RULE, ActionEnum.MANAGE_EVENT])]
        return [BusinessActionPermission([ActionEnum.MANAGE_EVENT])]

    resource_routes = [
        ResourceRoute("POST", resource.action.get_action_params, endpoint="get_action_params"),
        ResourceRoute("POST", resource.action.batch_create, endpoint="batch_create"),
        ResourceRoute("POST", resource.action.create_chat_group, endpoint="create_chat_group"),
        ResourceRoute("POST", resource.action.get_action_config_by_alerts, endpoint="get_action_config_by_alerts"),
        ResourceRoute("POST", resource.action.create_demo_action, endpoint="create_demo_action"),
        ResourceRoute("GET", resource.action.get_demo_action_detail, endpoint="get_demo_action_detail"),
        ResourceRoute("POST", resource.action.assign_alert, endpoint="assign_alert"),
    ]
