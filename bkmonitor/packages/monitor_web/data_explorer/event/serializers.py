# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from constants.data_source import DataSourceLabel


class EventMetricSerializer(serializers.Serializer):
    field = serializers.CharField(label="指标名")
    method = serializers.CharField(label="汇聚方法")
    alias = serializers.CharField(label="别名", required=False)


class EventDataSource(serializers.Serializer):
    table = serializers.CharField(label="结果表")
    data_type_label = serializers.CharField(label="数据类型标签")
    data_source_label = serializers.CharField(label="数据源标签")

    def validate(self, attrs):
        attrs["data_source_label"] = DataSourceLabel.BK_APM
        return attrs


class EventFilterSerializer(EventDataSource):
    query_string = serializers.CharField(label="查询语句（请优先使用 where）", required=False, default="*", allow_blank=True)
    filter_dict = serializers.DictField(label="过滤条件", required=False, default={})
    where = serializers.ListField(label="过滤条件", required=False, default=[], child=serializers.DictField())
    group_by = serializers.ListSerializer(label="聚合字段", required=False, default=[], child=serializers.CharField())


class EventQueryConfigSerializer(EventFilterSerializer):
    interval = serializers.IntegerField(label="汇聚周期（秒）", required=False)
    metrics = serializers.ListField(label="查询指标", child=EventMetricSerializer(), allow_empty=True, default=[])


class BaseEventRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    is_mock = serializers.BooleanField(label="是否使用mock数据", required=False, default=False)


class EventTimeSeriesRequestSerializer(BaseEventRequestSerializer):
    expression = serializers.CharField(label="查询表达式", allow_blank=True)
    query_configs = serializers.ListField(label="查询配置列表", child=EventQueryConfigSerializer(), allow_empty=False)


class EventLogsRequestSerializer(BaseEventRequestSerializer):
    # 聚合查询场景，limit 是每个数据源的数量限制，例如传 limit=5, offset=5，分别查询每个数据源的结果并聚合返回。
    # 如果有 3 个数据源，limit=10 最多返回 30 条数据，为保证数据拉取不跳页，下次拉取时 offset 设置为 10 而不是 30。
    limit = serializers.IntegerField(label="数量限制", required=False, default=10)
    offset = serializers.IntegerField(label="偏移量", required=False, default=0)
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=False)


class EventViewConfigRequestSerializer(BaseEventRequestSerializer):
    data_sources = serializers.ListSerializer(label="数据源列表", child=EventDataSource(), allow_empty=False)


class EventTopKRequestSerializer(BaseEventRequestSerializer):
    limit = serializers.IntegerField(label="数量限制", required=False, default=0)
    fields = serializers.ListField(label="维度字段列表", child=serializers.CharField(label="维度字段"), allow_empty=False)
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=False)


class EventTotalRequestSerializer(BaseEventRequestSerializer):
    query_configs = serializers.ListField(label="查询配置列表", child=EventFilterSerializer(), allow_empty=False)


class EventDownloadTopKRequestSerializer(EventTopKRequestSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if len(attrs["fields"]) > 1:
            raise ValueError(_("限制单次只能下载一个字段的数据，当前选择了多个字段。"))
        return attrs
