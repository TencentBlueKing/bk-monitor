"""Exercise AG-UI integration with the installed host platform adapter."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings

from ai_agent.core.aidev_interface import AIDevInterface
from ai_agent.services.agui import ChatRun, stream_events
from ai_agent.services.agui_history import AguiSessionHistory
from ai_agent.services.hermes_executor import HermesChatExecutor
from ai_agent.services.metrics_reporter import EnhancedStreamingResponseWrapper, StreamingMetricsTracker


def test_session_create_and_list_share_v2_protocol_without_mutating_input(monkeypatch):
    monkeypatch.setattr(settings, "AI_AGENT_STREAM_PROTOCOL", "agui", raising=False)
    interface = AIDevInterface.__new__(AIDevInterface)
    interface.api_client = Mock()
    interface.api_client.api.create_chat_session.return_value = {
        "result": True,
        "data": {"role_info": {"role_content": [{"content": "system"}]}},
    }
    interface.create_chat_session_content = Mock()
    params = {"session_code": "s1", "session_name": "会话"}
    interface.create_chat_session(params, "alice")
    payload = interface.api_client.api.create_chat_session.call_args.kwargs
    assert params == {"session_code": "s1", "session_name": "会话"}
    assert payload["headers"] == {"X-BKAIDEV-USER": "alice"}
    assert payload["json"]["protocol_version"] == "v2"
    assert payload["json"]["session_type"] == "agent"
    assert payload["json"]["channel_type"] == "popup"
    interface.list_chat_sessions("alice", page=2, page_size=10)
    assert interface.api_client.api.list_chat_session.call_args.kwargs == {
        "headers": {"X-BKAIDEV-USER": "alice"},
        "params": {"protocol_version": "v2", "session_type": "agent", "page": 2, "page_size": 10},
    }


@pytest.mark.parametrize("failure", ["sdk", "save"])
def test_agui_sdk_or_save_error_reports_one_failure_and_no_completion(failure):
    reporter = Mock()
    tracker = StreamingMetricsTracker(reporter, "CreateChatCompletionResource", "agent", "alice")
    api = SimpleNamespace(create_chat_session_content=Mock(return_value={"result": False}))
    executor = HermesChatExecutor(None, "session-metrics", "agent", "alice", [], None)
    executor.on_error = tracker.on_streaming_error
    agent = Mock()
    agent.stream.return_value = iter(
        []
        if failure == "sdk"
        else [
            SimpleNamespace(type="text_delta", delta="正文"),
            SimpleNamespace(type="done", result=None),
        ]
    )
    history = AguiSessionHistory(api, "session-metrics", username="alice", turn_id="t1")
    run = ChatRun("session-metrics", "alice")

    def on_error(error):
        if not tracker.error_occurred:
            tracker.on_streaming_error(error)

    response = EnhancedStreamingResponseWrapper(
        stream_events("session-metrics", executor._stream(agent, None, [], "问题"), history, run, on_error), tracker
    ).as_streaming_response()
    assert b'"RUN_ERROR"' in b"".join(response.streaming_content)
    response.close()
    statuses = [call.kwargs["status"] for call in reporter.report_request.call_args_list]
    assert statuses.count("error") == 1
    assert "completed" not in statuses
