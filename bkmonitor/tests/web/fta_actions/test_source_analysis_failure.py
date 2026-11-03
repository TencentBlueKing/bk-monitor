"""源码分析失败节点摘要：旧协议兼容、去重、脱敏和展示长度边界。"""

import json

from django.test import SimpleTestCase

from constants.issue import SourceAnalysisFailureMessage
from fta_web.issue.source_analysis_failure import (
    MAX_FAILURE_MESSAGE_LENGTH,
    build_bkfara_failure_message,
)


class TestSourceAnalysisFailureSummary(SimpleTestCase):
    def test_missing_or_invalid_details_preserve_top_level_message(self):
        for details in (None, [], "invalid", {}, {"failed_tasks": {"task_name": "ignored"}}):
            with self.subTest(details=details):
                self.assertEqual(
                    build_bkfara_failure_message({"message": "pipeline failed", "details": details}),
                    "pipeline failed",
                )
        self.assertEqual(build_bkfara_failure_message({}), SourceAnalysisFailureMessage.BKFARA_TASK_FAILED)

    def test_failed_tasks_and_error_info_are_merged_by_task_id(self):
        result = build_bkfara_failure_message(
            {
                "message": "pipeline failed",
                "details": {
                    "failed_tasks": [
                        {"task_id": "task-1", "task_name": "Input validation", "error_message": "missing parameter"}
                    ],
                    "error_info_list": [
                        {
                            "taskId": "task-1",
                            "taskName": "Input validation",
                            "errorCode": 2199002,
                            "errorMsg": "plugin failed",
                        }
                    ],
                    "build_message": "not a failure reason",
                    "private_debug": "not for display",
                },
            }
        )
        self.assertEqual(result, "pipeline failed | Input validation [2199002]: missing parameter")

    def test_error_info_alone_and_multiple_nodes(self):
        result = build_bkfara_failure_message(
            {
                "message": "pipeline failed",
                "details": {
                    "error_info_list": [
                        {"taskId": "1", "taskName": "Checkout", "errorCode": 42, "errorMsg": "not found"},
                        {"taskId": "2", "taskName": "Checkout", "errorMsg": "permission denied"},
                    ]
                },
            }
        )
        self.assertEqual(result, "pipeline failed | Checkout [42]: not found | Checkout: permission denied")

    def test_duplicate_nodes_without_id_are_deduplicated(self):
        node = {"task_name": "Checkout", "error_message": "not found"}
        result = build_bkfara_failure_message({"details": {"failed_tasks": [node, node]}})
        self.assertEqual(result.count("Checkout"), 1)

    def test_html_tags_are_removed_but_link_text_is_preserved(self):
        result = build_bkfara_failure_message(
            {
                "details": {
                    "failed_tasks": [
                        {
                            "task_name": "&lt;b&gt;Input validation&lt;/b&gt;",
                            "error_message": (
                                '<b>script failed</b>\r\n\r\n<a href="https://docs.example.com/help">plugin help</a>'
                            ),
                        }
                    ]
                }
            }
        )
        self.assertIn("Input validation: script failed plugin help", result)
        for content in ("<", ">", "docs.example.com"):
            self.assertNotIn(content, result)

    def test_credentials_are_masked_in_all_display_fields(self):
        secrets = (
            'BKAPI_ACCESS_TOKEN="secret-a", AIDEV_ACCESS_TOKEN=secret-b; '
            "bk_app_secret='secret-c', bk_ticket=secret-d; password=secret-e; api_key=secret-f"
        )
        result = build_bkfara_failure_message(
            {
                "message": "failed " + secrets,
                "details": {
                    "failed_tasks": [
                        {"task_name": secrets, "error_message": secrets, "errorCode": "token=secret-g"},
                        {"error_message": 'X-Bkapi-Authorization: {"access_token":"secret-h"}'},
                        {"error_message": "Authorization: Bearer secret-i"},
                    ]
                },
            }
        )
        self.assertNotIn("secret-", result)
        self.assertIn("******", result)

    def test_quoted_authorization_headers_are_masked(self):
        for header in (
            '"Authorization": "Bearer secret-header"',
            "'X-Bkapi-Authorization': 'Basic secret-header'",
        ):
            with self.subTest(header=header):
                result = build_bkfara_failure_message({"details": {"failed_tasks": [{"error_message": header}]}})
                self.assertNotIn("secret-header", result)

    def test_truncated_quoted_credential_does_not_leak_trailing_words(self):
        result = build_bkfara_failure_message({"message": 'access_token="first-word secret-tail ' + "x" * 10000})
        self.assertNotIn("secret-tail", result)

    def test_escaped_and_serialized_credentials_are_masked(self):
        for key in ("password", "access_token", "bk_app_secret", "Authorization"):
            for secret in ('prefix"private-tail', "prefix\\private-tail", "prefix\nprivate-tail"):
                text = json.dumps({key: secret})
                for depth in range(4):
                    with self.subTest(key=key, secret=secret, depth=depth):
                        result = build_bkfara_failure_message(
                            {
                                "message": text,
                                "details": {
                                    "failed_tasks": [{"task_name": text, "error_message": text, "errorCode": text}]
                                },
                            }
                        )
                        self.assertNotIn("private-tail", result)
                        self.assertIn("******", result)
                    text = json.dumps(text)

    def test_multiline_and_html_wrapped_credentials_are_masked(self):
        for text in (
            "Authorization: Bearer\nprivate-tail",
            "access_token=Bearer private-tail",
            "<b>access_token</b>=private-tail",
            '<a href="https://docs.example.com/help">access_token</a>=private-tail',
            'access_token="prefix\\"private-tail',
        ):
            with self.subTest(text=text):
                result = build_bkfara_failure_message({"details": {"failed_tasks": [{"error_message": text}]}})
                self.assertNotIn("private-tail", result)
                self.assertIn("******", result)

    def test_deep_html_is_discarded_without_losing_valid_node_fields(self):
        malformed = "<" * 60 + "a>" * 60
        result = build_bkfara_failure_message(
            {
                "message": malformed,
                "details": {
                    "failed_tasks": [{"task_id": malformed, "task_name": "Validation", "error_message": malformed}],
                    "error_info_list": [{"taskName": malformed, "errorCode": malformed, "errorMsg": "missing input"}],
                },
            }
        )
        self.assertIn(SourceAnalysisFailureMessage.BKFARA_TASK_FAILED, result)
        self.assertIn("Validation", result)
        self.assertIn("missing input", result)
        self.assertNotIn("<", result)

    def test_invalid_html_marked_sections_are_discarded_in_all_fields(self):
        for malformed in ("unexpected response: <![foo]>", "<![invalid section]>"):
            with self.subTest(malformed=malformed):
                result = build_bkfara_failure_message(
                    {
                        "message": malformed,
                        "details": {
                            "failed_tasks": [
                                {"task_id": malformed, "task_name": "Validation", "error_message": malformed}
                            ],
                            "error_info_list": [
                                {"taskName": malformed, "errorCode": malformed, "errorMsg": "missing input"}
                            ],
                        },
                    }
                )
                self.assertIn(SourceAnalysisFailureMessage.BKFARA_TASK_FAILED, result)
                self.assertIn("Validation", result)
                self.assertIn("missing input", result)
                self.assertNotIn("<![", result)

    def test_plain_error_paragraphs_are_preserved(self):
        for separator in ("\n\n", "\r\n\r\n"):
            with self.subTest(separator=separator):
                result = build_bkfara_failure_message(
                    {
                        "message": "pipeline failed",
                        "details": {
                            "failed_tasks": [
                                {
                                    "task_name": "Validation",
                                    "error_message": f"Task failed{separator}ValueError: required alert_id is missing",
                                }
                            ]
                        },
                    }
                )
                self.assertEqual(
                    result, "pipeline failed | Validation: Task failed ValueError: required alert_id is missing"
                )

    def test_help_titles_and_markers_do_not_hide_following_error_paragraphs(self):
        result = build_bkfara_failure_message(
            {
                "message": (
                    'Task failed\n\n<a href="https://docs.example.com/help">plugin help</a>'
                    "\n\nPython脚本执行插件常见问题\nValueError: missing input"
                    "\n\n======脚本执行失败,问题排查指引======\n通用排障建议\nRuntimeError: checkout failed"
                )
            }
        )
        self.assertEqual(
            result,
            "Task failed plugin help Python脚本执行插件常见问题 ValueError: missing input "
            "======脚本执行失败,问题排查指引====== 通用排障建议 RuntimeError: checkout failed",
        )

    def test_help_text_is_preserved_in_both_node_formats_and_still_redacted(self):
        for list_key, name_key, error_key in (
            ("failed_tasks", "task_name", "error_message"),
            ("error_info_list", "taskName", "errorMsg"),
        ):
            with self.subTest(list_key=list_key):
                result = build_bkfara_failure_message(
                    {
                        "message": "pipeline failed",
                        "details": {
                            list_key: [
                                {
                                    name_key: "plugin help",
                                    error_key: (
                                        "Python脚本执行插件常见问题\n======脚本执行失败,问题排查指引======"
                                        "\nRuntimeError: checkout failed\naccess_token=private-tail"
                                    ),
                                }
                            ]
                        },
                    }
                )
                self.assertEqual(
                    result,
                    "pipeline failed | plugin help: Python脚本执行插件常见问题 "
                    "======脚本执行失败,问题排查指引====== RuntimeError: checkout failed credential=******",
                )

    def test_invalid_nodes_do_not_break_terminal_state_processing(self):
        result = build_bkfara_failure_message(
            {
                "message": "pipeline failed",
                "details": {
                    "failed_tasks": [None, [], "bad", 1, {}, {"task_name": {}, "error_message": ["bad"]}],
                    "error_info_list": [{"errorCode": True}, {"taskName": "Checkout", "errorMsg": "not found"}],
                },
            }
        )
        self.assertEqual(result, "pipeline failed | Checkout: not found")

    def test_task_count_and_message_length_are_bounded(self):
        nodes = [{"task_id": str(i), "task_name": f"node-{i}", "error_message": "failure"} for i in range(30)]
        result = build_bkfara_failure_message({"details": {"failed_tasks": nodes}})
        self.assertEqual(result.count("node-"), 5)

        for node in nodes:
            node["error_message"] = "x" * 10000
        result = build_bkfara_failure_message({"message": "m" * 10000, "details": {"failed_tasks": nodes}})
        self.assertEqual(len(result), MAX_FAILURE_MESSAGE_LENGTH)
