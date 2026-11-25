"""AG-UI events and request-scoped cancellation for the chat HTTP adapter."""

import hashlib
import json
import logging
import re
import time
from uuid import uuid4

from django.core.cache import cache

logger = logging.getLogger("ai_whale")
_RUN_TTL = 14400
_SENSITIVE_KEYS = {"token", "credential", "credentials", "passwd", "bkticket", "bktoken"}
_SENSITIVE_VALUE = re.compile(
    r"(?i)(bearer\s+)[^\s\"'<>]+|"
    r"((?:api[_-]?key|access[_-]?token|refresh[_-]?token|app[_-]?secret|password|bk[_-]?ticket)=)[^&\s\"'<>]+"
)


def _sanitize(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            sensitive = normalized in _SENSITIVE_KEYS or normalized.endswith(
                ("authorization", "cookie", "password", "secret", "apikey", "accesstoken", "refreshtoken")
            )
            result[str(key)] = "[REDACTED]" if sensitive else _sanitize(item)
        return result
    if isinstance(value, list | tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", value)
        return _SENSITIVE_VALUE.sub(lambda match: (match.group(1) or match.group(2)) + "[REDACTED]", value)
    return value


def public_tool_call(call, phase):
    result = getattr(call, "result", None)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (ValueError, TypeError):
            pass
    is_error = isinstance(result, dict) and (
        result.get("isError") is True or result.get("error") not in (None, False, "")
    )
    if isinstance(result, dict) and result.get("result") is False:
        is_error = True
    arguments = json.dumps(_sanitize(dict(call.arguments or {})), ensure_ascii=False, default=str)
    safe_result = _sanitize(result)
    content = safe_result if isinstance(safe_result, str) else json.dumps(safe_result, ensure_ascii=False, default=str)
    if len(content) > 32768:
        content = content[:32768] + "\n[结果过长，已截断]"
    return {
        "id": call.id,
        "name": call.name,
        "phase": phase,
        "arguments": arguments,
        "result": content,
        "is_error": is_error,
        "duration": getattr(call, "elapsed_ms", None) or 0,
    }


def encode_event(event):
    return f"data: {json.dumps({'timestamp': int(time.time() * 1000), **event}, ensure_ascii=False)}\n\n"


class ChatRun:
    """The shared cache lets a stop request reach a stream in another worker."""

    def __init__(self, session_code, username):
        digest = hashlib.sha256(f"{username}\0{session_code}".encode()).hexdigest()
        self.key = f"ai_agent:agui:{digest}"
        self.run_id = uuid4().hex
        self.cancel_key = f"{self.key}:{self.run_id}:stop"
        self.closed = False
        if not cache.add(self.key, self.run_id, timeout=_RUN_TTL):
            raise ValueError("当前会话仍有正在执行的请求，请先停止或等待完成")

    def cancelled(self):
        return bool(cache.get(self.cancel_key))

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                if cache.get(self.key) == self.run_id:
                    cache.delete(self.key)
                cache.delete(self.cancel_key)
            except Exception as error:
                logger.error("AG-UI run cleanup failed, error_type=%s", type(error).__name__)

    @classmethod
    def stop(cls, session_code, username):
        digest = hashlib.sha256(f"{username}\0{session_code}".encode()).hexdigest()
        key = f"ai_agent:agui:{digest}"
        run_id = cache.get(key)
        if not run_id:
            return False
        cache.set(f"{key}:{run_id}:stop", True, timeout=_RUN_TTL)
        return True


def _events(session_code, chunks, history, run, on_error):
    message_id = uuid4().hex
    text_started = False
    completed = False
    failed = False
    closing = False
    seen_calls, seen_results = set(), set()
    error_event = {
        "type": "RUN_ERROR",
        "runId": run.run_id,
        "message": "本轮执行或会话保存未完成，请刷新历史确认后再试。",
    }

    def emit(event):
        history.record(event)
        return encode_event(event)

    try:
        yield encode_event({"type": "RUN_STARTED", "threadId": session_code, "runId": run.run_id})
        failed = run.cancelled()
        for chunk in () if failed else chunks:
            if run.cancelled():
                failed = True
                break
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            if text.startswith(":"):
                yield encode_event({"type": "RAW"})
                continue
            if not text.startswith("data:"):
                continue
            raw = text[5:].strip()
            if raw == "[DONE]":
                break
            payload = json.loads(raw)
            kind = payload.get("event")
            if kind == "error":
                failed = True
                break
            if kind == "done":
                completed = True
                continue  # Its full text has already been emitted as deltas.
            call = payload.get("tool_call")
            if call:
                call_id, phase = call["id"], call["phase"]
                if (phase == "start" and call_id in seen_calls) or (phase == "end" and call_id in seen_results):
                    continue
                if text_started:
                    yield emit({"type": "TEXT_MESSAGE_END", "messageId": message_id})
                    message_id, text_started = uuid4().hex, False
                if call_id not in seen_calls:
                    seen_calls.add(call_id)
                    yield emit({"type": "TOOL_CALL_START", "toolCallId": call_id, "toolCallName": call["name"]})
                    yield emit({"type": "TOOL_CALL_ARGS", "toolCallId": call_id, "delta": call["arguments"]})
                if phase == "end":
                    seen_results.add(call_id)
                    yield emit({"type": "TOOL_CALL_END", "toolCallId": call_id})
                    yield emit(
                        {
                            "type": "TOOL_CALL_RESULT",
                            "toolCallId": call_id,
                            "messageId": call_id,
                            "content": call["result"],
                            "isError": call["is_error"],
                            "duration": call["duration"],
                        }
                    )
                continue
            if kind != "text" or not payload.get("content"):
                continue
            if not text_started:
                text_started = True
                yield emit({"type": "TEXT_MESSAGE_START", "messageId": message_id, "role": "assistant"})
            yield emit({"type": "TEXT_MESSAGE_CONTENT", "messageId": message_id, "delta": payload["content"]})
    except GeneratorExit:
        closing = True
        raise
    except Exception as error:
        failed = True
        logger.error("AG-UI stream failed, error_type=%s", type(error).__name__)
    finally:
        try:
            close = getattr(chunks, "close", None)
            if callable(close):
                close()
        finally:
            try:
                interrupted = closing or failed or not completed or bool(history.tools) or run.cancelled()
                history.finish(interrupted=interrupted)
                if interrupted and not closing and not history.failed:
                    history.record(error_event)
            except Exception as error:
                interrupted, history.failed = True, True
                logger.error("AG-UI history cleanup failed, error_type=%s", type(error).__name__)
            finally:
                run.close()
    if text_started:
        yield encode_event({"type": "TEXT_MESSAGE_END", "messageId": message_id})
    if interrupted or history.failed:
        try:
            on_error(RuntimeError("AG-UI 执行或会话保存未确认"))
        except Exception as error:
            logger.error("AG-UI error reporting failed, error_type=%s", type(error).__name__)
        yield encode_event(error_event)
    else:
        yield encode_event(
            {"type": "RUN_FINISHED", "threadId": session_code, "runId": run.run_id, "outcome": {"type": "success"}}
        )


def stream_events(session_code, chunks, history, run, on_error):
    import contextvars

    from ai_agent.services.hermes_executor import iterate_in_context

    def close_unstarted():
        try:
            chunks.close()
        finally:
            run.close()

    return iterate_in_context(
        _events(session_code, chunks, history, run, on_error), contextvars.copy_context(), close_unstarted
    )
