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
        node = self.request()["traces"][0]["flow"][0]
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
        node = self.request()["traces"][0]["flow"][0]
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
            self.assertEqual(self.request()["traces"][0]["flow"][0]["input"], expected)
        attrs["gen_ai.input.messages"] = []
        self.assertEqual(self.request()["traces"][0]["flow"][0]["input"], "system")
        attrs.pop("gen_ai.system_instructions")
        attrs["gen_ai.tool.definitions"] = [{"name": "not a prompt"}]
        self.assertEqual(self.request()["traces"][0]["flow"][0]["input"], "")
        attrs["gen_ai.output.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "reasoning", "content": "reason"},
                    {"type": "tool_call", "name": "lookup", "arguments": {}},
                ],
            }
        ]
        self.assertEqual(self.request()["traces"][0]["flow"][0]["output"], "reason")

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
