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
import datetime

from rest_framework import exceptions, serializers

from bkmonitor.models import StrategyModel
from bkmonitor.utils.user import get_global_user
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.views.v4.notice_group import (
    SaveNoticeGroupResource,
    SearchNoticeGroupResource,
)


class SaveStrategyResource(Resource):
    """
    保存告警策略
    """

    class NoticeGroupSerializer(serializers.Serializer):
        name = serializers.CharField(required=False, max_length=128)
        notice_receiver = serializers.ListField(required=False, child=serializers.CharField())
        notice_way = serializers.DictField(required=False, child=serializers.ListField())
        message = serializers.CharField(required=False, allow_blank=True)
        webhook_url = serializers.CharField(required=False, allow_blank=True)
        id = serializers.IntegerField(required=False)

        def validate(self, attrs):
            if "id" not in attrs and len({"name", "notice_receiver", "notice_way"} & set(attrs.keys())) < 3:
                raise exceptions.ValidationError("notice_group_list validate error")

            if "id" in attrs:
                notice_group = SearchNoticeGroupResource()(ids=[attrs["id"]])
                if not notice_group:
                    raise exceptions.ValidationError("notice_group({}) does not exist".format(attrs["id"]))

                notice_group = notice_group[0]
                notice_group.update(attrs)

            return attrs

        def validate_notice_receiver(self, value):
            return [{"type": receiver.split("#")[0], "id": receiver.split("#")[-1]} for receiver in value]

    def parse_notice_group(self, bk_biz_id, notice_group_list):
        """
        解析通知组配置
        :param bk_biz_id: 业务ID
        :param notice_group_list: 通知组配置
        """
        serializer = self.NoticeGroupSerializer(many=True, data=notice_group_list)
        serializer.is_valid(raise_exception=True)
        notice_group_list = serializer.validated_data

        config = []
        for notice_group in notice_group_list:
            config.append(SaveNoticeGroupResource()(bk_biz_id=bk_biz_id, **notice_group)["id"])
        return config

    def perform_request(self, params):
        if "bk_biz_id" in params:
            for action in params.get("action_list", []):
                if "notice_group_list" in action:
                    action["notice_group_list"] = self.parse_notice_group(
                        params["bk_biz_id"], action["notice_group_list"]
                    )

        return resource.strategies.backend_strategy_config(**params)


class SearchStrategyResource(Resource):
    """
    搜索告警策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        order_by = serializers.CharField(required=False, default="-update_time", label="排序字段")
        search = serializers.CharField(required=False, label="查询参数")
        scenario = serializers.CharField(required=False, label="二级标签")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        notice_group_name = serializers.CharField(required=False, label="告警组名称")
        service_category = serializers.CharField(required=False, label="服务分类")
        task_id = serializers.IntegerField(required=False, label="任务ID")
        IP = serializers.IPAddressField(required=False, label="IP筛选")
        metric_id = serializers.CharField(required=False, label="指标ID")
        ids = serializers.ListField(required=False, label="ID列表")

        fields = serializers.ListField(default=[], label="所需字段")

    def perform_request(self, validated_request_data):
        result = resource.strategies.backend_strategy_config_list(**validated_request_data)

        notice_group_ids = set()

        for strategy in result:
            for action in strategy.get("action_list") or strategy["actions"]:
                notice_group_ids.update(action.get("notice_group_list") or action.get("notice_group_ids", []))

        notice_groups = SearchNoticeGroupResource()(
            bk_biz_id=validated_request_data["bk_biz_id"], ids=list(notice_group_ids)
        )

        notice_groups_mapping = {group["id"]: group for group in notice_groups}

        for strategy in result:
            for action_config in strategy.get("action_list") or strategy["actions"]:
                notice_group_details = []
                for group_id in action_config["notice_group_list"]:
                    if group_id in notice_groups_mapping:
                        notice_group_details.append(notice_groups_mapping[group_id])
                action_config["notice_group_list"] = notice_group_details

        if validated_request_data["fields"]:
            for index, alarm_strategy in enumerate(result):
                result[index] = {
                    key: value for key, value in alarm_strategy.items() if key in validated_request_data["fields"]
                }
        return result


class SwitchStrategyResource(Resource):
    """
    开关告警策略
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(child=serializers.IntegerField(), label="策略ID列表")
        is_enabled = serializers.BooleanField()

    def perform_request(self, params):
        strategies = StrategyModel.objects.filter(id__in=params["ids"])
        username = get_global_user() or "unknown"
        strategies.update(is_enabled=params["is_enabled"], update_user=username, update_time=datetime.datetime.now())

        switch_ids = [strategy.id for strategy in strategies]

        return {
            "ids": switch_ids,
        }


class AlarmStrategyViewSet(ResourceViewSet):
    """
    告警策略API
    """

    resource_routes = [
        ResourceRoute("POST", SearchStrategyResource, endpoint="search"),
        ResourceRoute("POST", SaveStrategyResource, endpoint="save"),
        ResourceRoute("POST", resource.strategies.delete_strategy_config, endpoint="delete"),
        ResourceRoute("POST", SwitchStrategyResource, endpoint="switch"),
    ]
