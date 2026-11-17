"""协议及生命周期检查；使用实际 SDK 的测试单独标记。"""

import contextvars
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8")

from ai_agent.services.hermes_executor import HermesChatExecutor, iterate_in_context


def event(kind, **kwargs):
    return SimpleNamespace(type=kind, **kwargs)


@pytest.fixture
def executor():
    interface = SimpleNamespace(
        app_code="synthetic-app",
        app_secret="synthetic-secret",
        api_client=SimpleNamespace(
            api=SimpleNamespace(create_chat_session_content=Mock(return_value={"result": True}))
        ),
    )
    return HermesChatExecutor(interface, "session-a", "agent-a", "alice", [], Mock())


def test_stream_preserves_legacy_sse_and_caller_owned_persistence(executor):
    agent = Mock()
    agent.stream.return_value = iter(
        [
            event("heartbeat"),
            event("text_delta", delta="你好"),
            event("done", result=SimpleNamespace(text="你好")),
        ]
    )
    output = list(executor._stream(agent, None, [], "你好"))
    assert output[0] == ": heartbeat\n\n"
    assert output[-1] == "data: [DONE]\n\n"
    payloads = [json.loads(row[6:]) for row in output if row.startswith("data: {")]
    assert [row["event"] for row in payloads] == ["text", "think", "done"]
    executor.interface.api_client.api.create_chat_session_content.assert_not_called()
    agent.close.assert_called_once()


@pytest.mark.parametrize(
    "events", [[], [event("text_delta", delta="未完成")], [event("error", error="sk-sensitive-value")]]
)
def test_missing_completion_is_failure_and_never_persisted(executor, events):
    agent = Mock()
    agent.stream.return_value = iter(events)
    output = "".join(executor._stream(agent, None, [], "问题"))
    assert '"event": "error"' in output
    assert '"event": "done"' not in output
    assert "sk-sensitive-value" not in output
    executor.interface.api_client.api.create_chat_session_content.assert_not_called()


def test_browser_close_interrupts_and_closes_sdk(executor):
    agent = Mock()
    closed = []

    def events():
        try:
            yield event("text_delta", delta="第一段")
            yield event("done", result=SimpleNamespace(text="第一段"))
        finally:
            closed.append(True)

    agent.stream.return_value = events()
    stream = executor._stream(agent, None, [], "问题")
    next(stream)
    stream.close()
    agent.interrupt.assert_called_once()
    agent.close.assert_called_once()
    assert closed == [True]
    executor.interface.api_client.api.create_chat_session_content.assert_not_called()


def test_completion_does_not_call_storage_owned_by_the_caller(executor):
    agent = Mock()
    agent.stream.return_value = iter([event("text_delta", delta="回答"), event("done", result=None)])
    executor.interface.api_client.api.create_chat_session_content.side_effect = RuntimeError("storage-is-caller-owned")
    output = "".join(executor._stream(agent, None, [], "问题"))
    assert '"event": "error"' not in output
    assert '"event": "done"' in output
    executor.interface.api_client.api.create_chat_session_content.assert_not_called()


def test_close_before_first_chunk_releases_prepared_sdk(executor):
    agent = Mock()
    executor.prepare = Mock(return_value=(agent, None, [], "问题"))
    stream = executor.execute_stream()
    stream.close()
    stream.close()
    agent.close.assert_called_once()
    agent.stream.assert_not_called()


def test_stream_start_failure_is_sanitized_and_closes_sdk(executor):
    agent = Mock()
    agent.stream.side_effect = RuntimeError("synthetic-secret")
    output = "".join(executor._stream(agent, None, [], "问题"))
    assert '"event": "error"' in output
    assert "synthetic-secret" not in output
    agent.close.assert_called_once()


def test_delayed_iterator_restores_context_and_closes_inside_it():
    identity = contextvars.ContextVar("test_identity", default="none")
    identity.set("alice")
    captured = contextvars.copy_context()
    seen = []

    def iterator():
        try:
            seen.append(identity.get())
            yield identity.get()
        finally:
            seen.append(identity.get())

    stream = iterate_in_context(iterator(), captured)
    identity.set("bob")
    assert next(stream) == "alice"
    stream.close()
    assert seen == ["alice", "alice"]
    assert identity.get() == "bob"


@pytest.fixture(scope="module")
def tracing_runtime():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield provider, exporter
    provider.shutdown()


@pytest.mark.parametrize(("streaming", "agui"), [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("async_tool", [False, True])
@pytest.mark.parametrize("tracing", [False, True])
def test_real_sdk_tool_roundtrip(
    executor, tmp_path, monkeypatch, tracing_runtime, streaming, async_tool, tracing, agui
):
    """回环 HTTP 固定模型响应，实际 SDK 执行工具并完成第二轮请求。"""
    if importlib.util.find_spec("hermes_core") is None:
        pytest.skip("可选 SDK 未安装；私有运行时验收必须执行本项")
    from opentelemetry.trace import SpanKind

    calls, requests = [], []
    from langchain_core.tools import StructuredTool

    def query(metric: str) -> str:
        """返回当前请求允许的样例指标。"""
        calls.append(metric)
        return json.dumps({"result": "cpu=25", "api_key": "synthetic-secret-for-redaction"})

    async def query_async(metric: str) -> str:
        """返回当前请求允许的样例指标。"""
        return query(metric)

    tool = StructuredTool.from_function(coroutine=query_async) if async_tool else StructuredTool.from_function(query)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = json.dumps({"object": "list", "data": [{"id": "gpt-4o-mini", "object": "model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            has_result = any(row.get("role") == "tool" for row in payload["messages"])
            message = {"role": "assistant", "content": "CPU=25" if has_result else None}
            if not has_result:
                message["tool_calls"] = [
                    {
                        "id": "call-cpu",
                        "type": "function",
                        "function": {"name": tool.name, "arguments": '{"metric":"cpu"}'},
                    }
                ]
            result = {
                "id": "synthetic-reply",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-4o-mini",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop" if has_result else "tool_calls"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            self.send_response(200)
            if payload.get("stream"):
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                delta = {key: value for key, value in message.items() if value is not None}
                for call in delta.get("tool_calls", []):
                    call["index"] = 0
                chunk = {
                    **result,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop" if has_result else "tool_calls"}]
                self.wfile.write(f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode())
            else:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for name, value in {
            "AI_AGENT_HERMES_LLM_API_KEY": "synthetic",
            "AI_AGENT_HERMES_LLM_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
            "AI_AGENT_HERMES_LLM_MODEL": "gpt-4o-mini",
            "AI_AGENT_HERMES_LLM_PROVIDER": "synthetic",
            "AI_AGENT_HERMES_HOME": str(tmp_path),
            "AI_AGENT_HERMES_MAX_ITERATIONS": 3,
            "AI_AGENT_OTEL_ENABLED": tracing,
            "AI_AGENT_OTEL_CAPTURE_CONTENT": tracing,
        }.items():
            monkeypatch.setattr(settings, name, value, raising=False)
        executor.context = [{"role": "user", "content": "查询 CPU"}]
        executor.interface.api_client.construct_tool = Mock(return_value=tool)
        executor.config_manager.get_config.return_value = SimpleNamespace(
            tool_codes=[tool.name],
            mcp_server_config={},
            role_prompt="先使用工具，再回答。",
            llm_model_name="gpt-4o-mini",
            agent_name="Synthetic Agent",
        )
        provider, exporter = tracing_runtime
        exporter.clear()
        with provider.get_tracer("synthetic-http").start_as_current_span(
            "HTTP synthetic", kind=SpanKind.SERVER
        ) as parent:
            parent_context = parent.get_span_context()
            if streaming:
                stream = executor.execute_stream()
                if agui:
                    from copy import deepcopy

                    from ai_agent.services.agui import ChatRun, stream_events
                    from ai_agent.services.agui_history import AguiSessionHistory

                    def save(**kwargs):
                        return {"result": True, "data": {"id": "saved", **deepcopy(kwargs["json"])}}

                    executor.interface.api_client.api.create_chat_session_content.side_effect = save
                    history = AguiSessionHistory(
                        executor.interface.api_client.api, "session-a", username="alice", turn_id="turn-a"
                    )
                    stream = stream_events(
                        "session-a",
                        stream,
                        history,
                        ChatRun("session-a", "alice"),
                        lambda error: pytest.fail(str(error)),
                    )
            else:
                assert executor.execute_invoke()["choices"][0]["delta"]["content"] == "CPU=25"
        if streaming:
            output = "".join(stream)
            assert ('"type": "RUN_FINISHED"' if agui else '"event": "done"') in output
            assert '"event": "error"' not in output and '"type": "RUN_ERROR"' not in output
            assert "synthetic-secret-for-redaction" not in output
        assert calls == ["cpu"]
        assert any(
            row.get("role") == "tool" and "cpu=25" in str(row.get("content")) for row in requests[-1]["messages"]
        )
        if not (streaming and agui):
            executor.interface.api_client.api.create_chat_session_content.assert_not_called()
        else:
            assert executor.interface.api_client.api.create_chat_session_content.call_count == 3
        if tracing:
            spans = exporter.get_finished_spans()
            roots = [span for span in spans if span.name.startswith("invoke_agent")]
            assert len(roots) == 1
            assert roots[0].parent.span_id == parent_context.span_id
            assert roots[0].context.trace_id == parent_context.trace_id
            assert any(span.name.startswith("chat") for span in spans)
            assert any(span.name.startswith("execute_tool") for span in spans)
            assert "synthetic-secret-for-redaction" not in str([dict(span.attributes) for span in spans])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
