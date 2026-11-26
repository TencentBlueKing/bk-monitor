"""Save public AG-UI events using the platform session-content write contract."""

import logging

logger = logging.getLogger("ai_whale")


class AguiSessionHistory:
    def __init__(self, api, session_code, *, username, turn_id):
        self.api = api
        self.session_code = session_code
        self.username = username
        self.turn_id = turn_id
        self.text = None
        self.tools = {}
        self.written = set()
        self.failed = False

    def _write(self, role, content, message_id, *, status="complete", **builtin):
        if message_id in self.written:
            return False
        # A timeout can occur after commit. Do not retry and duplicate a message.
        self.written.add(message_id)
        payload = {
            "session_code": self.session_code,
            "role": role,
            "content": content,
            "status": status,
            "property": {
                "turn_id": self.turn_id,
                "builtin_property": {"message_id": message_id, **builtin},
            },
        }
        try:
            response = self.api.create_chat_session_content(json=payload, headers={"X-BKAIDEV-USER": self.username})
            data = response.get("data") if isinstance(response, dict) else None
            if (
                not isinstance(response, dict)
                or response.get("result") is False
                or not isinstance(data, dict)
                or not data.get("id")
            ):
                raise ValueError("Session-content creation was not confirmed")
            stored = (data.get("property") or {}).get("builtin_property") or data
            if any(stored.get(key) != value for key, value in payload["property"]["builtin_property"].items()):
                raise ValueError("Session-content protocol fields were not retained")
            return True
        except Exception as error:
            self.failed = True
            logger.error("AG-UI history write unconfirmed, error_type=%s", type(error).__name__)
            return False

    def _flush_text(self, status="complete"):
        if self.text is None:
            return
        message_id, parts = self.text
        self.text = None
        if parts:
            self._write("assistant", "".join(parts), message_id, status=status, tool_calls=[])

    def _finish_tool(self, call_id, result, *, status="complete", duration=0):
        call = self.tools.pop(call_id, None)
        if call is None:
            return
        if not self._write("assistant", "", f"{call_id}:call", tool_calls=[call]):
            return
        self._write(
            "tool",
            result,
            call_id,
            status=status,
            tool_call_id=call_id,
            error=status == "error",
            additional_kwargs={"duration": duration},
        )

    def record(self, event):
        kind = event["type"]
        if kind == "TEXT_MESSAGE_START":
            self._flush_text()
            self.text = (event["messageId"], [])
        elif kind == "TEXT_MESSAGE_CONTENT" and self.text is not None:
            self.text[1].append(event["delta"])
        elif kind == "TEXT_MESSAGE_END":
            self._flush_text()
        elif kind == "TOOL_CALL_START":
            self._flush_text()
            call_id = event["toolCallId"]
            if call_id not in self.tools and call_id not in self.written:
                self.tools[call_id] = {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": event["toolCallName"], "arguments": ""},
                }
        elif kind == "TOOL_CALL_ARGS" and event["toolCallId"] in self.tools:
            self.tools[event["toolCallId"]]["function"]["arguments"] += event["delta"]
        elif kind == "TOOL_CALL_RESULT":
            self._finish_tool(
                event["toolCallId"],
                event["content"],
                status="error" if event.get("isError") else "complete",
                duration=event.get("duration", 0),
            )
        elif kind == "RUN_ERROR":
            self.finish(interrupted=True)
            self._write("assistant", event["message"], event["runId"], status="error", tool_calls=[])

    def finish(self, *, interrupted=False):
        self._flush_text("error" if interrupted else "complete")
        for call_id in list(self.tools):
            self._finish_tool(call_id, "工具执行结果未确认，请勿据此判断成功。", status="error")
