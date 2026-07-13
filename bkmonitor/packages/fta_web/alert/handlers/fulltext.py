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
# 短于此长度（非数字）不做 leading-wildcard，仅 prefix，降低 ES 成本
SHORT_KEYWORD_CONTAINS_MIN_LENGTH = 3
# 单条全字段检索词最大长度（超长直接无命中，防止异常大 payload）
MAX_FULLTEXT_TERM_LENGTH = 128
# conditions.query_string.value / include value 最多处理条数
MAX_FULLTEXT_VALUES = 10
# 顶层 query_string / 条件单值在 serializer 层的硬上限（略宽于检索门禁，给结构化语法留空间）
MAX_QUERY_STRING_LENGTH = 512

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
    判断是否为可叠加全字段模糊的「裸词」查询（QueryString 语句模式）。

    - 整段引号包裹：一律视为短语裸词（走白名单）
    - 未加引号且含字段语法 / 布尔 / 分组：视为结构化查询
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
    """最短/最长词长门禁。"""
    if not term:
        return False
    if len(term) > MAX_FULLTEXT_TERM_LENGTH:
        return False
    if term.isdigit():
        return len(term) >= MIN_DIGIT_TERM_LENGTH
    return len(term) >= MIN_FULLTEXT_TERM_LENGTH


def is_id_like_keyword_field(es_field: str) -> bool:
    """纯数字检索仅打在 ID/业务号类 Keyword，避免对 labels/人员做 *1* leading-wildcard。"""
    name = (es_field or "").split(".")[-1]
    return name == "id" or name.endswith("_id")


def escape_wildcard(value: str) -> str:
    """转义 Lucene wildcard 特殊字符：\\ * ?"""
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def build_keyword_contains_query(es_field: str, term: str) -> Q:
    """Keyword 字段：大小写不敏感的子串包含（leading/trailing wildcard）。"""
    pattern = f"*{escape_wildcard(term)}*"
    return Q("wildcard", **{es_field: {"value": pattern, "case_insensitive": True}})


def build_keyword_prefix_query(es_field: str, term: str) -> Q:
    """Keyword 前缀匹配（无 leading wildcard），短词场景使用。"""
    return Q("prefix", **{es_field: {"value": term, "case_insensitive": True}})


def build_keyword_id_query(es_field: str, term: str) -> Q:
    """数字 ID：精确 term OR 前缀 prefix，禁止 leading wildcard。"""
    return Q("term", **{es_field: term}) | Q("prefix", **{es_field: term})


def build_keyword_fuzzy_query(es_field: str, term: str) -> Q:
    """
    Keyword 模糊策略：
    - 纯数字：term | prefix（仅适合 ID 类字段调用方自行过滤）
    - 短词（< SHORT_KEYWORD_CONTAINS_MIN_LENGTH）：仅 prefix
    - 其它：*term* contains
    """
    if term.isdigit():
        return build_keyword_id_query(es_field, term)
    if len(term) < SHORT_KEYWORD_CONTAINS_MIN_LENGTH:
        return build_keyword_prefix_query(es_field, term)
    return build_keyword_contains_query(es_field, term)


def build_text_contains_query(es_field: str, term: str) -> Q:
    """Text 字段：分词匹配 OR 前缀短语（近似包含）。"""
    match_q = Q("match", **{es_field: {"query": term, "operator": "and"}})
    if len(term) < SHORT_KEYWORD_CONTAINS_MIN_LENGTH:
        # 短词不做 phrase_prefix 膨胀
        return match_q
    prefix_q = Q("match_phrase_prefix", **{es_field: {"query": term, "max_expansions": 50}})
    return match_q | prefix_q


def build_field_contains_query(es_field: str, value) -> Q | None:
    """
    单字段 include/exclude 共用：转义、长度门禁、数字/短词降级。

    用于 parse_condition_item(include/exclude)，与全字段 Keyword 策略对齐。
    """
    if value is None:
        return None
    term = unescape_lucene_literals(str(value).strip())
    if not term or len(term) > MAX_FULLTEXT_TERM_LENGTH:
        return None
    if term.isdigit():
        return build_keyword_id_query(es_field, term)
    if len(term) < MIN_FULLTEXT_TERM_LENGTH:
        return None
    return build_keyword_fuzzy_query(es_field, term)


def build_field_contains_queries(es_field: str, values) -> Q | None:
    """多值 include/exclude：限条数后 OR 组合。"""
    clauses: list[Q] = []
    for item in iter_fulltext_condition_values(values if isinstance(values, list) else [values]):
        q = build_field_contains_query(es_field, item)
        if q is not None:
            clauses.append(q)
    if not clauses:
        return Q("match_none")
    if len(clauses) == 1:
        return clauses[0]
    return Q("bool", should=clauses, minimum_should_match=1)


def build_fulltext_fuzzy_query(query: str, fields: list[FulltextSearchField] | None) -> Q | None:
    """
    按白名单字段类型构造全字段模糊查询（bool.should）。

    - 普通词：TEXT → match + phrase_prefix；KEYWORD → *term* case_insensitive
    - 纯数字：仅 ID 类 Keyword → term | prefix（无 leading wildcard，且不扫人员/标签/Text）
    """
    if not fields:
        return None
    term = normalize_fulltext_term(query)
    if not should_apply_fulltext_term(term):
        return None

    should_clauses: list[Q] = []
    if term.isdigit():
        for field in fields:
            if field.kind == FulltextFieldKind.KEYWORD and is_id_like_keyword_field(field.es_field):
                should_clauses.append(build_keyword_id_query(field.es_field, term))
    else:
        for field in fields:
            if field.kind == FulltextFieldKind.TEXT:
                should_clauses.append(build_text_contains_query(field.es_field, term))
            else:
                should_clauses.append(build_keyword_fuzzy_query(field.es_field, term))

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
    if len(term) > MAX_FULLTEXT_TERM_LENGTH:
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
    """裸词/UI 字面全字段：白名单模糊 OR 枚举显示名 term。"""
    term = normalize_fulltext_term(query)
    if len(term) > MAX_FULLTEXT_TERM_LENGTH:
        return None
    fuzzy_q = build_fulltext_fuzzy_query(query, fields)
    enum_q = build_enum_display_term_query(term, value_translate_fields)
    if fuzzy_q is not None and enum_q is not None:
        return fuzzy_q | enum_q
    return fuzzy_q if fuzzy_q is not None else enum_q


def iter_fulltext_condition_values(values) -> list[str]:
    """截断 conditions.query_string.value，防止多值放大 should 子句。"""
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    limited: list[str] = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        limited.append(text)
        if len(limited) >= MAX_FULLTEXT_VALUES:
            break
    return limited
