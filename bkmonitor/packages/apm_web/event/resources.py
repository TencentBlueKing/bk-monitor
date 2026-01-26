"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from monitor_web.data_explorer.event import resources as event_resources
from monitor_web.data_explorer.event.constants import (
    EventSource,
    EventType,
)
from monitor_web.data_explorer.event.utils import get_field_label

from ..models import ApmMetaConfig, Application
from . import serializers

logger = logging.getLogger(__name__)


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventTimeSeriesResource().request(validated_request_data)


class EventLogsResource(Resource):
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventLogsResource().request(validated_request_data)


class EventViewConfigResource(Resource):
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        sources: list[dict[str, str]] = []
        for related_source in validated_request_data["related_sources"]:
            sources.append({"value": related_source, "alias": EventSource.from_value(related_source).label})

        view_config: dict[str, Any] = event_resources.EventViewConfigResource().request(validated_request_data)
        view_config["sources"] = sources
        return view_config


class EventTopKResource(Resource):
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        return event_resources.EventTopKResource().request(validated_request_data)


class EventTotalResource(Resource):
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventTotalResource().request(validated_request_data)


class EventTagDetailResource(Resource):
    RequestSerializer = serializers.EventTagDetailRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventTagDetailResource().request(validated_request_data)


class EventGetTagConfigResource(Resource):
    RequestSerializer = serializers.EventGetTagConfigRequestSerializer

    DEFAULT_TAG_CONFIG: dict[str, Any] = {
        "is_enabled_metric_tags": False,
        "source": {"is_select_all": True, "list": []},
        "type": {"is_select_all": True, "list": []},
    }

    @classmethod
    def process_key(cls, key: str) -> str:
        return f"event_tag_config:{key}"

    @classmethod
    def generate_field_columns(cls, field_metas: dict[str, Any]) -> list[dict[str, Any]]:
        field_columns: list[dict[str, Any]] = []
        for field, meta in field_metas.items():
            field_column = {
                "name": field,
                "alias": get_field_label(field),
                "list": [
                    {"value": value, "alias": meta["enum"].from_value(value).label}
                    for value, _ in meta["enum"].choices()
                ],
            }
            field_columns.append(field_column)

            count_map: dict[str, int] | None = meta.get("count_map")
            if count_map is None:
                continue

            for option in field_column["list"]:
                option["count"] = meta["count_map"].get(option["value"], 0)

        return field_columns

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        request = get_request(peaceful=True)
        if not request:
            return {}

        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        app: Application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

        # 序列化器已做存在性判断，此处直接使用。
        app_event_config: dict[str, Any] = app.event_config

        servie_tag_config: dict[str, Any] = {}
        servie_config: ApmMetaConfig | None = ApmMetaConfig.get_service_config_value(
            bk_biz_id, app_name, service_name, self.process_key(validated_request_data["key"])
        )
        if servie_config:
            servie_tag_config = servie_config.config_value

        return {
            "columns": self.generate_field_columns({"type": {"enum": EventType}, "source": {"enum": EventSource}}),
            # 配置优先级：默认 > App > Service
            "config": {**self.DEFAULT_TAG_CONFIG, **app_event_config, **servie_tag_config},
        }


class EventUpdateTagConfigResource(Resource):
    RequestSerializer = serializers.EventUpdateTagConfigRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        ApmMetaConfig.service_config_setup(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            service_name=validated_request_data["service_name"],
            config_key=EventGetTagConfigResource.process_key(validated_request_data["key"]),
            config_value=validated_request_data["config"],
        )
        return {}


class EventStatisticsGraphResource(Resource):
    RequestSerializer = serializers.EventStatisticsGraphRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventStatisticsGraphResource().request(validated_request_data)


class EventStatisticsInfoResource(Resource):
    RequestSerializer = serializers.EventStatisticsInfoRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        return event_resources.EventStatisticsInfoResource().request(validated_request_data)
