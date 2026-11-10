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

import base64
import gzip
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import tiktoken
from django.utils.translation import gettext as _

from apm_web.llm.adapter.utils import nonnegative_int
from apm_web.llm.constants import SpanType

CONTENT_CATEGORIES = {
    "system": ("gen_ai.system_instructions", "系统提示词"),
    "definitions": ("gen_ai.tool.definitions", "可用工具"),
    "input": ("gen_ai.input.messages", "输入"),
    "output": ("gen_ai.output.messages", "输出"),
}


@lru_cache(maxsize=2)
def load_encoding(name: str) -> tiktoken.Encoding:
    """词表随模块分发，初始化不访问网络。"""
    with gzip.open(Path(__file__).with_name("tokenizers") / f"{name}.json.gz", "rt") as source:
        data = json.load(source)
    data["mergeable_ranks"] = {base64.b64decode(token): rank for token, rank in data["mergeable_ranks"].items()}
    return tiktoken.Encoding(name=name, **data)


class TokenCounter:
    """一次请求内复用分词结果，避免重复编码历史上下文。"""

    def __init__(self, model: str):
        try:
            name = tiktoken.encoding_name_for_model(model)
        except KeyError:
            name = "cl100k_base"
        self.encoding = load_encoding(name if name == "o200k_base" else "cl100k_base")
        encode = self.encoding.encode_ordinary
        # 超长无空白片段的 BPE 编码可能呈二次耗时，分段限制延迟。
        self._count = lru_cache(maxsize=128)(
            lambda text: sum(len(encode(text[start : start + 8192])) for start in range(0, len(text), 8192))
        )

    def count(self, value: Any) -> int:
        if value is None or value == "":
            return 0
        text: str = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return self._count(text)

    def part(self, part: dict[str, Any]) -> int:
        kind: str = part.get("type", "")
        if kind in {"text", "reasoning"}:
            return self.count(part.get("content", part.get("text")))
        if kind == "tool_call":
            return self.count(part.get("name")) + self.count(part.get("arguments"))
        if kind in {"tool_call_response", "tool_result"}:
            return self.count(part.get("response", part.get("result", part.get("content"))))
        return 0


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


@dataclass
class TokenCount:
    section: str
    category: str
    tokens: int
    call_id: str = ""
    tool_name: str = ""


def count_span_tokens(span: dict[str, Any], counter: TokenCounter) -> list[TokenCount]:
    """只计数一次；分类、矩阵和工具占用按不同维度汇总这些结果。"""
    counts: list[TokenCount] = []
    for section, (field, _label) in CONTENT_CATEGORIES.items():
        for index, item in enumerate(_objects(span["attributes"].get(field))):
            if section in {"system", "definitions"}:
                tokens = counter.part(item) if section == "system" else counter.count(item)
                counts.append(TokenCount(section, section, tokens))
                continue
            for part_index, part in enumerate(_objects(item.get("parts"))):
                kind: str = part.get("type", "")
                call_id = ""
                if kind in {"tool_call", "tool_call_response", "tool_result"}:
                    call_id = part.get("id") or f"{span['span_id']}:{index}:{part_index}"
                if section == "output":
                    category = "reasoning" if kind == "reasoning" else "content"
                elif call_id:
                    category = "tool_calls"
                else:
                    category = {
                        "system": "system",
                        "developer": "system",
                        "user": "user",
                        "assistant": "model",
                        "model": "model",
                    }.get(item.get("role", ""), "other")
                counts.append(TokenCount(section, category, counter.part(part), call_id, part.get("name") or ""))
    return counts


def scale_token_counts(counts: list[TokenCount], total: int, section: str, fallback: str) -> list[TokenCount]:
    """按最大余数法校准整数总和；无正文的用量只计入分类总数。"""
    weight_sum: int = sum(count.tokens for count in counts)
    if not weight_sum:
        return [*counts, TokenCount(section, fallback, total)]
    remainders: list[int] = []
    for count in counts:
        count.tokens, remainder = divmod(count.tokens * total, weight_sum)
        remainders.append(remainder)
    order = sorted(range(len(counts)), key=lambda index: -remainders[index])
    for index in order[: total - sum(count.tokens for count in counts)]:
        counts[index].tokens += 1
    return counts


class TokenUsageBuilder:
    """逐 Span 计算并累计；预览调用方计数后即可释放正文。"""

    def __init__(self):
        self.counts: dict[str, int] = defaultdict(int)
        self.estimated_totals: dict[str, int | None] = {"input": 0, "output": 0}
        self.estimated_token_fields: set[str] = set()
        self.tool_calls: dict[tuple[str, str], dict[str, Any]] = {}
        self.tool_names: dict[tuple[str, str], str] = {}
        self.counters: dict[str, TokenCounter] = {}

    def add_span(self, span: dict[str, Any]) -> None:
        attrs: dict[str, Any] = span["attributes"]
        trace_id: str = span["trace_id"]
        if attrs.get("gen_ai.tool.call.id") and attrs.get("gen_ai.tool.name"):
            self.tool_names[trace_id, attrs["gen_ai.tool.call.id"]] = attrs["gen_ai.tool.name"]
        if span.get("span_type") != SpanType.LLM:
            return
        model: str = attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model") or ""
        if model not in self.counters:
            self.counters[model] = TokenCounter(model)
        counts = count_span_tokens(span, self.counters[model])
        for count in counts:
            if count.call_id and count.tool_name:
                self.tool_names[trace_id, count.call_id] = count.tool_name
        category_totals: dict[str, int] = dict.fromkeys(CONTENT_CATEGORIES, 0)
        for side in ("input", "output"):
            side_counts = [count for count in counts if (count.section == "output") == (side == "output")]
            reasoning = nonnegative_int(attrs.get("gen_ai.usage.reasoning.output_tokens")) if side == "output" else None
            if reasoning is not None:
                side_counts = [count for count in side_counts if count.category != "reasoning"]
            estimated: int = sum(count.tokens for count in side_counts) + (reasoning or 0)
            field: str = f"{side}_tokens"
            reported = nonnegative_int(attrs.get(f"gen_ai.usage.{field}"))
            if field in span.get("estimated_token_fields", []):
                reported = None
            total: int = reported if reported is not None else estimated
            if reported is None:
                self.estimated_totals[side] = None
                self.estimated_token_fields.add(field)
                span.setdefault("estimated_token_fields", [])
                if field not in span["estimated_token_fields"]:
                    span["estimated_token_fields"].append(field)
                span["attributes"] = {**span["attributes"], f"gen_ai.usage.{field}": total}
            elif (subtotal := self.estimated_totals[side]) is not None:
                self.estimated_totals[side] = subtotal + estimated
            reasoning_total: int = min(reasoning, total) if reasoning is not None else 0
            side_counts = scale_token_counts(
                side_counts, total - reasoning_total, side, "other" if side == "input" else "content"
            )
            if reasoning is not None:
                side_counts.append(TokenCount("output", "reasoning", reasoning_total))
            for count in side_counts:
                self.counts[count.category] += count.tokens
                category_totals[count.section] += count.tokens
                if count.category == "tool_calls":
                    call = self.tool_calls.setdefault((trace_id, count.call_id), {"span_ids": set(), "tokens": 0})
                    call["span_ids"].add(span["span_id"])
                    call["tokens"] += count.tokens
        span["token_categories"] = [
            {"key": field, "label": _(label), "tokens": category_totals[section]}
            for section, (field, label) in CONTENT_CATEGORIES.items()
        ]

    def build(self) -> dict[str, Any]:
        def node(key: str, label: str, *children: dict[str, Any]) -> dict[str, Any]:
            return {
                "key": key,
                "label": _(label),
                "tokens": sum(child["tokens"] for child in children) if children else self.counts[key],
                "children": list(children),
            }

        nodes = [
            node(
                "input",
                "输入",
                node("system", "系统提示词"),
                node("definitions", "可用工具"),
                node(
                    "context",
                    "会话上下文",
                    node("tool_calls", "工具调用"),
                    node(
                        "conversation",
                        "会话内容",
                        node("model", "模型消息"),
                        node("user", "用户消息"),
                        node("other", "其他"),
                    ),
                ),
            ),
            node("output", "输出", node("content", "内容"), node("reasoning", "推理")),
        ]
        for root in nodes:
            estimated = self.estimated_totals[root["key"]]
            root["estimate_ratio"] = estimated / root["tokens"] if estimated is not None and root["tokens"] else None
        tools: dict[tuple[str, str], dict[str, Any]] = {}
        for call_key, call in self.tool_calls.items():
            trace_id, _call_id = call_key
            name: str = self.tool_names.get(call_key, "")
            tool = tools.setdefault(
                (trace_id, name),
                {
                    "trace_id": trace_id,
                    "name": name,
                    "label": name or _("未知工具"),
                    "span_ids": set(),
                    "call_count": 0,
                    "tokens": 0,
                },
            )
            tool["span_ids"].update(call["span_ids"])
            tool["call_count"] += 1
            tool["tokens"] += call["tokens"]
        rows = [{**tool, "span_ids": sorted(tool["span_ids"])} for tool in tools.values()]
        return {"nodes": nodes, "tools": sorted(rows, key=lambda row: (-row["tokens"], row["trace_id"], row["name"]))}


def build_token_matrix(spans: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """补齐模型用量和分类总数，返回矩阵；入参为已标准化、去重的 Span。"""
    builder = TokenUsageBuilder()
    for span in spans:
        builder.add_span(span)
    return builder.build()
