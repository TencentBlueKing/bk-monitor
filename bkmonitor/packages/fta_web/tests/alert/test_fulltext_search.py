"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.base import BaseQueryHandler
from fta_web.alert.handlers.fulltext import (
    MAX_FULLTEXT_TERM_LENGTH,
    MAX_FULLTEXT_VALUES,
    SHORT_KEYWORD_CONTAINS_MIN_LENGTH,
    FulltextFieldKind,
    FulltextSearchField,
    build_bare_fulltext_query,
    build_enum_display_term_query,
    build_fulltext_fuzzy_query,
    build_keyword_contains_query,
    build_keyword_fuzzy_query,
    escape_wildcard,
    is_bare_fulltext_query,
    iter_fulltext_condition_values,
    normalize_fulltext_term,
    should_apply_fulltext_term,
)
from fta_web.alert.handlers.incident import IncidentQueryHandler
from fta_web.alert.serializers import AlertSearchSerializer, SearchConditionSerializer
from monitor_web.incident.serializers import IncidentSearchSerializer


class TestFulltextHelpers:
    def test_normalize_strips_quotes(self):
        assert normalize_fulltext_term('"分析"') == "分析"
        assert normalize_fulltext_term("  CPU  ") == "CPU"

    def test_is_bare_fulltext_query(self):
        assert is_bare_fulltext_query("分析") is True
        assert is_bare_fulltext_query('"Prod"') is True
        assert is_bare_fulltext_query("labels:Prod") is False
        assert is_bare_fulltext_query("CPU AND memory") is False
        assert is_bare_fulltext_query("(CPU)") is False
        # 整段引号：即使内容含 AND / field:value，仍走白名单短语
        assert is_bare_fulltext_query('"CPU AND memory"') is True
        assert is_bare_fulltext_query('"labels:Prod"') is True

    def test_normalize_unescapes_lucene_literals(self):
        assert normalize_fulltext_term(r"foo\:bar") == "foo:bar"
        assert normalize_fulltext_term('"a\\*b"') == "a*b"

    def test_escaped_colon_bare_wildcard_has_no_extra_backslash(self):
        fields = [FulltextSearchField("labels", FulltextFieldKind.KEYWORD)]
        # foo\:bar 因 (?<!\\): 不算字段语法 → 裸词；检索值应还原为 foo:bar
        assert is_bare_fulltext_query(r"foo\:bar") is True
        q = build_fulltext_fuzzy_query(r"foo\:bar", fields)
        assert q.to_dict()["wildcard"]["labels"]["value"] == "*foo:bar*"

    def test_should_apply_fulltext_term(self):
        assert should_apply_fulltext_term("a") is False
        assert should_apply_fulltext_term("ab") is True
        assert should_apply_fulltext_term("1") is True
        assert should_apply_fulltext_term("分析") is True
        assert should_apply_fulltext_term("x" * (MAX_FULLTEXT_TERM_LENGTH + 1)) is False

    def test_escape_wildcard(self):
        assert escape_wildcard("a*b?c\\d") == "a\\*b\\?c\\\\d"

    def test_keyword_contains_case_insensitive(self):
        q = build_keyword_contains_query("labels", "Prod")
        body = q.to_dict()
        assert "wildcard" in body
        assert body["wildcard"]["labels"]["value"] == "*Prod*"
        assert body["wildcard"]["labels"]["case_insensitive"] is True

    def test_fulltext_fuzzy_covers_keyword_and_text(self):
        fields = [
            FulltextSearchField("labels", FulltextFieldKind.KEYWORD),
            FulltextSearchField("incident_name", FulltextFieldKind.TEXT),
        ]
        q = build_fulltext_fuzzy_query("分析", fields)
        body = q.to_dict()
        assert "bool" in body
        assert body["bool"]["minimum_should_match"] == 1
        should = body["bool"]["should"]
        assert any("wildcard" in clause for clause in should)
        assert any("match" in clause or "bool" in clause for clause in should)

    def test_digit_uses_term_prefix_on_id_fields_only(self):
        fields = [
            FulltextSearchField("id", FulltextFieldKind.KEYWORD),
            FulltextSearchField("bk_biz_id", FulltextFieldKind.KEYWORD),
            FulltextSearchField("labels", FulltextFieldKind.KEYWORD),
            FulltextSearchField("assignees", FulltextFieldKind.KEYWORD),
            FulltextSearchField("incident_name", FulltextFieldKind.TEXT),
        ]
        q = build_fulltext_fuzzy_query("1", fields)
        dumped = str(q.to_dict())
        assert "*1*" not in dumped
        assert "wildcard" not in dumped
        assert "prefix" in dumped
        assert "term" in dumped
        assert "labels" not in dumped
        assert "assignees" not in dumped
        assert "incident_name" not in dumped
        assert "id" in dumped
        assert "bk_biz_id" in dumped

    def test_ascii_short_uses_prefix_not_leading_wildcard(self):
        assert SHORT_KEYWORD_CONTAINS_MIN_LENGTH == 3
        q = build_keyword_fuzzy_query("labels", "ab")
        dumped = str(q.to_dict())
        assert "prefix" in dumped
        assert "*ab*" not in dumped
        # 长 ASCII 仍 contains
        long_q = build_keyword_fuzzy_query("labels", "abcd")
        assert "*abcd*" in str(long_q.to_dict())

    def test_non_digit_skips_id_like_keyword_fields(self):
        fields = [
            FulltextSearchField("id", FulltextFieldKind.KEYWORD),
            FulltextSearchField("event.bk_biz_id", FulltextFieldKind.KEYWORD),
            FulltextSearchField("incident_id", FulltextFieldKind.KEYWORD),
            FulltextSearchField("labels", FulltextFieldKind.KEYWORD),
            FulltextSearchField("alert_name", FulltextFieldKind.TEXT),
        ]
        q = build_fulltext_fuzzy_query("分析", fields)
        body = q.to_dict()
        dumped = str(body)
        assert "*分析*" in dumped
        assert "labels" in dumped
        assert "alert_name" in dumped
        assert "incident_id" not in dumped
        assert "bk_biz_id" not in dumped
        # 顶层/子句字段名不应再扫纯 id
        assert '"id":' not in dumped and "'id':" not in dumped

    def test_cjk_two_char_uses_contains(self):
        """中文两字「分析」须 *分析* 子串命中，不可降级为 prefix。"""
        q = build_keyword_fuzzy_query("labels", "分析")
        dumped = str(q.to_dict())
        assert "*分析*" in dumped
        assert "prefix" not in dumped or "wildcard" in dumped

    def test_short_non_digit_skipped(self):
        fields = [FulltextSearchField("labels", FulltextFieldKind.KEYWORD)]
        assert build_fulltext_fuzzy_query("a", fields) is None

    def test_enum_display_term_query(self):
        q = build_enum_display_term_query("致命", {"severity": [(1, "致命"), (2, "预警")]})
        assert q.to_dict() == {"term": {"severity": 1}}

    def test_bare_fulltext_ors_enum_and_fuzzy(self):
        fields = [FulltextSearchField("labels", FulltextFieldKind.KEYWORD)]
        q = build_bare_fulltext_query("致命", fields, {"severity": [(1, "致命")]})
        dumped = str(q.to_dict())
        assert "wildcard" in dumped
        assert "term" in dumped
        assert "severity" in dumped

    def test_iter_fulltext_condition_values_rejects_overlimit(self):
        values = [f"v{i}" for i in range(MAX_FULLTEXT_VALUES + 5)]
        with pytest.raises(ValueError):
            iter_fulltext_condition_values(values)

    def test_condition_q_rejects_overlimit_as_validation_error(self):
        from rest_framework.exceptions import ValidationError

        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        with pytest.raises(ValidationError):
            handler.build_query_string_condition_q([f"v{i}" for i in range(MAX_FULLTEXT_VALUES + 1)])


class TestExplicitIncludeExcludeBaseline:
    """显式字段 include/exclude 须保持基线 *value* 子串，与全字段检索策略解耦。"""

    def _handler(self):
        return BaseQueryHandler.__new__(BaseQueryHandler)

    def test_include_digit_is_substring_wildcard(self):
        q = self._handler().parse_condition_item({"method": "include", "key": "labels", "value": ["123"]})
        assert q.to_dict() == {"wildcard": {"labels": "*123*"}}

    def test_include_short_ascii_is_substring_wildcard(self):
        q = self._handler().parse_condition_item({"method": "include", "key": "labels", "value": ["ab"]})
        assert q.to_dict() == {"wildcard": {"labels": "*ab*"}}

    def test_include_single_char_is_substring_wildcard(self):
        q = self._handler().parse_condition_item({"method": "include", "key": "labels", "value": ["a"]})
        assert q.to_dict() == {"wildcard": {"labels": "*a*"}}

    def test_include_mid_string_pattern(self):
        q = self._handler().parse_condition_item({"method": "include", "key": "alert_name", "value": "中间"})
        assert q.to_dict() == {"wildcard": {"alert_name": "*中间*"}}

    def test_exclude_digit_uses_substring_wildcard(self):
        q = self._handler().parse_condition_item({"method": "exclude", "key": "labels", "value": ["123"]})
        assert q.to_dict() == {"bool": {"must_not": [{"wildcard": {"labels": "*123*"}}]}}

    def test_include_multi_value_or(self):
        q = self._handler().parse_condition_item({"method": "include", "key": "labels", "value": ["a", "b"]})
        body = q.to_dict()
        assert body["bool"]["should"] == [{"wildcard": {"labels": "*a*"}}, {"wildcard": {"labels": "*b*"}}]


class TestFulltextSearchSerializerLimits:
    @staticmethod
    def _condition(values):
        return {"key": "query_string", "value": values, "method": "eq", "condition": "and"}

    @staticmethod
    def _payload(**kwargs):
        return {
            "bk_biz_ids": [2],
            "conditions": [],
            "query_string": "",
            "start_time": 1,
            "end_time": 2,
            **kwargs,
        }

    @pytest.mark.parametrize("serializer_class", [AlertSearchSerializer, IncidentSearchSerializer])
    def test_rejects_aggregate_fulltext_values_over_limit(self, serializer_class):
        conditions = [self._condition([f"first-{index}" for index in range(6)])]
        conditions.append(self._condition([f"second-{index}" for index in range(5)]))

        serializer = serializer_class(data=self._payload(conditions=conditions))

        assert serializer.is_valid() is False
        assert "query_string condition values exceed limit 10, got 11" in str(serializer.errors["conditions"])

    def test_shared_condition_serializer_does_not_apply_fulltext_limit(self):
        serializer = SearchConditionSerializer(
            data=[self._condition([f"value-{index}" for index in range(11)])],
            many=True,
        )

        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize("serializer_class", [AlertSearchSerializer, IncidentSearchSerializer])
    def test_accepts_aggregate_fulltext_values_at_limit(self, serializer_class):
        conditions = [self._condition([f"first-{index}" for index in range(5)])]
        conditions.append(self._condition([f"second-{index}" for index in range(5)]))

        serializer = serializer_class(data=self._payload(conditions=conditions))

        assert serializer.is_valid(), serializer.errors

    @pytest.mark.parametrize("serializer_class", [AlertSearchSerializer, IncidentSearchSerializer])
    def test_structured_query_string_keeps_baseline_length_compatibility(self, serializer_class):
        query_string = " OR ".join(f"labels:Prod{index}" for index in range(40))
        assert len(query_string) > 512
        serializer = serializer_class(data=self._payload(query_string=query_string))

        assert serializer.is_valid(), serializer.errors


class TestIncidentAlertFulltextWhitelist:
    def test_incident_whitelist_fields(self):
        es_fields = {f.es_field for f in IncidentQueryHandler.FULLTEXT_SEARCH_FIELDS}
        assert es_fields == {
            "id",
            "incident_id",
            "incident_name",
            "incident_reason",
            "labels",
            "assignees",
            "handlers",
            "bk_biz_id",
        }

    def test_alert_whitelist_fields(self):
        es_fields = {f.es_field for f in AlertQueryHandler.FULLTEXT_SEARCH_FIELDS}
        assert es_fields == {
            "id",
            "alert_name",
            "event.description",
            "labels",
            "appointee",
            "follower",
            "event.bk_biz_id",
        }
        assert "assignee" not in es_fields

    def test_incident_build_query_string_q_bare_uses_whitelist_only(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("分析")
        body = q.to_dict()
        dumped = str(body)
        # 裸词不应再走无界 query_string
        assert "query_string" not in body
        assert "labels" in dumped
        assert "assignees" in dumped
        assert "handlers" in dumped
        assert "incident_name" in dumped
        assert "case_insensitive" in dumped
        assert "snapshot" not in dumped

    def test_incident_bare_chinese_two_char_uses_contains(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("分析")
        dumped = str(q.to_dict())
        assert "*分析*" in dumped
        assert "labels" in dumped

    def test_short_char_returns_match_none(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("a")
        assert q.to_dict() == {"match_none": {}}

    def test_quoted_boolean_phrase_stays_on_whitelist(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q('"CPU AND memory"')
        body = q.to_dict()
        assert "query_string" not in body
        assert "wildcard" in str(body) or "match" in str(body)
        assert "*CPU AND memory*" in str(body) or "CPU AND memory" in str(body)

    def test_ui_literal_fulltext_for_colon_and_boolean(self):
        """UI 模式：foo:bar / CPU AND memory 按字面走白名单，不落入无界 query_string。"""
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        for text in ["foo:bar", "CPU AND memory"]:
            q = handler.build_query_string_q(text, literal_fulltext=True)
            body = q.to_dict()
            assert "query_string" not in body, text
            dumped = str(body)
            assert "wildcard" in dumped or "match" in dumped
            assert "labels" in dumped

    def test_ui_condition_helper_uses_literal(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_condition_q(["foo:bar"])
        assert "query_string" not in q.to_dict()
        assert "*foo:bar*" in str(q.to_dict())

    def test_querystring_mode_keeps_structured_syntax(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("labels:Prod")
        body = q.to_dict()
        # QueryString 语句模式仍走结构化 query_string
        assert "query_string" in body
        assert body["query_string"]["query"]

    def test_alert_build_query_string_q_includes_appointee_follower(self):
        handler = AlertQueryHandler.__new__(AlertQueryHandler)
        handler.query_context = None
        q = handler.build_query_string_q("Prod")
        dumped = str(q.to_dict())
        assert "appointee" in dumped
        assert "follower" in dumped
        assert "labels" in dumped
        assert "case_insensitive" in dumped
        assert "assignee" not in {f.es_field for f in AlertQueryHandler.FULLTEXT_SEARCH_FIELDS}

    def test_digit_query_on_handlers_avoids_leading_wildcard(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("1")
        dumped = str(q.to_dict())
        assert "*1*" not in dumped
        assert "wildcard" not in dumped
        assert "assignees" not in dumped
        assert "handlers" not in dumped
        assert "labels" not in dumped
