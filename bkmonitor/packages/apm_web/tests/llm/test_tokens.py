"""正文估算、用量校准与跨 Trace 合并契约。"""

from __future__ import annotations

from copy import deepcopy
from unittest import TestCase, mock

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.utils import repair_truncated_json
from apm_web.llm.tokens import TokenCounter, build_token_matrix, load_encoding
from apm_web.tests.llm.test_detail import entity_set, raw_span


def model_span(span_id="model-1", trace_id="trace-1", **usage):
    span = raw_span(span_id, "chat")
    span.update(trace_id=trace_id, span_type="LLM")
    span["attributes"].update(
        {
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.system_instructions": [{"type": "text", "content": "hello"}],
            "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "hello"}]}],
            "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "hello"}]}],
            **{f"gen_ai.usage.{key}": value for key, value in usage.items()},
        }
    )
    return span


def leaves(node):
    if not node["children"]:
        return {node["key"]: node["tokens"]}
    return {key: value for child in node["children"] for key, value in leaves(child).items()}


class TokenMatrixTests(TestCase):
    def test_known_tokenizers_and_special_tokens_are_literal_content(self):
        self.assertEqual(TokenCounter("gpt-4o").encoding.name, "o200k_base")
        self.assertEqual(TokenCounter("unknown-model").encoding.name, "cl100k_base")
        self.assertEqual(TokenCounter("gpt-4o").count("hello"), 1)
        self.assertGreater(TokenCounter("gpt-4o").count("<|endoftext|>"), 0)

    def test_bundled_encodings_match_official_tokens_without_network(self):
        load_encoding.cache_clear()
        with (
            mock.patch("tiktoken.load.read_file", side_effect=AssertionError("no vocabulary download")),
            mock.patch.dict("os.environ", {"TIKTOKEN_CACHE_DIR": ""}),
        ):
            for model, expected in (
                ("unknown-model", [57668, 53901, 3922, 14957, 0]),
                ("gpt-4o", [177519, 979, 24169, 0]),
            ):
                self.assertEqual(TokenCounter(model).encoding.encode_ordinary("你好，world!"), expected)

    def test_reported_total_calibrates_up_and_down_and_matches_sections(self):
        for reported in (0, 1, 3, 100):
            with self.subTest(reported=reported):
                span = model_span(input_tokens=reported, output_tokens=7)
                source = deepcopy(span["attributes"])
                matrix = build_token_matrix([span])
                input_node, output_node = matrix["nodes"]
                self.assertEqual(input_node["tokens"], reported)
                self.assertEqual(sum(leaves(input_node).values()), reported)
                self.assertEqual(input_node["estimate_ratio"], 2 / reported if reported else None)
                sections = span["token_categories"]
                self.assertTrue(all(set(section) == {"key", "label", "tokens"} for section in sections))
                self.assertEqual(sum(item["tokens"] for item in sections[:3]), reported)
                self.assertEqual(sections[3]["tokens"], output_node["tokens"])
                self.assertEqual(span["attributes"], source)
                self.assertNotIn("estimated_token_fields", span)

    def test_missing_usage_is_filled_once_without_overwriting_reported_zero(self):
        span = model_span(output_tokens=0)
        matrix = build_token_matrix([span])
        self.assertEqual(span["attributes"]["gen_ai.usage.input_tokens"], 2)
        self.assertEqual(span["estimated_token_fields"], ["input_tokens"])
        self.assertEqual(matrix["nodes"][0]["tokens"], 2)
        self.assertIsNone(matrix["nodes"][0]["estimate_ratio"])
        self.assertEqual(matrix, build_token_matrix([span]))
        self.assertEqual(span["attributes"]["gen_ai.usage.output_tokens"], 0)

    def test_output_tool_calls_are_content_and_hidden_reasoning_uses_reported_usage(self):
        span = model_span(input_tokens=10, output_tokens=20, **{"reasoning.output_tokens": 15})
        span["attributes"]["gen_ai.output.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "name": "search", "arguments": {"query": "hello"}},
                ],
            }
        ]
        matrix = build_token_matrix([span])
        self.assertEqual(leaves(matrix["nodes"][1]), {"content": 5, "reasoning": 15})
        self.assertEqual(span["token_categories"][3]["tokens"], 20)
        self.assertEqual(set(span["token_categories"][3]), {"key", "label", "tokens"})
        self.assertEqual(matrix["tools"], [])

    def test_missing_reasoning_usage_uses_visible_text_and_scales_with_content(self):
        span = model_span(output_tokens=9)
        span["attributes"]["gen_ai.output.messages"][0]["parts"].append({"type": "reasoning", "content": "hello"})
        output = build_token_matrix([span])["nodes"][1]
        self.assertEqual(leaves(output), {"content": 5, "reasoning": 4})
        self.assertEqual(output["estimate_ratio"], 2 / 9)
        self.assertEqual(span["token_categories"][3]["tokens"], 9)

    def test_missing_content_and_inconsistent_reasoning_never_produce_negative_counts(self):
        span = model_span(input_tokens=10, output_tokens=5, **{"reasoning.output_tokens": 7})
        span["attributes"].pop("gen_ai.system_instructions")
        span["attributes"].pop("gen_ai.input.messages")
        matrix = build_token_matrix([span])
        self.assertEqual(leaves(matrix["nodes"][0])["other"], 10)
        self.assertEqual(matrix["nodes"][0]["estimate_ratio"], 0)
        self.assertEqual(leaves(matrix["nodes"][1]), {"content": 0, "reasoning": 5})
        self.assertEqual(span["attributes"]["gen_ai.usage.reasoning.output_tokens"], 7)

    def test_tools_pair_arguments_and_responses_keep_all_rows_and_count_history_usage(self):
        a = model_span(input_tokens=200)
        a["attributes"]["gen_ai.input.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "id": f"call-{i}", "name": f"tool-{i}", "arguments": {"q": "hello"}}
                    for i in range(8)
                ],
            },
            {
                "role": "tool",
                "parts": [{"type": "tool_call_response", "id": f"call-{i}", "response": "hello"} for i in range(8)],
            },
        ]
        b = deepcopy(a)
        b["span_id"] = "model-2"
        matrix = build_token_matrix([a, b])
        self.assertEqual(len(matrix["tools"]), 8)
        self.assertEqual(sum(t["tokens"] for t in matrix["tools"]), leaves(matrix["nodes"][0])["tool_calls"])
        for tool in matrix["tools"]:
            self.assertEqual(tool["call_count"], 1)
            self.assertEqual(tool["span_ids"], ["model-1", "model-2"])
            self.assertEqual(tool["trace_id"], "trace-1")
        self.assertEqual(sum(x["tokens"] for x in a["token_categories"][:3]), 200)

    def test_result_only_messages_resolve_names_from_other_spans_in_any_order(self):
        result = model_span(input_tokens=30)
        result["attributes"]["gen_ai.input.messages"] = [
            {
                "role": "tool",
                "parts": [
                    {"type": "tool_call_response", "id": "call-1", "response": "first"},
                    {"type": "tool_call_response", "id": "call-2", "response": "second"},
                ],
            }
        ]
        call = model_span(span_id="caller")
        call["attributes"]["gen_ai.output.messages"] = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "id": "call-1", "name": "search", "arguments": {}},
                    {"type": "tool_call", "id": "call-2", "name": "search", "arguments": {}},
                ],
            }
        ]
        a = build_token_matrix([deepcopy(result), deepcopy(call)])
        b = build_token_matrix([deepcopy(call), deepcopy(result)])
        self.assertEqual(a, b)
        self.assertEqual(len(a["tools"]), 1)
        self.assertEqual(a["tools"][0]["name"], "search")
        self.assertEqual(a["tools"][0]["call_count"], 2)
        self.assertEqual(a["tools"][0]["span_ids"], ["model-1"])
        self.assertEqual(a["tools"][0]["tokens"], leaves(a["nodes"][0])["tool_calls"])

    def test_reported_zero_does_not_hide_aggregate_ratio(self):
        result = build_token_matrix([model_span(input_tokens=0), model_span(span_id="second", input_tokens=10)])
        self.assertEqual(result["nodes"][0]["estimate_ratio"], 0.4)

    def test_trace_chunks_merge_by_node_key_and_weighted_ratio(self):
        a = model_span(input_tokens=5, output_tokens=4)
        b = model_span(trace_id="trace-2", input_tokens=20, output_tokens=8)
        chunks = [build_token_matrix([deepcopy(s)]) for s in (a, b)]
        combined = build_token_matrix([a, b])
        for i, node in enumerate(combined["nodes"]):
            self.assertEqual(node["tokens"], sum(c["nodes"][i]["tokens"] for c in chunks))
            expected_ratio = (
                sum(c["nodes"][i]["tokens"] * c["nodes"][i]["estimate_ratio"] for c in chunks) / node["tokens"]
            )
            self.assertAlmostEqual(node["estimate_ratio"], expected_ratio)
            for key, tokens in leaves(node).items():
                self.assertEqual(tokens, sum(leaves(c["nodes"][i])[key] for c in chunks))

    def test_agent_and_tool_usage_are_not_added_to_model_usage(self):
        span = model_span(input_tokens=5, output_tokens=4)
        agent = model_span(span_id="agent", input_tokens=1000, output_tokens=1000)
        agent["span_type"] = "AGENT"
        tool = deepcopy(agent)
        tool.update(span_id="tool", span_type="TOOL")
        matrix = build_token_matrix([span, agent, tool])
        self.assertEqual([n["tokens"] for n in matrix["nodes"]], [5, 4])
        self.assertNotIn("token_categories", agent)
        self.assertNotIn("estimated_token_fields", tool)

    def test_mixed_reported_and_estimated_usage_has_no_accuracy_ratio(self):
        matrix = build_token_matrix([model_span(input_tokens=5), model_span(span_id="model-2")])
        self.assertEqual(matrix["nodes"][0]["tokens"], 7)
        self.assertIsNone(matrix["nodes"][0]["estimate_ratio"])


class TruncatedContentTests(TestCase):
    def test_truncated_messages_and_tool_json_are_repaired_without_changing_raw_span(self):
        span = model_span()
        span["attributes"]["gen_ai.input.messages"] = (
            '[{"role":"user","parts":[{"type":"text","content":"你好...[truncated 10 chars]'
        )
        span["attributes"]["gen_ai.system_instructions"] = '[{"type":"text","content":"系统'
        span["attributes"]["gen_ai.tool.definitions"] = (
            '[{"type":"function","name":"search","parameters":{"type":"object"'
        )
        span["attributes"]["gen_ai.output.messages"] = [
            {"role": "assistant", "parts": [{"type": "tool_call", "name": "search", "arguments": '{"q":"hello'}]}
        ]
        source = deepcopy(span)
        result = adapt_spans([span], entity_set("agent-service"))[0]
        self.assertEqual(result["attributes"]["gen_ai.input.messages"][0]["parts"][0]["content"], "你好")
        self.assertEqual(result["attributes"]["gen_ai.output.messages"][0]["parts"][0]["arguments"], {"q": "hello"})
        self.assertEqual(span, source)
        self.assertGreater(build_token_matrix([result])["nodes"][0]["tokens"], 0)

    def test_incomplete_escape_keeps_received_string_prefix(self):
        for suffix in (chr(92), chr(92) + "u4", chr(92) + "u4f"):
            self.assertEqual(repair_truncated_json('{"content":"hello' + suffix), {"content": "hello"})

    def test_valid_json_plain_text_and_invalid_nontruncation_are_preserved(self):
        for value in ('{"a":1}', "普通文本", 'prefix {"a":1', '{"a": @bad}', '{"a":1} trailing', None):
            self.assertEqual(repair_truncated_json(value), value)
