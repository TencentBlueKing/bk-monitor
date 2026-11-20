"""入口身份隔离及宿主流式统计回归，不调用业务服务。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai_agent.services.hermes_executor import HermesChatExecutor, create_chat_completion
from ai_agent.services.metrics_reporter import EnhancedStreamingResponseWrapper, StreamingMetricsTracker


def test_error_sse_is_not_reported_as_completed():
    reporter = Mock()
    tracker = StreamingMetricsTracker(reporter, "CreateChatCompletionResource", "agent", "alice")
    interface = SimpleNamespace(api_client=Mock())
    executor = HermesChatExecutor(interface, "session", "agent", "alice", [], Mock())
    executor.on_error = tracker.on_streaming_error
    agent = Mock()
    agent.stream.return_value = iter([])
    stream = EnhancedStreamingResponseWrapper(executor._stream(agent, None, [], "问题"), tracker)
    assert '"event": "error"' in "".join(stream._monitored_generator())
    statuses = [call.kwargs["status"] for call in reporter.report_request.call_args_list]
    assert statuses.count("error") == 1
    assert "completed" not in statuses


def test_response_close_propagates_to_sdk():
    agent = Mock()
    agent.stream.return_value = iter([SimpleNamespace(type="text_delta", delta="首段")])
    executor = HermesChatExecutor(SimpleNamespace(api_client=Mock()), "session", "agent", "alice", [], Mock())
    tracker = StreamingMetricsTracker(Mock(), "CreateChatCompletionResource", "agent", "alice")
    response = EnhancedStreamingResponseWrapper(
        executor._stream(agent, None, [], "问题"), tracker
    ).as_streaming_response()
    next(iter(response))
    response.close()
    agent.interrupt.assert_called_once()
    agent.close.assert_called_once()


def test_response_close_before_iteration_releases_prepared_sdk():
    agent = Mock()
    executor = HermesChatExecutor(SimpleNamespace(api_client=Mock()), "session", "agent", "alice", [], Mock())
    executor.prepare = Mock(return_value=(agent, None, [], "问题"))
    tracker = StreamingMetricsTracker(Mock(), "CreateChatCompletionResource", "agent", "alice")
    response = EnhancedStreamingResponseWrapper(executor.execute_stream(), tracker).as_streaming_response()
    response.close()
    agent.close.assert_called_once()
    agent.stream.assert_not_called()


def test_entrypoint_does_not_reuse_another_users_mcp_headers(monkeypatch):
    from ai_agent.core import custom_config_manager
    from ai_agent.services import hermes_executor

    monkeypatch.setattr(hermes_executor, "require_runtime", lambda: None)
    current_user = ["alice"]
    monkeypatch.setattr(custom_config_manager, "get_local_request", lambda: current_user[0])
    monkeypatch.setattr(custom_config_manager, "_get_mcp_auth_info", lambda user: {"access_token": f"token-{user}"})
    source = {
        "agent_name": "Synthetic agent",
        "prompt_setting": {
            "content": [{"role": "system", "content": "只读查询"}],
            "llm_code": "model",
            "non_thinking_llm": "",
        },
        "knowledgebase_settings": {"knowledgebases": []},
        "related_tools": [],
        "conversation_settings": {"opening_remark": "", "commands": []},
        "mcp_server_config": {"mcpServers": {"synthetic-metadata": {"url": "https://mcp.example.com"}}},
    }
    client = Mock()
    client.retrieve_agent_config.side_effect = lambda code: deepcopy(source)
    client.get_chat_session_context.side_effect = lambda code: [{"role": "user", "content": "查看 CPU"}]
    interface = SimpleNamespace(api_client=client, retrieve_chat_session=Mock(return_value={"data": {}}))
    captured = []

    def invoke(executor):
        config = executor.config_manager.get_config("agent", executor.interface.api_client)
        captured.append(config.mcp_server_config["synthetic-metadata"]["headers"]["X-Bkapi-Authorization"])
        return {"ok": True}

    monkeypatch.setattr(HermesChatExecutor, "execute_invoke", invoke)
    for user in ("alice", "bob"):
        current_user[0] = user
        result = create_chat_completion(
            interface,
            session_code="session",
            execute_kwargs={"stream": False},
            agent_code="agent",
            username=user,
            temperature=0.3,
            switch_agent_by_scene=False,
        )
        assert result == {"ok": True}
    assert "token-alice" in captured[0] and "token-bob" not in captured[0]
    assert "token-bob" in captured[1] and "token-alice" not in captured[1]
    assert client.retrieve_agent_config.call_count == 2


def test_runtime_absence_is_explicit(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    from ai_agent.services import hermes_runtime

    monkeypatch.setattr(hermes_runtime, "runtime_available", lambda: False)
    with pytest.raises(ImproperlyConfigured, match="SDK 未安装"):
        hermes_runtime.require_runtime()
