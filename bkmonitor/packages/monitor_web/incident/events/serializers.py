"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers

from monitor_web.incident.events.constants import EntityType


class BaseIncidentEventsSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", default=0)
    start_time = serializers.IntegerField(label="开始时间", default=0)
    end_time = serializers.IntegerField(label="结束时间", default=0)
    interval = serializers.IntegerField(label="时间间隔", default=3600)

    def validate_index_info(self, index_info):
        if not isinstance(index_info, dict):
            raise serializers.ValidationError("index_info must be a json object")

        entity_type = index_info.get("entity_type")

        if entity_type is None:
            raise serializers.ValidationError("entity_type不能为空")

        valid_entity_types = EntityType.choices()
        if entity_type not in valid_entity_types:
            raise serializers.ValidationError(f"entity_type must be one of {valid_entity_types}")

        return index_info


class EventsSearchSerializer(BaseIncidentEventsSerializer):
    index_info = serializers.JSONField(label="索引信息", default=None)

    def validate(self, attrs):
        # 调用基类的索引信息验证方法
        if attrs.get("index_info"):
            attrs["index_info"] = self.validate_index_info(attrs["index_info"])
        return attrs


class EventDetailSerializer(BaseIncidentEventsSerializer):
    index_info = serializers.JSONField(label="索引信息", default=None)

    def validate(self, attrs):
        # 调用基类的索引信息验证方法
        if attrs.get("index_info"):
            attrs["index_info"] = self.validate_index_info(attrs["index_info"])
        return attrs
