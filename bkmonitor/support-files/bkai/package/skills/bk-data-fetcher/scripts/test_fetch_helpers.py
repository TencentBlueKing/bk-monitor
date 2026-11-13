"""Regression coverage for explicit target selection and query failures."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import sys
import unittest
from unittest import mock

import fetch_cpu_data
import fetch_logs
import fetch_metrics
import mcp_data_fetcher as mcp


def configured_client(*names):
    client = mcp.MCPClient.__new__(mcp.MCPClient)
    client.servers = {name: {"type": "streamableHttp", "url": "https://gateway.example.com"} for name in names}
    return client


class TargetSelectionTests(unittest.TestCase):
    def test_arbitrary_explicit_environment_and_user_prefix(self):
        client = configured_client("user-bk-monitor-sandbox-west-metrics-query", "bkm-prod-metrics-query")
        self.assertEqual(
            client.find_server("sandbox-west", "metrics-query"), "user-bk-monitor-sandbox-west-metrics-query"
        )

    def test_missing_environment_never_falls_back_to_another_environment(self):
        client = configured_client("bkm-prod-metrics-query")
        for environment in (None, "", "stage"):
            with self.subTest(environment=environment), self.assertRaises(ValueError):
                client.find_server(environment, "metrics-query")

    def test_ambiguous_environment_requires_exact_configured_name(self):
        client = configured_client("bkm-stage-metrics-query", "bk-monitor-stage-metrics-query")
        with self.assertRaises(ValueError):
            client.find_server("stage", "metrics-query")
        self.assertEqual(client.find_server("stage", "bkm-stage-metrics-query"), "bkm-stage-metrics-query")

    def test_full_name_cannot_override_explicit_environment_or_missing_config(self):
        client = configured_client("bkm-prod-metrics-query")
        for environment, name in (("stage", "bkm-prod-metrics-query"), ("prod", "bk-monitor-prod-metrics-query")):
            with self.subTest(environment=environment, name=name), self.assertRaises(ValueError):
                client.find_server(environment, name)


class FetchHelpersTests(unittest.TestCase):
    def test_all_commands_require_business_and_environment_before_config_loading(self):
        for module in (fetch_metrics, fetch_logs, fetch_cpu_data):
            for arguments in (["--biz-id", "7"], ["--env", "stage"]):
                with self.subTest(module=module.__name__, arguments=arguments):
                    with mock.patch.object(sys, "argv", [module.__name__, *arguments]):
                        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                            module.main()
                        self.assertEqual(error.exception.code, 2)

    def test_invalid_windows_fail_before_server_selection_or_request(self):
        client = mock.Mock()
        for start, end in ((1, 1), (2, 1), (-1, 1), (1, 86402)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    fetch_metrics.fetch_metrics(client, "7", "up", start, end, env="stage")
                with self.assertRaises(ValueError):
                    fetch_logs.fetch_logs_batch(client, "7", "9", start, end, "stage")
        client.find_server.assert_not_called()
        client.call_tool.assert_not_called()

    def test_metric_boundary_window_uses_selected_environment_and_seconds(self):
        client = mock.Mock()
        client.find_server.return_value = "bkm-stage-metrics-query"
        client.call_tool.return_value = {"response_body": {"result": True, "data": {}}}
        fetch_metrics.fetch_metrics(client, "7", "up", 0, 86400, env="stage")
        client.find_server.assert_called_once_with("stage", "metrics-query")
        self.assertEqual(client.call_tool.call_args.args[2]["body_param"]["start_time"], "0")
        self.assertEqual(client.call_tool.call_args.args[2]["body_param"]["end_time"], "86400")

    def test_ambiguous_index_name_stops_without_selecting_first_match(self):
        client = mock.Mock()
        client.call_tool.return_value = {
            "response_body": {
                "result": True,
                "data": [
                    {"index_set_id": "8", "index_set_name": "example-api-a"},
                    {"index_set_id": "9", "index_set_name": "example-api-b"},
                ],
            }
        }
        with redirect_stdout(StringIO()):
            self.assertIsNone(fetch_logs.find_index_set(client, "7", "stage", index_name="example-api"))

    def test_log_request_failure_is_not_an_empty_success(self):
        client = mock.Mock()
        client.call_tool.side_effect = mcp.MCPProtocolError("example protocol failure")
        with self.assertRaisesRegex(RuntimeError, "example protocol failure"):
            fetch_logs.fetch_logs_batch(client, "7", "9", 1, 2, "stage")

    def test_small_batch_window_has_no_empty_segments_and_reports_truncation(self):
        calls = []

        def batch(client, biz_id, index_id, start, end, env, query, limit):
            calls.append((start, end))
            return ([{"log": "example"}], 10)

        output = StringIO()
        with mock.patch.object(fetch_logs, "fetch_logs_batch", side_effect=batch):
            with mock.patch.object(fetch_logs.time, "sleep"), redirect_stdout(output):
                fetch_logs.fetch_all_logs(mock.Mock(), "7", "9", 1, 3, "stage", batch_size=1)
        self.assertTrue(all(start < end for start, end in calls))
        self.assertIn("结果已截断", output.getvalue())
        self.assertIn("不能据此确认全量覆盖", output.getvalue())

    def test_cpu_wrapper_forwards_selected_business_and_environment(self):
        with mock.patch.object(sys, "argv", ["fetch_cpu_data", "--biz-id", "7", "--env", "sandbox-west"]):
            with mock.patch.object(fetch_cpu_data.subprocess, "run") as run:
                run.return_value.returncode = 0
                with self.assertRaises(SystemExit) as error:
                    fetch_cpu_data.main()
        self.assertEqual(error.exception.code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--biz-id") + 1], "7")
        self.assertEqual(command[command.index("--env") + 1], "sandbox-west")


if __name__ == "__main__":
    unittest.main()
