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
from monitor_web.data_explorer.event import serializers as event_serializers


class BaseEventRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称", required=False)

    def validate(self, attrs):
        if not Application.objects.filter(bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]).exists():
            raise ValueError(f"应用: ({attrs['bk_biz_id']}){attrs['app_name']} 不存在")
        return attrs


class EventTimeSeriesRequestSerializer(event_serializers.EventTimeSeriesRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super(BaseEventRequestSerializer, self).validate(attrs)
        attrs = super(event_serializers.EventTimeSeriesRequestSerializer, self).validate(attrs)
        return attrs


class EventLogsRequestSerializer(event_serializers.EventLogsRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super(BaseEventRequestSerializer, self).validate(attrs)
        attrs = super(event_serializers.EventLogsRequestSerializer, self).validate(attrs)
        return attrs


class EventViewConfigRequestSerializer(event_serializers.EventViewConfigRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super(BaseEventRequestSerializer, self).validate(attrs)
        attrs = super(event_serializers.EventViewConfigRequestSerializer, self).validate(attrs)
        return attrs


class EventTopKRequestSerializer(event_serializers.EventTopKRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super(BaseEventRequestSerializer, self).validate(attrs)
        attrs = super(event_serializers.EventTopKRequestSerializer, self).validate(attrs)
        return attrs


class EventTotalRequestSerializer(event_serializers.EventTotalRequestSerializer, BaseEventRequestSerializer):
    def validate(self, attrs):
        attrs = super(BaseEventRequestSerializer, self).validate(attrs)
        attrs = super(event_serializers.EventTotalRequestSerializer, self).validate(attrs)
        return attrs
