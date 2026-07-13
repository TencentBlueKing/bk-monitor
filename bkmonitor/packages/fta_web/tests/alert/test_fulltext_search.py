"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.fulltext import (
    FulltextFieldKind,
    FulltextSearchField,
    build_fulltext_fuzzy_query,
    build_keyword_contains_query,
    escape_wildcard,
    is_bare_fulltext_query,
    normalize_fulltext_term,
    should_apply_fulltext_term,
)
from fta_web.alert.handlers.incident import IncidentQueryHandler


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

    def test_should_apply_fulltext_term(self):
        assert should_apply_fulltext_term("a") is False
        assert should_apply_fulltext_term("ab") is True
        assert should_apply_fulltext_term("1") is True
        assert should_apply_fulltext_term("分析") is True

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

    def test_short_non_digit_skipped(self):
        fields = [FulltextSearchField("labels", FulltextFieldKind.KEYWORD)]
        assert build_fulltext_fuzzy_query("a", fields) is None


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
        q = handler.build_query_string_q("分析", escape_colon=True)
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

    def test_incident_structured_query_skips_fuzzy(self):
        handler = IncidentQueryHandler.__new__(IncidentQueryHandler)
        q = handler.build_query_string_q("labels:Prod")
        body = q.to_dict()
        # 结构化查询仍走 query_string，不叠加全字段 wildcard 白名单展开
        assert "query_string" in body
        assert body["query_string"]["query"]

    def test_alert_build_query_string_q_includes_appointee_follower(self):
        handler = AlertQueryHandler.__new__(AlertQueryHandler)
        handler.query_context = None
        q = handler.build_query_string_q("Prod", escape_colon=True)
        dumped = str(q.to_dict())
        assert "appointee" in dumped
        assert "follower" in dumped
        assert "labels" in dumped
        assert "case_insensitive" in dumped
        assert "assignee" not in {f.es_field for f in AlertQueryHandler.FULLTEXT_SEARCH_FIELDS}

