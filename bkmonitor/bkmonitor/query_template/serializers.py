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

from bk_monitor_base.strategy import get_metric_id
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from . import constants


class MixedTypeListField(serializers.ListField):
    def __init__(self, **kwargs):
        self.allowed_types = kwargs.pop("allowed_types", [])
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any):
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
    default = serializers.JSONField(label=_("默认值"), required=False, default=None, allow_null=True)
    related_tag = serializers.CharField(label=_("关联维度"), required=False)
    related_metrics = serializers.ListField(
        label=_("关联指标"), required=False, min_length=1, child=MetricInfoSerializer()
    )
    options = serializers.ListField(label=_("可选范围"), required=False, default=[], child=serializers.CharField())


class VariableSerializer(serializers.Serializer):
    name = serializers.RegexField(label=_("变量名"), max_length=50, regex=r"^[a-zA-Z0-9._]+$")
    alias = serializers.CharField(label=_("变量别名"), max_length=128, default="", allow_blank=True)
    type = serializers.ChoiceField(label=_("变量类型"), choices=constants.VariableType.choices())
    config = VariableConfigSerializer(label=_("变量配置"), default={})
    description = serializers.CharField(label=_("变量描述"), required=False, allow_blank=True, default="")

    def validate(self, attrs: dict[str, Any]):
        variable_type: constants.VariableType = constants.VariableType.from_value(attrs["type"])

        if variable_type.is_required_related_tag() and not attrs["config"].get("related_tag"):
            raise serializers.ValidationError(
                _("变量类型为 {name} 时，必须指定「关联维度」。").format(name=variable_type.label)
            )

        if variable_type.is_required_related_metrics() and not attrs["config"].get("related_metrics"):
            raise serializers.ValidationError(
                _("变量类型为 {name} 时，必须指定「关联指标」。").format(name=variable_type.label)
            )

        # 校验变量默认值的类型
        default_value: Any = attrs["config"].get("default")
        if default_value is None:
            return attrs

        error_message: str = _("变量类型为 {name} 时，默认值类型必须为 {value_type}。")
        if variable_type in {constants.VariableType.GROUP_BY, constants.VariableType.TAG_VALUES}:
            error_message = error_message.format(name=variable_type.label, value_type="list[str]")
            self._validate_string_list(default_value, error_message)
        elif variable_type in {
            constants.VariableType.CONDITIONS,
            constants.VariableType.FUNCTIONS,
            constants.VariableType.EXPRESSION_FUNCTIONS,
        }:
            error_message = error_message.format(name=variable_type.label, value_type="list[dict]")
            self._validate_dict_list(default_value, error_message)
        elif variable_type in {constants.VariableType.METHOD, constants.VariableType.CONSTANTS}:
            error_message = error_message.format(name=variable_type.label, value_type="str")
            self._validate_string(default_value, error_message)

        return attrs

    @classmethod
    def _validate_string_list(cls, default_value: Any, error_message: str):
        cls._validate_list(default_value, error_message)
        for v in default_value:
            cls._validate_string(v, error_message)

    @classmethod
    def _validate_dict_list(cls, default_value: Any, error_message: str):
        cls._validate_list(default_value, error_message)
        for v in default_value:
            if not isinstance(v, dict):
                raise serializers.ValidationError(error_message)

    @staticmethod
    def _validate_string(default_value: Any, error_message: str):
        if not isinstance(default_value, str):
            raise serializers.ValidationError(error_message)

    @staticmethod
    def _validate_list(default_value: Any, error_message: str):
        if not isinstance(default_value, list):
            raise serializers.ValidationError(error_message)


class QueryConfigSerializer(serializers.Serializer):
    table = serializers.CharField(label=_("结果表"), allow_blank=True)
    data_label = serializers.CharField(label=_("数据标签"), required=False, allow_blank=True, default="")
    data_type_label = serializers.CharField(label=_("数据类型标签"))
    data_source_label = serializers.CharField(label=_("数据源标签"))
    interval = serializers.IntegerField(label=_("汇聚周期（秒）"), required=False)
    index_set_id = serializers.CharField(label=_("索引集 ID"), required=False)
    metric_id = serializers.CharField(label=_("指标 ID"), required=False)
    promql = serializers.CharField(label=_("PromQL 查询语句"), required=False, allow_blank=True, default="")
    metrics = serializers.ListField(label=_("指标"), required=False, default=[], child=MetricSerializer())
    where = MixedTypeListField(label=_("过滤条件"), required=False, default=[], allowed_types=[dict, str])
    functions = MixedTypeListField(label=_("函数"), required=False, default=[], allowed_types=[dict, str])
    group_by = serializers.ListField(label=_("聚合字段"), required=False, default=[], child=serializers.CharField())
    query_string = serializers.CharField(label=_("查询语句"), required=False, allow_blank=True, default="")

    def validate(self, attrs: dict[str, Any]):
        metric_field: str = ""
        try:
            metric_field = attrs["metrics"][0]["field"]
        except (KeyError, IndexError):
            pass

        attrs["metric_id"] = get_metric_id(
            attrs["data_source_label"],
            attrs["data_type_label"],
            metric_field=metric_field,
            result_table_id=attrs["table"],
            promql=attrs.get("promql", ""),
        )
        return attrs


class QueryTemplateSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    name = serializers.RegexField(label=_("查询模板名称"), max_length=50, regex=r"^[a-z0-9_]+$")
    alias = serializers.CharField(label=_("查询模板别名"), max_length=128, required=False, allow_blank=True, default="")
    namespace = serializers.ChoiceField(
        label=_("命名空间"),
        required=False,
        choices=constants.Namespace.choices(),
        default=constants.Namespace.DEFAULT.value,
    )
    description = serializers.CharField(label=_("查询模板描述"), required=False, allow_blank=True, default="")
    space_scope = serializers.ListField(
        label=_("生效范围"), required=False, default=[], child=serializers.IntegerField(label=_("空间 ID"))
    )
    expression = serializers.CharField(label="查询表达式", required=False, allow_blank=True, default="")
    query_configs = serializers.ListField(
        label=_("查询配置"), required=True, min_length=1, child=QueryConfigSerializer()
    )
    functions = MixedTypeListField(label=_("函数"), required=False, default=[], allowed_types=[dict, str])
    variables = serializers.ListField(label=_("查询模板变量"), required=False, default=[], child=VariableSerializer())
    unit = serializers.CharField(label=_("单位"), allow_blank=True, default="")

    @staticmethod
    def validate_variables(variables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 变量名称唯一性校验
        variable_names: set[str] = set()
        for variable in variables:
            if variable["name"] in variable_names:
                raise serializers.ValidationError(
                    _("变量名 {variable_name} 重复").format(variable_name=variable["name"])
                )
            variable_names.add(variable["name"])
        return variables
