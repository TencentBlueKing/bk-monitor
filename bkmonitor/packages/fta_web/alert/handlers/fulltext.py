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

import re
from dataclasses import dataclass
from enum import Enum

from elasticsearch_dsl import Q

# 非纯数字检索词最短长度，避免单字符 leading-wildcard 误召回与性能问题
MIN_FULLTEXT_TERM_LENGTH = 2
# 纯数字（ID / 业务号）允许更短
MIN_DIGIT_TERM_LENGTH = 1

_BARE_BOOLEAN_RE = re.compile(r"\b(AND|OR|NOT)\b", re.IGNORECASE)
_FIELD_SEP_RE = re.compile(r"(?<!\\):")


class FulltextFieldKind(str, Enum):
    TEXT = "text"
    KEYWORD = "keyword"


@dataclass(frozen=True)
class FulltextSearchField:
    """全字段裸词检索白名单条目。"""

    es_field: str
    kind: FulltextFieldKind


def strip_wrapping_quotes(query: str) -> str:
    """去掉首尾空白与包裹引号。"""
    term = (query or "").strip()
    if len(term) >= 2 and ((term[0] == term[-1] == '"') or (term[0] == term[-1] == "'")):
        term = term[1:-1].strip()
    return term


def unescape_lucene_literals(term: str) -> str:
    """还原 \\: \\* \\? \\\\ 为字面字符，避免白名单 wildcard 残留多余反斜杠。"""
    if not term or "\\" not in term:
        return term
    out: list[str] = []
    i = 0
    length = len(term)
    while i < length:
        if term[i] == "\\" and i + 1 < length and term[i + 1] in "\\:*?":
            out.append(term[i + 1])
            i += 2
            continue
        out.append(term[i])
        i += 1
    return "".join(out)


def normalize_fulltext_term(query: str) -> str:
    """去掉包裹引号并还原 Lucene 字面转义，得到实际检索词。"""
    return unescape_lucene_literals(strip_wrapping_quotes(query))


def is_quoted_phrase(query: str) -> bool:
    """整段被引号包裹时，视为短语而非 Lucene 语法。"""
    raw = (query or "").strip()
    return len(raw) >= 2 and ((raw[0] == raw[-1] == '"') or (raw[0] == raw[-1] == "'"))


def is_bare_fulltext_query(query: str) -> bool:
    """
    判断是否为可叠加全字段模糊的「裸词」查询。

    - 整段引号包裹：一律视为短语裸词（走白名单），避免 "CPU AND memory" / "labels:Prod"
      被去引号后误判为结构化语法，掉进无 fields 限制的 query_string。
    - 未加引号且含字段语法（field:value）、布尔运算符或分组括号：视为结构化查询。
      结构化判定在 unescape 之前，保留 \\: 不被当成 field 分隔。
    """
    raw = (query or "").strip()
    if not raw:
        return False
    if is_quoted_phrase(raw):
        return bool(normalize_fulltext_term(raw))

    term = strip_wrapping_quotes(raw)
    if not term:
        return False
    if _FIELD_SEP_RE.search(term):
        return False
    if _BARE_BOOLEAN_RE.search(term):
        return False
    if any(ch in term for ch in "()[]{}"):
        return False
    return True


def should_apply_fulltext_term(term: str) -> bool:
    """最短词长门禁：非数字 ≥2，纯数字 ≥1。"""
    if not term:
        return False
    if term.isdigit():
        return len(term) >= MIN_DIGIT_TERM_LENGTH
    return len(term) >= MIN_FULLTEXT_TERM_LENGTH


def escape_wildcard(value: str) -> str:
    """转义 Lucene wildcard 特殊字符：\\ * ?"""
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def build_keyword_contains_query(es_field: str, term: str) -> Q:
    """Keyword 字段：大小写不敏感的子串包含（leading/trailing wildcard）。"""
    pattern = f"*{escape_wildcard(term)}*"
    return Q("wildcard", **{es_field: {"value": pattern, "case_insensitive": True}})


def build_text_contains_query(es_field: str, term: str) -> Q:
    """Text 字段：分词匹配 OR 前缀短语（近似包含）。"""
    match_q = Q("match", **{es_field: {"query": term, "operator": "and"}})
    prefix_q = Q("match_phrase_prefix", **{es_field: {"query": term, "max_expansions": 50}})
    return match_q | prefix_q


def build_fulltext_fuzzy_query(query: str, fields: list[FulltextSearchField] | None) -> Q | None:
    """
    按白名单字段类型构造全字段模糊查询（bool.should）。

    - TEXT → match + match_phrase_prefix
    - KEYWORD → wildcard + case_insensitive
    """
    if not fields:
        return None
    term = normalize_fulltext_term(query)
    if not should_apply_fulltext_term(term):
        return None

    should_clauses: list[Q] = []
    for field in fields:
        if field.kind == FulltextFieldKind.TEXT:
            should_clauses.append(build_text_contains_query(field.es_field, term))
        else:
            should_clauses.append(build_keyword_contains_query(field.es_field, term))

    if not should_clauses:
        return None
    if len(should_clauses) == 1:
        return should_clauses[0]
    return Q("bool", should=should_clauses, minimum_should_match=1)


def build_enum_display_term_query(term: str, value_translate_fields: dict | None) -> Q | None:
    """
    裸词精确匹配枚举中文显示名时，补 term 查询（兼容旧 query_string 的「致命 => 致命 OR severity:1」）。

    仅做整词相等，不做子串，避免短词误伤。
    """
    if not term or not value_translate_fields:
        return None

    clauses: list[Q] = []
    for field, choices in value_translate_fields.items():
        for value, display in choices:
            if str(display) == term:
                clauses.append(Q("term", **{field: value}))

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return Q("bool", should=clauses, minimum_should_match=1)


def build_bare_fulltext_query(
    query: str,
    fields: list[FulltextSearchField] | None,
    value_translate_fields: dict | None = None,
) -> Q | None:
    """裸词全字段：白名单模糊 OR 枚举显示名 term。"""
    term = normalize_fulltext_term(query)
    fuzzy_q = build_fulltext_fuzzy_query(query, fields)
    enum_q = build_enum_display_term_query(term, value_translate_fields)
    if fuzzy_q is not None and enum_q is not None:
        return fuzzy_q | enum_q
    return fuzzy_q if fuzzy_q is not None else enum_q

