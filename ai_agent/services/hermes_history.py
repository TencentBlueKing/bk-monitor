"""将平台会话恢复为模型历史，保留工具证据及未确认状态。"""

import json


def protocol_field(record, name, default=None):
    if name in record:
        return record[name]
    return ((record.get("property") or {}).get("builtin_property") or {}).get(name, default)


def normalize_tool_calls(record):
    calls = []
    stored = protocol_field(record, "tool_calls", [])
    if not isinstance(stored, list):
        return calls
    for call in stored:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        if not call.get("id") or not isinstance(function, dict) or not function.get("name"):
            continue
        arguments = function.get("arguments", "{}")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        try:
            if not isinstance(arguments, str) or not isinstance(json.loads(arguments), dict):
                continue
        except ValueError:
            continue
        calls.append(
            {
                "id": str(call["id"]),
                "type": "function",
                "function": {"name": str(function["name"]), "arguments": arguments},
            }
        )
    return calls


def repair_tool_pairs(turns):
    result, pending, seen = [], {}, set()

    def close_pending():
        for call_id in pending:
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": '{"status":"unconfirmed","message":"历史中缺少工具结果，不能判断执行成功。"}',
                }
            )
        pending.clear()

    for turn in turns:
        if turn["role"] == "tool":
            call_id = turn["tool_call_id"]
            if call_id in pending:
                result.append(turn)
                del pending[call_id]
            continue
        if turn.get("tool_calls"):
            calls = [call for call in turn["tool_calls"] if call["id"] not in seen]
            seen.update(call["id"] for call in calls)
            turn = {**turn, "tool_calls": calls}
            if not calls:
                turn.pop("tool_calls")
        if not turn.get("content") and not turn.get("tool_calls"):
            continue
        close_pending()
        pending.update((call["id"], call) for call in turn.get("tool_calls", []))
        result.append(turn)
    close_pending()
    return result


def convert_session_context(records):
    system_parts, turns = [], []
    for record in records or []:
        role = str(record.get("role") or "").removeprefix("hidden-")
        role = {"ai": "assistant", "pause": "assistant", "hidden": "user", "user-image": "user"}.get(role, role)
        content = record.get("content") or ""
        if role == "system":
            if content:
                system_parts.append(content)
        elif role in ("user", "assistant"):
            turn = {"role": role, "content": content}
            if role == "assistant" and (calls := normalize_tool_calls(record)):
                turn["tool_calls"] = calls
            if content or turn.get("tool_calls"):
                turns.append(turn)
        elif role == "tool" and (call_id := protocol_field(record, "tool_call_id")):
            turns.append({"role": "tool", "tool_call_id": str(call_id), "content": content})
    for index in range(len(turns) - 1, -1, -1):
        if turns[index]["role"] == "user":
            return "\n".join(system_parts) or None, repair_tool_pairs(turns[:index]), turns[index]["content"]
    raise ValueError("会话中没有用户消息")
