"""LLM Adapter 的协议与产品转换回归测试。"""

from __future__ import annotations

import json
import time
from unittest import TestCase

from apm_web.llm.adapter import adapt_trace
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
    def test_product_routing_uses_app_then_galileo_then_agentlens_then_default(
        self,
    ) -> None:
        span = agentlens_span()
        self.assertEqual(detect_product([span], "agent-test"), "agentlens")

        span["resource"]["telemetry.sdk.name"] = "galileo"
        self.assertEqual(detect_product([span], "agent-test"), "galileo")
        self.assertEqual(detect_product([span], "bkapp_ai_demo"), "bkaidev")

        span["resource"] = {"telemetry.sdk.name": "opentelemetry"}
        span["span_name"] = "chat demo-model"
        span["attributes"] = {"gen_ai.operation.name": "chat"}
        self.assertEqual(detect_product([span], "agent-test"), "default")

    def test_explicit_sdk_type_overrides_product_detection(self) -> None:
        span = agentlens_span()
        span["resource"]["telemetry.sdk.name"] = "galileo"

        trace = adapt_trace(
            [span],
            trace_id=TRACE_ID,
            app_name="bkapp_ai_demo",
            sdk_type="agentlens",
            include_content=True,
        )

        attributes = trace["spans"][0]["attributes"]
        self.assertEqual(attributes["gen_ai.input.messages"][0]["parts"][0]["content"], "secret prompt")

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

        trace = adapt_trace([span], trace_id=TRACE_ID, include_content=True)
        attributes = trace["spans"][0]["attributes"]

        self.assertEqual(attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(attributes["gen_ai.provider.name"], "openai")
        self.assertEqual(
            attributes["gen_ai.input.messages"][0]["parts"][0]["content"],
            "hello",
        )
        self.assertNotIn("gen_ai.system", attributes)
        self.assertNotIn("gen_ai.conversation.id", attributes)
        self.assertEqual(attributes["gen_ai.usage.input_tokens"], 0)
        self.assertNotIn("vendor.debug", attributes)

    def test_default_adapter_requires_explicit_operation(self) -> None:
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
                trace = adapt_trace([span], trace_id=TRACE_ID)
                self.assertEqual(trace["spans"], [])
                self.assertFalse(trace["classification"]["is_agent_trace"])

    def test_default_adapter_does_not_invent_tool_type(self) -> None:
        span = agentlens_span()
        span["span_name"] = "execute add"
        span["attributes"] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "add",
        }

        attributes = adapt_trace([span], trace_id=TRACE_ID)["spans"][0]["attributes"]

        self.assertNotIn("gen_ai.tool.type", attributes)

    def test_open_operation_is_preserved_and_status_is_not_inferred(self) -> None:
        span = agentlens_span()
        span["span_name"] = "vendor.operation"
        span["attributes"] = {"gen_ai.operation.name": "vendor.magic"}
        span["status"] = {"code": 1, "message": ""}

        attributes = adapt_trace([span], trace_id=TRACE_ID)["spans"][0]["attributes"]

        self.assertEqual(attributes["gen_ai.operation.name"], "vendor.magic")
        self.assertNotIn("gen_ai.response.status", attributes)

    def test_explicit_response_status_is_preserved(self) -> None:
        span = agentlens_span()
        span["attributes"]["gen_ai.response.status"] = "in_progress"
        attributes = adapt_trace([span], trace_id=TRACE_ID)["spans"][0]["attributes"]
        self.assertEqual(attributes["gen_ai.response.status"], "in_progress")

    def test_standard_span_does_not_expose_adapter_metadata(self) -> None:
        span = adapt_trace([agentlens_span()], trace_id=TRACE_ID)["spans"][0]
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

        trace = adapt_trace([span], trace_id=TRACE_ID)

        self.assertEqual(trace["spans"], [])
        self.assertFalse(trace["classification"]["is_gen_ai_trace"])

    def test_trace_without_agent_features_is_not_agent(self) -> None:
        span = agentlens_span()
        span["span_name"] = "GET /healthz"
        span["attributes"] = {"http.request.method": "GET"}
        trace = adapt_trace([span], trace_id=TRACE_ID)
        self.assertFalse(trace["classification"]["is_agent_trace"])
        self.assertFalse(trace["classification"]["has_decision_loop"])
        self.assertEqual(trace["spans"], [])

    def test_async_tool_poll_is_debuggable_but_not_a_conversation(self) -> None:
        trace_id = "e" * 32
        trace = adapt_trace([seedance_poll_span(trace_id=trace_id)], trace_id=trace_id)

        self.assertTrue(trace["classification"]["is_gen_ai_trace"])
        self.assertTrue(trace["classification"]["is_agent_trace"])
        self.assertFalse(trace["classification"]["is_conversation_trace"])
        step = trace["spans"][0]
        self.assertEqual(step["attributes"]["gen_ai.operation.name"], "execute_tool")
        self.assertNotIn("correlation", step)

    def test_llm_step_is_a_conversation(self) -> None:
        trace = adapt_trace([agentlens_span()], trace_id=TRACE_ID)
        self.assertTrue(trace["classification"]["is_conversation_trace"])

    def test_raw_debug_payload_preserves_values(self) -> None:
        span = agentlens_span()
        span["resource"].update(
            {
                "api_key": "resource-secret",
                "clientSecret": "visible-client-secret",
                "safe.resource": "visible",
            }
        )
        span["attributes"].update(
            {
                "http.request.header.authorization": "Bearer attribute-secret",
                "authorizationHeader": "visible-authorization-header",
                "passwordHash": "visible-password-hash",
                "token": "plain-token-secret",
                "client_token": "client-token-secret",
                "accessTokens": "visible-access-tokens",
                "gen_ai.usage.input_tokens": 10,
                "gen_ai.usage.output_tokens": 3,
                "http.request.headers": {
                    "cookie": "session=attribute-secret",
                    "x-request-id": "visible-request",
                },
            }
        )
        span["events"] = [
            {
                "name": "debug",
                "timestamp": span["start_time"],
                "attributes": {
                    "session_token": "event-secret",
                    "secretKey": "visible-secret-key",
                    "safe.event": "visible-event",
                },
            }
        ]

        trace = adapt_trace(
            [span],
            trace_id=TRACE_ID,
            include_content=True,
            include_raw=True,
        )
        raw = trace["raw_spans"][0]

        self.assertEqual(raw["resource"]["api_key"], "resource-secret")
        self.assertEqual(raw["resource"]["clientSecret"], "visible-client-secret")
        self.assertEqual(raw["attributes"]["http.request.header.authorization"], "Bearer attribute-secret")
        self.assertEqual(raw["attributes"]["token"], "plain-token-secret")
        self.assertEqual(raw["attributes"]["client_token"], "client-token-secret")
        self.assertEqual(raw["attributes"]["authorizationHeader"], "visible-authorization-header")
        self.assertEqual(raw["attributes"]["passwordHash"], "visible-password-hash")
        self.assertEqual(raw["attributes"]["accessTokens"], "visible-access-tokens")
        self.assertEqual(raw["attributes"]["http.request.headers"]["cookie"], "session=attribute-secret")
        self.assertEqual(raw["attributes"]["gen_ai.usage.input_tokens"], 10)
        self.assertEqual(raw["attributes"]["gen_ai.usage.output_tokens"], 3)
        self.assertEqual(raw["events"][0]["attributes"]["session_token"], "event-secret")
        self.assertEqual(raw["events"][0]["attributes"]["secretKey"], "visible-secret-key")
        serialized = json.dumps(raw)
        for value in (
            "resource-secret",
            "attribute-secret",
            "event-secret",
            "plain-token-secret",
            "client-token-secret",
        ):
            self.assertIn(value, serialized)
        self.assertIn("visible-request", serialized)
        self.assertIn("visible-event", serialized)

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

        trace = adapt_trace([span], trace_id=TRACE_ID, include_content=True)
        step = trace["spans"][0]

        self.assertEqual(step["span_id"], SPAN_ID)
        self.assertEqual(step["parent_span_id"], "c" * 16)
        self.assertEqual(step["trace_id"], TRACE_ID)
        self.assertEqual(step["resource"]["host.name"], "agent-host")
        self.assertEqual(step["resource"]["safe.resource"], "visible")
        self.assertEqual(step["resource"]["api_key"], "resource-secret")
        self.assertNotIn("events", step)

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

        trace = adapt_trace([span], trace_id=TRACE_ID, include_content=True)
        step = trace["spans"][0]

        self.assertEqual(step["attributes"]["gen_ai.operation.name"], "chat")
        self.assertNotIn("gen_ai.input.messages", step["attributes"])
        self.assertNotIn("gen_ai.output.messages", step["attributes"])
        self.assertNotIn("gen_ai.tool.call.arguments", step["attributes"])
        self.assertNotIn("gen_ai.tool.call.result", step["attributes"])

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

        trace = adapt_trace([span], trace_id=TRACE_ID, include_content=True, include_raw=True)
        step = trace["spans"][0]
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
        trace = adapt_trace([root], trace_id=TRACE_ID, include_content=True)
        attributes = trace["spans"][0]["attributes"]
        self.assertEqual(
            attributes["gen_ai.input.messages"][0]["parts"][0]["content"],
            "plain user question",
        )
        self.assertEqual(
            attributes["gen_ai.output.messages"][0]["parts"][0]["content"],
            "plain assistant answer",
        )
        self.assertEqual(trace["trace_io"]["source"], "reported")

        llm = agentlens_span()
        llm["attributes"]["gen_ai.response.time_to_first_chunk"] = 0.125
        llm_trace = adapt_trace([llm], trace_id=TRACE_ID)
        self.assertEqual(
            llm_trace["spans"][0]["attributes"]["gen_ai.response.time_to_first_chunk"],
            0.125,
        )

    def test_current_galileo_operations_flat_events_and_cache_alias(self) -> None:
        current_spans = (
            ("invocation", "invoke_agent", "invoke_agent"),
            ("agent_run [math_agent]", "invoke_agent", "invoke_agent"),
            ("call_llm", "chat", "chat"),
        )
        # invocation 与 agent_run 都是 invoke_agent；有真实父子关系时由 Trace 层合并。
        spans = []
        for index, (span_name, operation, _) in enumerate(current_spans, 1):
            span = {
                "trace_id": TRACE_ID,
                "span_id": f"{index:016x}",
                "span_name": span_name,
                "start_time": (NOW - 60) * 1_000_000 + index,
                "end_time": (NOW - 59) * 1_000_000 + index,
                "elapsed_time": 1_000_000,
                "status.code": 1,
                "resource.telemetry.sdk.name": "galileo",
                "attributes.gen_ai.operation.name": operation,
            }
            if span_name == "call_llm":
                span.update(
                    {
                        "attributes.gen_ai.usage.input_tokens": 5,
                        "attributes.gen_ai.usage.output_tokens": 2,
                        "attributes.gen_ai.usage.cache_read_input_tokens": 3,
                        "attributes.gen_ai.usage.cache_creation_input_tokens": 2,
                        "events.name": ["gen_ai.user.message", "gen_ai.choice"],
                        "events.timestamp": [1, 2],
                        "events.attributes.message.detail": [
                            '{"role":"user","content":"hello"}',
                            '{"finish_reason":"stop","message":{"role":"assistant","content":"hi"}}',
                        ],
                    }
                )
            spans.append(span)
        trace = adapt_trace(spans, trace_id=TRACE_ID, include_content=True)
        operations = {step["span_name"]: step["attributes"]["gen_ai.operation.name"] for step in trace["spans"]}
        self.assertEqual(
            operations,
            {span_name: expected for span_name, _, expected in current_spans},
        )
        llm = next(step for step in trace["spans"] if step["attributes"]["gen_ai.operation.name"] == "chat")
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

        attributes = adapt_trace([span], trace_id=TRACE_ID)["spans"][0]["attributes"]

        self.assertNotIn("gen_ai.request.stream", attributes)
        self.assertNotIn("gen_ai.response.time_to_first_chunk", attributes)
        self.assertNotIn("gen_ai.usage.cached.input_tokens", attributes)
        self.assertEqual(attributes["gen_ai.usage.reasoning.output_tokens"], 3)

    def test_agent_context_inheritance_is_limited_to_galileo_chat(self) -> None:
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

        trace = adapt_trace([parent, chat, tool], trace_id=TRACE_ID)
        spans = {span["span_id"]: span for span in trace["spans"]}

        self.assertEqual(
            spans[chat["span_id"]]["attributes"]["gen_ai.conversation.id"],
            "conversation-1",
        )
        self.assertEqual(spans[chat["span_id"]]["attributes"]["user.id"], "user-1")
        self.assertNotIn("gen_ai.conversation.id", spans[tool["span_id"]]["attributes"])
        self.assertNotIn("user.id", spans[tool["span_id"]]["attributes"])

        parent["resource"] = {"telemetry.sdk.name": "opentelemetry"}
        default_trace = adapt_trace([parent, chat], trace_id=TRACE_ID)
        default_chat = next(span for span in default_trace["spans"] if span["span_id"] == chat["span_id"])
        self.assertNotIn("gen_ai.conversation.id", default_chat["attributes"])
        self.assertNotIn("user.id", default_chat["attributes"])

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
        trace = adapt_trace(
            [business, traceloop, wrapper],
            trace_id=TRACE_ID,
            app_name="bkapp_ai0us0devops0us0agent_prod_3068",
            include_content=True,
        )
        self.assertEqual(trace["summary"]["llm_count"], 2)
        self.assertEqual(trace["summary"]["tool_count"], 0)
        self.assertEqual(trace["summary"]["total_tokens"], 10)
        self.assertEqual(trace["summary"]["span_count"], 2)
        self.assertEqual(
            {span["span_id"] for span in trace["spans"]},
            {"1" * 16, "2" * 16},
        )

    def test_bkaidev_still_deduplicates_documented_workflow_and_tool_pairs(
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

        trace = adapt_trace(
            [workflow, workflow_wrapper, tool, tool_wrapper],
            trace_id=TRACE_ID,
            app_name="bkapp_ai0us0devops0us0agent_prod_3068",
        )

        self.assertEqual(trace["summary"]["span_count"], 2)
        self.assertEqual(trace["summary"]["tool_count"], 1)
        self.assertEqual(
            {span["attributes"]["gen_ai.operation.name"] for span in trace["spans"]},
            {"invoke_workflow", "execute_tool"},
        )

    def test_bkaidev_agent_execution_uses_the_shared_dialect(self) -> None:
        span = agentlens_span()
        span["span_name"] = "agent.execution"
        span["attributes"] = {
            "agent.info.id": 3129,
            "agent.info.name": "进度管理",
            "agent.session.session_code": "session-1",
            "agent.status": "completed",
        }

        trace = adapt_trace(
            [span],
            trace_id=TRACE_ID,
            app_name="bkapp_ai0us0riot0us0pm_prod_2322",
        )

        self.assertEqual(trace["summary"]["span_count"], 1)
        self.assertTrue(trace["classification"]["is_agent_trace"])
        agent = trace["spans"][0]
        self.assertEqual(agent["attributes"]["gen_ai.operation.name"], "invoke_agent")
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

        trace = adapt_trace(
            [span],
            trace_id=TRACE_ID,
            app_name="bkapp_ai0us0devops0us0agent_prod_3068",
            include_content=True,
        )
        step = trace["spans"][0]
        inputs = step["attributes"]["gen_ai.input.messages"]
        output = step["attributes"]["gen_ai.output.messages"][0]

        self.assertEqual(step["attributes"]["gen_ai.usage.input_tokens"], 0)
        self.assertEqual(step["attributes"]["gen_ai.usage.output_tokens"], 0)
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
