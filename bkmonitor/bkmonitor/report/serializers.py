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

from constants.new_report import StaffEnum


class SubscriberSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.ChoiceField(required=False, choices=StaffEnum.get_choices())
    is_enabled = serializers.BooleanField()


class ChannelSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    subscribers = SubscriberSerializer(many=True)
    channel_name = serializers.CharField()
    send_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ScenarioConfigSerializer(serializers.Serializer):
    # Clustering
    index_set_id = serializers.IntegerField()
    is_show_new_pattern = serializers.BooleanField()
    pattern_level = serializers.CharField()
    log_display_count = serializers.IntegerField()
    year_on_year_change = serializers.CharField()
    year_on_year_hour = serializers.IntegerField()
    generate_attachment = serializers.BooleanField()


class FrequencySerializer(serializers.Serializer):
    type = serializers.IntegerField(required=True, label="频率类型")
    day_list = serializers.ListField(required=False, label="几天")
    week_list = serializers.ListField(required=False, label="周几")
    hour = serializers.FloatField(required=False, label="小时频率")
    run_time = serializers.CharField(required=False, label="运行时间", allow_blank=True)

    class DataRangeSerializer(serializers.Serializer):
        time_level = serializers.CharField(required=True, label="数据范围时间等级")
        number = serializers.IntegerField(required=True, label="数据范围时间")

    data_range = DataRangeSerializer(required=False)


class ContentConfigSerializer(serializers.Serializer):
    title = serializers.CharField()
    is_link_enabled = serializers.BooleanField()
