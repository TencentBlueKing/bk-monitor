"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from . import constants


class MixedTypeListField(serializers.ListField):
    def __init__(self, **kwargs):
        self.allowed_types = kwargs.pop("allowed_types", [])
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError(_("输入必须是一个列表。"))

        for item in data:
            if any(isinstance(item, t) for t in self.allowed_types):
                continue

            raise serializers.ValidationError(
                _("列表中的项必须是 {allowed_types}，但收到了类型为 {actual_type} 的项。").format(
                    allowed_types=", ".join([t.__name__ for t in self.allowed_types]),
                    actual_type=type(item).__name__,
                )
            )

        return super().to_internal_value(data)


class MetricSerializer(serializers.Serializer):
    field = serializers.CharField(label=_("指标名"))
    method = serializers.CharField(label=_("汇聚方法"))
    alias = serializers.CharField(label=_("别名"), required=False)


class MetricInfoSerializer(serializers.Serializer):
    metric_id = serializers.CharField(label=_("指标 ID"))
    metric_field = serializers.CharField(label=_("指标字段"))


class VariableConfigSerializer(serializers.Serializer):
    default = serializers.JSONField(label=_("默认值"), required=False, default=None)
    data_type = serializers.ChoiceField(label=_("数据类型"), required=False, choices=constants.DataType.choices())
    related_tag = serializers.CharField(label=_("关联维度"), required=False)
    related_metrics = serializers.ListField(
        label=_("关联指标"), required=False, min_length=1, child=MetricInfoSerializer()
    )
    options = serializers.ListField(label=_("可选范围"), required=False, default=[], child=serializers.CharField())


class VariableSerializer(serializers.Serializer):
    name = serializers.CharField(label=_("变量名"), max_length=128)
    alias = serializers.CharField(label=_("变量别名"), max_length=128)
    type = serializers.ChoiceField(label=_("变量类型"), choices=constants.VariableType.choices())
    config = VariableConfigSerializer(label=_("变量配置"), default={})
    description = serializers.CharField(label=_("变量描述"), required=False, allow_blank=True, default="")

    def validate(self, attrs):
        variable_type: constants.VariableType = constants.VariableType.from_value(attrs["type"])

        if variable_type.is_required_data_type() and not attrs["config"].get("data_type"):
            raise serializers.ValidationError(
                _("变量类型为 {name} 时，必须指定「数据类型」。").format(name=variable_type.label)
            )

        if variable_type.is_required_related_tag() and not attrs["config"].get("related_tag"):
            raise serializers.ValidationError(
                _("变量类型为 {name} 时，必须指定「关联维度」。").format(name=variable_type.label)
            )

        if variable_type.is_required_related_metrics() and not attrs["config"].get("related_metrics"):
            raise serializers.ValidationError(
                _("变量类型为 {name} 时，必须指定「关联指标」。").format(name=variable_type.label)
            )

        return attrs


class QueryConfigSerializer(serializers.Serializer):
    table = serializers.CharField(label=_("结果表"))
    data_label = serializers.CharField(label=_("数据标签"), required=False, allow_blank=True, default="")
    data_type_label = serializers.CharField(label=_("数据类型标签"))
    data_source_label = serializers.CharField(label=_("数据源标签"))
    interval = serializers.IntegerField(label=_("汇聚周期（秒）"), required=False)
    promql = serializers.CharField(label=_("PromQL 查询语句"), required=False, allow_blank=True, default="")
    metrics = serializers.ListField(label=_("指标"), required=False, default=[], child=MetricSerializer())
    where = MixedTypeListField(label=_("过滤条件"), required=False, default=[], allowed_types=[dict, str])
    functions = MixedTypeListField(label=_("函数"), required=False, default=[], allowed_types=[dict, str])
    group_by = serializers.ListField(label=_("聚合字段"), required=False, default=[], child=serializers.CharField())


class QueryTemplateSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    name = serializers.CharField(label=_("查询模板名称"), max_length=128)
    space_scope = serializers.ListField(
        label=_("生效范围"), required=False, default=[], child=serializers.IntegerField(label=_("空间 ID"))
    )
    expression = serializers.CharField(label="查询表达式", required=False, allow_blank=True, default="")
    query_configs = serializers.ListField(
        label=_("查询配置"), required=True, min_length=1, child=QueryConfigSerializer()
    )
    functions = MixedTypeListField(label=_("函数"), required=False, default=[], allowed_types=[dict, str])
    variables = serializers.ListField(label=_("查询模板变量"), required=False, default=[], child=VariableSerializer())
