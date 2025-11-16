"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import uuid
from typing import Any

from django.utils.translation import gettext_lazy as _

from ...constants import (
    DISPLAY_FIELDS,
    DisplayFieldType,
    EventDomain,
    EVENT_ORIGIN_MAPPING,
    EventSource,
    EventType,
)
from .base import BaseEventProcessor
from ...utils import get_field_label, format_field


class OriginEventProcessor(BaseEventProcessor):
    """原始事件数据处理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def _flatten_dict(cls, data: dict[str, Any], paths: list[str]) -> dict[str, Any]:
        flatten_dict: dict[str, Any] = {}
        for key, value in list(data.items()):
            next_paths: list[str] = paths + [key]
            paths_str: str = ".".join(next_paths)
            if isinstance(value, dict):
                flatten_dict.update(cls._flatten_dict(value, next_paths))
            else:
                flatten_dict[paths_str] = value
        return flatten_dict

    def process(self, origin_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events = []
        for origin_event in origin_events:
            origin_event: dict[str, Any] = self._flatten_dict(origin_event, [])
            # 提取并处理元数据
            _meta = origin_event.pop("_meta", {})
            data_label = _meta.get("__data_label")
            domain, source = self.get_source_and_domain(origin_event, data_label)
            _meta["__source"], _meta["__domain"] = source, domain
            if "__doc_id" not in _meta:
                # 兼容非 UnifyQuery 查询场景下没有 __doc_id 的情况，随机生成一个哈希，该值仅用于前端作为数据唯一标识。
                _meta["__doc_id"] = uuid.uuid4().hex

            # 补充 source 字段
            source_alias: str = _("{domain}/{source}").format(
                domain=EventDomain.from_value(domain).label, source=EventSource.from_value(source).label
            )

            # 事件字段统一转为整数
            origin_event["time"] = int(origin_event.get("time", 0))

            event = self.process_display_field(origin_event)
            event["source"] = {"value": source, "alias": source_alias}

            # 补充 type 字段
            dimensions_type = origin_event.get("dimensions.type")
            if not dimensions_type or dimensions_type not in (EventType.Normal.value, EventType.Warning.value):
                # 填充默认值
                dimensions_type = EventType.Default.value
            event["type"] = {"value": dimensions_type, "alias": dimensions_type}

            # 加入元数据和原始数据
            event["_meta"] = _meta
            event["origin_data"] = origin_event

            events.append(event)

        return sorted(events, key=lambda _e: -(_e["_meta"].get("_time_") or int(_e["origin_data"].get("time", 0))))

    @classmethod
    def process_display_field(cls, origin_event: dict[str, Any]) -> dict[str, Any]:
        """
        构建展示字段
        """
        event = {}
        for field in DISPLAY_FIELDS:
            field_name = field["name"]
            field_value = origin_event.get(field_name, "")

            # 初始化事件字段
            event[field_name] = {"value": field_value, "alias": field_value}

            # 添加类型相关的字段
            if field.get("type", "") == DisplayFieldType.LINK.value:
                event[field_name]["url"] = ""
            elif field.get("type", "") == DisplayFieldType.DESCRIPTIONS.value:
                event[field_name]["detail"] = {
                    field_name: {
                        "label": get_field_label(field_name, data_label=""),
                        "value": field_value,
                        "alias": field_value,
                    }
                }

        return event

    @classmethod
    def get_source_and_domain(cls, origin_event, data_label) -> tuple[str, str]:
        # 根据 data_label获取
        event_origin: tuple[str, str] = EVENT_ORIGIN_MAPPING.get(data_label)
        if event_origin:
            return event_origin

        # 从维度获取，获取不到返回默认值 DEFAULT
        return (
            origin_event.get(format_field("domain"), EventDomain.DEFAULT.value),
            origin_event.get(format_field("source"), EventSource.DEFAULT.value),
        )
