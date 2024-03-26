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

from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.strategy.new_strategy import Item
from bkmonitor.views import serializers
from constants.aiops import DEFAULT_SENSITIVITY


class AiSettingTemplateSerializer(serializers.Serializer):
    """
    ai设置默认序列化器
    """

    default_sensitivity = serializers.IntegerField(min_value=0, max_value=10, default=DEFAULT_SENSITIVITY)

    # 当该设置开启时校验其他参数
    def validate(self, attrs):
        is_enabled = attrs.get("is_enabled", False)
        if not is_enabled:
            return attrs
        for value in attrs.values():
            if value is None or value == "":
                raise serializers.ValidationError(_("有开启的检测未填写参数"))
            return attrs


class KPIAnomalyDetectionSerializer(serializers.Serializer):
    """
    单指标异常检测序列化器
    """

    default_plan_id = serializers.IntegerField(default=settings.BK_DATA_PLAN_ID_INTELLIGENT_DETECTION)


class MultivariateAnomalyDetectionSceneSerializer(AiSettingTemplateSerializer):
    """
    多指标异常检测场景序列化器
    """

    is_enabled = serializers.BooleanField(default=False)
    # 关闭通知对象，复用策略中的target序列化器
    exclude_target = serializers.ListField(
        allow_empty=True, child=serializers.ListField(child=Item.Serializer.TargetSerializer()), default=list
    )
    intelligent_detect = serializers.DictField(required=False)


class MultivariateAnomalyDetectionHostSerializer(MultivariateAnomalyDetectionSceneSerializer):
    """
    多指标异常检测主机场景序列化器
    """

    default_plan_id = serializers.IntegerField(default=settings.BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION)


class MultivariateAnomalyDetectionSerializer(serializers.Serializer):
    """
    多指标检测序列化器
    """

    host = MultivariateAnomalyDetectionHostSerializer()
