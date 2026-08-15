"""源码分析结果协议校验测试。"""

import json
from unittest.mock import patch

from django.test import SimpleTestCase

from constants.issue import SourceAnalysisResultType
from fta_web.issue.source_analysis_result import (
    SourceAnalysisResultValidationError,
    SourceAnalysisResultValidator,
)


class TestSourceAnalysisResultValidator(SimpleTestCase):
    @staticmethod
    def build_result(result_type=SourceAnalysisResultType.HIGH_CONFIDENCE) -> dict:
        responsibility = None
        if result_type == SourceAnalysisResultType.HIGH_CONFIDENCE:
            responsibility = {
                "commit_id": "a3fa531",
                "commit_message": "restore session guard",
                "author_name": "Edwin Wu",
                "bk_username": "edwinwu",
            }
        return {
            "schema_version": "1.0.0",
            "result_type": result_type,
            "result_card": {
                "description": "Session 空值检查缺失导致异常。",
                "responsibility": responsibility,
            },
            "content_type": "text/markdown",
            "content": "# 分析结论\n\nSession 空值检查缺失导致异常。",
        }

    def assert_validation_code(self, payload, expected_code):
        with self.assertRaises(SourceAnalysisResultValidationError) as context:
            SourceAnalysisResultValidator.validate(payload)
        self.assertEqual(context.exception.code, expected_code)

    def test_accepts_two_final_result_types(self):
        high_confidence = self.build_result()
        insufficient = self.build_result(SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)

        self.assertEqual(SourceAnalysisResultValidator.validate(high_confidence), high_confidence)
        self.assertEqual(SourceAnalysisResultValidator.validate(json.dumps(insufficient)), insufficient)

    def test_high_confidence_allows_empty_responsibility(self):
        payload = self.build_result()
        payload["result_card"]["responsibility"] = None

        self.assertEqual(SourceAnalysisResultValidator.validate(payload), payload)

    def test_rejects_non_json_result(self):
        self.assert_validation_code("not-json", "RESULT_NOT_JSON")
        self.assert_validation_code(b"\xff", "RESULT_NOT_JSON")

    def test_rejects_unsupported_schema_version(self):
        payload = self.build_result()
        payload["schema_version"] = "2.0.0"

        self.assert_validation_code(payload, "RESULT_SCHEMA_UNSUPPORTED")

    def test_rejects_insufficient_evidence_responsibility(self):
        payload = self.build_result(SourceAnalysisResultType.INSUFFICIENT_EVIDENCE)
        payload["result_card"]["responsibility"] = self.build_result()["result_card"]["responsibility"]

        self.assert_validation_code(payload, "RESULT_SEMANTIC_INVALID")

    def test_rejects_schema_violations(self):
        invalid_payloads = []

        extra_field = self.build_result()
        extra_field["source_build"] = {}
        invalid_payloads.append(extra_field)

        empty_description = self.build_result()
        empty_description["result_card"]["description"] = ""
        invalid_payloads.append(empty_description)

        wrong_content_type = self.build_result()
        wrong_content_type["content_type"] = "text/plain"
        invalid_payloads.append(wrong_content_type)

        empty_content = self.build_result()
        empty_content["content"] = ""
        invalid_payloads.append(empty_content)

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assert_validation_code(payload, "RESULT_SCHEMA_INVALID")

    def test_rejects_payload_over_transport_limit(self):
        payload = self.build_result()
        payload["content"] = "1234567890"

        with patch.object(SourceAnalysisResultValidator, "MAX_PAYLOAD_BYTES", 8):
            self.assert_validation_code(payload, "RESULT_SCHEMA_INVALID")
