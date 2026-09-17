"""Agent 执行线构造与 Token 统计。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from constants.apm import OtlpKey


class FlowBuilder:
    """根据完整 Span 父子关系构造 Agent 执行线。"""

    TOKEN_FIELDS = (
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        "gen_ai.usage.cache_write.input_tokens",
    )

    def __init__(self, raw_spans: list[dict[str, Any]], spans: list[dict[str, Any]]):
        self.raw_spans = raw_spans
        self.spans = spans

    @staticmethod
    def _token_values(span: dict[str, Any]) -> dict[str, int]:
        attributes = span.get(OtlpKey.ATTRIBUTES) or {}
        return {
            field: value if isinstance((value := attributes.get(field)), int) and not isinstance(value, bool) else 0
            for field in FlowBuilder.TOKEN_FIELDS
        }

    @classmethod
    def _fill_agent_tokens(cls, nodes: list[dict[str, Any]]) -> dict[str, int]:
        totals = dict.fromkeys(cls.TOKEN_FIELDS, 0)
        for node in nodes:
            child_totals = cls._fill_agent_tokens(node["childs"])
            if node.get("span_type") == "LLM":
                values = cls._token_values(node)
                for field in cls.TOKEN_FIELDS:
                    child_totals[field] += values[field]

            if node.get("span_type") == "AGENT":
                values = cls._token_values(node)
                if values["gen_ai.usage.input_tokens"] or values["gen_ai.usage.output_tokens"]:
                    # Agent 自报值代表整个子树，向父层传递时不能再叠加后代 LLM。
                    child_totals = values
                elif any(child_totals.values()):
                    node[OtlpKey.ATTRIBUTES].update(child_totals)

            for field in cls.TOKEN_FIELDS:
                totals[field] += child_totals[field]
        return totals

    def build(self) -> list[dict[str, Any]]:
        nodes = [
            {
                **span,
                OtlpKey.ATTRIBUTES: {**(span.get(OtlpKey.ATTRIBUTES) or {})},
                "childs": [],
            }
            for span in self.spans
        ]
        nodes_by_span_id = {node[OtlpKey.SPAN_ID]: node for node in nodes if node.get(OtlpKey.SPAN_ID)}
        raw_spans_by_span_id = {span[OtlpKey.SPAN_ID]: span for span in self.raw_spans if span.get(OtlpKey.SPAN_ID)}
        raw_children_by_parent_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_roots = []
        for span in self.raw_spans:
            span_id = span.get(OtlpKey.SPAN_ID)
            parent_span_id = span.get(OtlpKey.PARENT_SPAN_ID)
            if parent_span_id and parent_span_id in raw_spans_by_span_id and parent_span_id != span_id:
                raw_children_by_parent_id[parent_span_id].append(span)
            else:
                raw_roots.append(span)

        roots = []

        def project(span: dict[str, Any], parent: dict[str, Any] | None) -> None:
            node = nodes_by_span_id.get(span.get(OtlpKey.SPAN_ID))
            if node is not None:
                if parent is None:
                    roots.append(node)
                else:
                    parent["childs"].append(node)
                parent = node

            for child in raw_children_by_parent_id.get(span.get(OtlpKey.SPAN_ID), []):
                project(child, parent)

        for raw_root in raw_roots:
            project(raw_root, None)

        self._fill_agent_tokens(roots)
        return roots

    @classmethod
    def token_statistics_map(cls, flow: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        statistics: dict[str, dict[str, int]] = {}
        for node in flow:
            span_id = node.get(OtlpKey.SPAN_ID)
            if span_id and node.get("span_type") == "AGENT":
                values = cls._token_values(node)
                statistics[span_id] = {
                    "input_tokens": values["gen_ai.usage.input_tokens"],
                    "output_tokens": values["gen_ai.usage.output_tokens"],
                    "total_tokens": values["gen_ai.usage.input_tokens"] + values["gen_ai.usage.output_tokens"],
                    "cache_read_input_tokens": values["gen_ai.usage.cache_read.input_tokens"],
                    "cache_write_input_tokens": values["gen_ai.usage.cache_write.input_tokens"],
                }
            statistics.update(cls.token_statistics_map(node["childs"]))
        return statistics
