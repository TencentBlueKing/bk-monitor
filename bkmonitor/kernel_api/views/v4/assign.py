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
from collections import defaultdict

from rest_framework import serializers

from bkmonitor.action.serializers import (
    AssignGroupSlz,
    AssignRuleSlz,
    BatchSaveAssignRulesSlz,
)
from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from core.drf_resource import Resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class SaveRuleGroupResource(Resource):
    """
    保存告警分派组
    """

    RequestSerializer = BatchSaveAssignRulesSlz

    def perform_request(self, validated_data):
        return self.request_serializer.save(validated_data)


class DeleteRuleGroupResource(Resource):
    """
    删除告警分派组列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        group_ids = serializers.ListField(child=serializers.IntegerField(), required=True, allow_empty=False)

    def perform_request(self, validated_data):
        group_queryset = AlertAssignGroup.objects.filter(bk_biz_id=validated_data["bk_biz_id"])
        if validated_data["group_ids"]:
            group_queryset = group_queryset.filter(id__in=validated_data["group_ids"])
        deleted_group_ids = list(group_queryset.values_list("id", flat=True))
        if deleted_group_ids:
            AlertAssignRule.objects.filter(assign_group_id__in=deleted_group_ids).delete()
        group_queryset.delete()
        return {"deleted_group_ids": deleted_group_ids}


class SearchRuleGroupResource(Resource):
    """
    查找分派组列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        group_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=False)

    def perform_request(self, validated_data):
        group_queryset = AlertAssignGroup.objects.filter(bk_biz_id=validated_data["bk_biz_id"])
        if validated_data.get("group_ids"):
            group_queryset = group_queryset.filter(id__in=validated_data["group_ids"])
        groups_data = AssignGroupSlz(instance=group_queryset, many=True).data
        group_ids = [group["id"] for group in groups_data]
        group_rules_dict = defaultdict(list)
        #
        if group_ids:
            assign_rules_queryset = AlertAssignRule.objects.filter(
                assign_group_id__in=group_ids, bk_biz_id=validated_data["bk_biz_id"]
            )
            rules_data = AssignRuleSlz(instance=assign_rules_queryset, many=True).data
            for rule in rules_data:
                group_rules_dict[rule["assign_group_id"]].append(rule)
        for group in groups_data:
            group["rules"] = group_rules_dict.get(group["id"], [])
        return groups_data


class AlertAssignViewSet(ResourceViewSet):
    """
    告警分派后台
    """

    resource_routes = [
        ResourceRoute("POST", SaveRuleGroupResource, endpoint="save_rule_group"),
        ResourceRoute("POST", DeleteRuleGroupResource, endpoint="delete_rule_group"),
        ResourceRoute("POST", SearchRuleGroupResource, endpoint="search_rule_groups"),
    ]
