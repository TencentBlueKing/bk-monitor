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
from rest_framework import serializers

from apm.constants import QueryMode


class FilterSerializer(serializers.Serializer):
    key = serializers.CharField(label="查询键")
    operator = serializers.CharField(label="操作符")
    value = serializers.ListSerializer(label="查询值", child=serializers.CharField(allow_blank=True), allow_empty=True)


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
