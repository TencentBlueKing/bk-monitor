"""Compile an expression over named PromQL queries into one PromQL query."""

import re
from collections.abc import Mapping
from typing import Any


_ALIAS_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_TOKEN_RE = re.compile(
    r"""\s+|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`[^`]*`|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|"""
    r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|[()+\-*/%^,<>]"
)
_OPERATORS = {"and", "or", "unless", "bool"}
_LABEL_MODIFIERS = {"on", "ignoring", "group_left", "group_right", "by", "without"}
_RESERVED = _OPERATORS | _LABEL_MODIFIERS | {"offset"}


def compile_promql_expression(query_configs: list[Mapping[str, Any]], expression: str) -> str:
    """Expand references to PromQL queries, rejecting ambiguous bare names."""
    if len(query_configs) < 2:
        raise ValueError("multiple PromQL queries are required")
    if not expression or not expression.strip():
        raise ValueError("PromQL expression is required")

    queries: dict[str, str] = {}
    intervals: set[int] = set()
    for query in query_configs:
        if (query.get("data_source_label"), query.get("data_type_label")) != ("prometheus", "time_series"):
            raise ValueError("all queries must use the Prometheus time-series data source")
        alias = query.get("alias")
        promql = query.get("promql")
        interval = query.get("agg_interval", query.get("interval"))
        if not isinstance(alias, str) or not _ALIAS_RE.fullmatch(alias) or alias.lower() in _RESERVED:
            raise ValueError(f"invalid PromQL query alias: {alias}")
        if alias in queries:
            raise ValueError(f"duplicate PromQL query alias: {alias}")
        if not isinstance(promql, str) or not promql.strip():
            raise ValueError(f"PromQL query is empty: {alias}")
        if isinstance(interval, bool) or not str(interval).isdigit() or int(interval) <= 0:
            raise ValueError(f"invalid PromQL query interval: {alias}")
        queries[alias] = promql.strip()
        intervals.add(int(interval))
    if len(intervals) != 1:
        raise ValueError("PromQL queries must use the same interval")

    result: list[str] = []
    used_aliases: set[str] = set()
    label_list = False
    pending_modifier = ""
    position = 0
    while position < len(expression):
        match = _TOKEN_RE.match(expression, position)
        if match is None:
            if expression[position] == "[":
                raise ValueError("range selectors must be specified in an individual PromQL query")
            raise ValueError(f"unsupported PromQL expression token at position {position + 1}")
        token = match.group()
        position = match.end()
        if token.isspace():
            result.append(token)
            continue
        if pending_modifier:
            if token == "(":
                pending_modifier = ""
                label_list = True
                result.append(token)
                continue
            if pending_modifier in {"on", "ignoring", "by", "without"}:
                raise ValueError("vector matching modifier requires a label list")
            pending_modifier = ""
        if label_list:
            if token == ")":
                label_list = False
            elif token != "," and not _ALIAS_RE.fullmatch(token):
                raise ValueError("invalid vector matching label list")
            result.append(token)
            continue
        if _ALIAS_RE.fullmatch(token):
            keyword = token.lower()
            if keyword in _LABEL_MODIFIERS:
                pending_modifier = keyword
                result.append(token)
            elif keyword in _OPERATORS:
                result.append(token)
            elif keyword == "offset":
                raise ValueError("offset must be specified in an individual PromQL query")
            elif token in queries:
                if re.match(r"\s*\(", expression[position:]):
                    raise ValueError(f"PromQL query alias conflicts with a function call: {token}")
                used_aliases.add(token)
                result.append(f"({queries[token]})")
            elif re.match(r"\s*(?:\(|(?:by|without)\b)", expression[position:]):
                # Functions and aggregators are part of PromQL; bare metrics must be declared aliases.
                result.append(token)
            else:
                raise ValueError(f"unknown PromQL query alias: {token}")
        else:
            result.append(token)
    if pending_modifier or label_list:
        raise ValueError("incomplete vector matching modifier")
    if used_aliases != queries.keys():
        raise ValueError(f"unused PromQL query aliases: {', '.join(sorted(queries.keys() - used_aliases))}")
    return "".join(result)
