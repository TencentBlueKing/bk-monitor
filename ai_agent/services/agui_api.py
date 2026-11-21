"""Session and message contracts used by the AG-UI HTTP endpoints."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ai_agent.services.agui import ChatRun
from ai_agent.services.agui_history import AguiSessionHistory


def enabled():
    protocol = getattr(settings, "AI_AGENT_STREAM_PROTOCOL", "legacy")
    if protocol not in {"legacy", "agui"}:
        raise ImproperlyConfigured("AI_AGENT_STREAM_PROTOCOL 必须是 legacy 或 agui")
    return protocol == "agui"


def platform_data(response):
    if not isinstance(response, dict) or response.get("result") is False or "data" not in response:
        raise RuntimeError("平台请求未成功，无法确认会话状态")
    return response["data"]


def response_data(response):
    # ResourceViewSet supplies the HTTP envelope. The new helper expects data
    # directly inside it, rather than another platform result/data envelope.
    return platform_data(response) if enabled() else response


def frontend_history(response):
    if not enabled():
        return response
    records = platform_data(response)
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise RuntimeError("平台返回了无效会话历史")
    roles = {
        "activity",
        "assistant",
        "developer",
        "guide",
        "hidden",
        "hidden-assistant",
        "hidden-guide",
        "hidden-system",
        "hidden-user",
        "info",
        "interrupt",
        "loading",
        "pause",
        "placeholder",
        "reasoning",
        "system",
        "template-assistant",
        "template-guide",
        "template-hidden",
        "template-system",
        "template-user",
        "tool",
        "user",
    }
    result = []
    for record in records:
        if record.get("role") not in roles:
            continue
        builtin = (record.get("property") or {}).get("builtin_property") or {}
        result.append({**builtin, **record})
    return result


def prepare_history(interface, session_code, username, message_id=None):
    if not username:
        raise ValueError("缺少登录用户身份")
    session = platform_data(interface.retrieve_chat_session(session_code, username=username))
    if not isinstance(session, dict):
        raise ValueError("会话不可用")
    # Platform deployments may expose the owner under either field.
    owner = session.get("username") or session.get("bk_username")
    if owner and str(owner) != str(username):
        raise ValueError("无权访问该会话")
    records = platform_data(interface.get_chat_session_contents(session_code, username=username))
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("会话历史不可用")
    user = next((item for item in reversed(records) if item.get("role") == "user"), None)
    prop = (user or {}).get("property") or {}
    current_id = (prop.get("builtin_property") or {}).get("message_id") or (user or {}).get("message_id")
    if message_id and str(message_id) not in {str(current_id or ""), str((user or {}).get("id") or "")}:
        raise ValueError("用户消息与当前会话轮次不一致")
    if not prop.get("turn_id"):
        raise ValueError("会话缺少当前用户轮次，请先保存用户消息")
    history = AguiSessionHistory(interface.api_client.api, session_code, username=username, turn_id=prop["turn_id"])
    return history, ChatRun(session_code, username)
