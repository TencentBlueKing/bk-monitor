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

from monitor_web.custom_report.constants import DEFAULT_FIELD_SCOPE
from monitor_web.models.custom_report import CustomTSTable


class BasicScopeSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("分组 ID"))
    name = serializers.CharField(label=_("分组名称"))


class BasicMetricRequestSerializer(serializers.Serializer):
    field_id = serializers.IntegerField(label=_("指标 ID"), source="id")
    metric_name = serializers.CharField(label=_("指标名称"), source="name")


class BasicMetricResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("指标 ID"), source="field_id")
    name = serializers.CharField(label=_("指标名称"), source="metric_name")


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


class BaseCustomTSTableSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        bk_biz_id: int = attrs["bk_biz_id"]
        time_series_group_id: int = attrs["time_series_group_id"]
        if not CustomTSTable.objects.filter(bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id).exists():
            raise serializers.ValidationError(
                _("自定义时序表不存在, bk_biz_id: {bk_biz_id}, time_series_group_id: {time_series_group_id}")
            )
        return super().validate(attrs)


class BaseCustomTSSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))


class CustomTSScopeRequestSerializer(serializers.Serializer):
    scope_id = serializers.IntegerField(label=_("分组 ID"), allow_null=True, required=False)
    name = serializers.CharField(label=_("分组名称"))
    metric_list = serializers.ListField(label=_("关联指标"), child=BasicMetricRequestSerializer(), default=list)
    auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), default=list)

    def validate(self, attrs: dict) -> dict:
        attrs["name"] = attrs["name"].strip()
        return super().validate(attrs)


class CustomTSScopeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("分组 ID"), source="scope_id")
    name = serializers.CharField(label=_("分组名称"))
    dimension_config = serializers.DictField(label=_("维度配置"))
    metric_list = serializers.ListField(label=_("指标列表"), child=BasicMetricResponseSerializer())
    auto_rules = serializers.ListField(label=_("自动规则"))
    create_from = serializers.CharField(label=_("创建来源"))

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().to_internal_value(data)
        validated_data["metric_count"] = len(validated_data["metric_list"])
        return validated_data


class DimensionConfigRequestSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, required=False)
    common = serializers.BooleanField(label=_("是否常用字段"), required=False)
    hidden = serializers.BooleanField(label=_("是否隐藏"), required=False)


class DimensionConfigResponseSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, default="")
    common = serializers.BooleanField(label=_("是否常用字段"), default=False)
    hidden = serializers.BooleanField(label=_("是否隐藏"), default=False)


class MetricConfigRequestSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, required=False)
    unit = serializers.CharField(label=_("字段单位"), allow_blank=True, required=False)
    hidden = serializers.BooleanField(label=_("是否隐藏"), required=False)
    aggregate_method = serializers.CharField(label=_("聚合方法"), allow_blank=True, required=False)
    function = serializers.ListSerializer(label=_("指标函数"), child=serializers.DictField(), required=False)
    interval = serializers.IntegerField(label=_("指标周期"), required=False)
    disabled = serializers.BooleanField(label=_("是否禁用"), required=False)


class MetricConfigResponseSerializer(serializers.Serializer):
    alias = serializers.CharField(label=_("字段别名"), allow_blank=True, default="")
    unit = serializers.CharField(label=_("字段单位"), allow_blank=True, default="")
    hidden = serializers.BooleanField(label=_("是否隐藏"), default=False)
    aggregate_method = serializers.CharField(label=_("聚合方法"), allow_blank=True, default="")
    function = serializers.ListSerializer(label=_("指标函数"), child=serializers.DictField(), default=[])
    interval = serializers.IntegerField(label=_("指标周期"), default=0)
    disabled = serializers.BooleanField(label=_("是否禁用"), default=False)


class MetricResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("指标 ID"))
    name = serializers.CharField(label=_("指标名称"))
    dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField(), default=list)
    config = MetricConfigResponseSerializer(label=_("指标配置"))
    field_scope = serializers.CharField(label=_("数据分组"), default=DEFAULT_FIELD_SCOPE)
    create_time = serializers.FloatField(label=_("创建时间"))
    update_time = serializers.FloatField(label=_("更新时间"))


class ImportExportScopeSerializer(serializers.Serializer):
    class ImportExportMetricSerializer(serializers.Serializer):
        name = serializers.CharField(label=_("指标名称"))
        field_scope = serializers.CharField(label=_("数据分组"), default=DEFAULT_FIELD_SCOPE)
        dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField(), default=list)
        config = MetricConfigResponseSerializer(label=_("指标配置"))

    name = serializers.CharField(label=_("分组名称"), allow_blank=True)
    dimension_config = serializers.DictField(
        label=_("维度配置"), child=DimensionConfigResponseSerializer(), default=dict
    )
    auto_rules = serializers.ListField(
        label=_("自动分组的匹配规则列表"), child=serializers.CharField(allow_blank=True), default=list
    )
    metric_list = serializers.ListField(label=_("关联指标"), child=ImportExportMetricSerializer(), default=list)
