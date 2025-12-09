"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from monitor_web.models.custom_report import CustomEventGroup, CustomTSTable


class EventInfoSerializer(serializers.Serializer):
    class DimensionSerializer(serializers.Serializer):
        dimension_name = serializers.RegexField(label=_("维度字段名称"), regex=r"^[_a-zA-Z][a-zA-Z0-9_]*$")

    custom_event_id = serializers.IntegerField(label=_("事件 ID"), required=False)
    custom_event_name = serializers.CharField(label=_("事件名称"), required=True)
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
