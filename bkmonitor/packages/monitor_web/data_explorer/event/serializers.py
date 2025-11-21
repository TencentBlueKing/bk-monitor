"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.data_source import get_auto_interval
from constants.data_source import DataSourceLabel
from monitor_web.data_explorer.event.constants import EventDimensionTypeEnum


class EventMetricSerializer(serializers.Serializer):
    field = serializers.CharField(label="指标名")
    method = serializers.CharField(label="汇聚方法")
    alias = serializers.CharField(label="别名", required=False)


class EventDataSource(serializers.Serializer):
    table = serializers.CharField(label="结果表")
    data_type_label = serializers.CharField(label="数据类型标签")
    data_source_label = serializers.CharField(label="数据源标签")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        # 兼容老数据源
        if attrs["data_source_label"] == DataSourceLabel.BK_APM:
            attrs["data_source_label"] = DataSourceLabel.CUSTOM
        return attrs


class EventFilterSerializer(EventDataSource):
    NO_KEYWORD_QUERY_PATTERN = re.compile(r"[+\-=&|><!(){}\[\]^\"~*?:/]|AND|OR|TO|NOT|^\d+$")

    query_string = serializers.CharField(
        label="查询语句（请优先使用 where）", required=False, default="*", allow_blank=True
    )
    filter_dict = serializers.DictField(label="过滤条件", required=False, default={})
    where = serializers.ListField(label="过滤条件", required=False, default=[], child=serializers.DictField())
    group_by = serializers.ListSerializer(label="聚合字段", required=False, default=[], child=serializers.CharField())

    @classmethod
    def drop_group_by(cls, query_configs: list[dict[str, Any]]):
        for query_config in query_configs:
            query_config["group_by"] = []

    def validate(self, attrs):
        attrs = super().validate(attrs)

        query_string: str = attrs.get("query_string", "")
        if not query_string:
            return attrs

        if self.NO_KEYWORD_QUERY_PATTERN.search(query_string):
            return attrs

        attrs["query_string"] = f"*{query_string}*"
        return attrs


class EventQueryConfigSerializer(EventFilterSerializer):
    interval = serializers.IntegerField(label="汇聚周期（秒）", required=False)
    metrics = serializers.ListField(label="查询指标", child=EventMetricSerializer(), allow_empty=True, default=[])


class BaseEventRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)


class EventTimeSeriesRequestSerializer(BaseEventRequestSerializer):
    expression = serializers.CharField(label="查询表达式", allow_blank=True)
    # 事件/日志场景，无论最后一个点的数据是否完整都需要返回，所以默认不做时间对齐。
    time_alignment = serializers.BooleanField(label="是否对齐时间", required=False, default=False)
    query_configs = serializers.ListField(label="查询配置列表", child=EventQueryConfigSerializer(), allow_empty=True)

    query_method = serializers.CharField(label="查询方法", required=False)

    def validate(self, attrs):
        time_alignment: bool = attrs.get("time_alignment", False)
        attrs["query_method"] = ("query_reference", "query_data")[time_alignment]
        attrs["null_as_zero"] = not time_alignment

        # interval 自适应
        for query_config in attrs["query_configs"]:
            if "interval" not in query_config:
                # why factor? 放大期望聚合周期，避免 1d 以上的时间范围计算出的柱子太小。
                query_config["interval"] = get_auto_interval(60, attrs["start_time"], attrs["end_time"], factor=10)
        return attrs


class EventLogsRequestSerializer(BaseEventRequestSerializer):
    # 聚合查询场景，limit 是每个数据源的数量限制，例如传 limit=5, offset=5，分别查询每个数据源的结果并聚合返回。
    # 如果有 3 个数据源，limit=10 最多返回 30 条数据，为保证数据拉取不跳页，下次拉取时 offset 设置为 10 而不是 30。
    limit = serializers.IntegerField(label="数量限制", required=False, default=10)
    offset = serializers.IntegerField(label="偏移量", required=False, default=0)
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=True)
    sort = serializers.ListSerializer(
        label="排序字段", required=False, child=serializers.CharField(), default=[], allow_empty=True
    )

    def validate(self, attrs):
        EventFilterSerializer.drop_group_by(attrs.get("query_configs") or [])
        return attrs


class EventViewConfigRequestSerializer(BaseEventRequestSerializer):
    data_sources = serializers.ListSerializer(label="数据源列表", child=EventDataSource(), allow_empty=False)


class EventTopKRequestSerializer(BaseEventRequestSerializer):
    limit = serializers.IntegerField(label="数量限制", required=False, default=0)
    fields = serializers.ListField(
        label="维度字段列表", child=serializers.CharField(label="维度字段"), allow_empty=False
    )
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=True)
    need_empty = serializers.BooleanField(label="是否需要统计空值", required=False, default=False)


class EventTotalRequestSerializer(BaseEventRequestSerializer):
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=True)

    def validate(self, attrs):
        EventFilterSerializer.drop_group_by(attrs.get("query_configs") or [])
        return attrs


class EventDownloadTopKRequestSerializer(EventTopKRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if len(attrs["fields"]) > 1:
            raise ValueError(_("限制单次只能下载一个字段的数据，当前选择了多个字段。"))
        return attrs


class EventStatisticsFieldSerializer(serializers.Serializer):
    field_type = serializers.ChoiceField(label="字段类型", choices=EventDimensionTypeEnum.choices())
    field_name = serializers.CharField(label="字段名称")
    values = serializers.ListField(label="查询过滤条件值列表", required=False, allow_empty=True, default=[])


class EventStatisticsInfoRequestSerializer(BaseEventRequestSerializer):
    field = EventStatisticsFieldSerializer(label="字段")
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=True)


class EventStatisticsGraphRequestSerializer(EventTimeSeriesRequestSerializer):
    field = EventStatisticsFieldSerializer(label="字段")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        field = attrs["field"]
        if field["field_type"] != EventDimensionTypeEnum.INTEGER.value:
            return attrs
        if len(field["values"]) < 4:
            raise ValueError(_("数值类型查询条件不足"))
        return attrs


class EventGenerateQueryStringRequestSerializer(serializers.Serializer):
    where = serializers.ListField(label="过滤条件", default=[], child=serializers.DictField())


class EventTagDetailRequestSerializer(EventTimeSeriesRequestSerializer):
    limit = serializers.IntegerField(label="数量限制", required=False, default=5)
    interval = serializers.IntegerField(label="汇聚周期（秒）", required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        attrs["expression"] = "a"
        for query_config in attrs["query_configs"]:
            attrs["interval"] = query_config.get("interval") or 60

        attrs["end_time"] = attrs["start_time"] + attrs["interval"]

        return attrs
