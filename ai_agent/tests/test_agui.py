"""AG-UI lifecycle, platform persistence, identity and frontend message contracts."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from django.http import StreamingHttpResponse

from ai_agent.services.agui import ChatRun, public_tool_call, stream_events
from ai_agent.services.agui_api import frontend_history, platform_data, prepare_history, response_data
from ai_agent.services.agui_history import AguiSessionHistory
from ai_agent.services.hermes_executor import HermesChatExecutor
from ai_agent.services.hermes_history import convert_session_context


@pytest.fixture(autouse=True)
def agui_settings(monkeypatch):
    monkeypatch.setattr(settings, "AI_AGENT_STREAM_PROTOCOL", "agui", raising=False)


@pytest.fixture
def storage():
    records = []

    def write(*, json, headers):
        assert headers == {"X-BKAIDEV-USER": "alice"}
        data = deepcopy(json)
        data["id"] = len(records) + 1
        records.append(data)
        return {"result": True, "data": data}

    return SimpleNamespace(create_chat_session_content=Mock(side_effect=write), records=records)


def setup(storage, chunks):
    history = AguiSessionHistory(storage, "session-a", username="alice", turn_id="turn-a")
    run = ChatRun("session-a", "alice")
    errors = []
    return stream_events("session-a", iter(chunks), history, run, errors.append), history, run, errors


def frame(event, **values):
    return f"data: {json.dumps({'event': event, **values})}\n\n"


def events(stream):
    return [json.loads(line[5:]) for line in stream]


def tool(phase="start", *, is_error=False):
    return {
        "id": "call-1",
        "name": "query_metric",
        "phase": phase,
        "arguments": '{"metric": "cpu"}',
        "result": '{"value": 12}',
        "is_error": is_error,
        "duration": 25,
    }


def test_text_tool_text_persists_once_and_restores_model_history(storage):
    chunks = [
        frame("text", content="先查询"),
        frame("think", content="not a second text bubble", tool_call=tool()),
        frame("think", tool_call=tool("end")),
        frame("text", content="结论"),
        frame("done", content="先查询结论"),
        "data: [DONE]\n\n",
    ]
    stream, history, run, errors = setup(storage, chunks)
    output = events(stream)
    assert [event["type"] for event in output] == [
        "RUN_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_RESULT",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert [item["role"] for item in storage.records] == ["assistant", "assistant", "tool", "assistant"]
    assert [item["content"] for item in storage.records] == ["先查询", "", '{"value": 12}', "结论"]
    assert len({item["property"]["builtin_property"]["message_id"] for item in storage.records}) == 4
    prompt, restored, question = convert_session_context(
        [{"role": "user", "content": "查指标"}, *storage.records, {"role": "user", "content": "继续"}]
    )
    assert prompt is None and question == "继续"
    assert any(item["role"] == "tool" and item["tool_call_id"] == "call-1" for item in restored)
    assert not history.failed and not errors
    assert cache.get(run.key) is None


@pytest.mark.parametrize(
    "chunks",
    [
        [],
        [frame("text", content="半句")],
        [frame("error", message="synthetic-secret")],
        [frame("think", tool_call=tool()), frame("done")],
        ["data: [DONE]\n\n"],
        ["data: {broken\n\n"],
    ],
)
def test_failure_or_unfinished_tool_never_reports_success(storage, chunks):
    stream, history, _, errors = setup(storage, chunks)
    output = events(stream)
    assert output[-1]["type"] == "RUN_ERROR"
    assert not any(item["type"] == "RUN_FINISHED" for item in output)
    assert "synthetic-secret" not in json.dumps(output)
    assert errors
    assert all(item["status"] == "error" for item in storage.records if item["role"] != "assistant" or item["content"])


def test_history_write_not_confirmed_fails_without_retry_or_orphan_result(storage):
    storage.create_chat_session_content.return_value = {"result": False}
    storage.create_chat_session_content.side_effect = None
    stream, _, _, errors = setup(storage, [frame("think", tool_call=tool("end")), frame("done")])
    output = events(stream)
    assert output[-1]["type"] == "RUN_ERROR" and errors
    storage.create_chat_session_content.assert_called_once()


def test_dropped_protocol_fields_are_not_reported_as_saved(storage):
    storage.create_chat_session_content.side_effect = lambda **_: {"result": True, "data": {"id": 1}}
    stream, _, _, _ = setup(storage, [frame("text", content="正文"), frame("done")])
    assert events(stream)[-1]["type"] == "RUN_ERROR"


def test_duplicate_tool_events_do_not_duplicate_cards_or_history(storage):
    stream, _, _, _ = setup(
        storage,
        [
            frame("think", tool_call=tool()),
            frame("think", tool_call=tool()),
            frame("think", tool_call=tool("end")),
            frame("think", tool_call=tool("end")),
            frame("done"),
        ],
    )
    output = events(stream)
    assert [x["type"] for x in output].count("TOOL_CALL_START") == 1
    assert [x["type"] for x in output].count("TOOL_CALL_RESULT") == 1
    assert len(storage.records) == 2


def test_tool_failure_status_survives_live_events_and_history(storage):
    stream, _, _, _ = setup(storage, [frame("think", tool_call=tool("end", is_error=True)), frame("done")])
    result = next(event for event in events(stream) if event["type"] == "TOOL_CALL_RESULT")
    assert result["isError"] is True
    assert storage.records[-1]["status"] == "error"
    assert storage.records[-1]["property"]["builtin_property"]["error"] is True


def test_heartbeat_is_json_and_does_not_open_a_text_bubble(storage):
    stream, _, _, _ = setup(storage, [": heartbeat\n\n", frame("done")])
    assert [item["type"] for item in events(stream)] == ["RUN_STARTED", "RAW", "RUN_FINISHED"]


def test_stop_is_user_scoped_and_visible_across_run_instances(storage):
    stream, _, run, _ = setup(storage, [frame("text", content="半句"), frame("done")])
    assert json.loads(next(stream)[5:])["type"] == "RUN_STARTED"
    assert ChatRun.stop("session-a", "bob") is False
    assert not run.cancelled()
    assert ChatRun.stop("session-a", "alice") is True
    assert run.cancelled()
    output = events(stream)
    assert output[-1]["type"] == "RUN_ERROR"
    assert cache.get(run.key) is None


def test_same_user_cannot_start_two_streams_for_one_session():
    run = ChatRun("session-a", "alice")
    with pytest.raises(ValueError):
        ChatRun("session-a", "alice")
    other = ChatRun("session-a", "bob")
    run.close()
    other.close()


@pytest.mark.parametrize("consume", [False, True])
def test_response_close_propagates_to_sdk_even_before_first_chunk(storage, consume):
    agent = Mock()
    agent.stream.return_value = iter(
        [
            SimpleNamespace(type="text_delta", delta="半句"),
            SimpleNamespace(type="done", result=None),
        ]
    )
    executor = HermesChatExecutor(None, "session-a", "agent-a", "alice", [], None)
    executor.prepare = Mock(return_value=(agent, None, [], "问题"))
    chunks = executor.execute_stream()
    history = AguiSessionHistory(storage, "session-a", username="alice", turn_id="turn-a")
    run = ChatRun("session-a", "alice")
    response = StreamingHttpResponse(stream_events("session-a", chunks, history, run, Mock()))
    if consume:
        iterator = iter(response.streaming_content)
        for _ in range(3):  # RUN_STARTED, TEXT_MESSAGE_START, first delta
            next(iterator)
    response.close()
    agent.close.assert_called_once()
    if consume:
        agent.interrupt.assert_called_once()
        assert storage.records[0]["status"] == "error"
    else:
        agent.stream.assert_not_called()
    assert cache.get(run.key) is None


def test_public_tools_redact_credentials_before_stream_and_storage():
    call = SimpleNamespace(
        id="c1",
        name="query_metric",
        elapsed_ms=5,
        arguments={
            "metric": "cpu",
            "headers": {"Authorization": "Bearer synthetic-secret"},
            "nested": {"X-Bkapi-Authorization": "synthetic-auth", "bk_app_secret": "synthetic-app-secret"},
        },
        result='{"error": "denied", "access_token": "synthetic-token", "url": "https://example.com/?api_key=secret"}',
    )
    output = public_tool_call(call, "end")
    assert output["is_error"] is True
    assert "synthetic-secret" not in json.dumps(output)
    assert "synthetic-token" not in json.dumps(output)
    assert "synthetic-auth" not in json.dumps(output)
    assert "synthetic-app-secret" not in json.dumps(output)
    assert "api_key=secret" not in json.dumps(output)
    assert json.loads(output["arguments"])["metric"] == "cpu"


def test_history_preparation_binds_the_saved_user_message(storage):
    interface = SimpleNamespace(
        api_client=SimpleNamespace(api=storage),
        retrieve_chat_session=Mock(return_value={"result": True, "data": {"username": "alice"}}),
        get_chat_session_contents=Mock(
            return_value={
                "result": True,
                "data": [
                    {"id": 10, "role": "user", "message_id": "user-1", "property": {"turn_id": "turn-1"}},
                ],
            }
        ),
    )
    history, run = prepare_history(interface, "session-a", "alice", "user-1")
    assert history.turn_id == "turn-1"
    interface.get_chat_session_contents.assert_called_once_with("session-a", username="alice")
    run.close()
    with pytest.raises(ValueError):
        prepare_history(interface, "session-a", "bob", "user-1")
    with pytest.raises(ValueError):
        prepare_history(interface, "session-a", "alice", "another-message")


def test_history_projection_filters_unsupported_roles_and_preserves_tool_fields():
    data = {
        "result": True,
        "data": [
            {"role": "hidden-role", "content": "system prompt"},
            {"role": "unknown"},
            {"role": "tool", "content": "12", "property": {"builtin_property": {"tool_call_id": "c1"}}},
        ],
    }
    assert frontend_history(data) == [
        {
            "role": "tool",
            "content": "12",
            "tool_call_id": "c1",
            "property": {"builtin_property": {"tool_call_id": "c1"}},
        }
    ]
    with pytest.raises(RuntimeError):
        frontend_history({"result": False})
    with pytest.raises(RuntimeError):
        platform_data({"data": None, "result": False})
    assert response_data({"result": True, "data": {"id": 1}}) == {"id": 1}


def test_legacy_response_shape_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "AI_AGENT_STREAM_PROTOCOL", "legacy")
    response = {"result": True, "data": [{"role": "hidden-role", "content": "system"}]}
    assert response_data(response) is response
    assert frontend_history(response) is response


def serializers_module():
    path = Path(__file__).resolve().parents[2] / "bkmonitor/ai_whale/resources/session_serializers.py"
    spec = importlib.util.spec_from_file_location("agui_session_serializers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_chat_helper_message_fields_use_platform_builtin_property():
    serializer = serializers_module().SessionContentSerializer(
        data={
            "session_code": "session-a",
            "role": "tool",
            "content": "",
            "message_id": "result-1",
            "tool_call_id": "call-1",
            "duration": 25,
            "error": True,
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["property"]["builtin_property"] == {
        "message_id": "result-1",
        "tool_call_id": "call-1",
        "error": True,
        "additional_kwargs": {"duration": 25},
    }
    update = serializers_module().UpdateSessionContentSerializer(data={"id": "1", "status": "error"})
    assert update.is_valid(), update.errors
    assert update.validated_data == {"id": "1", "status": "error"}


@pytest.mark.parametrize(
    "data",
    [
        {"role": "user", "content": ""},
        {"role": "tool", "content": "missing call"},
        {"role": "assistant", "tool_calls": [{"id": "broken"}]},
        {"role": "user", "content": "hi", "message_id": "a", "property": {"builtin_property": {"message_id": "b"}}},
    ],
)
def test_invalid_message_contract_is_rejected(data):
    serializer = serializers_module().SessionContentSerializer(data={"session_code": "session-a", **data})
    assert not serializer.is_valid()
