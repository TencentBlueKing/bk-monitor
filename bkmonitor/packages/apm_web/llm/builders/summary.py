"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections.abc import Mapping
from typing import Any

from constants.apm import OtlpKey


class TraceSummary:
    """从原始 Span 取时间范围，从标准 Span 选取输入输出及会话信息。"""

    _TEXT_PART_TYPES = {"", "text", "input_text", "output_text"}
    _OUTPUT_PREVIEW_KEYS = ("text", "reasoning", "tool_call", "tool_result")

    @staticmethod
    def _preview_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if value in (None, "", [], {}):
            return ""
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value).strip()

    @classmethod
    def part_preview(cls, part: dict[str, Any], expected: str) -> str:
        part_type = str(part.get("type") or "")
        if expected == "text" and part_type in cls._TEXT_PART_TYPES:
            return cls._preview_text(part.get("content", part.get("text")))
        if expected == "reasoning" and part_type in {"reasoning", "thinking"}:
            return cls._preview_text(part.get("content", part.get("text", part.get("thinking"))))
        if expected == "tool_call" and part_type == "tool_call":
            name = cls._preview_text(part.get("name"))
            arguments = cls._preview_text(part.get("arguments"))
            return " ".join(item for item in (name, arguments) if item)
        if expected == "tool_result" and part_type in {"tool_call_response", "tool_result"}:
            return cls._preview_text(part.get("response", part.get("content", part.get("result"))))
        return ""

    @classmethod
    def _message_previews(cls, messages: Any, expected: str, *, roles: set[str]) -> list[str]:
        if not isinstance(messages, list):
            return []
        previews: list[str] = []
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") not in roles:
                continue
            parts = message.get("parts")
            if not isinstance(parts, list):
                continue
            for part in reversed(parts):
                if isinstance(part, dict) and (preview := cls.part_preview(part, expected)):
                    return [preview]
        return previews

    @classmethod
    def _input_preview(cls, attributes: dict[str, Any]) -> tuple[int, str]:
        messages = attributes.get("gen_ai.input.messages")
        for priority, roles in enumerate(({"user"}, {"assistant", "model"})):
            if texts := cls._message_previews(messages, "text", roles=roles):
                return priority, texts[0]
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, dict) or message.get("role") not in {"tool", "assistant"}:
                    continue
                parts = message.get("parts")
                if not isinstance(parts, list):
                    continue
                for part in reversed(parts):
                    if isinstance(part, dict):
                        for kind in ("tool_result", "tool_call"):
                            if text := cls.part_preview(part, kind):
                                return 2, text
        if arguments := cls._preview_text(attributes.get("gen_ai.tool.call.arguments")):
            return 2, arguments
        instructions = attributes.get("gen_ai.system_instructions")
        if isinstance(instructions, list):
            for part in reversed(instructions):
                if isinstance(part, dict) and (text := cls.part_preview(part, "text")):
                    return 3, text
        if texts := cls._message_previews(messages, "text", roles={"system"}):
            return 3, texts[0]
        return 4, ""

    @classmethod
    def trace_previews(cls, spans: list[dict[str, Any]], *, latest_input: bool = False) -> tuple[str, str]:
        """消息倒序取最新内容；Trace 输入默认取最早 Span，执行线可选择最新 Span。"""
        inputs: dict[int, list[tuple[int, int, str]]] = {}
        outputs: dict[str, list[tuple[int, int, str]]] = {key: [] for key in cls._OUTPUT_PREVIEW_KEYS}
        for index, span in enumerate(spans):
            attributes = span.get(OtlpKey.ATTRIBUTES) or {}
            start_time = span.get(OtlpKey.START_TIME) or 0
            end_time = span.get(OtlpKey.END_TIME) or start_time
            priority, text = cls._input_preview(attributes)
            if "input" in span:
                text = cls._preview_text(span["input"])
            if text:
                inputs.setdefault(priority, []).append((start_time, index, text))
            for kind in cls._OUTPUT_PREVIEW_KEYS:
                roles = {"assistant", "model", "tool"} if kind == "tool_result" else {"assistant", "model"}
                previews = cls._message_previews(attributes.get("gen_ai.output.messages"), kind, roles=roles)
                if kind == "tool_result" and not previews:
                    if result := cls._preview_text(attributes.get("gen_ai.tool.call.result")):
                        previews = [result]
                if kind == "text" and "output" in span:
                    previews = [cls._preview_text(span["output"])]
                if previews and previews[0]:
                    outputs[kind].append((end_time, index, previews[0]))
        input_text = ""
        if inputs:
            candidates = inputs[min(inputs)]
            input_text = (max(candidates) if latest_input else min(candidates))[2]
        for kind in cls._OUTPUT_PREVIEW_KEYS:
            if candidates := outputs[kind]:
                return input_text, max(candidates)[2]
        return input_text, ""

    @classmethod
    def build(
        cls,
        trace_id: str,
        raw_spans: list[dict[str, Any]],
        converted_spans: list[dict[str, Any]],
        tokens: Mapping[str, float],
        has_error: bool = False,
    ) -> dict[str, Any]:
        input_text, output_text = cls.trace_previews(converted_spans)
        start_time: int = min((span.get(OtlpKey.START_TIME, 0) for span in raw_spans), default=0)
        end_time: int = max((span.get(OtlpKey.END_TIME, start_time) for span in raw_spans), default=start_time)

        def first_attribute(attribute: str) -> str:
            for span in converted_spans:
                attributes = span.get(OtlpKey.ATTRIBUTES)
                if isinstance(attributes, dict) and (value := attributes.get(attribute)) not in (None, ""):
                    return str(value)
            return ""

        return {
            "group_id": trace_id,
            "group_field": OtlpKey.TRACE_ID,
            "trace_id": trace_id,
            "conversation_id": first_attribute("gen_ai.conversation.id"),
            "status": "error" if has_error else "success",
            "input": input_text,
            "output": output_text,
            "input_tokens": tokens.get("input_tokens", 0),
            "output_tokens": tokens.get("output_tokens", 0),
            **tokens,
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_time": max(0, end_time - start_time),
            "user_id": first_attribute("user.id"),
        }
