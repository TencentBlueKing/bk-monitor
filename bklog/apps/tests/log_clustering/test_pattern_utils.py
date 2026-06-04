import base64
import json
import re

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
        r"IP-PORT:[^ ]+",
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

    def test_parse_pattern_placeholders_supports_hyphenated_names(self):
        result = parse_pattern_placeholders("#DATETIME# client #IP-PORT# local #IP-PORT#")

        self.assertEqual(
            result,
            [
                {"name": "DATETIME", "index": 0},
                {"name": "IP-PORT", "index": 1},
                {"name": "IP-PORT", "index": 2},
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

    def test_build_doris_regexp_treats_hyphenated_placeholder_as_variable(self):
        result = build_doris_regexp(
            "traceId #PATH# client address #IP-PORT# local address #IP-PORT#",
            placeholder_index=1,
            predefined_varibles=PREDEFINED_VARIABLES,
        )

        self.assertIn(r"([^ ]+)", result)
        self.assertIn(r"(?:[^ ]+)", result)
        self.assertNotIn(r"\#IP\-PORT\#", result)

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

    def test_build_doris_regexp_keeps_duplicate_named_placeholder_rules_for_anchor_placeholder(self):
        predefined_variables = encode_predefined_variables(
            [
                r"DATETIME:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                r"NUMBER:^[-+]?[0-9]+(?:\.[0-9]+)?$",
                r"UUID:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                r"UUID:[0-9a-fA-F]{32}",
            ]
        )
        regex = build_doris_regexp(
            "#DATETIME# INFO auth_manager.py #NUMBER# #UUID# message success",
            placeholder_index=1,
            predefined_varibles=predefined_variables,
        )

        for uuid_value in [
            "d8369e7c-52f0-4c6b-9e88-bf813bd281c4",
            "d8369e7c52f04c6b9e88bf813bd281c4",
        ]:
            with self.subTest(uuid_value=uuid_value):
                match = re.search(
                    regex,
                    f"2026-05-28 20:31:17 INFO auth_manager.py 238 {uuid_value} message success",
                )

                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), "238")

    def test_build_doris_regexp_extracts_duplicate_named_placeholder_rules_for_target_placeholder(self):
        predefined_variables = encode_predefined_variables(
            [
                r"DATETIME:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                r"UUID:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                r"UUID:[0-9a-fA-F]{32}",
            ]
        )
        regex = build_doris_regexp(
            "#DATETIME# INFO request_id #UUID# message success",
            placeholder_index=1,
            predefined_varibles=predefined_variables,
        )

        for uuid_value in [
            "d8369e7c-52f0-4c6b-9e88-bf813bd281c4",
            "d8369e7c52f04c6b9e88bf813bd281c4",
        ]:
            with self.subTest(uuid_value=uuid_value):
                match = re.search(
                    regex,
                    f"2026-05-28 20:31:17 INFO request_id {uuid_value} message success",
                )

                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), uuid_value)

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
