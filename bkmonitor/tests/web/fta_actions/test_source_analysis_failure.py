"""源码分析失败节点摘要：旧协议兼容、去重、脱敏和展示长度边界。"""

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

    def test_html_and_plugin_help_are_not_returned(self):
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
        self.assertIn("Input validation: script failed", result)
        for content in ("<", ">", "docs.example.com", "plugin help"):
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
