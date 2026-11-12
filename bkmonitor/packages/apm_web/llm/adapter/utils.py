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

import ast
import json
import re
from typing import Any

from pydantic_core import from_json

CONTENT_FIELDS = (
    "gen_ai.system_instructions",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.tool.definitions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
)


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def put(target: dict[str, Any], key: str, value: Any) -> None:
    if key not in target and value not in (None, "", []):
        target[key] = value


def safe_parse(value: Any) -> Any:
    """解析 JSON/Python 字面量并恢复截断 JSON；无法解析时保留原值。"""
    if not isinstance(value, str):
        return value
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed: Any = parser(value)
            return parsed if isinstance(parsed, dict | list) else value
        except (ValueError, SyntaxError):
            continue
    return repair_truncated_json(value)


def indexed(attrs: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    """将 prefix.N.field 扁平属性按 N 重组。"""
    result: dict[int, dict[str, Any]] = {}
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)\.(.+)$")
    for key, value in attrs.items():
        if match := pattern.match(key):
            result.setdefault(int(match.group(1)), {})[match.group(2)] = value
    return [result[index] for index in sorted(result)]


def standard_content(attrs: dict[str, Any]) -> dict[str, Any]:
    """读取已符合标准的正文属性，产品字段只补充缺失值。"""
    content: dict[str, Any] = {}
    instructions = safe_parse(attrs.get("gen_ai.system_instructions"))
    if instructions not in (None, "") and not isinstance(instructions, list):
        instructions = [{"type": "text", "content": str(instructions)}]
    put(content, "gen_ai.system_instructions", instructions)
    for key in CONTENT_FIELDS[1:]:
        put(content, key, safe_parse(attrs.get(key)))
    return content


def split_system(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    instructions: list[dict[str, Any]] = []
    regular: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "system":
            instructions.extend(message.get("parts", []))
        else:
            regular.append(message)
    return instructions, regular


def text_message(role: str, content: Any) -> dict[str, Any]:
    return {"role": role, "parts": [{"type": "text", "content": str(content)}]}


def tool_call_part(call: dict[str, Any]) -> dict[str, Any]:
    function: dict[str, Any] = call
    if isinstance(nested := call.get("function"), dict):
        function = nested
    name = function.get("name", call.get("function.name", ""))
    arguments = function.get("arguments", function.get("args", call.get("function.arguments", {})))
    part = {"type": "tool_call", "name": str(name), "arguments": safe_parse(arguments)}
    if call.get("id") not in (None, ""):
        part["id"] = str(call["id"])
    return part


def tool_response_part(response: Any, call_id: Any = None) -> dict[str, Any]:
    part = {"type": "tool_call_response", "response": safe_parse(response)}
    if call_id not in (None, ""):
        part["id"] = str(call_id)
    return part


def normalize_schema(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_schema(item) for item in value]
    if isinstance(value, dict):
        return {
            key: item.lower() if key == "type" and isinstance(item, str) else normalize_schema(item)
            for key, item in value.items()
        }
    return value


def repair_truncated_json(value: Any) -> Any:
    """只恢复截断的 JSON 容器；普通文本、有效 JSON 和无法解析的内容保持原样。"""
    if not isinstance(value, str) or not value.lstrip().startswith(("[", "{")):
        return value
    try:
        json.loads(value)
    except json.JSONDecodeError as error:
        if error.msg == "Extra data":
            return value
        try:
            partial = value
            # 不完整转义会让解析器丢弃整段字符串，只移除尚未收全的尾部转义。
            escape = re.search(r"(\\+)(?:u[0-9a-fA-F]{0,3})?$", partial)
            if escape and len(escape[1]) % 2:
                partial = partial[: escape.start() + len(escape[1]) - 1]
            repaired = from_json(partial, allow_partial="trailing-strings", cache_strings=False)
        except ValueError:
            return value
        if isinstance(repaired, dict | list) and repaired:
            return repaired
    return value


def repair_span_content(span: dict[str, Any]) -> dict[str, Any]:
    """复制被修复的字段，保留 origin_data；不把正文中的普通 JSON 文本当成协议解析。"""
    attributes: dict[str, Any] = dict(span.get("attributes") or {})
    for field in CONTENT_FIELDS:
        if field not in attributes:
            continue
        value = repair_truncated_json(attributes[field])
        if isinstance(value, list):
            items: list[Any] = []
            for item in value:
                if not isinstance(item, dict) or not isinstance(item.get("parts"), list):
                    items.append(item)
                    continue
                parts: list[Any] = []
                for part in item["parts"]:
                    if not isinstance(part, dict):
                        parts.append(part)
                        continue
                    part = dict(part)
                    for key in ("arguments", "response", "result"):
                        if key in part:
                            part[key] = repair_truncated_json(part[key])
                    parts.append(part)
                items.append({**item, "parts": parts})
            value = items
        attributes[field] = value
    return {**span, "attributes": attributes}
