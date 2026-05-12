import base64
import json

from django.test import SimpleTestCase

from apps.log_clustering.utils.pattern import (
    RISK_REASON_AMBIGUOUS_DUPLICATE_PLACEHOLDER,
    RISK_REASON_INSUFFICIENT_LITERAL_TOKENS,
    RISK_REASON_INSUFFICIENT_RIGHT_ANCHOR,
    RISK_REASON_TRUNCATED_TAIL,
    build_doris_regexp,
    escape_sql_literal,
    evaluate_pattern_risk,
    parse_pattern_placeholders,
)


def encode_predefined_variables(variables):
    return base64.b64encode(json.dumps(variables).encode("utf-8")).decode("utf-8")


PREDEFINED_VARIABLES = encode_predefined_variables(
    [
        r"PATH:[^ ]+",
        r"NUMBER:\d+",
    ]
)


class TestPatternUtils(SimpleTestCase):
    def test_parse_pattern_placeholders_keeps_occurrence_order(self):
        result = parse_pattern_placeholders("#NUMBER# x #PATH# y #NUMBER#")

        self.assertEqual(
            result,
            [
                {"name": "NUMBER", "index": 0},
                {"name": "PATH", "index": 1},
                {"name": "NUMBER", "index": 2},
            ],
        )

    def test_build_doris_regexp_builds_capture_for_target_placeholder(self):
        result = build_doris_regexp(
            "prefix #PATH# middle #NUMBER# suffix",
            placeholder_index=1,
            predefined_varibles=PREDEFINED_VARIABLES,
        )

        self.assertEqual(
            result,
            r"prefix[\s\S]*?(?:[^ ]+)[\s\S]*?middle[\s\S]*?(\d+)[\s\S]*?suffix",
        )

    def test_build_doris_regexp_escapes_literal_and_wildcard(self):
        result = build_doris_regexp(
            "foo.bar * (#NUMBER#)",
            placeholder_index=0,
            predefined_varibles=PREDEFINED_VARIABLES,
        )

        self.assertIn(r"foo\.bar", result)
        self.assertIn(r"\(", result)
        self.assertIn(r"\)", result)
        self.assertIn(r"(\d+)", result)
        self.assertFalse(result.endswith("$"))

    def test_build_doris_regexp_normalizes_inner_capturing_groups(self):
        predefined_variables = encode_predefined_variables(
            [
                r"PATH:([a-z]+)/(\d+)",
            ]
        )

        result = build_doris_regexp(
            "prefix #PATH# suffix",
            placeholder_index=0,
            predefined_varibles=predefined_variables,
        )

        self.assertEqual(result, r"prefix[\s\S]*?((?:[a-z]+)/(?:\d+))[\s\S]*?suffix")

    def test_build_doris_regexp_strips_outer_anchors_from_placeholder_regex(self):
        predefined_variables = encode_predefined_variables(
            [
                r"NUMBER:^[-+]?[0-9]+(?:\.[0-9]+)?$",
                r"TIME:\d{2}:\d{2}:\d{2}(?:\.\d{6})?",
            ]
        )

        result = build_doris_regexp(
            "Apr #NUMBER# #TIME# * systemd Started Session #NUMBER# of user root.",
            placeholder_index=1,
            predefined_varibles=predefined_variables,
        )

        self.assertNotIn(r"(?:^[-+]?[0-9]+(?:\.[0-9]+)?$)", result)
        self.assertIn(r"(?:[-+]?[0-9]+(?:\.[0-9]+)?)", result)
        self.assertEqual(
            result,
            r"Apr[\s\S]*?(?:[-+]?[0-9]+(?:\.[0-9]+)?)[\s\S]*?(\d{2}:\d{2}:\d{2}(?:\.\d{6})?)[\s\S]*?[\s\S]*?[\s\S]*?systemd[\s\S]*?Started[\s\S]*?Session[\s\S]*?(?:[-+]?[0-9]+(?:\.[0-9]+)?)[\s\S]*?of[\s\S]*?user[\s\S]*?root\.",
        )

    def test_escape_sql_literal_handles_backslash_and_quote(self):
        result = escape_sql_literal(r"foo\bar'baz")

        self.assertEqual(result, r"foo\\bar''baz")

    def test_evaluate_pattern_risk_reports_weak_anchor_and_duplicate_placeholder(self):
        result = evaluate_pattern_risk(
            "#NUMBER# -> #NUMBER# *",
            placeholder_index=1,
            max_log_length=18,
            predefined_varibles=PREDEFINED_VARIABLES,
        )

        self.assertEqual(result["risk_level"], "medium")
        self.assertIn(RISK_REASON_AMBIGUOUS_DUPLICATE_PLACEHOLDER, result["reasons"])
        self.assertIn(RISK_REASON_INSUFFICIENT_LITERAL_TOKENS, result["reasons"])
        self.assertIn(RISK_REASON_INSUFFICIENT_RIGHT_ANCHOR, result["reasons"])
        self.assertIn(RISK_REASON_TRUNCATED_TAIL, result["reasons"])
