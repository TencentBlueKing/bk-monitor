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

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import tiktoken
from django.utils.translation import gettext as _

from apm_web.llm.adapter.utils import nonnegative_int
from apm_web.llm.constants import SpanType


class TokenCounter:
    """正文估算；缓存仅存活于一次矩阵计算，避免重复编码历史上下文。"""

    def __init__(self, model: str):
        try:
            encoding = tiktoken.encoding_name_for_model(model)
        except KeyError:
            encoding = "cl100k_base"
        # 只使用随部署预热的两套编码；其他模型也明确按近似值处理。
        self.encoding = tiktoken.get_encoding(encoding if encoding == "o200k_base" else "cl100k_base")
        encode = self.encoding.encode_ordinary
        # BPE 对超长无空白片段可能呈二次耗时；分段控制最坏延迟，结果仍是估算值。
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
        # 图片、音频等需要供应商用量，不能按 URL 或二进制字符串估算。
        return 0


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


@dataclass
class _TokenPart:
    section: str
    item_index: int
    part_index: int | None
    category: str
    tokens: int
    tool_name: str | None = None
    call_id: str = ""


def _allocate(weights: list[int], total: int) -> list[int]:
    """最大余数法：整数分项之和等于总量，相同余数按原顺序分配。"""
    weight_sum: int = sum(weights)
    if not weight_sum:
        return [0] * len(weights)
    result = [weight * total // weight_sum for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: -(weights[i] * total % weight_sum))
    for index in order[: total - sum(result)]:
        result[index] += 1
    return result


def estimate_span_tokens(span: dict[str, Any], counter: TokenCounter | None = None) -> dict[str, Any]:
    """计数并按上报总量校准；矩阵、工具占用和分类统计共用同一批分项。"""
    attrs: dict[str, Any] = span["attributes"]
    counter = counter or TokenCounter(attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model") or "")
    sections: dict[str, dict[str, Any]] = {}
    parts: dict[str, list[_TokenPart]] = {"input": [], "output": []}
    names: dict[str, str] = {}
    for message in _objects(attrs.get("gen_ai.input.messages")):
        for part in _objects(message.get("parts")):
            if part.get("type") == "tool_call" and part.get("id"):
                names[part["id"]] = part.get("name") or ""

    for section, field, label in (
        ("system", "gen_ai.system_instructions", _("系统提示词")),
        ("definitions", "gen_ai.tool.definitions", _("可用工具")),
        ("input", "gen_ai.input.messages", _("输入")),
        ("output", "gen_ai.output.messages", _("输出")),
    ):
        items: list[dict[str, Any]] = []
        sections[section] = {"key": field, "label": label, "tokens": 0, "items": items}
        for item_index, item in enumerate(_objects(attrs.get(field))):
            items.append({"tokens": 0, "parts": []})
            if section in {"system", "definitions"}:
                count = counter.part(item) if section == "system" else counter.count(item)
                parts["input"].append(_TokenPart(section, item_index, None, section, count))
                continue
            for part_index, part in enumerate(_objects(item.get("parts"))):
                items[-1]["parts"].append(0)
                kind: str = part.get("type", "")
                tool_name: str | None = None
                call_id: str = ""
                if section == "output":
                    category = "reasoning" if kind == "reasoning" else "content"
                elif kind in {"tool_call", "tool_call_response", "tool_result"}:
                    category = "tool_calls"
                    call_id = part.get("id") or f"@{span['span_id']}:{item_index}:{part_index}"
                    tool_name = part.get("name") or names.get(call_id, "")
                else:
                    category = {
                        "system": "system",
                        "developer": "system",
                        "user": "user",
                        "assistant": "model",
                        "model": "model",
                    }.get(item.get("role", ""), "other")
                parts[section].append(
                    _TokenPart(section, item_index, part_index, category, counter.part(part), tool_name, call_id)
                )

    counts: dict[str, dict[str, int]] = {side: defaultdict(int) for side in parts}
    raw_totals: dict[str, int] = {}
    estimated_fields: list[str] = []
    tools: dict[tuple[str, str], dict[str, Any]] = {}
    for side, atoms in parts.items():
        usage_key: str = f"{side}_tokens"
        reported = nonnegative_int(attrs.get(f"gen_ai.usage.{usage_key}"))
        if usage_key in span.get("estimated_token_fields", []):
            reported = None
        # 隐式推理正文不可见时，用已上报推理量参与输出估算，而不由摘要长度推断。
        reasoning = nonnegative_int(attrs.get("gen_ai.usage.reasoning.output_tokens")) if side == "output" else None
        raw_total: int = sum(atom.tokens for atom in atoms if reasoning is None or atom.category != "reasoning")
        raw_total += reasoning or 0
        raw_totals[side] = raw_total
        total: int = reported if reported is not None else raw_total
        if reported is None:
            estimated_fields.append(usage_key)
        if reasoning is None:
            groups = [(atoms, total, "other" if side == "input" else "content")]
        else:
            reasoning_total: int = min(reasoning, total)
            groups = [
                ([atom for atom in atoms if atom.category == "reasoning"], reasoning_total, "reasoning"),
                ([atom for atom in atoms if atom.category != "reasoning"], total - reasoning_total, "content"),
            ]
        for group, target, fallback_category in groups:
            if not sum(atom.tokens for atom in group):
                # 没有可计数正文时仍保留总量，不能把缺失正文归给某个已知消息或工具。
                counts[side][fallback_category] += target
                sections[side]["tokens"] += target
                continue
            for atom, tokens in zip(group, _allocate([atom.tokens for atom in group], target)):
                counts[side][atom.category] += tokens
                section_data = sections[atom.section]
                section_data["tokens"] += tokens
                item_data = section_data["items"][atom.item_index]
                item_data["tokens"] += tokens
                if atom.part_index is not None:
                    item_data["parts"][atom.part_index] = tokens
                if atom.tool_name is not None:
                    tool = tools.setdefault(
                        (atom.tool_name, atom.call_id), {"name": atom.tool_name, "tokens": 0, "call_id": atom.call_id}
                    )
                    tool["tokens"] += tokens
    return {
        "counts": counts,
        "sections": list(sections.values()),
        "tools": list(tools.values()),
        "raw_totals": raw_totals,
        "estimated_fields": estimated_fields,
    }


class TokenMatrixBuilder:
    """逐 Span 累计，预览调用方可以在计数后立即释放正文。"""

    def __init__(self):
        self.counts: dict[str, dict[str, int]] = {side: defaultdict(int) for side in ("input", "output")}
        self.ratio_totals: dict[str, float | None] = {"input": 0, "output": 0}
        self.tools: dict[tuple[str, str], dict[str, Any]] = {}
        self.call_names: dict[tuple[str, str], str] = {}
        self.counters: dict[str, TokenCounter] = {}
        self.seen: set[tuple[str, str]] = set()
        self.estimated_fields: set[str] = set()

    def add_span(self, span: dict[str, Any]) -> list[dict[str, Any]] | None:
        identity = (span["trace_id"], span["span_id"])
        attrs: dict[str, Any] = span["attributes"]
        if attrs.get("gen_ai.tool.call.id") and attrs.get("gen_ai.tool.name"):
            self.call_names[(span["trace_id"], attrs["gen_ai.tool.call.id"])] = attrs["gen_ai.tool.name"]
        for side in ("input", "output"):
            for message in _objects(attrs.get(f"gen_ai.{side}.messages")):
                for part in _objects(message.get("parts")):
                    if part.get("type") == "tool_call" and part.get("id") and part.get("name"):
                        self.call_names[(span["trace_id"], part["id"])] = part["name"]
        if span.get("span_type") != SpanType.LLM or identity in self.seen:
            return None
        self.seen.add(identity)
        model: str = attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model") or ""
        if model not in self.counters:
            self.counters[model] = TokenCounter(model)
        estimate = estimate_span_tokens(span, self.counters[model])
        for side, counts in estimate["counts"].items():
            for key, value in counts.items():
                self.counts[side][key] += value
            if f"{side}_tokens" in estimate["estimated_fields"]:
                self.ratio_totals[side] = None
            elif self.ratio_totals[side] is not None:
                self.ratio_totals[side] += estimate["raw_totals"][side]
        if estimate["estimated_fields"]:
            span["attributes"] = attrs = dict(attrs)
            span["estimated_token_fields"] = estimate["estimated_fields"]
            self.estimated_fields.update(estimate["estimated_fields"])
            for field in estimate["estimated_fields"]:
                attrs[f"gen_ai.usage.{field}"] = sum(estimate["counts"][field.removesuffix("_tokens")].values())
        for tool in estimate["tools"]:
            key = (span["trace_id"], tool["call_id"])
            row = self.tools.setdefault(
                key,
                {"trace_id": span["trace_id"], "name": tool["name"], "span_ids": set(), "tokens": 0},
            )
            row["span_ids"].add(span["span_id"])
            row["tokens"] += tool["tokens"]
        return estimate["sections"]

    def build(self) -> dict[str, Any]:
        def node(side: str, key: str, label: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
            children = children or []
            return {
                "key": key,
                "label": label,
                "tokens": sum(child["tokens"] for child in children) if children else self.counts[side][key],
                "children": children,
            }

        conversation = node(
            "input",
            "conversation",
            _("会话内容"),
            [
                node("input", "model", _("模型消息")),
                node("input", "user", _("用户消息")),
                node("input", "other", _("其他")),
            ],
        )
        context = node("input", "context", _("会话上下文"), [node("input", "tool_calls", _("工具调用")), conversation])
        nodes = [
            node(
                "input",
                "input",
                _("输入"),
                [
                    node("input", "system", _("系统提示词")),
                    node("input", "definitions", _("可用工具")),
                    context,
                ],
            ),
            node(
                "output",
                "output",
                _("输出"),
                [node("output", "content", _("内容")), node("output", "reasoning", _("推理"))],
            ),
        ]
        for side in nodes:
            numerator = self.ratio_totals[side["key"]]
            side["estimate_ratio"] = numerator / side["tokens"] if numerator is not None and side["tokens"] else None
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for call_key, row in self.tools.items():
            name: str = self.call_names.get(call_key) or row["name"]
            key = (row["trace_id"], name)
            tool = grouped.setdefault(
                key,
                {
                    "trace_id": key[0],
                    "name": name,
                    "label": name or _("未知工具"),
                    "span_ids": set(),
                    "call_count": 0,
                    "tokens": 0,
                },
            )
            tool["span_ids"].update(row["span_ids"])
            tool["call_count"] += 1
            tool["tokens"] += row["tokens"]
        tools = [{**tool, "span_ids": sorted(tool["span_ids"])} for tool in grouped.values()]
        return {"nodes": nodes, "tools": sorted(tools, key=lambda row: (-row["tokens"], row["trace_id"], row["name"]))}


def build_token_matrix(spans: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """补齐模型 Span 的缺失用量、分类估算，并返回同口径矩阵。"""
    builder = TokenMatrixBuilder()
    for span in spans:
        if sections := builder.add_span(span):
            span["token_estimates"] = sections
    return builder.build()
