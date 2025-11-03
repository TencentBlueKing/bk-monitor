"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from bkmonitor.utils.range import SUPPORT_COMPOSITE_METHODS, SUPPORT_SIMPLE_METHODS
from constants.shield import ShieldCategory


class BaseSerializer(serializers.Serializer):
    class CycleConfigSlz(serializers.Serializer):
        type = serializers.IntegerField(required=True)
        week_list = serializers.ListField(required=False, default=[])
        day_list = serializers.ListField(required=False, default=[])
        begin_time = serializers.CharField(required=False, default="", allow_blank=True)
        end_time = serializers.CharField(required=False, default="", allow_blank=True)

    class NoticeConfigSlz(serializers.Serializer):
        notice_way = serializers.ListField(required=False)
        notice_receiver = serializers.ListField(required=False)
        notice_time = serializers.IntegerField(required=False)

    bk_biz_id = serializers.IntegerField(required=True, label="业务id")
    category = serializers.ChoiceField(required=True, choices=ShieldCategory.CHOICES, label="屏蔽类型")
    begin_time = serializers.CharField(required=True, label="屏蔽开始时间")
    end_time = serializers.CharField(required=True, label="屏蔽结束时间")
    dimension_config = serializers.DictField(required=True, label="维度配置")
    cycle_config = CycleConfigSlz(required=False, label="周期配置")
    shield_notice = serializers.BooleanField(required=True, label="是否有屏蔽通知")
    notice_config = NoticeConfigSlz(required=False, label="通知配置")
    description = serializers.CharField(required=False, label="屏蔽原因", allow_blank=True)
    is_quick = serializers.BooleanField(required=False, label="是否是快捷屏蔽", default=False)
    label = serializers.CharField(required=False, label="标签", default="", allow_blank=True)


class ScopeSerializer(BaseSerializer):
    class DimensionConfig(serializers.Serializer):
        scope_type = serializers.CharField(required=True)
        target = serializers.ListField(required=False)
        metric_id = serializers.ListField(required=False)

    dimension_config = DimensionConfig(required=True, label="维度配置")


class StrategySerializer(BaseSerializer):
    class DimensionConfig(serializers.Serializer):
        class DimensionCondition(serializers.Serializer):
            key = serializers.CharField(required=True)
            value = serializers.ListField(required=True, child=serializers.CharField())
            method = serializers.ChoiceField(choices=SUPPORT_SIMPLE_METHODS, default="eq")
            condition = serializers.ChoiceField(choices=SUPPORT_COMPOSITE_METHODS, default="and")
            name = serializers.CharField(required=False)

        id = serializers.ListField(required=True)
        level = serializers.ListField(required=False)
        scope_type = serializers.CharField(required=False)
        target = serializers.ListField(required=False)
        dimension_conditions = serializers.ListField(required=False, child=DimensionCondition(required=True))

    dimension_config = DimensionConfig(required=True, label="维度配置")


class EventSerializer(BaseSerializer):
    class DimensionConfig(serializers.Serializer):
        id = serializers.CharField(required=True)

    dimension_config = DimensionConfig(required=True, label="维度配置")
    # 用于移动端，快捷屏蔽，动态删除维度
    dimension_keys = serializers.ListField(label="维度键名列表", child=serializers.CharField(), default=None)


class AlertSerializer(BaseSerializer):
    class DimensionConfig(serializers.Serializer):
        alert_id = serializers.CharField(required=False)
        alert_ids = serializers.ListField(required=False, child=serializers.CharField(allow_blank=False))
        dimensions = serializers.DictField(required=False)
        bk_topo_node = serializers.DictField(required=False)

        def validate(self, attrs):
            if not attrs.get("alert_id") and not attrs.get("alert_ids"):
                raise serializers.ValidationError("alert_id or alert_ids is required")
            return attrs

    dimension_config = DimensionConfig(required=True, label="维度配置")
    # 用于移动端，快捷屏蔽，动态删除维度
    dimension_keys = serializers.ListField(label="维度键名列表", child=serializers.CharField(), default=None)


class DimensionSerializer(BaseSerializer):
    class DimensionConfig(serializers.Serializer):
        class DimensionCondition(serializers.Serializer):
            key = serializers.CharField(required=True)
            value = serializers.ListField(required=True, child=serializers.CharField())
            method = serializers.ChoiceField(choices=SUPPORT_SIMPLE_METHODS, default="eq")
            condition = serializers.ChoiceField(choices=SUPPORT_COMPOSITE_METHODS, default="and")
            name = serializers.CharField(required=False)

        dimension_conditions = serializers.ListField(required=True, child=DimensionCondition(required=True))

    dimension_config = DimensionConfig(required=True, label="维度配置")


SHIELD_SERIALIZER = {
    ShieldCategory.SCOPE: ScopeSerializer,
    ShieldCategory.STRATEGY: StrategySerializer,
    ShieldCategory.EVENT: EventSerializer,
    ShieldCategory.ALERT: AlertSerializer,
    ShieldCategory.DIMENSION: DimensionSerializer,
}
