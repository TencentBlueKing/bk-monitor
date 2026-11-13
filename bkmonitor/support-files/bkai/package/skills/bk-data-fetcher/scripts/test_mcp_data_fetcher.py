#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import requests

import mcp_data_fetcher as mcp


class MCPResultParsingTests(unittest.TestCase):
    def test_parse_mcp_result_finds_json_in_later_text_chunk(self):
        result = {
            "content": [
                {"type": "text", "text": "debug: calling remote MCP"},
                {
                    "type": "text",
                    "text": '```json\n{"response_body": {"result": true, "data": [1, 2]}}\n```',
                },
            ]
        }

        self.assertEqual(
            mcp.parse_mcp_result(result),
            {"response_body": {"result": True, "data": [1, 2]}},
        )

    def test_parse_sse_response_supports_multiline_data_event(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        text = 'event: message\ndata: {"jsonrpc":"2.0",\ndata: "id":"request-1",\ndata: "result":{"ok":true}}\n\n'

        self.assertEqual(
            client._parse_sse_response(text, request_id="request-1"),
            {"jsonrpc": "2.0", "id": "request-1", "result": {"ok": True}},
        )

    def test_parse_sse_response_skips_keepalive_and_event_only_frames(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        text = (
            ": ping\n"
            "\n"
            "event: keepalive\n"
            "\n"
            "event: message\n"
            "id: server-1\n"
            'data: {"jsonrpc":"2.0","id":"req-1","result":{"ok":true}}\n'
            "\n"
        )

        self.assertEqual(
            client._parse_sse_response(text, request_id="req-1"),
            {"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True}},
        )

    def test_parse_sse_response_returns_none_on_only_keepalive(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        text = ": ping\n\nevent: keepalive\n\n"
        self.assertIsNone(client._parse_sse_response(text, request_id="req-1"))

    def test_parse_sse_response_handles_done_marker(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        text = 'data: {"jsonrpc":"2.0","id":"req-1","result":{"ok":true}}\n\ndata: [DONE]\n\n'
        self.assertEqual(
            client._parse_sse_response(text, request_id="req-1"),
            {"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True}},
        )

    def test_decode_jsonrpc_body_falls_back_when_content_type_misreports_sse(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False
        body = '{"jsonrpc":"2.0","id":"req-1","result":{"ok":true}}'

        result = client._decode_jsonrpc_body(
            text_body=body,
            content_type="text/event-stream",
            request_id="req-1",
            tool_name="dummy",
        )
        self.assertEqual(result, {"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True}})

    def test_decode_jsonrpc_body_raises_protocol_error_when_unparseable(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False
        with self.assertRaises(mcp.MCPProtocolError) as ctx:
            client._decode_jsonrpc_body(
                text_body=": ping\n\n",
                content_type="text/event-stream",
                request_id="req-1",
                tool_name="dummy",
            )
        msg = str(ctx.exception)
        self.assertIn("无法解析", msg)
        self.assertIn("dummy", msg)

    def test_call_tool_retries_on_protocol_error(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.servers = {"bkm-prod-metrics-query": {"type": "remote", "url": "https://gateway.example.com"}}
        client.verbose = False

        attempts = {"n": 0}

        def fake_http(*args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise mcp.MCPProtocolError("simulated chunked SSE failure")
            return {"ok": True}

        with mock.patch.object(client, "_call_tool_http", side_effect=fake_http):
            result = client.call_tool("bkm-prod-metrics-query", "execute_range_query", {}, retries=1)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(attempts["n"], 2)

    def test_call_tool_retries_on_5xx(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.servers = {"bkm-prod-metrics-query": {"type": "remote", "url": "https://gateway.example.com"}}
        client.verbose = False

        attempts = {"n": 0}

        def fake_http(*args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise mcp.MCPServerUnavailableError("503 Service Unavailable")
            return {"ok": True}

        with mock.patch.object(client, "_call_tool_http", side_effect=fake_http):
            result = client.call_tool("bkm-prod-metrics-query", "execute_range_query", {}, retries=1)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(attempts["n"], 2)

    def test_raise_for_http_status_marks_502_as_retryable(self):
        resp = requests.Response()
        resp.status_code = 502
        resp._content = b"Bad Gateway"
        with self.assertRaises(mcp.MCPServerUnavailableError):
            mcp.MCPClient._raise_for_http_status(resp)

    def test_raise_for_http_status_keeps_401_as_auth_error(self):
        resp = requests.Response()
        resp.status_code = 401
        resp._content = b""
        with self.assertRaises(mcp.MCPAuthenticationError):
            mcp.MCPClient._raise_for_http_status(resp)

    def test_decode_jsonrpc_body_concatenates_data_across_events(self):
        """处理某些非规范服务器把单个 JSON 拆到多个独立 SSE 事件的情况。"""
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False
        body = (
            'data: {"jsonrpc":"2.0","id":"req-1","result":{"content":\n\ndata: [{"type":"text","text":"hello"}]}}\n\n'
        )
        result = client._decode_jsonrpc_body(
            text_body=body,
            content_type="text/event-stream",
            request_id="req-1",
            tool_name="dummy",
        )
        self.assertEqual(
            result,
            {"jsonrpc": "2.0", "id": "req-1", "result": {"content": [{"type": "text", "text": "hello"}]}},
        )

    def test_decode_jsonrpc_body_dumps_failed_response(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False
        with tempfile.TemporaryDirectory() as tmp:
            client.output_dir = tmp
            with self.assertRaises(mcp.MCPProtocolError) as ctx:
                client._decode_jsonrpc_body(
                    text_body=": ping\n\n: ping\n\n",
                    content_type="text/event-stream",
                    request_id="req-1",
                    tool_name="search_event_log",
                    save_failed_dump=True,
                )
            err = str(ctx.exception)
            self.assertIn("原始响应已保存", err)
            dump_dir = Path(tmp) / "_mcp_failed_responses"
            files = list(dump_dir.iterdir())
            self.assertEqual(len(files), 1)
            content = files[0].read_text(encoding="utf-8")
            self.assertIn("# tool: search_event_log", content)
            self.assertIn("# request_id: req-1", content)
            self.assertIn(": ping", content)

    def test_stream_sse_until_match_returns_immediately_on_id_match(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False

        class FakeResp:
            def iter_lines(self, decode_unicode=False, chunk_size=8192):
                lines = [
                    b": ping",
                    b"",
                    b"event: message",
                    b'data: {"jsonrpc":"2.0","id":"req-1","result":{"ok":true}}',
                    b"",
                ]
                yield from lines

        result, all_text = client._stream_sse_until_match(
            response=FakeResp(),
            request_id="req-1",
            tool_name="dummy",
            chunk_collector=[],
        )
        self.assertEqual(
            result,
            {"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True}},
        )
        self.assertIn("data:", all_text)

    def test_stream_sse_until_match_returns_none_for_only_keepalive(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.verbose = False

        class FakeResp:
            def iter_lines(self, decode_unicode=False, chunk_size=8192):
                yield from [b": ping", b"", b"event: keepalive", b""]

        result, _ = client._stream_sse_until_match(
            response=FakeResp(),
            request_id="req-1",
            tool_name="dummy",
            chunk_collector=[],
        )
        self.assertIsNone(result)

    def test_decode_sse_line_handles_utf8_and_bad_bytes(self):
        # 正常 UTF-8 中文
        ok = mcp.MCPClient._decode_sse_line('data: {"text":"中文"}'.encode())
        self.assertEqual(ok, 'data: {"text":"中文"}')
        # 非法字节序列 → replace 而非崩溃
        bad = mcp.MCPClient._decode_sse_line(b"data: \xff\xfe garbage\r")
        self.assertTrue(bad.startswith("data: "))

    def test_parse_sse_response_supports_gateway_chunked_json_strings(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        text = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":"request-1","result":{"content":[{"type":"text","text":"'
            '{\\"request_id\\":\\"inner-1\\",\\"response_body\\"'
            "\n"
            'data: :{\\"result\\":true}}"}]}}\n'
            "\n"
        )

        self.assertEqual(
            client._parse_sse_response(text, request_id="request-1"),
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"request_id":"inner-1","response_body":{"result":true}}',
                        }
                    ]
                },
            },
        )


class MCPConfigDiscoveryTests(unittest.TestCase):
    def setUp(self):
        # Legacy-client cases must not inherit a host/container's active Hermes
        # home or explicit MCP override; those precedence rules are tested below.
        env = mock.patch.dict(
            os.environ, {key: "" for key in (*mcp.MCP_CONFIG_ENV_VARS, "HERMES_HOME", "HERMES_SAFE_MODE")}
        )
        env.start()
        self.addCleanup(env.stop)

    def test_find_mcp_config_honors_env_override_before_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_text(
                json.dumps({"mcpServers": {"bkm-prod-log-query": {"type": "http"}}}),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"BK_MCP_CONFIG_PATH": str(config_path)}):
                with mock.patch.object(mcp, "_build_mcp_config_candidates", return_value=[]):
                    self.assertEqual(mcp._find_mcp_config(), str(config_path))

    def test_find_mcp_config_supports_bkai_code_jsonc_mcp_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            config_path = home / ".bkai-code" / "xdg-config" / "opencode" / "opencode.jsonc"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                """
                {
                  // OpenCode schema from bkai-code
                  "mcp": {
                    "bkm-prod-metrics-query": {
                      "type": "remote",
                      "url": "https://gateway.example.com/mcp"
                    },
                  }
                }
                """,
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                with mock.patch("os.getcwd", return_value=str(Path(tmp) / "workspace")):
                    with mock.patch.object(mcp, "_detect_workspace_root", return_value=str(Path(tmp) / "workspace")):
                        self.assertEqual(mcp._find_mcp_config(), str(config_path))

    def test_client_loads_mcp_top_level_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "opencode.jsonc"
            config_path.write_text(
                """
                {
                  "mcp": {
                    "bkm-prod-log-query": {
                      "type": "remote",
                      "url": "https://gateway.example.com/log"
                    }
                  }
                }
                """,
                encoding="utf-8",
            )

            client = mcp.MCPClient(mcp_config_path=str(config_path))
            self.assertEqual(client.list_servers(), ["bkm-prod-log-query"])

    def test_config_candidates_include_bkai_latest_mcp_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            workspace = Path(tmp) / "workspace"
            candidates = mcp._build_mcp_config_candidates(str(workspace), str(workspace))

            expected_suffixes = [
                ".codebuddy/mcp.json",
                ".bkai-code/xdg-config/opencode/opencode.jsonc",
            ]
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                rebuilt = mcp._build_mcp_config_candidates(str(workspace), str(workspace))
            for suffix in expected_suffixes:
                self.assertTrue(
                    any(path.endswith(suffix) for path in rebuilt),
                    f"missing candidate suffix {suffix}; candidates={rebuilt}",
                )
            self.assertTrue(candidates)


class MCPHermesConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": os.environ["PATH"]}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        cwd = mock.patch.object(mcp.os, "getcwd", return_value=str(self.home))
        cwd.start()
        self.addCleanup(cwd.stop)
        workspace = mock.patch.object(mcp, "_detect_workspace_root", return_value=str(self.home))
        workspace.start()
        self.addCleanup(workspace.stop)

    def write_config(self, entries, name="hermes/config.yaml"):
        # JSON is a YAML subset. Other cases exercise YAML-specific syntax.
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mcp_servers": entries}))
        return path

    def test_explicit_yaml_load_and_request_headers(self):
        path = self.home / "hermes.yml"
        path.write_text("""mcp_servers:
  example-sg-alarm:
    url: https://gateway.example.com/mcp
    headers:
      X-Test: fixture-auth-header
""")
        before = path.read_bytes()
        client = mcp.MCPClient(str(path))
        self.assertEqual(client.list_servers(), ["example-sg-alarm"])
        self.assertEqual(client.servers["example-sg-alarm"]["type"], "streamableHttp")
        with mock.patch.object(client, "_stream_jsonrpc_request", return_value={"result": {"ok": True}}) as request:
            self.assertEqual(client.call_tool("example-sg-alarm", "probe", {}, retries=0), {"ok": True})
            self.assertEqual(request.call_args.kwargs["headers"]["X-Test"], "fixture-auth-header")
            self.assertEqual(request.call_args.kwargs["url"], "https://gateway.example.com/mcp")
        self.assertEqual(path.read_bytes(), before)

    def test_subprocess_reads_config_and_calls_loopback_server(self):
        received = []
        probe = "local-fixture-header-not-for-logs"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append((self.headers.get("X-Test"), body["method"], body["params"]))
                response = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {"ok": True}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        server = ThreadingHTTPServer(("localhost", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        host, port = server.server_address
        entry = {"url": f"http://{host}:{port}/mcp", "headers": {"X-Test": probe}}
        yaml_path = self.write_config({"example": entry})
        before = yaml_path.read_bytes()
        json_path = self.home / "explicit.json"
        json_path.write_text(json.dumps({"mcpServers": {"example": dict(entry, type="http")}}))
        jsonc_path = self.home / "explicit.jsonc"
        jsonc_path.write_text('// JSONC fixture\n{"mcp":{"example":' + json.dumps(dict(entry, type="remote")) + ",},}")
        code = """import sys
sys.path.insert(0, sys.argv[1])
from mcp_data_fetcher import MCPClient
client = MCPClient()
assert client.list_servers() == ["example"]
assert client.call_tool("example", "probe", {"value": 1}, timeout=5, retries=0) == {"ok": True}
print("subprocess-request-ok")
"""
        for label, override in (
            ("yaml-home", {"HERMES_HOME": str(yaml_path.parent)}),
            ("yaml-explicit", {"BK_MCP_CONFIG_PATH": str(yaml_path)}),
            ("json", {"BK_MCP_CONFIG_PATH": str(json_path)}),
            ("jsonc", {"BK_MCP_CONFIG_PATH": str(jsonc_path)}),
        ):
            with self.subTest(format=label):
                env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **override}
                proc = subprocess.run(
                    [sys.executable, "-B", "-c", code, str(Path(__file__).resolve().parent)],
                    env=env,
                    cwd=self.home,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(proc.returncode, 0, "isolated MCP child failed")
                self.assertIn("subprocess-request-ok", proc.stdout)
                self.assertNotIn(probe, proc.stdout + proc.stderr)
        self.assertEqual(received, [(probe, "tools/call", {"name": "probe", "arguments": {"value": 1}})] * 4)
        self.assertEqual(yaml_path.read_bytes(), before)
        self.assertFalse((yaml_path.parent / "mcp-compat.json").exists())

    def test_hermes_home_precedes_legacy_config(self):
        path = self.write_config({"hermes": {"url": "https://gateway.example.com"}})
        cursor = self.home / ".cursor/mcp.json"
        cursor.parent.mkdir()
        cursor.write_text(json.dumps({"mcpServers": {"stale": {"type": "http"}}}))
        os.environ["HERMES_HOME"] = str(path.parent)
        self.assertEqual(mcp.MCPClient().list_servers(), ["hermes"])

    def test_missing_or_disabled_active_home_does_not_fallback(self):
        cursor = self.home / ".cursor/mcp.json"
        cursor.parent.mkdir()
        cursor.write_text(json.dumps({"mcpServers": {"stale": {"type": "http"}}}))
        os.environ["HERMES_HOME"] = str(self.home / "hermes")
        with self.assertRaises(mcp.MCPConfigError):
            mcp.MCPClient()
        self.write_config({"off": {"url": "https://gateway.example.com", "enabled": False}})
        with self.assertRaises(mcp.MCPConfigError):
            mcp.MCPClient()

    def test_environment_overrides_hermes_home(self):
        yaml_path = self.write_config({"hermes": {"url": "https://gateway.example.com"}})
        explicit = self.home / "explicit.jsonc"
        explicit.write_text('{/* JSONC */"mcp":{"explicit":{"type":"remote"},},}')
        os.environ.update(HERMES_HOME=str(yaml_path.parent), BK_MCP_CONFIG_PATH=str(explicit))
        self.assertEqual(mcp.MCPClient().list_servers(), ["explicit"])
        os.environ["BK_MCP_CONFIG_PATH"] = str(self.home / "missing.yaml")
        with self.assertRaises(FileNotFoundError):
            mcp.MCPClient()

    def test_environment_can_point_to_yaml(self):
        path = self.write_config({"hermes": {"url": "https://gateway.example.com"}})
        for variable in mcp.MCP_CONFIG_ENV_VARS:
            with self.subTest(variable=variable), mock.patch.dict(os.environ, {variable: str(path)}):
                self.assertEqual(mcp.MCPClient().list_servers(), ["hermes"])

    def test_default_hermes_home_discovery(self):
        path = self.write_config({"hermes": {"url": "https://gateway.example.com"}}, ".hermes/config.yaml")
        self.assertEqual(mcp.MCPClient().mcp_config_path, str(path))

    def test_disabled_and_stdio_are_not_exposed(self):
        for disabled in (False, "false", "0", "no", "off"):
            path = self.write_config(
                {
                    "off": {"url": "https://gateway.example.com", "enabled": disabled},
                    "local": {"command": "example"},
                    "on": {"url": "https://gateway.example.com", "enabled": "true"},
                }
            )
            with self.assertWarnsRegex(UserWarning, "stdio"):
                client = mcp.MCPClient(str(path))
            self.assertEqual(client.list_servers(), ["on"])
            with self.assertRaises(ValueError):
                client.call_tool("off", "probe", {})
        os.environ["HERMES_SAFE_MODE"] = "1"
        self.assertEqual(mcp._load_mcp_config(str(path)), {"mcpServers": {}})

    def test_sse_and_http_aliases_preserve_dispatch(self):
        for transport in ("sse", "http", "remote", "streamableHttp"):
            with self.subTest(transport=transport):
                path = self.write_config({"test": {"url": "https://gateway.example.com", "transport": transport}})
                client = mcp.MCPClient(str(path))
                method = {
                    "sse": "_call_tool_sse",
                    "http": "_call_tool_http",
                    "remote": "_call_tool_http",
                    "streamableHttp": "_call_tool_streamable_http",
                }[transport]
                with mock.patch.object(client, method, return_value={"ok": True}) as request:
                    self.assertEqual(client.call_tool("test", "probe", {}), {"ok": True})
                    request.assert_called_once()

    def test_invalid_or_policy_bearing_entries_fail_closed(self):
        for extra in (
            {"type": "sse"},
            {"transport": "unknown"},
            {"transport": "sse", "type": "http"},
            {"tools": {"exclude": ["write"]}},
            {"auth": "oauth"},
            {"ssl_verify": False},
            {"headers": {"X-Key": 123}},
            {"url": "file:///tmp/example"},
            {"enabled": "invalid"},
        ):
            path = self.write_config({"test": {"url": "https://gateway.example.com", **extra}})
            with self.subTest(options=list(extra)), self.assertRaises(mcp.MCPConfigError):
                mcp.MCPClient(str(path))

    def test_environment_interpolation_missing_value_is_error(self):
        path = self.write_config({"test": {"url": "https://gateway.example.com", "headers": {"X-Key": "${TEST_KEY}"}}})
        with self.assertRaises(mcp.MCPConfigError):
            mcp.MCPClient(str(path))
        os.environ["TEST_KEY"] = "fixture-key"
        self.assertEqual(mcp.MCPClient(str(path)).servers["test"]["headers"]["X-Key"], "fixture-key")

    def test_yaml_errors_do_not_disclose_source(self):
        path = self.home / "bad.yaml"
        path.write_text('mcp_servers: ["fixture-secret-probe')
        with self.assertRaises(mcp.MCPConfigError) as error:
            mcp.MCPClient(str(path))
        self.assertNotIn("fixture-secret-probe", str(error.exception))
        for invalid in (
            "[]",
            "mcp_servers: []",
            "mcp_servers:\n  test: []",
            "!!python/object/apply:os.system ['false']",
        ):
            path.write_text(invalid)
            with self.assertRaises(mcp.MCPConfigError):
                mcp.MCPClient(str(path))

    def test_json_remains_usable_without_pyyaml(self):
        json_path = self.home / "old.json"
        json_path.write_text(json.dumps({"mcpServers": {"old": {"type": "http"}}}))
        yaml_path = self.write_config({"test": {"url": "https://gateway.example.com"}})
        with mock.patch.dict("sys.modules", {"yaml": None}):
            self.assertEqual(mcp.MCPClient(str(json_path)).list_servers(), ["old"])
            with self.assertRaisesRegex(mcp.MCPConfigError, "PyYAML"):
                mcp.MCPClient(str(yaml_path))


class MCPServerResolutionTests(unittest.TestCase):
    def test_find_server_supports_legacy_non_query_names(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.servers = {
            "bk-monitor-prod-metrics": {"type": "sse"},
            "bk-monitor-prod-alerts": {"type": "sse"},
            "bk-monitor-prod-event": {"type": "sse"},
        }

        self.assertEqual(client.find_server("prod", "metrics-query"), "bk-monitor-prod-metrics")
        self.assertEqual(client.find_server("prod", "alarm"), "bk-monitor-prod-alerts")
        self.assertEqual(client.find_server("prod", "event-query"), "bk-monitor-prod-event")

    def test_find_server_supports_bkai_latest_service_names(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.servers = {
            "bkm-prod-dashboard-edit": {"type": "http"},
            "bkm-prod-metric-anomaly-detection": {"type": "http"},
            "bkm-prod-openclaw-recovering": {"type": "http"},
        }

        self.assertEqual(client.find_server("prod", "dashboard-edit"), "bkm-prod-dashboard-edit")
        self.assertEqual(
            client.find_server("prod", "metric-anomaly-detection"),
            "bkm-prod-metric-anomaly-detection",
        )
        self.assertEqual(
            client.find_server("prod", "openclaw-recovering"),
            "bkm-prod-openclaw-recovering",
        )

    def test_remote_protocol_is_listed_and_called_as_http(self):
        client = mcp.MCPClient.__new__(mcp.MCPClient)
        client.servers = {
            "bkm-prod-metrics-query": {
                "type": "remote",
                "url": "https://gateway.example.com/mcp",
            }
        }
        self.assertEqual(client.list_servers(), ["bkm-prod-metrics-query"])

        with mock.patch.object(client, "_call_tool_http", return_value={"ok": True}) as call_http:
            result = client.call_tool("bkm-prod-metrics-query", "execute_range_query", {})
        self.assertEqual(result, {"ok": True})
        call_http.assert_called_once()


if __name__ == "__main__":
    unittest.main()
