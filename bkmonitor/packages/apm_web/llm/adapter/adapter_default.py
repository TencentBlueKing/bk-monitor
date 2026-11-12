"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any

from apm_web.llm.constants import STANDARD_FIELDS

from .utils import safe_parse, standard_content, text_message


def append_system_messages(attrs: dict[str, Any], content: dict[str, Any]) -> None:
    messages = content.get("gen_ai.input.messages")
    source = safe_parse(attrs.get("llm.input"))
    if not isinstance(messages, list) or not isinstance(source, list):
        return

    merged = list(messages)
    for item in source:
        if not isinstance(item, dict) or item.get("type") != "system":
            continue
        data = item.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("content"), str):
            continue
        message = text_message("system", data["content"])
        if message not in merged:
            merged.append(message)
    content["gen_ai.input.messages"] = merged


def convert(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for span in raw:
        attrs = span["attributes"]
        attributes = {
            key: value for key, value in attrs.items() if key in STANDARD_FIELDS and value not in (None, "", [])
        }
        attributes.update(standard_content(attrs))
        append_system_messages(attrs, attributes)
        if not attributes:
            continue
        spans.append(
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span["parent_span_id"],
                "span_name": span["span_name"],
                "start_time": span["start_time"],
                "end_time": span["end_time"],
                "elapsed_time": span["elapsed_time"],
                "status": span["status"],
                "resource": span["resource"],
                "attributes": attributes,
            }
        )
    return spans
