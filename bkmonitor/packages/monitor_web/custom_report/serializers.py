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


from monitor_web.models.custom_report import CustomEventGroup, CustomTSTable
from rest_framework import serializers


class EventInfoSerializer(serializers.Serializer):
    class DimensionSerializer(serializers.Serializer):
        dimension_name = serializers.RegexField(label="维度字段名称", regex=r"^[_a-zA-Z][a-zA-Z0-9_]*$")

    custom_event_id = serializers.IntegerField(required=False, label="事件ID")
    custom_event_name = serializers.CharField(required=True, label="事件名称")
    dimension_list = DimensionSerializer(required=True, many=True, allow_empty=False)


class CustomEventGroupDetailSerializer(serializers.ModelSerializer):
    event_info_list = EventInfoSerializer(read_only=True, many=True)
    is_readonly = serializers.SerializerMethodField()

    def get_is_readonly(self, obj: CustomTSTable) -> bool:
        """判断当前自定义上报表是否只读"""
        if "request_bk_biz_id" not in self.context:
            return False

        # 当且仅当【获取到其他业务的全平台内容时】为只读
        if obj.is_platform and obj.bk_biz_id != self.context["request_bk_biz_id"]:
            return True

        return False

    class Meta:
        model = CustomEventGroup
        fields = "__all__"


class CustomEventGroupSerializer(serializers.ModelSerializer):
    is_readonly = serializers.SerializerMethodField()

    def get_is_readonly(self, obj: CustomTSTable) -> bool:
        """判断当前自定义上报表是否只读"""
        if "request_bk_biz_id" not in self.context:
            return False

        # 当且仅当【获取到其他业务的全平台内容时】为只读
        if obj.is_platform and obj.bk_biz_id != self.context["request_bk_biz_id"]:
            return True

        return False

    class Meta:
        model = CustomEventGroup
        fields = "__all__"


class MetricListSerializer(serializers.Serializer):
    class FieldSerializer(serializers.Serializer):

        unit = serializers.CharField(required=True, label="字段单位", allow_blank=True)
        name = serializers.CharField(required=True, label="字段名")
        description = serializers.CharField(required=True, label="字段描述", allow_blank=True)
        monitor_type = serializers.CharField(required=True, label="字段类型，指标或维度")
        type = serializers.CharField(required=True, label="字段类型")
        label = serializers.ListField(required=False, label="分组标签", default=[])

    fields = FieldSerializer(required=True, label="字段信息", many=True)


class CustomTSTableSerializer(serializers.ModelSerializer):
    is_readonly = serializers.SerializerMethodField()

    def get_is_readonly(self, obj: CustomTSTable) -> bool:
        """判断当前自定义上报表是否只读"""
        if "request_bk_biz_id" not in self.context:
            return False

        # 当且仅当【获取到其他业务的全平台内容时】为只读
        if obj.is_platform and obj.bk_biz_id != self.context["request_bk_biz_id"]:
            return True

        return False

    class Meta:
        model = CustomTSTable
        fields = "__all__"


class CustomTSGroupingRuleSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, label="分组名称")
    manual_list = serializers.ListField(required=False, label="手动分组的指标列表")
    auto_rules = serializers.ListField(required=False, label="自动分组的匹配规则列表")
