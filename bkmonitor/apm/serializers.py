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
from django.utils.translation import gettext as _

from apm.constants import EnabledStatisticsDimension, QueryMode, StatisticsProperty
from constants.apm import OperatorGroupRelation


class FilterSerializer(serializers.Serializer):
    class OptionsSerializer(serializers.Serializer):
        is_wildcard = serializers.BooleanField(label="是否使用通配符", default=False)
        group_relation = serializers.ChoiceField(
            label="分组关系", choices=OperatorGroupRelation.choices(), default=OperatorGroupRelation.OR
        )

    key = serializers.CharField(label="查询键")
    operator = serializers.CharField(label="操作符")
    value = serializers.ListSerializer(label="查询值", child=serializers.CharField(allow_blank=True), allow_empty=True)
    options = OptionsSerializer(label="操作符选项", default={})


class BaseTraceRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    is_mock = serializers.BooleanField(label="是否使用mock数据", required=False, default=False)


class BaseTraceFilterSerializer(serializers.Serializer):
    filters = serializers.ListSerializer(label="查询条件", child=FilterSerializer(), default=[])
    query_string = serializers.CharField(label="查询字符串", allow_blank=True)
    mode = serializers.ChoiceField(label="查询视角", choices=QueryMode.choices())
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")


class TraceFieldsTopkRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    fields = serializers.ListField(child=serializers.CharField(), label="查询字段列表")
    limit = serializers.IntegerField(label="数量限制", required=False, default=5)


class TraceStatisticsFieldSerializer(serializers.Serializer):
    field_type = serializers.ChoiceField(label="字段类型", choices=EnabledStatisticsDimension.choices())
    field_name = serializers.CharField(label="字段名称")
    values = serializers.ListField(label="查询过滤条件值列表", required=False, allow_empty=True, default=[])


class TraceFieldStatisticsInfoRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label="字段")
    exclude_property = serializers.ListSerializer(
        label="排除属性", child=serializers.ChoiceField(choices=StatisticsProperty.choices()), default=[]
    )


class TraceFieldStatisticsGraphRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label="字段")
    query_method = serializers.CharField(label="查询方法", required=False)
    time_alignment = serializers.BooleanField(label="是否对齐时间", required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        time_alignment: bool = attrs.get("time_alignment", False)
        attrs["query_method"] = ("query_reference", "query_data")[time_alignment]
        field = attrs["field"]
        if field["field_type"] != EnabledStatisticsDimension.INTEGER.value:
            return attrs
        if len(field["values"]) < 4:
            raise ValueError(_("数值类型查询条件不足"))
        return attrs
