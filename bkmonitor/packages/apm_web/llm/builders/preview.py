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


def _preview_string(value: Any) -> str:
    if isinstance(value, str):
        return value[:PREVIEW_LENGTH]
    if value is None:
        return ""
    # 按片段编码，避免为复杂工具参数先生成完整的 JSON 字符串。
    chunks: list[str] = []
    remaining: int = PREVIEW_LENGTH
    for chunk in json.JSONEncoder(ensure_ascii=False, default=str).iterencode(value):
        chunks.append(chunk[:remaining])
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "".join(chunks)


def tool_preview(value: Any) -> str | dict[str, str]:
    for _ in range(32):
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
                    input_text, output_text = TraceSummary._trace_previews([span], latest_input=True)
                    span["input"] = input_text[:PREVIEW_LENGTH]
                    span["output"] = output_text[:PREVIEW_LENGTH]
                    del input_text, output_text
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
