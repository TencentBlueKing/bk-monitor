import contextlib
from collections import defaultdict
from unittest import TestCase, mock

from django.db.models import Q

from apm_web.handlers.metric_group.define import CalculationType as MetricCalculationType
from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import AGENT_CANDIDATE_Q
from apm_web.llm.constants import CalculationType
from apm_web.llm.metric_group import LLMMetricGroup
from apm_web.llm.query import LLMQuery
from apm_web.llm.resources import (
    CalculateByRangeResource,
    ListFlowsResource,
    ListSpansResource,
    ListTracesResource,
    TimeSeriesResource,
)


class ListTracesResourceTestCase(TestCase):
    def test_empty_keyword_does_not_add_span_field_filters(self):
        application = mock.Mock()
        span_query = mock.Mock()
        span_query.query_group_list.return_value = []
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
        ):
            result = ListTracesResource().request(LLM_METRIC_REQUEST)

        self.assertEqual(result["items"], [])
        self.assertEqual(span_query.query_group_list.call_args.kwargs["query_string"], "")
        self.assertEqual(span_query.query_group_list.call_args.kwargs["extra_filter"], AGENT_CANDIDATE_Q)
        self.assertEqual(
            span_query.query_group_list.call_args.kwargs["filters"],
            [{"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]}],
        )

    def test_hex32_keyword_searches_trace_and_product_conversation_fields(self):
        keyword = "0123456789abcdef0123456789abcdef"
        cases = {
            "aidev": "attributes.agent.session.session_code",
            "agentlens": "attributes.gen_ai.session.id",
            "galileo": "attributes.gen_ai.session_id",
            "langfuse": "attributes.session.id",
            "default": "attributes.gen_ai.conversation.id",
        }

        for product, conversation_field in cases.items():
            with self.subTest(product=product):
                self.assertEqual(
                    ListTracesResource._build_keyword_query(product, 11, "demo", keyword),
                    f'trace_id: "{keyword}" OR {conversation_field}: "{keyword}"',
                )

    def test_request_exposes_supported_filters(self):
        fields = ListTracesResource.RequestSerializer().fields

        self.assertIn("keyword", fields)
        self.assertIn("service_name", fields)
        self.assertNotIn("filters", fields)

    def test_span_field_value_can_read_nested_path(self):
        span = {
            "attributes": {
                "gen_ai": {
                    "conversation": {
                        "id": "conversation-1",
                    },
                }
            }
        }

        self.assertEqual(
            ListTracesResource._span_field_value(span, "attributes.gen_ai.conversation.id"), "conversation-1"
        )

    def test_limit_max_value(self):
        request_data = {
            "bk_biz_id": 11,
            "app_name": "sand_local_dev",
            "service_name": "agent-service",
            "start_time": 1,
            "end_time": 2,
            "limit": 100,
        }

        serializer = ListTracesResource.RequestSerializer(data=request_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        serializer = ListTracesResource.RequestSerializer(data={**request_data, "limit": 101})
        self.assertFalse(serializer.is_valid())
        self.assertIn("limit", serializer.errors)

    @staticmethod
    def convert_spans(raw_spans, _entity_set, _product_override=""):
        return [
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span.get("parent_span_id", ""),
                "start_time": span.get("start_time", 0),
                "end_time": span.get("end_time", 0),
                "attributes": {
                    "gen_ai.conversation.id": span.get("attributes", {}).get("agent.session.session_code", ""),
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": span["input"]}]}],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": span["output"]}]}
                    ],
                    "gen_ai.usage.input_tokens": span.get("input_tokens", 0),
                    "gen_ai.usage.output_tokens": span.get("output_tokens", 0),
                    "gen_ai.usage.cache_read.input_tokens": span.get("cache_read_input_tokens", 0),
                    "gen_ai.usage.cache_write.input_tokens": span.get("cache_write_input_tokens", 0),
                    "user.id": span.get("user_id", ""),
                },
            }
            for span in raw_spans
        ]

    def test_trace_group_flattens_child(self):
        span_query = mock.Mock(QUERY_MAX_LIMIT=10000)
        span_query.query_group_list.return_value = ["trace-2", "trace-1"]
        span_query.query_group_trace_list.return_value = [
            {"trace_id": "trace-2"},
            {"trace_id": "trace-1"},
        ]
        application = mock.Mock()
        data_sources = [mock.sentinel.data_source]
        application.build_data_sources.return_value = data_sources
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "parent_span_id": "",
                "status": {"code": 0},
                "input": "问一",
                "output": "答一",
                "start_time": 100,
                "end_time": 160,
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_write_input_tokens": 2,
                "user_id": "user-1",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2",
                "parent_span_id": "",
                "status": {"code": 1},
                "input": "问二",
                "output": "处理中",
                "start_time": 200,
                "end_time": 280,
                "input_tokens": 12,
                "output_tokens": 5,
                "cache_read_input_tokens": 4,
                "cache_write_input_tokens": 1,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-3",
                "parent_span_id": "span-2",
                "status": {"code": 2},
                "input": "问二（包含工具结果）",
                "output": "答二",
                "start_time": 250,
                "end_time": 280,
                "input_tokens": 8,
                "output_tokens": 3,
                "cache_read_input_tokens": 2,
                "cache_write_input_tokens": 0,
                "user_id": "user-2",
            },
        ]
        span_query.iter_by_group_ids.return_value = [raw_spans]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "agentlens"}

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application) as get_application,
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query) as get_query,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.adapt_spans", side_effect=self.convert_spans),
        ):
            result = ListTracesResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "start_time": 1,
                    "end_time": 2,
                    "service_name": "agent-service",
                    "keyword": "订单",
                }
            )

        self.maxDiff = None
        self.assertEqual(
            result["items"],
            [
                {
                    "group_id": "trace-2",
                    "group_field": "trace_id",
                    "trace_id": "trace-2",
                    "conversation_id": "",
                    "status": "error",
                    "input": "问二",
                    "output": "答二",
                    "input_tokens": 20,
                    "output_tokens": 8,
                    "cache_read_input_tokens": 6,
                    "cache_write_input_tokens": 1,
                    "start_time": 200,
                    "end_time": 280,
                    "elapsed_time": 80,
                    "user_id": "user-2",
                },
                {
                    "group_id": "trace-1",
                    "group_field": "trace_id",
                    "trace_id": "trace-1",
                    "conversation_id": "",
                    "status": "success",
                    "input": "问一",
                    "output": "答一",
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 3,
                    "cache_write_input_tokens": 2,
                    "start_time": 100,
                    "end_time": 160,
                    "elapsed_time": 60,
                    "user_id": "user-1",
                },
            ],
        )
        self.assertNotIn("childs", result["items"][0])
        self.assertNotIn("total", result)
        get_application.assert_called_once_with(bk_biz_id=11, app_name="sand_local_dev")
        application.build_data_sources.assert_called_once_with()
        get_query.assert_called_once_with(data_sources)
        span_query.query_group_list.assert_called_once_with(
            start_time=1,
            end_time=2,
            group_field="trace_id",
            offset=0,
            limit=20,
            filters=[{"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]}],
            query_string="*订单*",
            extra_filter=AGENT_CANDIDATE_Q,
        )
        span_query.iter_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-1"],
        )
        span_query.query_group_trace_list.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-1"],
        )

    def test_conversation_group_maps_field_by_product(self):
        span_query = mock.Mock(QUERY_MAX_LIMIT=10000)
        span_query.query_group_list.return_value = ["session-2", "session-1"]
        query_field = "attributes.agent.session.session_code"
        span_query.query_group_trace_list.return_value = [
            {query_field: "session-2", "trace_id": "trace-2"},
            {query_field: "session-2", "trace_id": "trace-3"},
            {query_field: "session-1", "trace_id": "trace-1"},
        ]
        application = mock.Mock()
        data_sources = [mock.sentinel.data_source]
        application.build_data_sources.return_value = data_sources
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "parent_span_id": "",
                "attributes": {"agent.session.session_code": "session-1"},
                "status": {"code": 1},
                "input": "问一",
                "output": "答一",
                "start_time": 300,
                "end_time": 330,
                "input_tokens": 5,
                "output_tokens": 2,
                "cache_read_input_tokens": 1,
                "cache_write_input_tokens": 0,
                "user_id": "user-1",
            },
            {
                "trace_id": "trace-3",
                "span_id": "span-3",
                "parent_span_id": "",
                "attributes": {"agent.session.session_code": "session-2"},
                "status": {"code": 2},
                "input": "问三",
                "output": "答三",
                "start_time": 200,
                "end_time": 280,
                "input_tokens": 20,
                "output_tokens": 8,
                "cache_read_input_tokens": 6,
                "cache_write_input_tokens": 1,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2",
                "parent_span_id": "",
                "attributes": {"agent.session.session_code": "session-2"},
                "status": {"code": 1},
                "input": "问二",
                "output": "答二",
                "start_time": 100,
                "end_time": 360,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2-llm",
                "parent_span_id": "span-2",
                "attributes": {},
                "status": {"code": 0},
                "input": "模型输入",
                "output": "模型输出",
                "start_time": 120,
                "end_time": 150,
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_write_input_tokens": 2,
                "user_id": "",
            },
        ]
        span_query.iter_by_group_ids.return_value = [raw_spans]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "aidev"}

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application) as get_application,
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query) as get_query,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.adapt_spans", side_effect=self.convert_spans) as adapt_spans_mock,
        ):
            result = ListTracesResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "start_time": 1,
                    "end_time": 2,
                    "service_name": "agent-service",
                    "group_field": "attributes.gen_ai.conversation.id",
                    "keyword": "demo-user",
                }
            )

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(
            result["items"][0],
            {
                "group_id": "session-2",
                "group_field": "attributes.gen_ai.conversation.id",
                "status": "error",
                "input": "问二",
                "output": "答二",
                "input_tokens": 30,
                "output_tokens": 12,
                "cache_read_input_tokens": 9,
                "cache_write_input_tokens": 3,
                "start_time": 100,
                "end_time": 360,
                "elapsed_time": 260,
                "user_id": "user-2",
                "childs": [
                    {
                        "group_id": "trace-2",
                        "group_field": "trace_id",
                        "trace_id": "trace-2",
                        "conversation_id": "session-2",
                        "status": "success",
                        "input": "问二",
                        "output": "答二",
                        "input_tokens": 10,
                        "output_tokens": 4,
                        "cache_read_input_tokens": 3,
                        "cache_write_input_tokens": 2,
                        "start_time": 100,
                        "end_time": 360,
                        "elapsed_time": 260,
                        "user_id": "user-2",
                    },
                    {
                        "group_id": "trace-3",
                        "group_field": "trace_id",
                        "trace_id": "trace-3",
                        "conversation_id": "session-2",
                        "status": "error",
                        "input": "问三",
                        "output": "答三",
                        "input_tokens": 20,
                        "output_tokens": 8,
                        "cache_read_input_tokens": 6,
                        "cache_write_input_tokens": 1,
                        "start_time": 200,
                        "end_time": 280,
                        "elapsed_time": 80,
                        "user_id": "user-2",
                    },
                ],
            },
        )
        self.assertEqual(result["items"][1]["status"], "success")
        span_query.query_group_list.assert_called_once_with(
            start_time=1,
            end_time=2,
            group_field=query_field,
            offset=0,
            limit=20,
            filters=[],
            query_string="demo-user",
            extra_filter=None,
        )
        span_query.iter_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-3", "trace-1"],
        )
        span_query.query_group_trace_list.assert_called_once_with(
            group_field=query_field,
            group_ids=["session-2", "session-1"],
        )
        get_application.assert_called_once_with(bk_biz_id=11, app_name="sand_local_dev")
        application.build_data_sources.assert_called_once_with()
        get_query.assert_called_once_with(data_sources)
        entity_set.get_system.assert_called_once_with("agent-service")

        self.assertGreaterEqual(len(adapt_spans_mock.call_args_list), 1)
        for call in adapt_spans_mock.call_args_list:
            self.assertEqual(call.args[1], entity_set)

    def test_consume_span_batch_releases_raw_before_assembling_groups(self):
        entity_set = mock.Mock(service_names=["agent-service"])
        trace_group_map = {"trace-1": "session-1", "trace-2": "session-1"}
        batch_one = [
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "parent_span_id": "",
                "status": {"code": 0},
                "input": "问一",
                "output": "答一",
                "start_time": 100,
                "end_time": 160,
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 1,
                "cache_write_input_tokens": 0,
                "user_id": "user-1",
            }
        ]
        batch_two = [
            {
                "trace_id": "trace-2",
                "span_id": "span-2",
                "parent_span_id": "",
                "status": {"code": 2},
                "input": "问二",
                "output": "答二",
                "start_time": 200,
                "end_time": 280,
                "input_tokens": 8,
                "output_tokens": 3,
                "cache_read_input_tokens": 2,
                "cache_write_input_tokens": 1,
                "user_id": "user-1",
            }
        ]
        childs_by_group = defaultdict(list)

        with mock.patch("apm_web.llm.resources.adapt_spans", side_effect=self.convert_spans):
            ListTracesResource._consume_span_batch(batch_one, trace_group_map, entity_set, childs_by_group)
            self.assertEqual(batch_one, [])
            ListTracesResource._consume_span_batch(batch_two, trace_group_map, entity_set, childs_by_group)
            self.assertEqual(batch_two, [])

        items = ListTracesResource._assemble_group_items(
            "attributes.gen_ai.conversation.id",
            ["session-1"],
            childs_by_group,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual([child["trace_id"] for child in items[0]["childs"]], ["trace-2", "trace-1"])
        self.assertEqual(items[0]["status"], "error")
        self.assertEqual(items[0]["input_tokens"], 18)

    def test_aidev_default_service_queries_the_whole_application(self):
        span_query = mock.Mock()
        span_query.query_group_list.return_value = []
        application = mock.Mock()
        application.build_data_sources.return_value = [mock.sentinel.data_source]
        selected_entity_set = mock.Mock(service_names=["agent-service-default"])
        selected_entity_set.get_system.return_value = {"is_support_llm": True, "product": "aidev"}
        application_entity_set = mock.Mock(service_names=["agent-service", "agent-service-default"])

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch(
                "apm_web.llm.resources.EntitySet", side_effect=[selected_entity_set, application_entity_set]
            ) as entity_set,
        ):
            result = ListTracesResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "bkapp_ai0us0demo",
                    "start_time": 1,
                    "end_time": 2,
                    "service_name": "agent-service-default",
                    "group_field": "attributes.gen_ai.conversation.id",
                }
            )

        self.assertEqual(result["items"], [])
        span_query.query_group_list.assert_called_once_with(
            start_time=1,
            end_time=2,
            group_field="attributes.agent.session.session_code",
            offset=0,
            limit=20,
            filters=[],
            query_string="",
            extra_filter=None,
        )
        self.assertEqual(
            entity_set.call_args_list,
            [
                mock.call(bk_biz_id=11, app_name="bkapp_ai0us0demo", service_names=["agent-service-default"]),
                mock.call(bk_biz_id=11, app_name="bkapp_ai0us0demo"),
            ],
        )

    def test_assemble_session_keeps_groups_without_traces(self):
        child = {
            "group_id": "trace-1",
            "group_field": "trace_id",
            "trace_id": "trace-1",
            "conversation_id": "session-1",
            "status": "success",
            "input": "问一",
            "output": "答一",
            "input_tokens": 1,
            "output_tokens": 1,
            "cache_read_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "start_time": 100,
            "end_time": 160,
            "elapsed_time": 60,
            "user_id": "user-1",
        }
        items = ListTracesResource._assemble_group_items(
            "attributes.gen_ai.conversation.id",
            ["session-empty", "session-1"],
            {"session-1": [child]},
        )

        self.assertEqual([item["group_id"] for item in items], ["session-empty", "session-1"])
        self.assertEqual(items[0]["childs"], [])
        self.assertEqual(items[0]["input_tokens"], 0)
        self.assertEqual(items[1]["childs"], [child])

    def test_assemble_trace_still_skips_groups_without_spans(self):
        items = ListTracesResource._assemble_group_items("trace_id", ["trace-missing"], {})
        self.assertEqual(items, [])

    def test_trace_conversation_id_uses_first_nonempty_standardized_value(self):
        for product, field in [
            ("default", "gen_ai.conversation.id"),
            ("agentlens", "gen_ai.session.id"),
            ("aidev", "agent.session.session_code"),
            ("galileo", "gen_ai.session_id"),
            ("langfuse", "session.id"),
        ]:
            with self.subTest(product=product):
                entity_set = mock.Mock(service_names=["agent-service"])
                entity_set.get_system.return_value = {"is_support_llm": True, "product": product}
                raw_spans = [
                    {
                        "trace_id": "trace-1",
                        "span_id": f"span-{start_time}",
                        "parent_span_id": "" if start_time == 100 else "span-100",
                        "span_name": "invoke_agent demo",
                        "start_time": start_time,
                        "end_time": start_time + 10,
                        "elapsed_time": 10,
                        "status": {"code": 1},
                        "resource": {"service.name": "agent-service"},
                        "attributes": {"gen_ai.operation.name": "invoke_agent", field: value},
                        "events": [],
                    }
                    for start_time, value in [(300, "conversation-later"), (100, ""), (200, "conversation-first")]
                ]

                item = ListTracesResource._trace_item("trace-1", raw_spans, entity_set)

                self.assertEqual(item["conversation_id"], "conversation-first")

    def test_langfuse_root_context_survives_trace_and_session_grouping(self):
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "langfuse"}
        root = {
            "trace_id": "trace-1",
            "span_id": "root",
            "parent_span_id": "",
            "span_name": "application-turn",
            "start_time": 100,
            "end_time": 300,
            "elapsed_time": 200,
            "status": {"code": 1, "message": ""},
            "resource": {"service.name": "agent-service"},
            "attributes": {
                "langfuse.observation.type": "span",
                "langfuse.internal.is_app_root": True,
                "user.id": "test-user",
                "session.id": "session-1",
                "langfuse.observation.input": "user question",
                "langfuse.observation.output": "assistant answer",
            },
        }
        child = {
            **root,
            "span_id": "generation",
            "parent_span_id": "root",
            "start_time": 150,
            "end_time": 250,
            "elapsed_time": 100,
            "attributes": {
                "langfuse.observation.type": "generation",
                "langfuse.observation.input": "model prompt",
                "langfuse.observation.output": "model answer",
                "langfuse.observation.usage_details": {"input": 10, "output": 3},
            },
        }
        for group_field, group_id in [("trace_id", "trace-1"), ("attributes.gen_ai.conversation.id", "session-1")]:
            with self.subTest(group_field=group_field):
                items = ListTracesResource._group_spans(
                    group_field, [group_id], {"trace-1": group_id}, [child, root], entity_set
                )

                self.assertEqual(len(items), 1)
                item = items[0]
                self.assertEqual(item["group_id"], group_id)
                for row in [item, *item.get("childs", [])]:
                    self.assertEqual(row["user_id"], "test-user")
                    self.assertEqual(row["input"], "user question")
                    self.assertEqual(row["output"], "assistant answer")
                    self.assertEqual(row["input_tokens"], 10)
                    self.assertEqual(row["output_tokens"], 3)
                trace = item["childs"][0] if "childs" in item else item
                self.assertEqual(trace["conversation_id"], "session-1")

    def test_trace_status_includes_spans_filtered_by_adapter(self):
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}

        for root_code, child_code, expected_status in [(1, 1, "success"), (0, 0, "success"), (1, 2, "error")]:
            with self.subTest(root_code=root_code, child_code=child_code):
                raw_spans = [
                    {
                        "trace_id": "trace-1",
                        "span_id": "root",
                        "parent_span_id": "",
                        "span_name": "invoke_agent demo",
                        "start_time": 100,
                        "end_time": 300,
                        "elapsed_time": 200,
                        "status": {"code": root_code, "message": ""},
                        "resource": {"service.name": "agent-service"},
                        "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.usage.input_tokens": 10},
                    },
                    {
                        "trace_id": "trace-1",
                        "span_id": "http-child",
                        "parent_span_id": "root",
                        "span_name": "GET /orders",
                        "start_time": 150,
                        "end_time": 200,
                        "elapsed_time": 50,
                        "status": {"code": child_code, "message": "timeout" if child_code == 2 else ""},
                        "resource": {"service.name": "agent-service"},
                        "attributes": {"http.method": "GET"},
                    },
                ]

                self.assertEqual([span["span_id"] for span in adapt_spans(raw_spans, entity_set)], ["root"])

                item = ListTracesResource._trace_item("trace-1", raw_spans, entity_set)

                self.assertEqual(item["status"], expected_status)
                self.assertEqual(item["input_tokens"], 10)

    def test_trace_time_uses_root_start_and_latest_span_end(self):
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "root",
                "parent_span_id": "",
                "start_time": 100,
                "end_time": 300,
                "status": {"code": 1},
            },
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "root",
                "start_time": 150,
                "end_time": 350,
                "status": {"code": 1},
            },
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "start_time": 150,
                "end_time": 200,
                "attributes": {},
            }
        ]

        with mock.patch("apm_web.llm.resources.adapt_spans", return_value=converted_spans):
            item = ListTracesResource._trace_item("trace-1", raw_spans, mock.sentinel.entity_set)

        self.assertEqual(item["start_time"], 100)
        self.assertEqual(item["end_time"], 350)
        self.assertEqual(item["elapsed_time"], 250)

    def test_trace_time_falls_back_to_earliest_span_without_root(self):
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "child-1",
                "parent_span_id": "external-parent",
                "start_time": 150,
                "end_time": 350,
                "status": {"code": 1},
            },
            {
                "trace_id": "trace-1",
                "span_id": "child-2",
                "parent_span_id": "external-parent",
                "start_time": 100,
                "end_time": 300,
                "status": {"code": 1},
            },
        ]

        with mock.patch("apm_web.llm.resources.adapt_spans", return_value=[]):
            item = ListTracesResource._trace_item("trace-1", raw_spans, mock.sentinel.entity_set)

        self.assertEqual(item["start_time"], 100)
        self.assertEqual(item["end_time"], 350)
        self.assertEqual(item["elapsed_time"], 250)

    def test_trace_preview_uses_earliest_user_text_and_latest_model_text(self):
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "http-root",
                "parent_span_id": "",
                "start_time": 100,
                "end_time": 300,
                "status": {"code": 1},
            }
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "http-root",
                "parent_span_id": "",
                "start_time": 100,
                "end_time": 300,
                "attributes": {},
            },
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "http-root",
                "start_time": 110,
                "end_time": 300,
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.input.messages": [
                        {"role": "system", "parts": [{"type": "text", "content": "系统提示词"}]},
                        {"role": "user", "parts": [{"type": "text", "content": "历史问题"}]},
                        {"role": "assistant", "parts": [{"type": "text", "content": "历史回答"}]},
                        {
                            "role": "tool",
                            "parts": [{"type": "tool_call_response", "content": "内部工具结果"}],
                        },
                        {
                            "role": "user",
                            "parts": [
                                {"type": "text", "content": "最新问题"},
                                {"type": "reasoning", "content": "用户推理"},
                            ],
                        },
                    ],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": "历史输出"}]},
                        {"role": "tool", "parts": [{"type": "text", "content": "工具输出"}]},
                        {
                            "role": "assistant",
                            "parts": [
                                {"type": "reasoning", "content": "内部推理"},
                                {"type": "text", "content": "最终回答"},
                            ],
                        },
                    ],
                },
            },
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "agent",
                "start_time": 150,
                "end_time": 280,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.input.messages": [
                        {"role": "user", "parts": [{"type": "text", "content": "子 LLM 内部提示词"}]}
                    ],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": "子 LLM 输出"}]}
                    ],
                },
            },
        ]

        with mock.patch("apm_web.llm.resources.adapt_spans", return_value=converted_spans):
            item = ListTracesResource._trace_item("trace-1", raw_spans, mock.sentinel.entity_set)

        self.assertEqual(item["input"], "最新问题")
        self.assertEqual(item["output"], "最终回答")

    def test_trace_preview_falls_back_to_child_model_output(self):
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "",
                "start_time": 100,
                "end_time": 300,
                "status": {"code": 1},
            }
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "",
                "start_time": 100,
                "end_time": 300,
                "attributes": {"gen_ai.operation.name": "invoke_workflow"},
            },
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "agent",
                "start_time": 120,
                "end_time": 200,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "内部提示词"}]}],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": "内部回答"}]}
                    ],
                },
            },
        ]

        with mock.patch("apm_web.llm.resources.adapt_spans", return_value=converted_spans):
            item = ListTracesResource._trace_item("trace-1", raw_spans, mock.sentinel.entity_set)

        self.assertEqual(item["input"], "内部提示词")
        self.assertEqual(item["output"], "内部回答")

    def test_trace_preview_output_priority_is_text_then_reasoning_then_tool_call_then_result(self):
        raw_spans = [{"trace_id": "trace-1", "span_id": "root", "parent_span_id": "", "status": {"code": 1}}]

        def item_for(converted_spans):
            with mock.patch("apm_web.llm.resources.adapt_spans", return_value=converted_spans):
                return ListTracesResource._trace_item("trace-1", raw_spans, mock.sentinel.entity_set)

        tool_call_span = {
            "trace_id": "trace-1",
            "span_id": "chat-tool",
            "start_time": 120,
            "end_time": 180,
            "attributes": {
                "gen_ai.output.messages": [
                    {
                        "role": "assistant",
                        "parts": [{"type": "tool_call", "name": "read_file", "arguments": {"path": "/tmp/a"}}],
                    }
                ]
            },
        }
        reasoning_span = {
            "trace_id": "trace-1",
            "span_id": "chat-reason",
            "start_time": 110,
            "end_time": 160,
            "attributes": {
                "gen_ai.output.messages": [
                    {"role": "assistant", "parts": [{"type": "reasoning", "content": "先查文件"}]}
                ]
            },
        }
        text_span = {
            "trace_id": "trace-1",
            "span_id": "chat-text",
            "start_time": 100,
            "end_time": 150,
            "attributes": {
                "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "最终回答"}]}]
            },
        }
        tool_span = {
            "trace_id": "trace-1",
            "span_id": "tool",
            "start_time": 130,
            "end_time": 200,
            "attributes": {
                "gen_ai.tool.call.arguments": {"path": "/tmp/a"},
                "gen_ai.tool.call.result": {"ok": True},
            },
        }

        tool_arguments = ListTracesResource._preview_text({"path": "/tmp/a"})
        self.assertEqual(item_for([tool_span])["input"], tool_arguments)
        self.assertEqual(item_for([tool_span])["output"], ListTracesResource._preview_text({"ok": True}))
        self.assertEqual(item_for([tool_call_span, tool_span])["output"], f"read_file {tool_arguments}")
        self.assertEqual(item_for([reasoning_span, tool_call_span, tool_span])["output"], "先查文件")
        self.assertEqual(item_for([text_span, reasoning_span, tool_call_span, tool_span])["output"], "最终回答")

        tool_response_span = {
            "trace_id": "trace-1",
            "span_id": "tool-response",
            "start_time": 140,
            "end_time": 190,
            "attributes": {
                "gen_ai.output.messages": [
                    {
                        "role": "tool",
                        "parts": [{"type": "tool_call_response", "response": "file contents"}],
                    }
                ]
            },
        }
        self.assertEqual(item_for([tool_response_span])["output"], "file contents")


class ListSpansResourceTestCase(TestCase):
    def test_adapts_standard_span(self):
        trace_id = "a" * 32
        response = {
            "total": 1,
            "data": [
                {
                    "trace_id": trace_id,
                    "span_id": "b" * 16,
                    "parent_span_id": "",
                    "span_name": "chat demo-model",
                    "start_time": 1,
                    "end_time": 2,
                    "elapsed_time": 1,
                    "status": {"code": 1, "message": ""},
                    "resource": {"service.name": "demo"},
                    "attributes": {
                        "gen_ai.operation.name": "chat",
                        "gen_ai.request.model": "demo-model",
                        "vendor.debug": "drop-me",
                    },
                    "events": [],
                }
            ],
        }
        entity_set = mock.Mock()
        entity_set.service_names = ["demo"]
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
        ):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": trace_id,
                }
            )

        self.assertEqual(result["trace_id"], trace_id)
        self.assertEqual(result["total"], 1)
        attributes = result["spans"][0]["attributes"]
        self.assertEqual(attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(attributes["gen_ai.request.model"], "demo-model")
        self.assertNotIn("vendor.debug", attributes)

    def test_adapts_apm_api_response(self):
        response = {"total": 1, "data": [{"trace_id": "trace-1", "span_id": "span-1"}]}
        converted_span = {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "attributes": {"gen_ai.operation.name": "chat"},
        }
        entity_set = mock.sentinel.entity_set

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch(
                "apm_web.llm.resources.adapt_spans",
                return_value=[converted_span],
            ) as adapt_spans,
        ):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": "trace-1",
                }
            )

        self.assertEqual(
            result,
            {"trace_id": "trace-1", "total": 1, "spans": [converted_span]},
        )
        adapt_spans.assert_called_once_with(response["data"], entity_set)
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [{"key": "trace_id", "operator": "equal", "value": ["trace-1"]}],
                "limit": 10000,
                "exclude_field": ["bk_app_code"],
            }
        )

    def test_filters_by_trace_and_span_id(self):
        response = {"total": 1, "data": [{"trace_id": "trace-1", "span_id": "span-1"}]}

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=mock.sentinel.entity_set),
            mock.patch("apm_web.llm.resources.adapt_spans", return_value=response["data"]),
        ):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": "trace-1",
                    "span_id": "span-1",
                }
            )

        self.assertEqual(result["total"], 1)
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [
                    {"key": "trace_id", "operator": "equal", "value": ["trace-1"]},
                    {"key": "span_id", "operator": "equal", "value": ["span-1"]},
                ],
                "limit": 10000,
                "exclude_field": ["bk_app_code"],
            }
        )

    def test_allows_span_id_without_trace_id(self):
        response = {"total": 1, "data": [{"trace_id": "trace-1", "span_id": "span-1"}]}

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=mock.sentinel.entity_set),
            mock.patch("apm_web.llm.resources.adapt_spans", return_value=response["data"]),
        ):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "span_id": "span-1",
                }
            )

        self.assertEqual(result, {"trace_id": "trace-1", "total": 1, "spans": response["data"]})
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [{"key": "span_id", "operator": "equal", "value": ["span-1"]}],
                "limit": 10000,
                "exclude_field": ["bk_app_code"],
            }
        )

    def test_requires_trace_id_or_span_id(self):
        serializer = ListSpansResource.RequestSerializer(
            data={
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)


class ListFlowsResourceTestCase(TestCase):
    def test_list_spans_and_flows_share_complete_agent_trace_contract(self):
        trace_id = "trace-agent-tool-call"
        tool_call_id = "tool-call-1"
        resource = {"service.name": "agent-service"}
        status = {"code": 1, "message": ""}
        raw_spans = [
            {
                "trace_id": trace_id,
                "span_id": "agent",
                "parent_span_id": "",
                "span_name": "invoke_agent troubleshooting",
                "start_time": 100,
                "end_time": 500,
                "elapsed_time": 400,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "检查当前故障"}]}],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": "CPU 使用率持续升高"}]}
                    ],
                },
                "events": [],
            },
            {
                "trace_id": trace_id,
                "span_id": "chat-tool-call",
                "parent_span_id": "agent",
                "span_name": "chat demo-model",
                "start_time": 110,
                "end_time": 200,
                "elapsed_time": 90,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.response.finish_reasons": ["tool_call"],
                    "gen_ai.tool.definitions": [
                        {
                            "type": "function",
                            "name": "list_incident_events",
                            "description": "查询故障关联事件",
                            "parameters": {
                                "type": "object",
                                "properties": {"incident_id": {"type": "string"}},
                                "required": ["incident_id"],
                                "additionalProperties": False,
                            },
                        }
                    ],
                    "gen_ai.output.messages": [
                        {
                            "role": "assistant",
                            "parts": [
                                {"type": "reasoning", "content": "需要先查询故障事件"},
                                {
                                    "type": "tool_call",
                                    "id": tool_call_id,
                                    "name": "list_incident_events",
                                    "arguments": {"incident_id": "incident-1"},
                                },
                            ],
                        }
                    ],
                    "gen_ai.usage.input_tokens": 120,
                    "gen_ai.usage.output_tokens": 32,
                },
                "events": [],
            },
            {
                "trace_id": trace_id,
                "span_id": "tool",
                "parent_span_id": "chat-tool-call",
                "span_name": "execute_tool list_incident_events",
                "start_time": 210,
                "end_time": 250,
                "elapsed_time": 40,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": "list_incident_events",
                    "gen_ai.tool.call.id": tool_call_id,
                    "gen_ai.tool.call.arguments": {"incident_id": "incident-1"},
                    "gen_ai.tool.call.result": {"status": "ABNORMAL"},
                },
                "events": [],
            },
            {
                "trace_id": trace_id,
                "span_id": "chat-final-answer",
                "parent_span_id": "agent",
                "span_name": "chat demo-model",
                "start_time": 260,
                "end_time": 490,
                "elapsed_time": 230,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.response.finish_reasons": ["stop"],
                    "gen_ai.input.messages": [
                        {
                            "role": "tool",
                            "parts": [
                                {
                                    "type": "tool_call_response",
                                    "id": tool_call_id,
                                    "response": {"status": "ABNORMAL"},
                                }
                            ],
                        }
                    ],
                    "gen_ai.output.messages": [
                        {
                            "role": "assistant",
                            "parts": [
                                {"type": "reasoning", "content": "事件仍处于异常状态"},
                                {"type": "text", "content": "CPU 使用率持续升高"},
                            ],
                        }
                    ],
                    "gen_ai.usage.input_tokens": 180,
                    "gen_ai.usage.output_tokens": 84,
                },
                "events": [],
            },
        ]
        application = mock.Mock()
        application.build_data_sources.return_value = [mock.sentinel.data_source]
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = [{"trace_id": trace_id}]
        span_query.query_by_group_ids.return_value = raw_spans
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}

        with (
            mock.patch(
                "core.drf_resource.api.apm_api.query_span_list",
                return_value={"total": len(raw_spans), "data": raw_spans},
            ),
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
        ):
            spans_result = ListSpansResource().request({"bk_biz_id": 11, "app_name": "agent-app", "trace_id": trace_id})
            flows_result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "agent-app",
                    "group_field": "trace_id",
                    "group_id": trace_id,
                }
            )

        def flatten(nodes):
            flattened = []
            for node in nodes:
                flattened.append({key: value for key, value in node.items() if key != "childs"})
                flattened.extend(flatten(node["childs"]))
            return flattened

        spans = spans_result["spans"]
        flow = flows_result["traces"][0]["flow"]
        self.assertEqual(spans_result["total"], 4)
        self.assertEqual(flatten(flow), spans)
        self.assertEqual(
            [span["attributes"]["gen_ai.operation.name"] for span in spans],
            ["invoke_agent", "chat", "execute_tool", "chat"],
        )
        self.assertEqual([child["span_id"] for child in flow[0]["childs"]], ["chat-tool-call", "chat-final-answer"])
        self.assertEqual([child["span_id"] for child in flow[0]["childs"][0]["childs"]], ["tool"])
        self.assertEqual(spans[1]["attributes"]["gen_ai.response.finish_reasons"], ["tool_call"])
        self.assertEqual(spans[3]["attributes"]["gen_ai.response.finish_reasons"], ["stop"])
        self.assertEqual(
            [
                (span["attributes"]["gen_ai.usage.input_tokens"], span["attributes"]["gen_ai.usage.output_tokens"])
                for span in (spans[1], spans[3])
            ],
            [(120, 32), (180, 84)],
        )

        tool_call = next(
            part
            for message in spans[1]["attributes"]["gen_ai.output.messages"]
            for part in message["parts"]
            if part["type"] == "tool_call"
        )
        tool_response = next(
            part
            for message in spans[3]["attributes"]["gen_ai.input.messages"]
            for part in message["parts"]
            if part["type"] == "tool_call_response"
        )
        tool_attributes = spans[2]["attributes"]
        self.assertEqual(tool_call["id"], tool_attributes["gen_ai.tool.call.id"])
        self.assertEqual(tool_response["id"], tool_attributes["gen_ai.tool.call.id"])
        self.assertEqual(tool_call["arguments"], tool_attributes["gen_ai.tool.call.arguments"])
        self.assertEqual(tool_response["response"], tool_attributes["gen_ai.tool.call.result"])
        self.assertIn(
            tool_attributes["gen_ai.tool.name"],
            {definition["name"] for definition in spans[1]["attributes"]["gen_ai.tool.definitions"]},
        )

    def test_build_flow_links_span_to_nearest_gen_ai_ancestor(self):
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "",
                "start_time": 100,
            },
            {
                "trace_id": "trace-1",
                "span_id": "framework",
                "parent_span_id": "agent",
                "start_time": 110,
            },
            {
                "trace_id": "trace-1",
                "span_id": "tool",
                "parent_span_id": "framework",
                "start_time": 120,
            },
        ]

        flow = ListFlowsResource._build_flow(raw_spans, [raw_spans[0], raw_spans[2]])

        self.assertEqual([span["span_id"] for span in flow], ["agent"])
        self.assertEqual([span["span_id"] for span in flow[0]["childs"]], ["tool"])
        self.assertEqual(flow[0]["childs"][0]["parent_span_id"], "framework")

    def test_builds_span_tree_for_each_trace(self):
        group_field = "attributes.gen_ai.conversation.id"
        application = mock.Mock()
        data_sources = [mock.sentinel.data_source]
        application.build_data_sources.return_value = data_sources
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = [
            {group_field: "conversation-1", "trace_id": "trace-1"},
            {group_field: "conversation-1", "trace_id": "trace-2"},
        ]
        spans = [
            {
                "trace_id": "trace-1",
                "span_id": "root-1",
                "parent_span_id": "",
                "start_time": 100,
                "attributes": {"gen_ai.operation.name": "invoke_agent"},
            },
            {
                "trace_id": "trace-1",
                "span_id": "child-1",
                "parent_span_id": "root-1",
                "start_time": 110,
                "attributes": {"gen_ai.operation.name": "chat"},
            },
            {
                "trace_id": "trace-2",
                "span_id": "root-2",
                "parent_span_id": "external-parent",
                "start_time": 200,
                "attributes": {"gen_ai.operation.name": "invoke_agent"},
            },
        ]
        span_query.query_by_group_ids.return_value = spans
        entity_set = mock.Mock(service_names=[])

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application) as get_application,
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query) as get_query,
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set) as entity_set_class,
            mock.patch(
                "apm_web.llm.resources.adapt_spans", side_effect=lambda raw_spans, _entity_set: raw_spans
            ) as adapt_spans,
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "group_field": group_field,
                    "group_id": "conversation-1",
                }
            )

        self.assertEqual(result["group_field"], group_field)
        self.assertEqual(result["group_id"], "conversation-1")
        self.assertEqual([trace["trace_id"] for trace in result["traces"]], ["trace-1", "trace-2"])
        self.assertEqual(result["traces"][0]["flow"][0]["span_id"], "root-1")
        self.assertEqual(result["traces"][0]["flow"][0]["childs"][0]["span_id"], "child-1")
        self.assertEqual(result["traces"][0]["flow"][0]["childs"][0]["parent_span_id"], "root-1")
        self.assertEqual(result["traces"][1]["flow"][0]["span_id"], "root-2")
        self.assertEqual(result["traces"][1]["flow"][0]["parent_span_id"], "external-parent")
        get_application.assert_called_once_with(bk_biz_id=11, app_name="sand_local_dev")
        application.build_data_sources.assert_called_once_with()
        get_query.assert_called_once_with(data_sources)
        entity_set_class.assert_called_once_with(bk_biz_id=11, app_name="sand_local_dev")
        span_query.query_group_trace_list.assert_called_once_with(
            group_field=group_field,
            group_ids=["conversation-1"],
        )
        span_query.query_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-1", "trace-2"],
        )
        self.assertEqual(
            adapt_spans.call_args_list,
            [mock.call(spans[:2], entity_set), mock.call(spans[2:], entity_set)],
        )

    def test_returns_empty_traces_when_group_does_not_exist(self):
        application = mock.Mock()
        application.build_data_sources.return_value = []
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = []

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "group_field": "trace_id",
                    "group_id": "missing-trace",
                }
            )

        self.assertEqual(
            result,
            {
                "group_field": "trace_id",
                "group_id": "missing-trace",
                "traces": [],
            },
        )
        span_query.query_by_group_ids.assert_not_called()


LLM_METRIC_REQUEST = {
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "agent-service",
    "start_time": 1700000000,
    "end_time": 1700003600,
}

CAL_TYPE_CHOICES = {
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_tokens",
    "request_count",
    "model_call_count",
    "duration",
    "operation_count",
}

GROUP_MODULE = "apm_web.llm.metric_group"


def make_query(records=None):
    """Trace 查询对象的替身，只保留算子取数会用到的行为。"""
    query = mock.Mock()
    query.TIME_FIELD_ACCURACY = 1000
    query.QUERY_MAX_LIMIT = 10000
    query.build_queries.return_value = [mock.Mock()]
    if records is not None:
        query.query_field_aggregated_group.return_value = records
    return query


def patch_llm_metric_group(query, product="default"):
    """把产品路由与数据源都替换掉，只保留算子本身的取数行为。"""
    application = mock.Mock()
    application.build_data_sources.return_value = [mock.sentinel.data_source]
    entity_set = mock.Mock(service_names=["agent-service"])
    entity_set.get_system.return_value = {"is_support_llm": True, "product": product}

    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set))
    stack.enter_context(mock.patch(f"{GROUP_MODULE}.Application.objects.get", return_value=application))
    stack.enter_context(mock.patch(f"{GROUP_MODULE}.get_query", return_value=query))
    return stack


def layer_query(query):
    """取算子实际下发的层级谓词：调用方过滤条件在下一个 filter 上，不会混进来。"""
    return query.build_queries.return_value[0].filter.call_args.args[0]


def aggregate_call(query):
    """取算子实际下发的聚合调用：(字段列表, 聚合方式, 分组字段)。"""
    _, _, _, fields, method, group_by = query.query_field_aggregated_group.call_args.args
    return fields, method, group_by


def fetched_fields(query):
    """取本地聚合实际拉回的原始字段列表。"""
    return query.query_field_values.call_args.args[3]


class LLMMetricGroupTestCase(TestCase):
    """声明表按产品换算的行为。"""

    @staticmethod
    def _group(product, **kwargs):
        return LLMMetricGroup(11, "sand_local_dev", product=product, query=mock.Mock(), **kwargs)

    def test_llm_calculation_types_are_independent(self):
        self.assertEqual({value for value, _ in CalculationType.choices()}, CAL_TYPE_CHOICES)
        self.assertTrue(CAL_TYPE_CHOICES.isdisjoint(value for value, _ in MetricCalculationType.choices()))
        self.assertEqual(str(CalculationType.INPUT_TOKENS.label), "输入 Token 数")

    def test_bkaidev_queries_the_whole_application(self):
        """带 Token 的模型 Span 上报在兄弟服务 {svc}-default 上，加服务过滤必然漏数。"""
        for service_name in ("ai-als-title-sum", "ai-als-title-sum-default"):
            group = self._group("aidev", service_name=service_name)
            self.assertNotIn("resource.service.name__eq", group.filter_dict)

    def test_keeps_single_service_for_other_products(self):
        group = self._group("galileo", service_name="agent-service")

        self.assertEqual(group.filter_dict["resource.service.name__eq"], ["agent-service"])

    def test_group_by_falls_back_to_standard_field(self):
        """只登记与标准名不一致的产品，未登记的落到标准名。"""
        group_by = ["gen_ai.response.model"]

        self.assertEqual(
            [self._group(product, group_by=group_by).group_fields[0] for product in ("default", "galileo", "langfuse")],
            [
                "attributes.gen_ai.response.model",
                "attributes.gen_ai.request.model",
                "attributes.langfuse.observation.model.name",
            ],
        )

    def test_rejects_unknown_calculation_type(self):
        with self.assertRaises(ValueError):
            self._group("default").handle("not_exists")


class CalculateByRangeResourceTestCase(TestCase):
    def test_accepts_metrics_required_by_overview_page(self):
        fields = CalculateByRangeResource.RequestSerializer().fields

        self.assertEqual(set(fields["cal_type"].choices), CAL_TYPE_CHOICES)

    def test_operation_count_uses_query_scope_without_layer_filter(self):
        operation_fields = {
            "default": "attributes.gen_ai.operation.name",
            "galileo": "attributes.gen_ai.operation.name",
            "agentlens": "attributes.gen_ai.span.kind",
            "langfuse": "attributes.langfuse.observation.type",
            "aidev": "attributes.llm.request.type",
        }
        for product, field in operation_fields.items():
            for group_by in ([], ["gen_ai.operation.name"]):
                with self.subTest(product=product, group_by=group_by):
                    query = make_query(records=[{"_result_": 12, field: "chat"}])
                    with patch_llm_metric_group(query, product=product):
                        result = CalculateByRangeResource().request(
                            {**LLM_METRIC_REQUEST, "cal_type": "operation_count", "group_by": group_by}
                        )
                    self.assertEqual(result["data"][0]["0s"], 12)
                    self.assertIsInstance(result["data"][0]["0s"], int)
                    self.assertEqual(aggregate_call(query), (["_index"], "COUNT", [field] if group_by else []))
                    self.assertEqual(layer_query(query), Q())
                    service_filter = query.build_queries.return_value[0].filter.return_value.filter.call_args.args[0]
                    self.assertEqual(
                        service_filter,
                        Q() if product == "aidev" else Q(**{"resource.service.name__eq": ["agent-service"]}),
                    )

    def test_operation_count_drops_empty_and_maps_to_standard_names(self):
        cases = [
            (
                "default",
                "attributes.gen_ai.operation.name",
                [("CHAT", 10), ("", 100), ("chat", 5), ("invoke_agent", 4)],
                [("chat", 15), ("invoke_agent", 4)],
            ),
            (
                "aidev",
                "attributes.llm.request.type",
                [("chat", 20), ("", 12627), ("completion", 5)],
                [("chat", 20), ("text_completion", 5)],
            ),
            (
                "agentlens",
                "attributes.gen_ai.span.kind",
                [("LLM", 8), ("AGENT", 3), ("", 50)],
                [("chat", 8), ("invoke_agent", 3)],
            ),
            (
                "langfuse",
                "attributes.langfuse.observation.type",
                [("generation", 7), ("tool", 2), ("agent", 1)],
                [("chat", 7), ("execute_tool", 2), ("invoke_agent", 1)],
            ),
        ]
        for product, field, raw_records, expected in cases:
            with self.subTest(product=product):
                query = make_query(records=[{field: name, "_result_": count} for name, count in raw_records])
                with patch_llm_metric_group(query, product=product):
                    result = CalculateByRangeResource().request(
                        {**LLM_METRIC_REQUEST, "cal_type": "operation_count", "group_by": ["gen_ai.operation.name"]}
                    )

                self.assertEqual(
                    [(record["dimensions"]["gen_ai.operation.name"], record["0s"]) for record in result["data"]],
                    expected,
                )
                self.assertEqual(layer_query(query), Q())

    def test_input_tokens_aggregates_model_layer_only(self):
        """Agent 层的 Token 实测等于其子模型 Span 之和，两层都算会精确翻倍。"""
        query = make_query(records=[{"_result_": 15308239}])

        with patch_llm_metric_group(query):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "group_by": []}
            )

        self.assertEqual(
            result,
            {"total": 1, "data": [{"dimensions": {}, "0s": 15308239, "growth_rates": {"0s": 0}}]},
        )
        self.assertEqual(aggregate_call(query), (["attributes.gen_ai.usage.input_tokens"], "SUM", []))
        self.assertEqual(
            layer_query(query),
            Q(**{"attributes.gen_ai.operation.name": ["chat", "generate_content", "text_completion", "embeddings"]}),
        )

    def test_request_count_dedupes_by_trace_on_agent_layer(self):
        """Agent Span 数会被双层埋点和子 Agent 放大，按 trace 去重才收敛到真实请求数。"""
        query = make_query(records=[{"_result_": 27}])

        with patch_llm_metric_group(query, product="galileo"):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "request_count", "group_by": []}
            )

        # 计数类算子取整，不带小数
        self.assertIsInstance(result["data"][0]["0s"], int)
        self.assertEqual(result["data"][0]["0s"], 27)
        self.assertEqual(aggregate_call(query), (["trace_id"], "DISTINCT", []))
        self.assertEqual(
            layer_query(query), Q(**{"attributes.gen_ai.operation.name": ["invoke_agent", "invoke_workflow"]})
        )

    def test_bkaidev_reads_legacy_token_fields_on_token_bearing_span(self):
        """该产品用旧版 traceloop 命名，且只有 ChatModel.chat 带 Token。"""
        query = make_query(records=[{"_result_": 61083}])

        with patch_llm_metric_group(query, product="aidev"):
            CalculateByRangeResource().request({**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "group_by": []})

        self.assertEqual(aggregate_call(query)[0], ["attributes.gen_ai.usage.prompt_tokens"])
        self.assertEqual(layer_query(query), Q(span_name="ChatModel.chat"))

    def test_cache_tokens_sums_every_candidate_field_in_storage(self):
        """标准名字段可能存在但恒为 0，真实值在非标准名上，因此该产品的候选字段一次查询全部相加。"""
        query = make_query(records=[{"_result_": 8778620}])

        with patch_llm_metric_group(query, product="galileo"):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "cache_tokens", "group_by": []}
            )

        self.assertEqual(result["data"][0]["0s"], 8778620)
        # 求和下推给存储侧，SaaS 侧不再按字段逐个查询后相加
        query.query_field_aggregated_group.assert_called_once()
        self.assertEqual(
            aggregate_call(query)[0],
            [
                "attributes.gen_ai.usage.cache_read.input_tokens",
                "attributes.gen_ai.usage.cache_read_input_tokens",
                "attributes.gen_ai.usage.cached.input_tokens",
                "attributes.gen_ai.usage.cache_creation.input_tokens",
                "attributes.gen_ai.usage.cache_creation_input_tokens",
            ],
        )

    def test_cache_tokens_fall_back_to_the_standard_field_only(self):
        """多字段是产品特例：未单独登记的产品只查标准名，不跟着别家的拼写一起放大查询。"""
        query = make_query(records=[{"_result_": 0}])

        with patch_llm_metric_group(query, product="agentlens"):
            CalculateByRangeResource().request({**LLM_METRIC_REQUEST, "cal_type": "cache_tokens", "group_by": []})

        self.assertEqual(
            aggregate_call(query)[0],
            [
                "attributes.gen_ai.usage.cache_read.input_tokens",
                "attributes.gen_ai.usage.cache_write.input_tokens",
            ],
        )

    def test_group_by_model_queries_product_field_and_returns_standard_name(self):
        """该产品未上报 response.model，但返回给前端的维度名仍是请求方传入的标准名。"""
        query = make_query(
            records=[
                {"attributes.gen_ai.request.model": "kimi-k3", "_result_": 2560.5, "_time_": 1700003600000},
                {"attributes.gen_ai.request.model": "claude-opus-5", "_result_": 13042.0, "_time_": 1700003600000},
            ]
        )

        with patch_llm_metric_group(query, product="galileo"):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "duration", "group_by": ["gen_ai.response.model"]}
            )

        self.assertEqual(aggregate_call(query)[2], ["attributes.gen_ai.request.model"])
        self.assertEqual(
            [(record["dimensions"]["gen_ai.response.model"], record["0s"]) for record in result["data"]],
            [("claude-opus-5", 13042.0), ("kimi-k3", 2560.5)],
        )

    def test_langfuse_aggregates_usage_details_locally(self):
        """usage_details 是 keyword 类型的 JSON 串，存储侧聚合不了，只能取回本地算。"""
        query = make_query()
        query.query_field_values.return_value = [
            {
                "attributes.langfuse.observation.usage_details": (
                    '{"input": 0, "output": 38, "cache_read_input_tokens": 12, "cache_creation_input_tokens": 1672}'
                )
            },
            {"attributes.langfuse.observation.usage_details": '{"input": 5, "output": 7}'},
            {"attributes.langfuse.observation.usage_details": None},
        ]

        with patch_llm_metric_group(query, product="langfuse"):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "group_by": []}
            )

        # 该产品的 input 恒为 0，真实输入量需要把缓存部分加回来才与其他产品口径一致
        self.assertEqual(result["data"][0]["0s"], 1689)
        query.query_field_aggregated_group.assert_not_called()
        self.assertEqual(fetched_fields(query), ["attributes.langfuse.observation.usage_details"])

    def test_returns_time_shift_and_growth_rate(self):
        query = make_query()
        query.query_field_aggregated_group.side_effect = lambda queries, start_time, *args: (
            [{"_result_": 100 if start_time == LLM_METRIC_REQUEST["start_time"] else 80}]
        )

        with patch_llm_metric_group(query):
            result = CalculateByRangeResource().request(
                {
                    **LLM_METRIC_REQUEST,
                    "cal_type": "model_call_count",
                    "group_by": [],
                    "baseline": "0s",
                    "time_shifts": ["0s", "1d"],
                }
            )

        record = result["data"][0]
        self.assertEqual(set(record), {"dimensions", "0s", "1d", "growth_rates"})
        self.assertEqual((record["0s"], record["1d"]), (100, 80))
        self.assertEqual(record["growth_rates"]["0s"], 0)
        self.assertAlmostEqual(record["growth_rates"]["1d"], 25, delta=0.01)

    def test_rejects_more_than_two_comparison_time_shifts(self):
        serializer = CalculateByRangeResource.RequestSerializer(
            data={**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "time_shifts": ["1h", "1d", "1w"]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("最多支持两次时间对比", str(serializer.errors))

    def test_rejects_baseline_not_in_time_shifts(self):
        serializer = CalculateByRangeResource.RequestSerializer(
            data={**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "baseline": "1d"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("baseline 必须包含在 time_shifts 中", str(serializer.errors))


class TimeSeriesResourceTestCase(TestCase):
    def test_accepts_metrics_required_by_overview_page(self):
        fields = TimeSeriesResource.RequestSerializer().fields

        self.assertEqual(set(fields["cal_type"].choices), CAL_TYPE_CHOICES)

    def test_interval_widens_with_the_time_range(self):
        """固定 60s 出图时，时间范围拉长后数据点过密。"""
        intervals = []
        for end_time in (1700003600, 1700000000 + 86400 * 7):
            serializer = TimeSeriesResource.RequestSerializer(
                data={**LLM_METRIC_REQUEST, "end_time": end_time, "cal_type": "input_tokens"}
            )
            serializer.is_valid(raise_exception=True)
            intervals.append(serializer.validated_data["interval"])

        self.assertEqual(intervals, [60, 7200])

    def test_explicit_interval_is_kept(self):
        serializer = TimeSeriesResource.RequestSerializer(
            data={**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "interval": 300}
        )
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["interval"], 300)

    def test_operation_count_series_uses_query_scope_without_layer_filter(self):
        query = make_query()
        grafana = mock.Mock()
        grafana.grafana.graph_unify_query.return_value = {"series": [{"datapoints": [[12, 1700000000000]]}]}
        with patch_llm_metric_group(query), mock.patch(f"{GROUP_MODULE}.resource", grafana):
            result = TimeSeriesResource().request({**LLM_METRIC_REQUEST, "cal_type": "operation_count"})

        self.assertEqual(result["series"][0]["datapoints"], [[12, 1700000000000]])
        self.assertEqual(layer_query(query), Q())
        self.assertEqual(query.query_field_graph_config.call_args.args[3:5], (["_index"], "COUNT"))

    def test_operation_count_series_maps_and_drops_empty_names(self):
        query = make_query()
        grafana = mock.Mock()
        grafana.grafana.graph_unify_query.return_value = {
            "series": [
                {"dimensions": {"attributes.llm.request.type": ""}, "datapoints": [[100, 1700000000000]]},
                {"dimensions": {"attributes.llm.request.type": "completion"}, "datapoints": [[5, 1700000000000]]},
                {"dimensions": {"attributes.llm.request.type": "chat"}, "datapoints": [[20, 1700000000000]]},
            ]
        }
        with patch_llm_metric_group(query, product="aidev"), mock.patch(f"{GROUP_MODULE}.resource", grafana):
            result = TimeSeriesResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "operation_count", "group_by": ["gen_ai.operation.name"]}
            )

        self.assertEqual(
            [(item["dimensions"]["gen_ai.operation.name"], item["datapoints"]) for item in result["series"]],
            [
                ("text_completion", [[5, 1700000000000]]),
                ("chat", [[20, 1700000000000]]),
            ],
        )

    def test_input_tokens_series_delegates_to_graph_unify_query(self):
        query = make_query()
        query.query_field_graph_config.return_value = mock.sentinel.config
        datapoints = [[10, 1700000000000], [20, 1700001800000]]

        grafana = mock.Mock()
        grafana.grafana.graph_unify_query.return_value = {"series": [{"datapoints": datapoints}], "unit": "short"}
        with patch_llm_metric_group(query), mock.patch(f"{GROUP_MODULE}.resource", grafana):
            result = TimeSeriesResource().request({**LLM_METRIC_REQUEST, "cal_type": "input_tokens", "group_by": []})

        self.assertEqual(result["series"], [{"datapoints": datapoints, "dimensions": {}, "target": ""}])
        self.assertEqual(result["unit"], "short")
        # 前端按「数据步长」展示聚合周期
        self.assertEqual(result["query_config"], {"interval": 60})
        grafana.grafana.graph_unify_query.assert_called_once_with(mock.sentinel.config)
        self.assertEqual(query.query_field_graph_config.call_args.args[5], 60)

    def test_total_tokens_is_summed_in_storage_not_in_saas(self):
        """两个字段一次查询，由存储侧按表达式相加，SaaS 侧不做逐点累加。"""
        query = make_query()
        query.query_field_graph_config.return_value = mock.sentinel.config

        grafana = mock.Mock()
        grafana.grafana.graph_unify_query.return_value = {
            "series": [{"datapoints": [[107, 1700000000000], [200, 1700001800000]]}]
        }
        with patch_llm_metric_group(query), mock.patch(f"{GROUP_MODULE}.resource", grafana):
            result = TimeSeriesResource().request({**LLM_METRIC_REQUEST, "cal_type": "total_tokens", "group_by": []})

        self.assertEqual(
            result["series"],
            [{"datapoints": [[107, 1700000000000], [200, 1700001800000]], "dimensions": {}, "target": ""}],
        )
        grafana.grafana.graph_unify_query.assert_called_once_with(mock.sentinel.config)
        self.assertEqual(
            query.query_field_graph_config.call_args.args[3],
            ["attributes.gen_ai.usage.input_tokens", "attributes.gen_ai.usage.output_tokens"],
        )

    def test_group_by_returns_standard_dimension_name(self):
        query = make_query()

        grafana = mock.Mock()
        grafana.grafana.graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"attributes.gen_ai.request.model": "kimi-k3"},
                    "datapoints": [[5, 1700000000000]],
                }
            ]
        }
        with (
            patch_llm_metric_group(query, product="galileo"),
            mock.patch(f"{GROUP_MODULE}.resource", grafana),
        ):
            result = TimeSeriesResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "duration", "group_by": ["gen_ai.response.model"]}
            )

        self.assertEqual(
            result["series"],
            [
                {
                    "datapoints": [[5, 1700000000000]],
                    "dimensions": {"gen_ai.response.model": "kimi-k3"},
                    "target": "kimi-k3",
                }
            ],
        )

    def test_langfuse_series_buckets_locally_by_span_start_time(self):
        query = make_query()
        query.query_field_values.return_value = [
            {"attributes.langfuse.observation.usage_details": '{"output": 3}', "start_time": 1700000000_000000},
            {"attributes.langfuse.observation.usage_details": '{"output": 4}', "start_time": 1700000030_000000},
            {"attributes.langfuse.observation.usage_details": '{"output": 5}', "start_time": 1700000200_000000},
        ]

        with patch_llm_metric_group(query, product="langfuse"):
            result = TimeSeriesResource().request({**LLM_METRIC_REQUEST, "cal_type": "output_tokens", "group_by": []})

        datapoints = result["series"][0]["datapoints"]
        timestamps = [timestamp for _, timestamp in datapoints]
        # 一小时窗口的桶宽为 60s，前两条落在同一个桶里
        self.assertEqual([point for point in datapoints if point[0]], [[7.0, 1699999980000], [5.0, 1700000160000]])
        # 空桶补零，曲线不会退化成零星几个点
        self.assertEqual(timestamps, list(range(timestamps[0], timestamps[-1] + 60_000, 60_000)))
        self.assertIn("start_time", fetched_fields(query))
        # 本地聚合与下推出图回传同一个聚合周期
        self.assertEqual(result["query_config"], {"interval": 60})


class LLMQueryTestCase(TestCase):
    """查询层的通用聚合能力。"""

    @staticmethod
    def _query():
        return LLMQuery([mock.Mock(retention=7)])

    def test_single_field_needs_no_expression(self):
        self.assertEqual(LLMQuery._sum_expression(["attributes.gen_ai.usage.input_tokens"]), "q0")

    def test_sum_expression_keeps_dimensions_present_on_only_one_side(self):
        """`q0 + q1` 会因为维度取交集而丢掉只有一侧有数据的维度，缺失的一侧要补成 0。"""
        self.assertEqual(LLMQuery._sum_expression(["input", "output"]), "(q0 or q1 * 0) + (q1 or q0 * 0)")

    def test_metric_alias_never_occurs_inside_field_names(self):
        """grafana 把别名当普通子串替换成「方法(字段)」生成图例，别名撞进字段名会把图例替换到爆炸。"""
        expression: str = LLMQuery._sum_expression(["attributes.gen_ai.usage.cache_read.input_tokens"] * 5)
        rendered: str = expression
        for alias in LLMQuery.METRIC_ALIASES[:5]:
            rendered = rendered.replace(alias, "SUM(attributes.gen_ai.usage.cache_read.input_tokens)")

        self.assertNotIn("SUM(SUM(", rendered)
        self.assertEqual(rendered.count("SUM("), expression.count("q"))

    def test_ungrouped_single_field_uses_scalar_aggregation(self):
        """标量聚合额外处理了多结果表下 DISTINCT 的枚举合并去重，分组查询替代不了。"""
        queries = [mock.sentinel.query]

        with mock.patch.object(LLMQuery, "_query_field_aggregated_value", return_value=27) as aggregated_value:
            records = self._query().query_field_aggregated_group(queries, 1, 2, ["trace_id"], "DISTINCT")

        self.assertEqual(records, [{"_result_": 27}])
        aggregated_value.assert_called_once_with(queries, 1, 2, "trace_id", "DISTINCT")

    def test_field_values_flatten_nested_records(self):
        """存储把 `attributes.x.y` 嵌在 attributes 字典里返回，按扁平键直接取会全部取空。"""
        nested = [{"attributes": {"langfuse.observation.usage_details": '{"output": 3}'}, "start_time": 17}]

        with mock.patch.object(LLMQuery, "_query_list", return_value=nested):
            records = self._query().query_field_values(
                [mock.Mock()], 1, 2, ["attributes.langfuse.observation.usage_details", "start_time"]
            )

        self.assertEqual(
            records, [{"attributes.langfuse.observation.usage_details": '{"output": 3}', "start_time": 17}]
        )

    def test_graph_config_exports_seconds_for_grafana(self):
        added = mock.Mock(config={"start_time": 1700000000000, "end_time": 1700003600000})

        with (
            mock.patch.object(LLMQuery, "get_qs"),
            mock.patch.object(LLMQuery, "_add_query", return_value=added),
        ):
            config = self._query().query_field_graph_config([mock.Mock()], 1700000000, 1700003600, ["field"], "SUM", 60)

        self.assertEqual((config["start_time"], config["end_time"]), (1700000000, 1700003600))
        self.assertTrue(config["null_as_zero"])
        self.assertEqual(config["query_method"], "query_reference")

    def test_graph_config_pushes_interval_down_to_each_metric_query(self):
        """不下发 interval 时 grafana 按采集周期自动取点，时间范围拉长后数据点过密。"""
        query = mock.Mock()
        metric_query = query.alias.return_value.metric.return_value.group_by.return_value
        added = mock.Mock(config={"start_time": 0, "end_time": 0})

        with (
            mock.patch.object(LLMQuery, "get_qs"),
            mock.patch.object(LLMQuery, "_add_query", return_value=added) as add_query,
        ):
            self._query().query_field_graph_config([query], 1, 2, ["input", "output"], "SUM", 600)

        metric_query.interval.assert_has_calls([mock.call(600), mock.call(600)])
        self.assertEqual(add_query.call_args.args[1], [metric_query.interval.return_value] * 2)

    def test_graph_config_limits_series_when_grouped(self):
        qs = mock.Mock()
        added = mock.Mock(config={"start_time": 0, "end_time": 0})

        with (
            mock.patch.object(LLMQuery, "get_qs", return_value=qs),
            mock.patch.object(LLMQuery, "_add_query", return_value=added),
        ):
            self._query().query_field_graph_config([mock.Mock()], 1, 2, ["input", "output"], "SUM", 60, ["model"])

        self.assertEqual(qs.expression.call_args.args[0], "topk(20, (q0 or q1 * 0) + (q1 or q0 * 0))")
