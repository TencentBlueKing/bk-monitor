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
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers import ActionConfigDetailSlz
from bkmonitor.models import ActionConfig, StrategyActionConfigRelation
from core.drf_resource import Resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet

action_configs = ActionConfig.objects.exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID).all()


class SaveActionConfigResource(Resource):
    """
    保存处理套餐
    """

    RequestSerializer = ActionConfigDetailSlz

    def perform_request(self, params):
        action_config = ActionConfig.objects.create(**params)
        return {"id": action_config.id}


class GetActionConfigResource(Resource):
    """
    查询单个处理套餐
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, params):
        action_config = action_configs.get(id=params["id"], bk_biz_id=params["bk_biz_id"])
        return {
            "bk_biz_id": action_config.bk_biz_id,
            "desc": action_config.desc,
            "id": action_config.id,
            "name": action_config.name,
            "plugin_id": action_config.plugin_id,
            "execute_config": action_config.execute_config,
            "create_time": action_config.create_time,
            "create_user": action_config.create_user,
            "update_time": action_config.update_time,
            "update_user": action_config.update_user,
        }


class ListActionConfigResource(Resource):
    """
    批量查询处理套餐
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        page = serializers.IntegerField(required=False, default=1)
        order = serializers.ChoiceField(
            required=False,
            default="-id",
            label="排序字段",
            choices=["-id", "id", "create_time", "-create_time", "update_time", "-update_time"],
        )
        page_size = serializers.IntegerField(required=False, default=10, max_value=1000)

    def perform_request(self, params):
        page = params["page"]
        page_size = params["page_size"]

        total_action_configs = action_configs.filter(bk_biz_id=params["bk_biz_id"]).order_by(params["order"])
        count = total_action_configs.count()
        total_action_configs = total_action_configs[(page - 1) * page_size : page * page_size]
        action_config_list = []
        for action_config in total_action_configs:
            action_config_list.append(
                {
                    "bk_biz_id": action_config.bk_biz_id,
                    "desc": action_config.desc,
                    "id": action_config.id,
                    "name": action_config.name,
                    "plugin_id": action_config.plugin_id,
                    "execute_config": action_config.execute_config,
                    "create_time": action_config.create_time,
                    "create_user": action_config.create_user,
                    "update_time": action_config.update_time,
                    "update_user": action_config.update_user,
                }
            )

        return {"count": count, "data": action_config_list}


class EditActionConfigResource(Resource):
    """
    编辑处理套餐
    """

    class RequestSerializer(ActionConfigDetailSlz):
        id = serializers.IntegerField(required=True)
        name = serializers.CharField(required=False)

        def validate_name(self, value):
            query_result = ActionConfig.objects.filter(name=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], 0])
            query_result = query_result.exclude(id=self.initial_data["id"])
            if query_result.exists():
                raise ValidationError(detail=_("当前套餐名称已经存在，请重新确认!"))
            return value

    def perform_request(self, params):
        action_config = action_configs.get(id=params["id"])
        for field_name in ["name", "plugin_id", "desc", "execute_config", "is_enabled"]:
            if field_name not in params:
                continue
            setattr(action_config, field_name, params[field_name])
        action_config.save()

        return {
            "bk_biz_id": action_config.bk_biz_id,
            "desc": action_config.desc,
            "id": action_config.id,
            "name": action_config.name,
            "plugin_id": action_config.plugin_id,
            "execute_config": action_config.execute_config,
            "create_time": action_config.create_time,
            "create_user": action_config.create_user,
            "update_time": action_config.update_time,
            "update_user": action_config.update_user,
        }


class DeleteActionConfigResource(Resource):
    """
    删除处理套餐
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)

    def validate_request_data(self, request_data):
        validate_data = super(DeleteActionConfigResource, self).validate_request_data(request_data)
        try:
            self.instance = action_configs.get(id=validate_data["id"])
        except ActionConfig.DoesNotExist:
            raise CustomException(
                _("Resource[{}] 请求参数格式错误：{}").format(self.get_resource_name(), _("当前操作的处理套餐不存在，请确认信息是否正确!"))
            )

        if StrategyActionConfigRelation.objects.filter(config_id=validate_data["id"]).exists():
            raise CustomException(
                _("Resource[{}] 请求参数格式错误：{}").format(self.get_resource_name(), _("当前套餐关联了告警策略，无法删除!!"))
            )

    def perform_request(self, params):
        self.instance.delete()
        return {"id": self.instance.id, "name": self.instance.name}


class ActionConfigViewSet(ResourceViewSet):
    """
    处理套餐API
    """

    resource_routes = [
        ResourceRoute("POST", SaveActionConfigResource, endpoint="save"),
        ResourceRoute("GET", GetActionConfigResource, endpoint="detail"),
        ResourceRoute("GET", ListActionConfigResource, endpoint="search"),
        ResourceRoute("POST", EditActionConfigResource, endpoint="edit"),
        ResourceRoute("POST", DeleteActionConfigResource, endpoint="delete"),
    ]
