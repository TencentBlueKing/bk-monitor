"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from monitor_web.models.custom_report import CustomTSTable


class BasicScopeSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("分组 ID"))
    name = serializers.CharField(label=_("分组名称"))


class BasicMetricSerializer(serializers.Serializer):
    field_id = serializers.IntegerField(label=_("指标 ID"))
    metric_name = serializers.CharField(label=_("指标名称"))


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
    scope_id = serializers.IntegerField(label=_("分组 ID"), default=0)  # TODO: 去除 default
    name = serializers.CharField(label=_("分组名称"), required=True)
    manual_list = serializers.ListField(label=_("手动分组的指标列表"), default=list)
    auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), default=list)

    def validate(self, attrs: dict) -> dict:
        attrs["name"] = attrs["name"].strip()
        return attrs


class BaseCustomTSSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        bk_biz_id: int = attrs["bk_biz_id"]
        time_series_group_id: int = attrs["time_series_group_id"]
        if not CustomTSTable.objects.filter(bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id).first():
            raise serializers.ValidationError(
                _("自定义时序表不存在, bk_biz_id: {bk_biz_id}, time_series_group_id: {time_series_group_id}")
            )
        return super().validate(attrs)


class CustomTSScopeSerializer(serializers.Serializer):
    scope_id = serializers.IntegerField(label=_("分组 ID"), allow_null=True, required=False)
    name = serializers.CharField(label=_("分组名称"))
    metric_list = serializers.ListField(label=_("关联指标"), child=BasicMetricSerializer(), default=list)
    auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), default=list)

    def validate(self, attrs: dict) -> dict:
        attrs["name"] = attrs["name"].strip()
        return attrs


class DimensionConfigSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, required=False)
    common = serializers.BooleanField(label=_("是否常用字段"), required=False)
    hidden = serializers.BooleanField(label=_("是否隐藏"), required=False)


class MetricConfigSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, required=False)
    unit = serializers.CharField(label=_("字段单位"), allow_blank=True, required=False)
    hidden = serializers.BooleanField(label=_("是否隐藏"), required=False)
    aggregate_method = serializers.CharField(label=_("聚合方法"), allow_blank=True, required=False)
    function = serializers.JSONField(label=_("指标函数"), required=False)
    interval = serializers.IntegerField(label=_("指标周期"), required=False)
    disabled = serializers.BooleanField(label=_("是否禁用"), required=False)


class MetricSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("指标 ID"))
    name = serializers.CharField(label=_("指标名称"))
    dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField(), default=list)
    config = MetricConfigSerializer(label=_("指标配置"))
    create_time = serializers.FloatField(label=_("创建时间"))
    update_time = serializers.FloatField(label=_("更新时间"))


class ImportExportScopeSerializer(serializers.Serializer):
    name = serializers.CharField(label=_("分组名称"), allow_blank=True)
    dimension_config = serializers.DictField(label=_("维度配置"), child=DimensionConfigSerializer(), default=dict)
    auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), child=serializers.CharField(), default=list)
    metric_list = serializers.ListField(label=_("关联指标"), child=MetricSerializer(), default=list)
