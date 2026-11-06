"""标准 Span 的行内预览；原始产品字段仅由 Adapter 解释。"""

from __future__ import annotations

import json
from typing import Any

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import flow_attribute_fields
from apm_web.llm.adapter.utils import CONTENT_FIELDS
from apm_web.llm.builders.summary import TraceSummary
from apm_web.strategy.dispatch.entity import EntitySet
from constants.apm import OtlpKey

PREVIEW_LENGTH = 255


def _preview_string(value: Any, *, compact: bool = False, limit: int = PREVIEW_LENGTH) -> str:
    if isinstance(value, str):
        return value[:limit]
    if value is None:
        return ""
    # 按片段编码，避免为复杂工具参数先生成完整的 JSON 字符串。
    chunks: list[str] = []
    remaining: int = limit
    for chunk in json.JSONEncoder(
        ensure_ascii=False, default=str, separators=(",", ":") if compact else None
    ).iterencode(value):
        chunks.append(chunk[:remaining])
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "".join(chunks)


def tool_preview(value: Any) -> str | dict[str, str]:
    for _ in range(32):
        if isinstance(value, str):
            try:
                decoded: Any = json.loads(value)
            except (ValueError, RecursionError):
                break
            if not isinstance(decoded, dict | list):
                break
            value = decoded
        if not isinstance(value, list):
            break
        value = value[0] if value else None
    else:
        return ""
    if isinstance(value, dict):
        return {str(key)[:PREVIEW_LENGTH]: _preview_string(item) for key, item in value.items()}
    return _preview_string(value)


def remove_content(attributes: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in attributes.items() if key not in CONTENT_FIELDS}


def _interaction_parts(message: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    parts: Any = message.get("parts")
    if not isinstance(parts, list):
        return [], True
    selected: list[dict[str, Any]] = []
    continues: bool = True
    for part in reversed(parts):
        if not isinstance(part, dict):
            continue
        kind: str = part.get("type", "")
        if kind in {"tool_call", "tool_call_response", "tool_result"}:
            if selected and (kind == "tool_call") != (selected[0].get("type") == "tool_call"):
                continues = False
                break
            selected.append(part)
        elif TraceSummary.part_preview(part, "text"):
            if not selected:
                return [part], False
            continues = False
            break
    return list(reversed(selected)), continues


def _tool_json_preview(value: Any) -> str:
    if isinstance(value, str):
        try:
            decoded: Any = json.loads(value)
        except (ValueError, RecursionError):
            decoded = None
        if isinstance(decoded, dict | list):
            value = decoded
    preview: str = _preview_string(value, compact=True, limit=PREVIEW_LENGTH + 1)
    return f"{preview[:PREVIEW_LENGTH]}…" if len(preview) > PREVIEW_LENGTH else preview


def model_message_preview(messages: Any) -> dict[str, Any] | None:
    """选择最近一次交互；同批工具保留原始顺序，每个工具独立生成有界 JSON 预览。"""
    if not isinstance(messages, list):
        return None
    selected: list[tuple[int, list[dict[str, Any]]]] = []
    for index in range(len(messages) - 1, -1, -1):
        message: Any = messages[index]
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant", "model", "tool"}:
            continue
        parts, continues = _interaction_parts(message)
        if not parts:
            continue
        is_result: bool = parts[0].get("type") in {"tool_call_response", "tool_result"}
        if selected and not is_result:
            break
        selected.append((index, parts))
        if not is_result or not continues:
            break
    if not selected:
        return None
    last_index: int = selected[0][0]
    part: dict[str, Any] = selected[0][1][0]
    if part.get("type") not in {"tool_call", "tool_call_response", "tool_result"}:
        role: str = messages[last_index].get("role", "assistant")
        return {
            "source": "assistant" if role == "model" else role,
            "value": TraceSummary.part_preview(part, "text")[:PREVIEW_LENGTH],
        }

    # 一次扫描关联调用名，避免多工具时为每个返回重复回溯整段历史。
    call_names: dict[str, str] = {}
    for index in range(last_index + 1):
        message = messages[index]
        if not isinstance(message, dict) or not isinstance(message.get("parts"), list):
            continue
        for candidate in message["parts"]:
            if isinstance(candidate, dict) and candidate.get("type") == "tool_call":
                call_id: Any = candidate.get("id")
                if isinstance(call_id, str) and call_id:
                    call_names[call_id] = str(candidate.get("name") or "")
    tools: list[dict[str, str]] = []
    for index, parts in reversed(selected):
        for part in parts:
            call_id = part.get("id")
            name: Any = part.get("name") or messages[index].get("name")
            if not name and isinstance(call_id, str):
                name = call_names.get(call_id, "")
            value: Any = (
                part.get("arguments")
                if part.get("type") == "tool_call"
                else part.get("response", part.get("content", part.get("result")))
            )
            tools.append({"tool_name": str(name or "")[:PREVIEW_LENGTH], "value": _tool_json_preview(value)})
    return {"source": "tool", "tools": tools}


def prepare_flow_spans(
    raw_spans: list[dict[str, Any]], entity_set: EntitySet, *, include_input_output: bool, preview: bool
) -> list[dict[str, Any]]:
    """逐条标准化并提取预览，立即释放该条原始正文和解析后的消息。"""
    spans: list[dict[str, Any]] = []
    metadata_fields: set[str] = flow_attribute_fields()
    for index, raw in enumerate(raw_spans):
        raw = {**raw, "attributes": raw.get("attributes") or {}, "events": raw.get("events") or []}
        if not include_input_output:
            raw = {
                **raw,
                "attributes": {
                    key: value for key, value in (raw.get("attributes") or {}).items() if key in metadata_fields
                },
                "events": [],
            }
        converted = adapt_spans([raw], entity_set)
        for span in converted:
            if preview and include_input_output:
                attributes: dict[str, Any] = span["attributes"]
                if span.get("span_type") == "TOOL":
                    span["input"] = tool_preview(attributes.get("gen_ai.tool.call.arguments"))
                    span["output"] = tool_preview(attributes.get("gen_ai.tool.call.result"))
                else:
                    input_text, output_text = TraceSummary.trace_previews([span], latest_input=True)
                    span["input"] = input_text[:PREVIEW_LENGTH]
                    span["output"] = output_text[:PREVIEW_LENGTH]
                    del input_text, output_text
                    if span.get("span_type") == "LLM":
                        for side in ("input", "output"):
                            interaction: dict[str, Any] | None = model_message_preview(
                                attributes.get(f"gen_ai.{side}.messages")
                            )
                            if interaction is None and side == "input" and attributes.get("gen_ai.system_instructions"):
                                interaction = {"source": "system", "value": span[side]}
                            if interaction is not None:
                                span[f"{side}_preview"] = interaction
                del attributes
            if preview or not include_input_output:
                span["attributes"] = remove_content(span.get("attributes") or {})
            spans.append(span)
        if preview or not include_input_output:
            raw_spans[index] = {
                key: value for key, value in raw.items() if key not in ("attributes", "events", "links")
            }
        del raw, converted
    spans.sort(key=lambda span: span[OtlpKey.START_TIME])
    return spans
