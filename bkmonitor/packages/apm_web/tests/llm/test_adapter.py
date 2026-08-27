"""LLM Adapter 的协议与产品转换回归测试。"""

from __future__ import annotations

import json
import time
from unittest import TestCase

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import detect_product

TRACE_ID = "a" * 32
SPAN_ID = "b" * 16
NOW = int(time.time())


def agentlens_span(span_id: str = SPAN_ID, *, start_time: int = NOW - 60) -> dict:
    """构造一个最小 AgentLens LLM Span，供多组契约测试复用。"""
    return {
        "trace_id": TRACE_ID,
        "span_id": span_id,
        "parent_span_id": "",
        "span_name": "openai.chat.LLM",
        "start_time": start_time * 1_000_000,
        "end_time": (start_time + 1) * 1_000_000,
        "elapsed_time": 1_000_000,
        "status": {"code": 1, "message": ""},
        "resource": {"service.name": "demo"},
        "attributes": {
            "gen_ai.span.kind": "LLM",
            "gen_ai.operation.name": "CHAT",
            "gen_ai.request.model": "demo-model",
            "gen_ai.response.model": "demo-model",
            "gen_ai.usage.input_tokens": 10,
            "gen_ai.usage.output_tokens": 3,
            "gen_ai.prompts.0.role": "user",
            "gen_ai.prompts.0.content": "secret prompt",
            "gen_ai.completion.0.role": "assistant",
            "gen_ai.completion.0.content": "secret response",
            "gen_ai.completion.0.finish_reason": "stop",
        },
        "events": [],
    }


def seedance_poll_span(span_id: str = "d" * 16, *, trace_id: str = "e" * 32) -> dict:
    """构造一个 Seedance 异步任务轮询 Span。"""
    span = agentlens_span(span_id)
    span.update(
        {
            "trace_id": trace_id,
            "span_name": "mcp.seedance_query_task/cgt-20260813153725-2zmxv",
            "resource": {
                "service.name": "gemini-for-claude-code",
                "telemetry.sdk.name": "opentelemetry",
            },
            "attributes": {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.system": "gemini-for-claude-code",
                "http.path": "/v1/mcp/seedance_query_task/cgt-20260813153725-2zmxv",
            },
            "events": [],
        }
    )
    return span


class AdapterTests(TestCase):
    def test_product_routing_uses_span_data(self) -> None:
        span = agentlens_span()
        self.assertEqual(detect_product([span]), "agentlens")

        span["resource"]["telemetry.sdk.name"] = "galileo"
        self.assertEqual(detect_product([span]), "galileo")

        span["resource"] = {"telemetry.sdk.name": "opentelemetry"}
        span["span_name"] = "agent.execution"
        span["attributes"] = {"agent.info.name": "demo"}
        self.assertEqual(detect_product([span]), "bkaidev")

        span["span_name"] = "chat demo-model"
        span["attributes"] = {"gen_ai.operation.name": "chat"}
        self.assertEqual(detect_product([span]), "default")

    def test_default_adapter_keeps_only_standard_fields(self) -> None:
        span = agentlens_span()
        span["span_name"] = "chat demo-model"
        span["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": "demo-model",
            "gen_ai.input.messages": '[{"role":"user","parts":[{"type":"text","content":"hello"}]}]',
            "gen_ai.system": "legacy-provider",
            "gen_ai.session_id": "legacy-session",
            "gen_ai.usage.prompt_tokens": 99,
            "vendor.debug": "drop-me",
        }

        attributes = adapt_spans([span])[0]["attributes"]

        self.assertEqual(attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(attributes["gen_ai.provider.name"], "openai")
        self.assertEqual(
            attributes["gen_ai.input.messages"][0]["parts"][0]["content"],
            "hello",
        )
        self.assertNotIn("gen_ai.system", attributes)
        self.assertNotIn("gen_ai.conversation.id", attributes)
        self.assertNotIn("gen_ai.usage.input_tokens", attributes)
        self.assertNotIn("gen_ai.usage.output_tokens", attributes)
        self.assertNotIn("vendor.debug", attributes)

    def test_default_adapter_keeps_standard_fields_without_operation(self) -> None:
        cases = {
            "gen_ai.agent.id": "agent-1",
            "gen_ai.agent.name": "math-agent",
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": "model-a",
            "gen_ai.response.model": "model-a",
            "gen_ai.tool.name": "add",
        }
        for index, (field, value) in enumerate(cases.items(), 1):
            with self.subTest(field=field):
                span = agentlens_span(f"{index:016x}")
                span["span_name"] = "generic-span"
                span["attributes"] = {field: value}
                spans = adapt_spans([span])
                self.assertEqual(len(spans), 1)
                self.assertEqual(spans[0]["attributes"], {field: value})

    def test_adapters_do_not_invent_tool_type(self) -> None:
        default = agentlens_span("1" * 16)
        default["span_name"] = "execute add"
        default["attributes"] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        agentlens = agentlens_span("2" * 16)
        agentlens["span_name"] = "add.TOOL"
        agentlens["attributes"] = {
            "gen_ai.span.kind": "TOOL",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        galileo = agentlens_span("3" * 16)
        galileo["span_name"] = "execute_tool"
        galileo["resource"]["telemetry.sdk.name"] = "galileo"
        galileo["attributes"] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        for product, span in (("default", default), ("agentlens", agentlens), ("galileo", galileo)):
            with self.subTest(product=product):
                self.assertNotIn("gen_ai.tool.type", adapt_spans([span])[0]["attributes"])

    def test_explicit_tool_type_is_preserved(self) -> None:
        span = agentlens_span()
        span["attributes"].update(
            {
                "gen_ai.span.kind": "TOOL",
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "knowledge",
                "gen_ai.tool.type": "datastore",
            }
        )

        self.assertEqual(adapt_spans([span])[0]["attributes"]["gen_ai.tool.type"], "datastore")

    def test_open_operation_is_preserved_and_status_is_not_inferred(self) -> None:
        span = agentlens_span()
        span["span_name"] = "vendor.operation"
        span["attributes"] = {"gen_ai.operation.name": "vendor.magic"}
        span["status"] = {"code": 1, "message": ""}

        attributes = adapt_spans([span])[0]["attributes"]

        self.assertEqual(attributes["gen_ai.operation.name"], "vendor.magic")
        self.assertNotIn("gen_ai.response.status", attributes)

    def test_explicit_response_status_is_preserved(self) -> None:
        span = agentlens_span()
        span["attributes"]["gen_ai.response.status"] = "in_progress"
        attributes = adapt_spans([span])[0]["attributes"]
        self.assertEqual(attributes["gen_ai.response.status"], "in_progress")

    def test_standard_span_does_not_expose_adapter_metadata(self) -> None:
        span = adapt_spans([agentlens_span()])[0]
        self.assertEqual(
            set(span),
            {
                "trace_id",
                "span_id",
                "parent_span_id",
                "span_name",
                "start_time",
                "end_time",
                "elapsed_time",
                "status",
                "resource",
                "attributes",
            },
        )

    def test_galileo_runtime_does_not_make_ordinary_rpc_an_ai_step(self) -> None:
        span = agentlens_span()
        span["span_name"] = "trpc.call"
        span["resource"]["telemetry.sdk.name"] = "galileo"
        span["attributes"] = {"rpc.system": "trpc"}
        span["events"] = [{"name": "SENT", "attributes": {"message.detail": "opaque-rpc-body"}}]

        self.assertEqual(adapt_spans([span]), [])

    def test_non_ai_span_is_dropped(self) -> None:
        span = agentlens_span()
        span["span_name"] = "GET /healthz"
        span["attributes"] = {"http.request.method": "GET"}
        self.assertEqual(adapt_spans([span]), [])

    def test_async_tool_poll_is_kept_as_tool(self) -> None:
        step = adapt_spans([seedance_poll_span()])[0]
        self.assertEqual(step["attributes"]["gen_ai.operation.name"], "execute_tool")
        self.assertNotIn("correlation", step)

    def test_standard_span_uses_standard_envelope_and_full_resource(self) -> None:
        span = agentlens_span()
        span["parent_span_id"] = "c" * 16
        span["resource"].update(
            {
                "host.name": "agent-host",
                "safe.resource": "visible",
                "api_key": "resource-secret",
            }
        )
        span["events"] = [
            {
                "name": "source-only-event",
                "timestamp": span["start_time"],
                "attributes": {"debug": "value"},
            }
        ]

        step = adapt_spans([span])[0]

        self.assertEqual(step["span_id"], SPAN_ID)
        self.assertEqual(step["parent_span_id"], "c" * 16)
        self.assertEqual(step["trace_id"], TRACE_ID)
        self.assertEqual(step["resource"]["host.name"], "agent-host")
        self.assertEqual(step["resource"]["safe.resource"], "visible")
        self.assertEqual(step["resource"]["api_key"], "resource-secret")
        self.assertNotIn("events", step)

    def test_filtered_parent_does_not_change_original_span_relationship(self) -> None:
        parent = agentlens_span("1" * 16)
        parent["span_name"] = "GET /healthz"
        parent["attributes"] = {"http.request.method": "GET"}
        child = agentlens_span("2" * 16)
        child["span_name"] = "chat"
        child["parent_span_id"] = parent["span_id"]
        child["attributes"] = {"gen_ai.operation.name": "chat"}

        spans = adapt_spans([parent, child])

        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["span_id"], child["span_id"])
        self.assertEqual(spans[0]["parent_span_id"], parent["span_id"])

    def test_galileo_events_without_detail_do_not_fabricate_standard_content(
        self,
    ) -> None:
        span = agentlens_span()
        span["span_name"] = "call_llm"
        span["resource"] = {"telemetry.sdk.name": "galileo"}
        span["attributes"] = {"gen_ai.operation.name": "chat"}
        span["events"] = [
            {"name": "gen_ai.user.message", "timestamp": 1, "attributes": {}},
            {"name": "gen_ai.choice", "timestamp": 2, "attributes": {}},
            {"name": "gen_ai.tool_call_args", "timestamp": 3, "attributes": {}},
            {"name": "gen_ai.tool_response", "timestamp": 4, "attributes": {}},
        ]

        step = adapt_spans([span])[0]

        self.assertEqual(step["attributes"]["gen_ai.operation.name"], "chat")
        self.assertNotIn("gen_ai.input.messages", step["attributes"])
        self.assertNotIn("gen_ai.output.messages", step["attributes"])
        self.assertNotIn("gen_ai.tool.call.arguments", step["attributes"])
        self.assertNotIn("gen_ai.tool.call.result", step["attributes"])

    def test_galileo_event_handlers_cover_all_supported_content(self) -> None:
        span = agentlens_span()
        span["span_name"] = "invocation"
        span["resource"] = {"telemetry.sdk.name": "galileo"}
        span["attributes"] = {"gen_ai.operation.name": "invoke_agent"}
        span["events"] = [
            {
                "name": "gen_ai.system.message",
                "attributes": {"message.detail": '"system prompt"'},
            },
            {
                "name": "gen_ai.user.message",
                "attributes": {"message.detail": json.dumps({"role": "user", "content": "user message"})},
            },
            {
                "name": "gen_ai.assistant.message",
                "attributes": {"message.detail": json.dumps({"role": "assistant", "content": "assistant message"})},
            },
            {
                "name": "gen_ai.tool.message",
                "attributes": {
                    "message.detail": json.dumps(
                        {
                            "role": "tool",
                            "content": {"result": 3},
                            "tool_call_id": "call-1",
                        }
                    )
                },
            },
            {
                "name": "gen_ai.invoke_agent_request",
                "attributes": {"message.detail": json.dumps([{"role": "user", "content": "agent request"}])},
            },
            {
                "name": "gen_ai.invoke_agent_response",
                "attributes": {"message.detail": json.dumps({"role": "assistant", "content": "agent response"})},
            },
            {
                "name": "gen_ai.tools",
                "attributes": {"message.detail": json.dumps([{"name": "add", "parameters": {"type": "OBJECT"}}])},
            },
            {
                "name": "gen_ai.tool_call_args",
                "attributes": {"message.detail": '{"a":1,"b":2}'},
            },
            {
                "name": "gen_ai.tool_response",
                "attributes": {"message.detail": '{"result":3}'},
            },
            {
                "name": "gen_ai.choice",
                "attributes": {"message.detail": '{"ignored":true}'},
            },
            {
                "name": "gen_ai.unknown",
                "attributes": {"message.detail": '{"ignored":true}'},
            },
        ]

        attributes = adapt_spans([span])[0]["attributes"]

        self.assertEqual(
            attributes["gen_ai.system_instructions"],
            [{"type": "text", "content": "system prompt"}],
        )
        self.assertEqual(
            [message["role"] for message in attributes["gen_ai.input.messages"]],
            ["user", "assistant", "tool", "user"],
        )
        self.assertEqual(
            attributes["gen_ai.output.messages"][0]["parts"][0]["content"],
            "agent response",
        )
        self.assertEqual(attributes["gen_ai.tool.definitions"][0]["name"], "add")
        self.assertEqual(
            attributes["gen_ai.tool.definitions"][0]["parameters"]["type"],
            "object",
        )
        self.assertEqual(attributes["gen_ai.tool.call.arguments"], {"a": 1, "b": 2})
        self.assertEqual(attributes["gen_ai.tool.call.result"], {"result": 3})

    def test_normalized_content_preserves_values(self) -> None:
        span = agentlens_span()
        span["span_name"] = "add.TOOL"
        span["attributes"] = {
            "gen_ai.span.kind": "TOOL",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
            "tool.input": json.dumps(
                {
                    "password": "normalized-leak",
                    "access_token": "token-leak",
                    "input_tokens": 42,
                }
            ),
            "tool.output": json.dumps({"secret_key": "result-leak", "value": "visible-result"}),
        }

        step = adapt_spans([span])[0]
        arguments = step["attributes"]["gen_ai.tool.call.arguments"]
        result = step["attributes"]["gen_ai.tool.call.result"]

        self.assertEqual(arguments["password"], "normalized-leak")
        self.assertEqual(arguments["access_token"], "token-leak")
        self.assertEqual(arguments["input_tokens"], 42)
        self.assertEqual(result["secret_key"], "result-leak")
        self.assertEqual(result["value"], "visible-result")
        self.assertNotIn("content_state", step)
        serialized = json.dumps(step)
        for value in ("normalized-leak", "token-leak", "result-leak"):
            self.assertIn(value, serialized)

    def test_agent_root_content_and_standard_ttfc_are_available_to_pages(self) -> None:
        root = agentlens_span()
        root["span_name"] = "math_agent.AGENT"
        root["attributes"] = {
            "gen_ai.span.kind": "AGENT",
            "input.value": "plain user question",
            "output.value": '"plain assistant answer"',
        }
        attributes = adapt_spans([root])[0]["attributes"]
        self.assertEqual(
            attributes["gen_ai.input.messages"][0]["parts"][0]["content"],
            "plain user question",
        )
        self.assertEqual(
            attributes["gen_ai.output.messages"][0]["parts"][0]["content"],
            "plain assistant answer",
        )
        llm = agentlens_span()
        llm["attributes"]["gen_ai.response.time_to_first_chunk"] = 0.125
        converted_llm = adapt_spans([llm])[0]
        self.assertEqual(
            converted_llm["attributes"]["gen_ai.response.time_to_first_chunk"],
            0.125,
        )

    def test_galileo_keeps_nested_agent_spans_and_normalizes_events(self) -> None:
        current_spans = (
            ("invocation", "invoke_agent", "invoke_agent"),
            ("agent_run [math_agent]", "invoke_agent", "invoke_agent"),
            ("call_llm", "chat", "chat"),
        )
        # invocation 与 agent_run 即使有真实父子关系也分别保留。
        spans = []
        for index, (span_name, operation, _) in enumerate(current_spans, 1):
            span = {
                "trace_id": TRACE_ID,
                "span_id": f"{index:016x}",
                "parent_span_id": "",
                "span_name": span_name,
                "start_time": (NOW - 60) * 1_000_000 + index,
                "end_time": (NOW - 59) * 1_000_000 + index,
                "elapsed_time": 1_000_000,
                "status": {"code": 1, "message": ""},
                "resource": {"telemetry.sdk.name": "galileo"},
                "attributes": {"gen_ai.operation.name": operation},
                "events": [],
            }
            if span_name.startswith("agent_run"):
                span["parent_span_id"] = f"{1:016x}"
            elif span_name == "call_llm":
                span["parent_span_id"] = f"{2:016x}"
            if span_name == "call_llm":
                span["attributes"].update(
                    {
                        "gen_ai.usage.input_tokens": 5,
                        "gen_ai.usage.output_tokens": 2,
                        "gen_ai.usage.cache_read_input_tokens": 3,
                        "gen_ai.usage.cache_creation_input_tokens": 2,
                    }
                )
                span["events"] = [
                    {
                        "name": "gen_ai.user.message",
                        "timestamp": 1,
                        "attributes": {"message.detail": '{"role":"user","content":"hello"}'},
                    },
                    {
                        "name": "gen_ai.choice",
                        "timestamp": 2,
                        "attributes": {
                            "message.detail": ('{"finish_reason":"stop","message":{"role":"assistant","content":"hi"}}')
                        },
                    },
                ]
            spans.append(span)
        converted = adapt_spans(spans)
        operations = {step["span_name"]: step["attributes"]["gen_ai.operation.name"] for step in converted}
        self.assertEqual(
            operations,
            {span_name: expected for span_name, _, expected in current_spans},
        )
        by_name = {step["span_name"]: step for step in converted}
        self.assertEqual(len(converted), 3)
        self.assertEqual(by_name["agent_run [math_agent]"]["parent_span_id"], f"{1:016x}")
        self.assertEqual(by_name["call_llm"]["parent_span_id"], f"{2:016x}")
        llm = next(step for step in converted if step["attributes"]["gen_ai.operation.name"] == "chat")
        self.assertEqual(llm["attributes"]["gen_ai.usage.cache_read.input_tokens"], 3)
        self.assertEqual(llm["attributes"]["gen_ai.usage.cache_creation.input_tokens"], 2)
        # 第一版明确丢弃 gen_ai.choice，不从它生成 output/finish_reason。
        self.assertNotIn("gen_ai.output.messages", llm["attributes"])
        self.assertNotIn("gen_ai.response.finish_reasons", llm["attributes"])

    def test_galileo_drops_stream_ttft_and_cached_alias(self) -> None:
        span = agentlens_span()
        span["span_name"] = "call_llm"
        span["resource"] = {"telemetry.sdk.name": "galileo"}
        span["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.is_stream": True,
            "gen_ai.server.time_to_first_token": 0.2,
            "gen_ai.usage.cached.input_tokens": 12,
            "gen_ai.usage.reasoning_tokens": 3,
        }

        attributes = adapt_spans([span])[0]["attributes"]

        self.assertNotIn("gen_ai.request.stream", attributes)
        self.assertNotIn("gen_ai.response.time_to_first_chunk", attributes)
        self.assertNotIn("gen_ai.usage.cached.input_tokens", attributes)
        self.assertEqual(attributes["gen_ai.usage.reasoning.output_tokens"], 3)

    def test_galileo_does_not_copy_request_model_to_response_model(self) -> None:
        span = agentlens_span()
        span["span_name"] = "call_llm"
        span["resource"] = {"telemetry.sdk.name": "galileo"}
        span["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "requested-model",
        }

        attributes = adapt_spans([span])[0]["attributes"]

        self.assertEqual(attributes["gen_ai.request.model"], "requested-model")
        self.assertNotIn("gen_ai.response.model", attributes)

        span["attributes"]["gen_ai.response.model"] = "actual-model"
        attributes = adapt_spans([span])[0]["attributes"]
        self.assertEqual(attributes["gen_ai.response.model"], "actual-model")

    def test_trace_does_not_copy_agent_context_between_spans(self) -> None:
        parent = agentlens_span("1" * 16)
        parent["span_name"] = "invoke_agent"
        parent["resource"] = {"telemetry.sdk.name": "galileo"}
        parent["attributes"] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.conversation.id": "conversation-1",
            "user.id": "user-1",
        }
        chat = agentlens_span("2" * 16)
        chat["parent_span_id"] = parent["span_id"]
        chat["span_name"] = "chat"
        chat["attributes"] = {"gen_ai.operation.name": "chat"}
        tool = agentlens_span("3" * 16)
        tool["parent_span_id"] = parent["span_id"]
        tool["span_name"] = "execute_tool"
        tool["attributes"] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        spans = {span["span_id"]: span for span in adapt_spans([parent, chat, tool])}

        self.assertNotIn("gen_ai.conversation.id", spans[chat["span_id"]]["attributes"])
        self.assertNotIn("user.id", spans[chat["span_id"]]["attributes"])
        self.assertNotIn("gen_ai.conversation.id", spans[tool["span_id"]]["attributes"])
        self.assertNotIn("user.id", spans[tool["span_id"]]["attributes"])

    def test_trace_does_not_backfill_tool_call_id(self) -> None:
        llm = agentlens_span("1" * 16)
        llm["span_name"] = "chat"
        llm["parent_span_id"] = "f" * 16
        llm["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": [
                {
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "tool_call",
                            "id": "call-1",
                            "name": "add",
                            "arguments": {"a": 1, "b": 2},
                        }
                    ],
                }
            ],
        }
        tool = agentlens_span("2" * 16)
        tool["span_name"] = "tool"
        tool["parent_span_id"] = "f" * 16
        tool["start_time"] = llm["start_time"] + 1
        tool["attributes"] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        converted = adapt_spans([llm, tool])
        converted_tool = next(span for span in converted if span["span_id"] == tool["span_id"])

        self.assertNotIn("gen_ai.tool.call.id", converted_tool["attributes"])

    def test_standard_message_parts_win_over_legacy_fields(self) -> None:
        span = agentlens_span()
        span["span_name"] = "chat"
        span["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": [
                {
                    "role": "assistant",
                    "content": "legacy text",
                    "parts": [
                        {
                            "type": "tool_call",
                            "id": "canonical-call",
                            "name": "canonical",
                            "arguments": {},
                        }
                    ],
                    "tool_calls": [
                        {
                            "id": "legacy-call",
                            "name": "legacy",
                            "arguments": {},
                        }
                    ],
                }
            ],
        }

        attributes = adapt_spans([span])[0]["attributes"]
        parts = attributes["gen_ai.output.messages"][0]["parts"]

        self.assertEqual(parts, [{"type": "tool_call", "id": "canonical-call", "name": "canonical", "arguments": {}}])

    def test_standard_system_instructions_win_over_dialect_sources(self) -> None:
        standard = [{"type": "text", "content": "standard"}]

        default = agentlens_span("1" * 16)
        default["span_name"] = "chat"
        default["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.system_instructions": standard,
            "gen_ai.input.messages": [{"role": "system", "parts": [{"type": "text", "content": "history"}]}],
        }

        agentlens = agentlens_span("2" * 16)
        agentlens["attributes"] = {
            "gen_ai.span.kind": "LLM",
            "gen_ai.operation.name": "chat",
            "gen_ai.system_instructions": standard,
            "gen_ai.prompts.0.role": "system",
            "gen_ai.prompts.0.content": "agentlens",
        }

        bkaidev = agentlens_span("3" * 16)
        bkaidev["span_name"] = "chat_model.generate"
        bkaidev["attributes"] = {
            "gen_ai.system_instructions": standard,
            "llm.input": '[{"type":"system","data":{"content":"bkaidev"}}]',
        }

        galileo = agentlens_span("4" * 16)
        galileo["span_name"] = "call_llm"
        galileo["resource"] = {"telemetry.sdk.name": "galileo"}
        galileo["attributes"] = {
            "gen_ai.operation.name": "chat",
            "gen_ai.system_instructions": standard,
        }
        galileo["events"] = [
            {
                "name": "gen_ai.system.message",
                "timestamp": 1,
                "attributes": {"message.detail": '"galileo"'},
            }
        ]

        for source in (default, agentlens, bkaidev, galileo):
            with self.subTest(span_name=source["span_name"]):
                attributes = adapt_spans([source])[0]["attributes"]
                self.assertEqual(attributes["gen_ai.system_instructions"], standard)

    def test_bkaidev_llm_spans_are_not_deduplicated(self) -> None:
        base = agentlens_span()
        business = {
            **base,
            "span_id": "1" * 16,
            "span_name": "chat_model.generate",
            "attributes": {
                "agent.info.name": "DevOpsAgent",
                "gen_ai.request.model": "model-a",
                "llm.input": '[{"role":"user","content":"hello"}]',
                "llm.output": '{"role":"assistant","content":"hi"}',
            },
        }
        traceloop = {
            **base,
            "span_id": "2" * 16,
            "span_name": "ChatModel.chat",
            "start_time": business["start_time"] + 1,
            "end_time": business["end_time"] + 1,
            "attributes": {
                "traceloop.span.kind": "LLM",
                "gen_ai.request.model": "model-a",
                "gen_ai.usage.prompt_tokens": 8,
                "gen_ai.usage.completion_tokens": 2,
            },
        }
        wrapper = {
            **base,
            "span_id": "3" * 16,
            "span_name": "model.task",
            "attributes": {"traceloop.span.kind": "TASK"},
        }
        spans = adapt_spans([business, traceloop, wrapper])
        self.assertEqual(len(spans), 2)
        self.assertEqual(
            {span["span_id"] for span in spans},
            {"1" * 16, "2" * 16},
        )

    def test_bkaidev_keeps_mappable_spans_without_type_classification(
        self,
    ) -> None:
        base = agentlens_span()
        workflow = {
            **base,
            "span_id": "1" * 16,
            "span_name": "chain.workflow",
            "attributes": {"agent.info.name": "DevOpsAgent"},
        }
        workflow_wrapper = {
            **base,
            "span_id": "2" * 16,
            "span_name": "LangGraph.workflow",
            "attributes": {"traceloop.span.kind": "workflow"},
        }
        tool = {
            **base,
            "span_id": "3" * 16,
            "span_name": "tool.execution",
            "attributes": {
                "agent.info.name": "DevOpsAgent",
                "tool.name": "add",
            },
        }
        tool_wrapper = {
            **base,
            "span_id": "4" * 16,
            "span_name": "create_ai_message_options.tool",
            "attributes": {
                "traceloop.span.kind": "tool",
                "traceloop.entity.name": "add",
            },
        }

        spans = adapt_spans([workflow, workflow_wrapper, tool, tool_wrapper])

        self.assertEqual(len(spans), 3)
        self.assertEqual(
            {span["span_id"] for span in spans},
            {"1" * 16, "3" * 16, "4" * 16},
        )
        for span in spans:
            self.assertNotIn("gen_ai.operation.name", span["attributes"])

    def test_bkaidev_maps_agent_fields_without_inventing_operation(self) -> None:
        span = agentlens_span()
        span["span_name"] = "agent.execution"
        span["attributes"] = {
            "agent.info.id": 3129,
            "agent.info.name": "进度管理",
            "agent.session.session_code": "session-1",
            "agent.status": "completed",
        }

        spans = adapt_spans([span])

        self.assertEqual(len(spans), 1)
        agent = spans[0]
        self.assertNotIn("gen_ai.operation.name", agent["attributes"])
        self.assertEqual(agent["attributes"]["gen_ai.agent.id"], "3129")
        self.assertEqual(agent["attributes"]["gen_ai.conversation.id"], "session-1")

    def test_bkaidev_langchain_message_envelope_is_flattened(self) -> None:
        span = agentlens_span()
        span["span_name"] = "chat_model.generate"
        span["attributes"] = {
            "agent.info.id": 3841,
            "agent.info.name": "DevOpsAgent",
            "gen_ai.request.model": "qwen3",
            "llm.input": json.dumps(
                [
                    {"type": "system", "data": {"content": "系统提示"}},
                    {"type": "human", "data": {"content": "查询主机"}},
                    {
                        "type": "ai",
                        "data": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "name": "list_hosts",
                                    "args": {"limit": 8},
                                    "id": "call-1",
                                }
                            ],
                        },
                    },
                    {
                        "type": "tool",
                        "data": {
                            "content": '{"count": 8}',
                            "tool_call_id": "call-1",
                        },
                    },
                ],
                ensure_ascii=False,
            ),
            "llm.output": json.dumps(
                [
                    {
                        "role": "ChatGeneration",
                        "content": "共查询到 8 台主机。",
                        "tool_call": [],
                    }
                ],
                ensure_ascii=False,
            ),
        }

        spans = adapt_spans([span])
        step = spans[0]
        inputs = step["attributes"]["gen_ai.input.messages"]
        output = step["attributes"]["gen_ai.output.messages"][0]

        self.assertNotIn("gen_ai.usage.input_tokens", step["attributes"])
        self.assertNotIn("gen_ai.usage.output_tokens", step["attributes"])
        self.assertEqual(
            [message["role"] for message in inputs],
            ["user", "assistant", "tool"],
        )
        self.assertEqual(
            step["attributes"]["gen_ai.system_instructions"][0]["content"],
            "系统提示",
        )
        self.assertEqual(inputs[0]["parts"][0]["content"], "查询主机")
        self.assertEqual(inputs[1]["parts"][0]["type"], "tool_call")
        self.assertEqual(inputs[1]["parts"][0]["arguments"], {"limit": 8})
        self.assertEqual(inputs[2]["parts"][0]["type"], "tool_call_response")
        self.assertEqual(output["role"], "assistant")
        self.assertEqual(output["parts"][0]["content"], "共查询到 8 台主机。")
        self.assertNotIn("finish_reason", output)
        self.assertNotIn("gen_ai.response.finish_reasons", step["attributes"])
