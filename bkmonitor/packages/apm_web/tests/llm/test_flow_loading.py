"""执行线渐进加载与大正文预览回归。"""

import json
from unittest import TestCase, mock

from django.test import override_settings

from apm_web.llm.adapter.utils import CONTENT_FIELDS
from apm_web.llm.resources import ListFlowsResource


class FlowLoadingTests(TestCase):
    def setUp(self):
        self.enterContext(override_settings(LLM_BIZ_LIST=[11]))
        self.topology = mock.Mock(service_names=["agent-service"])
        self.topology.get_system.return_value = {"is_support_llm": True, "product": "default"}
        self.enterContext(mock.patch("apm_web.llm.resources.EntitySet", return_value=self.topology))
        self.enterContext(mock.patch("apm_web.llm.resources.Application.objects.get"))
        self.query = mock.Mock()
        self.enterContext(mock.patch("apm_web.llm.resources.get_query", return_value=self.query))
        self.source = {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "parent_span_id": "",
            "span_name": "chat",
            "start_time": 1,
            "end_time": 2,
            "elapsed_time": 1,
            "status": {"code": 1},
            "resource": {"service.name": "agent-service"},
            "attributes": {
                "gen_ai.operation.name": "chat",
                "gen_ai.conversation.id": "conversation-1",
                "user.id": "alice",
                "gen_ai.usage.input_tokens": 37,
                "gen_ai.usage.output_tokens": 9,
                "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "问题"}]}],
                "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "回答"}]}],
            },
        }
        self.query.query_by_group_ids.side_effect = lambda **kwargs: [self.source]

    def request(self, **parameters):
        return ListFlowsResource().request(
            {"bk_biz_id": 11, "app_name": "demo", "group_field": "trace_id", "group_id": "trace-1", **parameters}
        )

    def test_default_and_explicit_full_mode_preserve_complete_content(self):
        content = "完整正文" * 1000
        messages = [{"role": "user", "parts": [{"type": "text", "content": content}]}]
        self.source["attributes"]["gen_ai.input.messages"] = messages
        self.source["attributes"]["gen_ai.system_instructions"] = [{"type": "text", "content": content}]
        for parameters in ({}, {"include_input_output": True, "input_output_preview": False}):
            with self.subTest(parameters=parameters):
                node = self.request(**parameters)["traces"][0]["flow"][0]
                self.assertEqual(node["attributes"]["gen_ai.input.messages"], messages)
                self.assertEqual(
                    node["attributes"]["gen_ai.system_instructions"], [{"type": "text", "content": content}]
                )
                self.assertFalse(self.query.query_by_group_ids.call_args.kwargs["fields"])

    def test_structure_omits_content_but_preserves_metadata_and_statistics(self):
        result = self.request(include_input_output=False)
        fields = self.query.query_by_group_ids.call_args.kwargs["fields"]
        self.assertIn("attributes.gen_ai.usage.input_tokens", fields)
        self.assertNotIn("attributes", fields)
        self.assertNotIn("attributes.gen_ai.input.messages", fields)
        trace = result["traces"][0]
        self.assertEqual((trace["input_tokens"], trace["output_tokens"]), (37, 9))
        self.assertEqual((trace["conversation_id"], trace["user_id"]), ("conversation-1", "alice"))
        self.assertEqual(trace["input"], "")
        self.assertFalse(set(trace["flow"][0]["attributes"]) & set(CONTENT_FIELDS))
        self.assertIn("gen_ai.input.messages", self.source["attributes"])

    def test_default_full_mode_preserves_tool_arguments_and_results(self):
        arguments = {"path": "a" * 1000, "nested": {"limit": 20}}
        result = [{"data": "b" * 1000}, {"data": "second"}]
        self.source["attributes"].update(
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.call.arguments": arguments,
                "gen_ai.tool.call.result": result,
            }
        )
        node = self.request()["traces"][0]["flow"][0]
        self.assertEqual(node["attributes"]["gen_ai.tool.call.arguments"], arguments)
        self.assertEqual(node["attributes"]["gen_ai.tool.call.result"], result)

    def test_structure_mode_takes_precedence_over_preview(self):
        result = self.request(include_input_output=False, input_output_preview=True)
        node = result["traces"][0]["flow"][0]
        self.assertFalse(set(node["attributes"]) & set(CONTENT_FIELDS))
        self.assertNotIn("input", node)
        self.assertNotIn("output", node)

    def test_latest_user_and_model_text_are_selected_after_normalization(self):
        self.source["attributes"]["gen_ai.input.messages"] = json.dumps(
            [
                {"role": "user", "parts": [{"type": "text", "content": "old" * 100_000}]},
                {"role": "user", "parts": [{"type": "text", "content": "最新🦋" * 300}]},
                {"role": "assistant", "parts": [{"type": "text", "content": "later assistant"}]},
            ],
            ensure_ascii=False,
        )
        self.source["attributes"]["gen_ai.output.messages"] = [
            {"role": "assistant", "parts": [{"type": "text", "content": "old"}]},
            {
                "role": "assistant",
                "parts": [
                    {"type": "text", "content": "answer" * 100},
                    {"type": "thinking", "thinking": "thought"},
                    {"type": "tool_call", "name": "lookup", "arguments": {}},
                ],
            },
        ]
        node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
        self.assertEqual(node["input"], ("最新🦋" * 300)[:255])
        self.assertEqual(node["output"], ("answer" * 100)[:255])
        self.assertFalse(set(node["attributes"]) & set(CONTENT_FIELDS))

    def test_tool_dictionary_and_first_list_item_keep_kv_shape(self):
        self.source["attributes"].update(
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.call.arguments": [{"path": "a" * 1000, "limit": 20}, {"ignored": "second"}],
                "gen_ai.tool.call.result": [[{"ok": True, "data": "b" * 1000}]],
            }
        )
        node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
        self.assertEqual(node["input"], {"path": "a" * 255, "limit": "20"})
        self.assertEqual(node["output"], {"ok": "true", "data": "b" * 255})

    def test_input_priority_and_output_fallbacks(self):
        attrs = self.source["attributes"]
        attrs["gen_ai.system_instructions"] = [{"type": "text", "content": "system"}]
        for role, part, expected in [
            ("assistant", {"type": "text", "content": "model"}, "model"),
            ("tool", {"type": "tool_call_response", "response": "result"}, "result"),
        ]:
            attrs["gen_ai.input.messages"] = [{"role": role, "parts": [part]}]
            self.assertEqual(self.request(input_output_preview=True)["traces"][0]["flow"][0]["input"], expected)
        attrs["gen_ai.input.messages"] = []
        self.assertEqual(self.request(input_output_preview=True)["traces"][0]["flow"][0]["input"], "system")
        attrs.pop("gen_ai.system_instructions")
        attrs["gen_ai.tool.definitions"] = [{"name": "not a prompt"}]
        self.assertEqual(self.request(input_output_preview=True)["traces"][0]["flow"][0]["input"], "")
        attrs["gen_ai.output.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "reasoning", "content": "reason"},
                    {"type": "tool_call", "name": "lookup", "arguments": {}},
                ],
            }
        ]
        self.assertEqual(self.request(input_output_preview=True)["traces"][0]["flow"][0]["output"], "reason")

    def test_model_preview_keeps_latest_tool_batch_without_changing_trace_summary(self):
        messages = [
            {"role": "user", "parts": [{"type": "text", "content": "继续"}]},
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "id": "first", "name": "functions.exec", "arguments": {"cmd": "first"}},
                    {"type": "tool_call", "id": "second", "name": "lookup", "arguments": {"cmd": "second"}},
                ],
            },
            {
                "role": "tool",
                "parts": [{"type": "tool_call_response", "id": "first", "response": {"text": "a" * 1000}}],
            },
            {"role": "tool", "parts": [{"type": "tool_call_response", "id": "second", "response": {"text": "second"}}]},
        ]
        self.source["attributes"]["gen_ai.input.messages"] = messages
        full = self.request()["traces"][0]
        result = self.request(input_output_preview=True)["traces"][0]
        node = result["flow"][0]
        self.assertEqual(
            node["input_preview"],
            {
                "source": "tool",
                "tools": [
                    {"tool_name": "functions.exec", "value": '{"text":"' + "a" * 246 + "…"},
                    {"tool_name": "lookup", "value": '{"text":"second"}'},
                ],
            },
        )
        self.assertEqual(node["input"], "继续")
        self.assertEqual(result["input"], full["input"])
        self.assertEqual(result["output"], full["output"])
        self.assertNotIn("input_preview", full["flow"][0])
        self.assertEqual(self.source["attributes"]["gen_ai.input.messages"], messages)

    def test_new_user_message_replaces_tool_context_and_ignores_empty_trailing_messages(self):
        self.source["attributes"]["gen_ai.input.messages"].extend(
            [
                {"role": "tool", "parts": [{"type": "tool_call_response", "response": "old tool result"}]},
                {"role": "user", "parts": [{"type": "text", "content": "新的要求"}]},
                {"role": "assistant", "parts": [{"type": "text", "content": "  "}]},
            ]
        )
        node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
        self.assertEqual(node["input_preview"], {"source": "user", "value": "新的要求"})

    def test_model_tool_result_json_uses_compact_text_and_arrays_remain_one_tool(self):
        result = {"text": "a\nb", "count": 2}
        for response, expected in (
            (result, '{"text":"a\\nb","count":2}'),
            (json.dumps(result), '{"text":"a\\nb","count":2}'),
            (json.dumps([result, {"other": "second"}]), '[{"text":"a\\nb","count":2},{"other":"second"}]'),
            ([result], '[{"text":"a\\nb","count":2}]'),
        ):
            with self.subTest(response=response):
                self.source["attributes"]["gen_ai.input.messages"] = [
                    {
                        "role": "tool",
                        "name": "functions.exec",
                        "parts": [{"type": "tool_call_response", "response": response}],
                    }
                ]
                node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
                self.assertEqual(
                    node["input_preview"],
                    {"source": "tool", "tools": [{"tool_name": "functions.exec", "value": expected}]},
                )

    def test_model_tool_plain_text_does_not_gain_an_artificial_value_key(self):
        for response in ("plain text", '{"invalid":', "123"):
            with self.subTest(response=response):
                self.source["attributes"]["gen_ai.input.messages"] = [
                    {"role": "tool", "parts": [{"type": "tool_call_response", "response": response}]}
                ]
                node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
                self.assertEqual(
                    node["input_preview"], {"source": "tool", "tools": [{"tool_name": "", "value": response}]}
                )

    def test_non_tool_json_text_keeps_its_original_representation(self):
        content = '{"literal":"text"}'
        for role in ("user", "assistant"):
            with self.subTest(role=role):
                self.source["attributes"]["gen_ai.input.messages"] = [
                    {"role": role, "parts": [{"type": "text", "content": content}]}
                ]
                node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
                self.assertEqual(node["input_preview"], {"source": role, "value": content})

    def test_model_tool_output_preserves_all_calls_as_bounded_json(self):
        self.source["attributes"]["gen_ai.output.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "text", "content": "开始调用"},
                    {"type": "tool_call", "name": "functions.exec", "arguments": {"value": "x" * 1000, "count": 2}},
                    {"type": "tool_call", "name": "second", "arguments": {"ignored": True}},
                ],
            }
        ]
        node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
        self.assertEqual(
            node["output_preview"],
            {
                "source": "tool",
                "tools": [
                    {"tool_name": "functions.exec", "value": '{"value":"' + "x" * 245 + "…"},
                    {"tool_name": "second", "value": '{"ignored":true}'},
                ],
            },
        )

    def test_tool_result_without_matching_call_keeps_name_unknown_and_preserves_array(self):
        self.source["attributes"]["gen_ai.input.messages"].append(
            {
                "role": "tool",
                "parts": [
                    {"type": "tool_call_response", "id": "missing", "response": [{"text": "first"}, {"text": "second"}]}
                ],
            }
        )
        node = self.request(input_output_preview=True)["traces"][0]["flow"][0]
        self.assertEqual(
            node["input_preview"],
            {
                "source": "tool",
                "tools": [{"tool_name": "", "value": '[{"text":"first"},{"text":"second"}]'}],
            },
        )

    def test_agent_preview_and_summary_keep_existing_selection(self):
        self.source["attributes"]["gen_ai.operation.name"] = "invoke_agent"
        self.source["attributes"]["gen_ai.input.messages"].append(
            {"role": "tool", "parts": [{"type": "tool_call_response", "response": {"text": "tool result"}}]}
        )
        result = self.request(input_output_preview=True)["traces"][0]
        node = result["flow"][0]
        self.assertEqual(node["input"], "问题")
        self.assertEqual(result["input"], "问题")
        self.assertNotIn("input_preview", node)
        self.assertNotIn("output_preview", node)

    def test_model_preview_stops_at_the_latest_batch_and_keeps_repeated_tool_names(self):
        from apm_web.llm.builders.preview import model_message_preview

        messages = [
            {"role": "tool", "name": "old", "parts": [{"type": "tool_call_response", "response": "old"}]},
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "id": "one", "name": "exec", "arguments": {}},
                    {"type": "tool_call", "id": "two", "name": "exec", "arguments": {}},
                ],
            },
            {
                "role": "tool",
                "parts": [
                    {"type": "tool_call_response", "id": "two", "response": "second completed first"},
                    {"type": "tool_result", "id": "one", "result": "first completed second"},
                ],
            },
            {"role": "assistant", "parts": [{"type": "text", "content": " "}]},
        ]
        self.assertEqual(
            model_message_preview(messages),
            {
                "source": "tool",
                "tools": [
                    {"tool_name": "exec", "value": "second completed first"},
                    {"tool_name": "exec", "value": "first completed second"},
                ],
            },
        )
        messages.append({"role": "assistant", "parts": [{"type": "text", "content": "done"}]})
        self.assertEqual(model_message_preview(messages), {"source": "assistant", "value": "done"})

    def test_model_preview_does_not_merge_tools_across_intervening_text(self):
        from apm_web.llm.builders.preview import model_message_preview

        self.assertEqual(
            model_message_preview(
                [
                    {
                        "role": "assistant",
                        "parts": [
                            {"type": "tool_call", "name": "old", "arguments": {}},
                            {"type": "text", "content": "new batch"},
                            {"type": "tool_call", "name": "latest", "arguments": {"count": 2}},
                        ],
                    }
                ]
            ),
            {"source": "tool", "tools": [{"tool_name": "latest", "value": '{"count":2}'}]},
        )
        self.assertEqual(
            model_message_preview(
                [
                    {"role": "tool", "name": "old", "parts": [{"type": "tool_result", "result": "old"}]},
                    {
                        "role": "tool",
                        "parts": [
                            {"type": "text", "content": "new batch"},
                            {"type": "tool_result", "name": "latest", "result": {"count": 2}},
                        ],
                    },
                ]
            ),
            {"source": "tool", "tools": [{"tool_name": "latest", "value": '{"count":2}'}]},
        )

    def test_all_products_project_metadata_without_indexed_messages(self):
        from constants.apm import LLMProduct

        for product in LLMProduct:
            with self.subTest(product=product):
                self.topology.get_system.return_value = {"is_support_llm": True, "product": product.value}
                self.query.query_by_group_ids.reset_mock()
                self.request(include_input_output=False)
                self.query.query_by_group_ids.assert_called_once()
                fields = self.query.query_by_group_ids.call_args.kwargs["fields"]
                self.assertTrue(fields)
                self.assertNotIn("attributes", fields)
                self.assertNotIn("attributes.gen_ai.input.messages", fields)
                self.assertNotIn("attributes.gen_ai.prompts.0.content", fields)

    def test_indexed_messages_use_adapter_and_raw_content_is_released(self):
        from apm_web.llm.builders.preview import prepare_flow_spans

        self.topology.get_system.return_value = {"is_support_llm": True, "product": "agentlens"}
        self.source["attributes"] = {
            "gen_ai.span.kind": "LLM",
            "gen_ai.usage.input_tokens": 37,
            "gen_ai.prompts.0.role": "user",
            "gen_ai.prompts.0.content": "old",
            "gen_ai.prompts.1.role": "user",
            "gen_ai.prompts.1.content": "new",
        }
        sources = [self.source.copy()]
        spans = prepare_flow_spans(sources, self.topology, include_input_output=True, preview=True)
        self.assertEqual(spans[0]["input"], "new")
        self.assertEqual(spans[0]["attributes"]["gen_ai.usage.input_tokens"], 37)
        self.assertFalse(set(spans[0]["attributes"]) & set(CONTENT_FIELDS))
        self.assertNotIn("attributes", sources[0])

    def test_product_projection_preserves_type_and_token_aliases(self):
        from apm_web.llm.adapter import adapt_spans
        from apm_web.llm.adapter.fields import flow_query_fields
        from apm_web.llm.builders.preview import prepare_flow_spans
        from constants.apm import LLMProduct

        products = {
            LLMProduct.DEFAULT.value: {
                "gen_ai.operation.name": "chat",
                "gen_ai.usage.input_tokens": 10,
            },
            LLMProduct.AGENTLENS.value: {
                "gen_ai.span.kind": "LLM",
                "gen_ai.usage.input_tokens": 10,
                "gen_ai.prompts.0.role": "user",
                "gen_ai.prompts.0.content": "question",
            },
            LLMProduct.AIDEV.value: {
                "llm.request.type": "chat",
                "gen_ai.usage.prompt_tokens": 10,
                "gen_ai.usage.completion_tokens": 3,
                "gen_ai.usage.cache_creation_input_tokens": 5,
                "llm.input": "question",
            },
            LLMProduct.GALILEO.value: {
                "gen_ai.operation.name": "chat",
                "gen_ai.usage.input_tokens": 10,
                "gen_ai.usage.cache_creation.input_tokens": 5,
            },
            LLMProduct.LANGFUSE.value: {
                "langfuse.observation.type": "generation",
                "langfuse.observation.usage_details": '{"input":10,"output":3}',
                "langfuse.observation.input": "question",
            },
        }
        for product, attributes in products.items():
            with self.subTest(product=product):
                self.topology.get_system.return_value = {"is_support_llm": True, "product": product}
                source = {**self.source, "attributes": attributes, "events": []}
                expected = adapt_spans([source], self.topology)[0]
                fields = flow_query_fields(False, products=(product,))
                projected = {
                    **source,
                    "attributes": {key: value for key, value in attributes.items() if f"attributes.{key}" in fields},
                }
                result = prepare_flow_spans([projected], self.topology, include_input_output=False, preview=True)[0]
                self.assertEqual(result["span_type"], expected["span_type"])
                for key, value in expected["attributes"].items():
                    if key.startswith("gen_ai.usage."):
                        self.assertEqual(result["attributes"][key], value)

    def test_indexed_preview_projection_keeps_messages_and_omits_unrelated_attributes(self):
        from fnmatch import fnmatchcase

        from apm_web.llm.adapter.fields import flow_query_fields
        from apm_web.llm.builders.preview import prepare_flow_spans

        self.topology.get_system.return_value = {"is_support_llm": True, "product": "agentlens"}
        source = {
            **self.source,
            "attributes": {
                "gen_ai.span.kind": "LLM",
                "gen_ai.usage.input_tokens": 37,
                "gen_ai.prompts.0.role": "user",
                "gen_ai.prompts.0.content": "old",
                "gen_ai.prompts.1.role": "user",
                "gen_ai.prompts.1.content": "new",
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "answer",
                "large.unrelated": "x" * 100_000,
            },
        }
        fields = flow_query_fields(True, True, products=("agentlens",))
        self.assertNotIn("attributes", fields)
        self.assertNotIn("events", fields)
        projected = {
            **source,
            "attributes": {
                key: value
                for key, value in source["attributes"].items()
                if any(fnmatchcase(f"attributes.{key}", field) for field in fields)
            },
        }
        self.assertNotIn("large.unrelated", projected["attributes"])
        span = prepare_flow_spans([projected], self.topology, include_input_output=True, preview=True)[0]
        self.assertEqual((span["input"], span["output"]), ("new", "answer"))

    def test_each_parsed_message_list_is_released_before_next_span_is_adapted(self):
        import weakref

        from apm_web.llm.adapter import adapt_spans
        from apm_web.llm.builders.preview import prepare_flow_spans

        class Messages(list):
            pass

        sources = [
            {
                **self.source,
                "span_id": str(index),
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.input.messages": Messages(
                        [{"role": "user", "parts": [{"type": "text", "content": "x" * 100_000}]}]
                    ),
                },
            }
            for index in range(2)
        ]
        first_messages = weakref.ref(sources[0]["attributes"]["gen_ai.input.messages"])
        calls = 0

        def adapt(raw, topology):
            nonlocal calls
            if calls:
                self.assertIsNone(first_messages())
            calls += 1
            return adapt_spans(raw, topology)

        with mock.patch("apm_web.llm.builders.preview.adapt_spans", new=adapt):
            spans = prepare_flow_spans(sources, self.topology, include_input_output=True, preview=True)
        self.assertIsNone(first_messages())
        self.assertEqual(len(spans), 2)
        self.assertEqual(len(spans[0]["input"]), 255)
