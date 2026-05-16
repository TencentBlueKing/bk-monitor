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

from apm_web.constants import QueryMode
from apm_web.trace.constants import EnabledStatisticsDimension
from constants.apm import OperatorGroupRelation


class FilterSerializer(serializers.Serializer):
    class OptionsSerializer(serializers.Serializer):
        is_wildcard = serializers.BooleanField(label=_("是否使用通配符"), default=False)
        group_relation = serializers.ChoiceField(
            label=_("分组关系"), choices=OperatorGroupRelation.choices(), default=OperatorGroupRelation.OR
        )

    key = serializers.CharField(label=_("查询键"))
    operator = serializers.CharField(label=_("操作符"))
    options = OptionsSerializer(label=_("操作符选项"), default={})
    value = serializers.ListSerializer(
        label=_("查询值"), child=serializers.CharField(allow_blank=True), allow_empty=True
    )


class QuerySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"))
    offset = serializers.IntegerField(label=_("偏移量"), required=False, default=0)
    limit = serializers.IntegerField(label=_("每页数量"), required=False, default=10)
    start_time = serializers.IntegerField(label=_("开始时间"))
    end_time = serializers.IntegerField(label=_("结束时间"))

    sort = serializers.ListSerializer(label=_("排序条件"), default=[], child=serializers.CharField())
    query = serializers.CharField(label=_("查询语句"), default="", allow_blank=True, allow_null=True)
    filters = serializers.ListSerializer(label=_("查询条件"), child=FilterSerializer(), default=[])


class SpanIdInputSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务ID"))
    app_name = serializers.CharField(label=_("应用名称"))
    span_id = serializers.CharField(label=_("SpanId"))


class BaseTraceRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"))


class BaseTraceFilterSerializer(serializers.Serializer):
    filters = serializers.ListSerializer(label=_("查询条件"), child=FilterSerializer(), default=[])
    query_string = serializers.CharField(label=_("查询字符串"), allow_blank=True)
    mode = serializers.ChoiceField(label=_("查询视角"), choices=QueryMode.choices())
    start_time = serializers.IntegerField(label=_("开始时间"))
    end_time = serializers.IntegerField(label=_("结束时间"))


class GetFieldsOptionValuesRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    fields = serializers.ListField(label=_("查询字段列表"), child=serializers.CharField())
    limit = serializers.IntegerField(label=_("查询条数"), required=False, default=10)


class TraceFieldsTopkRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    fields = serializers.ListField(label=_("查询字段列表"), child=serializers.CharField())
    limit = serializers.IntegerField(label=_("数量限制"), required=False, default=5)


class TraceStatisticsFieldSerializer(serializers.Serializer):
    field_type = serializers.CharField(label=_("字段类型"))
    field_name = serializers.CharField(label=_("字段名称"))
    values = serializers.ListField(label=_("查询过滤条件值列表"), required=False, allow_empty=True, default=[])

    def validate(self, attrs):
        if attrs["field_type"] not in [dimension.value for dimension in EnabledStatisticsDimension]:
            raise ValueError(_("不支持的字段类型"))
        return attrs


class TraceFieldStatisticsInfoRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label=_("字段"))


class TraceFieldStatisticsGraphRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label=_("字段"))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        field = attrs["field"]
        if field["field_type"] == EnabledStatisticsDimension.KEYWORD.value:
            return attrs
        if len(field["values"]) < 4:
            raise ValueError(_("数值类型查询条件不足"))
        return attrs


class TraceGenerateQueryStringRequestSerializer(serializers.Serializer):
    class QueryStringFilterSerializer(FilterSerializer):
        value = serializers.ListSerializer(label=_("查询值"), child=serializers.JSONField(), allow_empty=True)

    filters = serializers.ListSerializer(label=_("查询条件"), child=QueryStringFilterSerializer(), default=[])
