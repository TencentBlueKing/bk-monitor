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

from rest_framework import serializers

from apm_web.models import Application

from .constants import EventSource


class BaseEventRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称", required=False)

    def validate(self, attrs):
        app = Application.objects.filter(bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]).first()
        if not app:
            raise ValueError(f"应用: ({attrs['bk_biz_id']}){attrs['app_name']} 不存在")
        return attrs


class BaseEventFilterRequestSerializer(BaseEventRequestSerializer):
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    query_string = serializers.CharField(label="查询语句（请优先使用 where）", required=False)
    where = serializers.ListField(label="过滤条件", required=False, default=[], child=serializers.DictField())
    sources = serializers.ChoiceField(label="事件来源", required=False, default=[], choices=EventSource.choices())


class EventTimeSeriesRequestSerializer(BaseEventRequestSerializer):
    pass


class EventListRequestSerializer(BaseEventRequestSerializer):
    pass
