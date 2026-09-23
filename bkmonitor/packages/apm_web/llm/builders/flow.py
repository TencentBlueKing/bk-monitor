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

from collections import defaultdict
from typing import Any

from apm_web.llm.constants import SpanType
from constants.apm import OtlpKey

# 响应字段 -> Span 属性：Token 的提取、累计、回填与输出共用这一份声明。
# total_tokens 不在此列，由输入、输出派生，避免同一语义出现两处来源。
TOKEN_FIELDS: dict[str, str] = {
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
    "cache_read_input_tokens": "gen_ai.usage.cache_read.input_tokens",
    "cache_write_input_tokens": "gen_ai.usage.cache_write.input_tokens",
}
TOKEN_ATTRIBUTES: tuple[str, ...] = tuple(TOKEN_FIELDS.values())


def _read_token(attributes: dict[str, Any], field: str) -> int | None:
    """读取 Token 属性：缺失或非整数（含 bool）返回 None，显式 0 视为有效上报。"""
    value = attributes.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _serialize_tokens(totals: dict[str, int]) -> dict[str, int]:
    """按 TOKEN_FIELDS 输出响应字段，total_tokens 由输入、输出派生。"""
    tokens: dict[str, int] = {name: totals[field] for name, field in TOKEN_FIELDS.items()}
    tokens["total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
    return tokens


class FlowBuilder:
    """根据完整 Span 父子关系构造 Agent 执行线，并按 Agent 子树统计 Token。"""

    def __init__(self, raw_spans: list[dict[str, Any]], spans: list[dict[str, Any]]):
        self.raw_spans = raw_spans
        self.spans = spans
        # 执行线根节点，build() 后可用
        self.flow: list[dict[str, Any]] = []
        # 各 Agent 的 Token 统计，key 为 span_id，build() 后可用
        self.statistics: dict[str, dict[str, int]] = {}

    @property
    def tokens(self) -> dict[str, int]:
        """Trace 消耗只累计 LLM Span，避免重复计入 Agent 自报或回填的 Token。"""
        totals: dict[str, int] = dict.fromkeys(TOKEN_ATTRIBUTES, 0)
        for span in self.spans:
            if span.get("span_type") == SpanType.LLM:
                attributes: dict[str, Any] = span.get(OtlpKey.ATTRIBUTES) or {}
                for field in TOKEN_ATTRIBUTES:
                    totals[field] += _read_token(attributes, field) or 0
        return _serialize_tokens(totals)

    def build(self) -> list[dict[str, Any]]:
        """构造执行线，并在同一次递归中完成 Token 回填与统计收集。"""
        self.flow = self._build_tree()
        self.statistics = {}
        for root in self.flow:
            self._aggregate(root)
        return self.flow

    def _build_tree(self) -> list[dict[str, Any]]:
        """按 Span 父子关系成树，仅展示支持的 Span 类型。"""
        nodes_by_span_id: dict[str, dict[str, Any]] = {
            span[OtlpKey.SPAN_ID]: {
                **span,
                # 复制 attributes，后续 Token 回填不修改入参
                OtlpKey.ATTRIBUTES: dict(span.get(OtlpKey.ATTRIBUTES) or {}),
                "childs": [],
            }
            for span in self.spans
            if span.get(OtlpKey.SPAN_ID) and span.get("span_type") in (SpanType.AGENT, SpanType.LLM, SpanType.TOOL)
        }
        raw_span_ids = {span[OtlpKey.SPAN_ID] for span in self.raw_spans if span.get(OtlpKey.SPAN_ID)}
        children_by_parent_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_roots: list[dict[str, Any]] = []
        for span in self.raw_spans:
            span_id = span.get(OtlpKey.SPAN_ID)
            parent_span_id = span.get(OtlpKey.PARENT_SPAN_ID)
            if parent_span_id and parent_span_id in raw_span_ids and parent_span_id != span_id:
                children_by_parent_id[parent_span_id].append(span)
            else:
                raw_roots.append(span)

        roots: list[dict[str, Any]] = []

        def project(span: dict[str, Any], parent: dict[str, Any] | None) -> None:
            node = nodes_by_span_id.get(span.get(OtlpKey.SPAN_ID))
            if node is not None:
                if parent is None:
                    roots.append(node)
                else:
                    parent["childs"].append(node)
                parent = node

            for child in children_by_parent_id.get(span.get(OtlpKey.SPAN_ID), []):
                project(child, parent)

        for raw_root in raw_roots:
            project(raw_root, None)
        # 中间 Span 投影后，原始兄弟关系的时间顺序不一定等于展示节点的顺序。
        roots.sort(key=lambda node: node.get(OtlpKey.START_TIME) or 0)
        for node in nodes_by_span_id.values():
            node["childs"].sort(key=lambda child: child.get(OtlpKey.START_TIME) or 0)
        return roots

    def _aggregate(self, node: dict[str, Any]) -> dict[str, int]:
        """递归累加子树 Token，返回本节点对父层的贡献量。"""
        attributes = node[OtlpKey.ATTRIBUTES]
        totals = dict.fromkeys(TOKEN_ATTRIBUTES, 0)
        for child in node["childs"]:
            child_totals = self._aggregate(child)
            for field in TOKEN_ATTRIBUTES:
                totals[field] += child_totals[field]

        if node.get("span_type") == SpanType.LLM:
            for field in TOKEN_ATTRIBUTES:
                totals[field] += _read_token(attributes, field) or 0
            return totals

        if node.get("span_type") == SpanType.AGENT:
            return self._resolve_agent_tokens(node, totals)

        # 非 LLM、非 Agent 的中间 Span 只透传子树统计
        return totals

    def _resolve_agent_tokens(self, node: dict[str, Any], child_totals: dict[str, int]) -> dict[str, int]:
        """按字段解析 Agent Token：自报值优先，缺失字段回填子树统计，缺失与显式 0 区分对待。"""
        attributes = node[OtlpKey.ATTRIBUTES]
        reported = {field: _read_token(attributes, field) for field in TOKEN_ATTRIBUTES}
        totals = {
            field: child_totals[field] if reported[field] is None else reported[field] for field in TOKEN_ATTRIBUTES
        }

        # 只回填缺失字段，不覆盖 Agent 已上报的取值；回填值全为 0 时不写入，避免污染属性
        missing = {field: totals[field] for field in TOKEN_ATTRIBUTES if reported[field] is None}
        if any(missing.values()):
            attributes.update(missing)

        if span_id := node.get(OtlpKey.SPAN_ID):
            self.statistics[span_id] = _serialize_tokens(totals)
        return totals
