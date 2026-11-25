"""历史恢复必须保留用户约束及工具失败，不重放未确认操作。"""

import json

import pytest

from ai_agent.services.hermes_history import convert_session_context, repair_tool_pairs


def test_history_roles_and_latest_question():
    prompt, history, message = convert_session_context(
        [
            {"role": "hidden-system", "content": "只查询业务 A"},
            {"role": "user", "content": "观察过去一小时"},
            {"role": "ai", "content": "已查询"},
            {"role": "guide", "content": "不应成为模型输入"},
            {"role": "user", "content": "现在只比较 CPU"},
        ]
    )
    assert prompt == "只查询业务 A"
    assert history == [{"role": "user", "content": "观察过去一小时"}, {"role": "assistant", "content": "已查询"}]
    assert message == "现在只比较 CPU"


def test_pending_tool_is_unknown_and_orphans_are_discarded():
    call = {"id": "call-a", "type": "function", "function": {"name": "query", "arguments": "{}"}}
    history = repair_tool_pairs(
        [
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "user", "content": "不要重试"},
            {"role": "tool", "tool_call_id": "orphan", "content": "不能成为证据"},
        ]
    )
    assert json.loads(history[1]["content"])["status"] == "unconfirmed"
    assert history[-1] == {"role": "user", "content": "不要重试"}


def test_legacy_tool_properties_survive_conversion():
    prompt, history, question = convert_session_context(
        [
            {
                "role": "ai",
                "property": {
                    "builtin_property": {
                        "tool_calls": [{"id": "a", "function": {"name": "query", "arguments": {"metric": "cpu"}}}]
                    }
                },
            },
            {"role": "tool", "content": "查询失败", "property": {"builtin_property": {"tool_call_id": "a"}}},
            {"role": "user", "content": "能判断根因吗"},
        ]
    )
    assert prompt is None
    assert question == "能判断根因吗"
    assert history[0]["tool_calls"][0]["function"]["arguments"] == '{"metric": "cpu"}'
    assert history[1]["content"] == "查询失败"


def test_consecutive_user_constraints_are_preserved():
    _, history, question = convert_session_context(
        [
            {"role": "user", "content": "限定业务 A"},
            {"role": "user", "content": "只读查询"},
            {"role": "user", "content": "查看 CPU"},
        ]
    )
    assert [row["content"] for row in history] == ["限定业务 A", "只读查询"]
    assert question == "查看 CPU"


def test_no_user_message_fails_instead_of_inventing_request():
    with pytest.raises(ValueError, match="用户消息"):
        convert_session_context([{"role": "system", "content": "system"}])
