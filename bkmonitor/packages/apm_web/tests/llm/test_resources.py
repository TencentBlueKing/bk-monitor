import contextlib
from threading import Barrier, get_ident
from unittest import TestCase, mock

from django.db.models import Q
from django.test import override_settings

from apm_web.handlers.metric_group.define import CalculationType as MetricCalculationType
from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import AGENT_CANDIDATE_Q, SPAN_TYPES, operation_query, resolve_query_fields
from apm_web.llm.builders.flow import FlowBuilder
from apm_web.llm.builders.summary import TraceSummary
from apm_web.llm.constants import CalculationType
from apm_web.llm.metric_group import LLMMetricGroup
from apm_web.llm.query import LLMQuery
from apm_web.llm.resources import (
    CalculateByRangeResource,
    ListFlowsResource,
    ListSpansResource,
    ListTracesResource,
    TokenStatisticsResource,
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
            "galileo": "attributes.gen_ai.conversation.id",
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
                "user_id": "user-2",
            },
        ]
        span_query.query_trace_preview.return_value = raw_spans
        span_query.query_trace_errors.return_value = [
            {"trace_id": span["trace_id"], "status": {"code": 2}} for span in raw_spans if span["status"]["code"] == 2
        ]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "agentlens"}

        with (
            mock.patch(
                "apm_web.llm.resources.LLMMetricGroup.handle",
                side_effect=lambda calculation_type: [
                    {"trace_id": "trace-1", "_result_": 10 if calculation_type == "input_tokens" else 4},
                    {"trace_id": "trace-2", "_result_": 20 if calculation_type == "input_tokens" else 8},
                ],
            ),
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
        self.assertCountEqual(
            span_query.query_trace_preview.call_args_list,
            [
                mock.call(
                    ["trace-2", "trace-1"],
                    extra_filter=operation_query(
                        "agentlens", [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}]
                    ),
                    sort=["start_time asc"],
                ),
                mock.call(
                    ["trace-2", "trace-1"],
                    extra_filter=operation_query(
                        "agentlens", [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}]
                    ),
                    sort=["end_time desc"],
                ),
            ],
        )
        span_query.iter_by_group_ids.assert_not_called()
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
                "user_id": "",
            },
        ]
        span_query.query_trace_preview.return_value = raw_spans
        span_query.query_trace_errors.return_value = [
            {"trace_id": span["trace_id"], "status": {"code": 2}} for span in raw_spans if span["status"]["code"] == 2
        ]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "aidev"}

        with (
            mock.patch(
                "apm_web.llm.resources.LLMMetricGroup.handle",
                side_effect=lambda calculation_type: [
                    {"trace_id": "trace-1", "_result_": 5 if calculation_type == "input_tokens" else 2},
                    {"trace_id": "trace-2", "_result_": 10 if calculation_type == "input_tokens" else 4},
                    {"trace_id": "trace-3", "_result_": 20 if calculation_type == "input_tokens" else 8},
                ],
            ),
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
        self.assertCountEqual(
            span_query.query_trace_preview.call_args_list,
            [
                mock.call(
                    ["trace-2", "trace-3", "trace-1"],
                    extra_filter=operation_query(
                        "aidev", [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}]
                    ),
                    sort=["start_time asc"],
                ),
                mock.call(
                    ["trace-2", "trace-3", "trace-1"],
                    extra_filter=operation_query(
                        "aidev", [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}]
                    ),
                    sort=["end_time desc"],
                ),
            ],
        )
        span_query.iter_by_group_ids.assert_not_called()
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

    def test_input_and_output_queries_returning_same_span_are_deduplicated(self):
        base = {
            "trace_id": "trace-1",
            "span_id": "root",
            "parent_span_id": "",
            "span_name": "invoke_agent",
            "start_time": 100,
            "end_time": 200,
            "elapsed_time": 100,
            "resource": {"service.name": "agent-service"},
            "status": {"code": 1},
        }
        query = mock.Mock()
        query.query_group_list.return_value = ["trace-1"]
        query.query_group_trace_list.return_value = [{"trace_id": "trace-1"}]
        query.query_trace_errors.return_value = []

        span = {
            **base,
            "attributes": {
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "input"}]}],
                "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "output"}]}],
            },
        }
        query.query_trace_preview.return_value = [span]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        with (
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.get_query", return_value=query),
            mock.patch("apm_web.llm.resources.LLMMetricGroup.handle", return_value=[]),
            mock.patch("apm_web.llm.resources.adapt_spans", wraps=adapt_spans) as adapt,
        ):
            item = ListTracesResource().request(LLM_METRIC_REQUEST)["items"][0]
        self.assertEqual((item["input"], item["output"]), ("input", "output"))
        adapt.assert_called_once_with([span], entity_set)

    def test_trace_items_query_only_requested_calculation_types(self):
        query = mock.Mock()
        query.query_trace_preview.return_value = [{"trace_id": "trace-1", "span_id": "span-1"}]
        query.query_trace_errors.return_value = []
        cases = (
            ((), {}),
            ((CalculationType.CACHE_READ_INPUT_TOKENS,) * 2, {"cache_read_input_tokens": 7}),
            ((CalculationType.CACHE_WRITE_INPUT_TOKENS,), {"cache_write_input_tokens": 0}),
        )
        for cal_types, expected in cases:
            with (
                self.subTest(cal_types=cal_types),
                mock.patch("apm_web.llm.resources.adapt_spans", return_value=[]),
                mock.patch(
                    "apm_web.llm.resources.LLMMetricGroup.handle",
                    side_effect=lambda cal_type: (
                        [{"trace_id": "trace-1", "_result_": 7}] if cal_type == "cache_read_input_tokens" else []
                    ),
                ) as handle,
            ):
                items = list(
                    ListTracesResource.iter_trace_items(
                        bk_biz_id=11,
                        app_name="demo",
                        span_query=query,
                        entity_set=mock.Mock(),
                        trace_ids=["trace-1"],
                        product="default",
                        cal_types=cal_types,
                    )
                )
                self.assertCountEqual(handle.call_args_list, [mock.call(name) for name in expected])
                self.assertEqual(
                    {name: value for name, value in items[0].items() if name.endswith("_tokens")},
                    {"input_tokens": 0, "output_tokens": 0, **expected},
                )

    def test_five_queries_run_concurrently_and_propagate_failures(self):
        for failure in (None, "token", "errors"):
            with self.subTest(failure=failure):
                barrier = Barrier(5, timeout=5)
                workers = set()

                def wait(result):
                    workers.add(get_ident())
                    barrier.wait()
                    return result

                query = mock.Mock()
                query.query_group_list.return_value = ["trace-1"]
                query.query_group_trace_list.return_value = [{"trace_id": "trace-1"}]
                query.query_trace_preview.side_effect = lambda *args, **kwargs: wait([])

                def tokens(calculation_type):
                    wait([])
                    if failure == "token" and calculation_type == "output_tokens":
                        raise RuntimeError("query failed")
                    return []

                def errors(*args):
                    wait([])
                    if failure == "errors":
                        raise RuntimeError("query failed")
                    return []

                query.query_trace_errors.side_effect = errors
                entity_set = mock.Mock(service_names=["agent-service"])
                entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
                with (
                    mock.patch("apm_web.llm.resources.Application.objects.get"),
                    mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
                    mock.patch("apm_web.llm.resources.get_query", return_value=query),
                    mock.patch("apm_web.llm.resources.LLMMetricGroup.handle", side_effect=tokens),
                ):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, "query failed"):
                            ListTracesResource().perform_request(
                                {
                                    **LLM_METRIC_REQUEST,
                                    "group_field": "trace_id",
                                    "offset": 0,
                                    "limit": 20,
                                    "keyword": "",
                                }
                            )
                    else:
                        self.assertEqual(ListTracesResource().request(LLM_METRIC_REQUEST)["items"], [])
                self.assertEqual(len(workers), 5)
                query.iter_by_group_ids.assert_not_called()

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
        standard_attributes: dict[str, str] = {"gen_ai.operation.name": "invoke_agent"}
        for product, field, span_name, attributes in [
            ("default", "gen_ai.conversation.id", "invoke_agent demo", standard_attributes),
            ("agentlens", "gen_ai.session.id", "invoke_agent demo", standard_attributes),
            # AIDev 标准语义与存量语义分别构造，避免混用两套字段。
            ("aidev", "gen_ai.conversation.id", "invoke_agent demo", standard_attributes),
            ("aidev", "agent.session.session_code", "agent.execution", {}),
            ("galileo", "gen_ai.conversation.id", "invoke_agent demo", standard_attributes),
            ("langfuse", "session.id", "invoke_agent demo", standard_attributes),
        ]:
            with self.subTest(product=product, field=field):
                entity_set = mock.Mock(service_names=["agent-service"])
                entity_set.get_system.return_value = {"is_support_llm": True, "product": product}
                raw_spans = [
                    {
                        "trace_id": "trace-1",
                        "span_id": f"span-{start_time}",
                        "parent_span_id": "" if start_time == 100 else "span-100",
                        "span_name": span_name,
                        "start_time": start_time,
                        "end_time": start_time + 10,
                        "elapsed_time": 10,
                        "status": {"code": 1},
                        "resource": {"service.name": "agent-service"},
                        "attributes": {**attributes, field: value},
                        "events": [],
                    }
                    for start_time, value in [(300, "conversation-later"), (100, ""), (200, "conversation-first")]
                ]

                item = TraceSummary.build(
                    "trace-1", raw_spans, adapt_spans(raw_spans, entity_set), {"input_tokens": 10}
                )

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
                trace_item = TraceSummary.build(
                    "trace-1",
                    [child, root],
                    adapt_spans([child, root], entity_set),
                    {"input_tokens": 10, "output_tokens": 3},
                )
                items = ListTracesResource._assemble_group_items(group_field, [group_id], {group_id: [trace_item]})

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

    def test_trace_status_uses_error_query_result(self):
        raw_spans = [{"trace_id": "trace-1", "status": {"code": 2}}]
        for has_error in (False, True):
            item = TraceSummary.build("trace-1", raw_spans, [], {}, has_error=has_error)
            self.assertEqual(item["status"], "error" if has_error else "success")

    def test_trace_time_uses_preview_bounds_without_root_preference(self):
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
                "start_time": 50,
                "end_time": 350,
                "status": {"code": 1},
            },
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "start_time": 50,
                "end_time": 200,
                "attributes": {},
            }
        ]

        item = TraceSummary.build("trace-1", raw_spans, converted_spans, {})

        self.assertEqual(item["start_time"], 50)
        self.assertEqual(item["end_time"], 350)
        self.assertEqual(item["elapsed_time"], 300)

    def test_trace_time_uses_earliest_and_latest_preview(self):
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

        item = TraceSummary.build("trace-1", raw_spans, [], {})

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

        item = TraceSummary.build("trace-1", raw_spans, converted_spans, {})

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

        item = TraceSummary.build("trace-1", raw_spans, converted_spans, {})

        self.assertEqual(item["input"], "内部提示词")
        self.assertEqual(item["output"], "内部回答")

    def test_trace_preview_output_priority_is_text_then_reasoning_then_tool_call_then_result(self):
        raw_spans = [{"trace_id": "trace-1", "span_id": "root", "parent_span_id": "", "status": {"code": 1}}]

        def item_for(converted_spans):
            return TraceSummary.build("trace-1", raw_spans, converted_spans, {})

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

        tool_arguments = TraceSummary._preview_text({"path": "/tmp/a"})
        self.assertEqual(item_for([tool_span])["input"], tool_arguments)
        self.assertEqual(item_for([tool_span])["output"], TraceSummary._preview_text({"ok": True}))
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
    def setUp(self):
        self.enterContext(override_settings(LLM_BIZ_LIST=[11]))

    def test_disabled_grayscale_skips_topology_and_span_queries(self):
        for biz_list in ([], [22]):
            for group_field in ("trace_id", "attributes.gen_ai.conversation.id"):
                with (
                    self.subTest(biz_list=biz_list, group_field=group_field),
                    override_settings(LLM_BIZ_LIST=biz_list),
                    mock.patch("apm_web.llm.resources.EntitySet") as entity_set,
                    mock.patch("apm_web.llm.resources.Application.objects.get") as application,
                    mock.patch("apm_web.llm.resources.get_query") as get_query,
                ):
                    result = ListFlowsResource().request(
                        {"bk_biz_id": 11, "app_name": "demo", "group_field": group_field, "group_id": "group-1"}
                    )
                    self.assertEqual(result, {"traces": []})
                    entity_set.assert_not_called()
                    application.assert_not_called()
                    get_query.assert_not_called()

    def test_no_llm_service_skips_span_queries(self):
        for service_names in ([], ["web-service"]):
            entity_set = mock.Mock(service_names=service_names)
            entity_set.get_system.return_value = {"is_support_llm": False}
            for group_field in ("trace_id", "attributes.gen_ai.conversation.id"):
                with (
                    self.subTest(service_names=service_names, group_field=group_field),
                    mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
                    mock.patch("apm_web.llm.resources.get_query") as get_query,
                    mock.patch("apm_web.llm.resources.Application.objects.get") as application,
                ):
                    result = ListFlowsResource().request(
                        {"bk_biz_id": 11, "app_name": "demo", "group_field": group_field, "group_id": "group-1"}
                    )
                    self.assertEqual(result["traces"], [])
                    get_query.assert_not_called()
                    application.assert_not_called()

    def test_empty_flow_returns_only_traces_without_building_summary(self):
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        span_query = mock.Mock()
        span_query.query_by_group_ids.return_value = [
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "span_name": "framework",
                "start_time": 1,
                "end_time": 2,
                "resource": {"service.name": "agent-service"},
                "attributes": {},
            }
        ]
        with (
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.TraceSummary.build") as summary,
        ):
            result = ListFlowsResource().request(
                {"bk_biz_id": 11, "app_name": "demo", "group_field": "trace_id", "group_id": "trace-1"}
            )
        self.assertEqual(result, {"traces": []})
        summary.assert_not_called()

    @override_settings(LLM_BIZ_LIST=[0])
    def test_flow_summary_uses_all_spans_and_counts_only_llm_tokens(self):
        def span(span_id, parent_span_id, start_time, end_time, attributes, status=1):
            return {
                "trace_id": "trace-1",
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "span_name": span_id,
                "start_time": start_time,
                "end_time": end_time,
                "elapsed_time": end_time - start_time,
                "attributes": attributes,
                "status": {"code": status},
                "resource": {"service.name": "agent-service"},
            }

        raw_spans = [
            span("framework", "upstream", 10, 500, {}, status=2),
            span(
                "agent",
                "framework",
                100,
                400,
                {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.conversation.id": "session-1",
                    "user.id": "user-1",
                    "gen_ai.usage.input_tokens": 999,
                    "gen_ai.usage.output_tokens": 999,
                    "gen_ai.usage.cache_read.input_tokens": 999,
                    "gen_ai.usage.cache_write.input_tokens": 999,
                },
            ),
            span(
                "first",
                "agent",
                110,
                200,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "question"}]}],
                    "gen_ai.usage.input_tokens": 10,
                    "gen_ai.usage.output_tokens": 3,
                    "gen_ai.usage.cache_read.input_tokens": 2,
                },
            ),
            span(
                "last",
                "another-upstream",
                210,
                300,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}],
                    "gen_ai.usage.input_tokens": 20,
                    "gen_ai.usage.output_tokens": 7,
                    "gen_ai.usage.cache_write.input_tokens": 4,
                },
            ),
        ]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        span_query = mock.Mock()
        span_query.query_by_group_ids.return_value = list(reversed(raw_spans))
        with (
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "demo",
                    "group_field": "trace_id",
                    "group_id": "trace-1",
                }
            )
        trace = result["traces"][0]
        flow = trace.pop("flow")
        self.assertEqual(
            trace,
            {
                "group_id": "trace-1",
                "group_field": "trace_id",
                "trace_id": "trace-1",
                "conversation_id": "session-1",
                "user_id": "user-1",
                "status": "error",
                "input": "question",
                "output": "answer",
                "input_tokens": 30,
                "output_tokens": 10,
                "total_tokens": 40,
                "cache_read_input_tokens": 2,
                "cache_write_input_tokens": 4,
                "start_time": 10,
                "end_time": 500,
                "elapsed_time": 490,
            },
        )
        self.assertEqual(
            trace,
            TraceSummary.build(
                "trace-1",
                raw_spans,
                adapt_spans(raw_spans, entity_set),
                {
                    "input_tokens": 30,
                    "output_tokens": 10,
                    "total_tokens": 40,
                    "cache_read_input_tokens": 2,
                    "cache_write_input_tokens": 4,
                },
                has_error=True,
            ),
        )
        self.assertEqual([node["span_id"] for node in flow], ["agent", "last"])
        for name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_read_input_tokens",
            "cache_write_input_tokens",
            "start_time",
            "end_time",
            "elapsed_time",
        ):
            self.assertEqual(result[name], trace[name])
        self.assertEqual(flow[0]["attributes"]["gen_ai.usage.input_tokens"], 999)

    def test_forest_orders_projected_siblings_by_time(self):
        raw_spans = [
            {"span_id": "late-root", "parent_span_id": "external", "start_time": 400},
            {"span_id": "bridge", "parent_span_id": "early-root", "start_time": 110},
            {"span_id": "late-child", "parent_span_id": "bridge", "start_time": 300},
            {"span_id": "early-child", "parent_span_id": "early-root", "start_time": 200},
            {"span_id": "early-root", "parent_span_id": "external", "start_time": 100},
        ]
        spans = [span for span in raw_spans if span["span_id"] != "bridge"]
        builder = FlowBuilder(raw_spans, spans)
        for _ in range(2):
            flow = builder.build()
            self.assertEqual([node["span_id"] for node in flow], ["early-root", "late-root"])
            self.assertEqual([node["span_id"] for node in flow[0]["childs"]], ["early-child", "late-child"])
        self.assertNotIn("childs", spans[0])

    def test_flow_tokens_ignore_non_llm_and_invalid_token_values(self):
        spans = [
            {"span_type": "AGENT", "attributes": {"gen_ai.usage.input_tokens": 999}},
            {"span_type": "TOOL", "attributes": {"gen_ai.usage.input_tokens": 999}},
            {"span_type": "LLM", "attributes": {"gen_ai.usage.input_tokens": True, "gen_ai.usage.output_tokens": "9"}},
            {"span_type": "LLM", "attributes": {"gen_ai.usage.input_tokens": 0, "gen_ai.usage.output_tokens": 3}},
        ]
        self.assertEqual(
            FlowBuilder([], spans).tokens,
            {
                "input_tokens": 0,
                "output_tokens": 3,
                "total_tokens": 3,
                "cache_read_input_tokens": 0,
                "cache_write_input_tokens": 0,
            },
        )

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
        flattened_flow = flatten(flow)
        self.assertEqual(spans_result["total"], 4)
        self.assertEqual(flattened_flow[1:], spans[1:])
        self.assertEqual(
            {
                key: value
                for key, value in flattened_flow[0]["attributes"].items()
                if not key.startswith("gen_ai.usage.")
            },
            spans[0]["attributes"],
        )
        self.assertEqual(flattened_flow[0]["attributes"]["gen_ai.usage.input_tokens"], 300)
        self.assertEqual(flattened_flow[0]["attributes"]["gen_ai.usage.output_tokens"], 116)
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

        flow = FlowBuilder(raw_spans, [raw_spans[0], raw_spans[2]]).build()

        self.assertEqual([span["span_id"] for span in flow], ["agent"])
        self.assertEqual([span["span_id"] for span in flow[0]["childs"]], ["tool"])
        self.assertEqual(flow[0]["childs"][0]["parent_span_id"], "framework")

    def test_flow_builder_fills_agent_tokens_from_llm_descendants(self):
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "agent", "parent_span_id": "", "start_time": 100},
            {"trace_id": "trace-1", "span_id": "framework", "parent_span_id": "agent", "start_time": 110},
            {"trace_id": "trace-1", "span_id": "llm-1", "parent_span_id": "framework", "start_time": 120},
            {"trace_id": "trace-1", "span_id": "llm-2", "parent_span_id": "agent", "start_time": 130},
        ]
        spans = [
            {
                **raw_spans[0],
                "span_type": "AGENT",
                "attributes": {"gen_ai.operation.name": "invoke_agent"},
            },
            {
                **raw_spans[2],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 10,
                    "gen_ai.usage.output_tokens": 3,
                    "gen_ai.usage.cache_read.input_tokens": 2,
                },
            },
            {
                **raw_spans[3],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 20,
                    "gen_ai.usage.output_tokens": 7,
                    "gen_ai.usage.cache_write.input_tokens": 4,
                },
            },
        ]

        builder = FlowBuilder(raw_spans, spans)
        flow = builder.build()

        self.assertEqual(
            builder.statistics["agent"],
            {
                "input_tokens": 30,
                "output_tokens": 10,
                "total_tokens": 40,
                "cache_read_input_tokens": 2,
                "cache_write_input_tokens": 4,
            },
        )
        self.assertEqual(
            {key: value for key, value in flow[0]["attributes"].items() if key.startswith("gen_ai.usage.")},
            {
                "gen_ai.usage.input_tokens": 30,
                "gen_ai.usage.output_tokens": 10,
                "gen_ai.usage.cache_read.input_tokens": 2,
                "gen_ai.usage.cache_write.input_tokens": 4,
            },
        )
        self.assertNotIn("gen_ai.usage.input_tokens", spans[0]["attributes"])

    def test_flow_builder_prefers_nested_agent_reported_tokens(self):
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "outer", "parent_span_id": "", "start_time": 100},
            {"trace_id": "trace-1", "span_id": "inner", "parent_span_id": "outer", "start_time": 110},
            {"trace_id": "trace-1", "span_id": "llm", "parent_span_id": "inner", "start_time": 120},
        ]
        spans = [
            {
                **raw_spans[0],
                "span_type": "AGENT",
                "attributes": {"gen_ai.operation.name": "invoke_workflow"},
            },
            {
                **raw_spans[1],
                "span_type": "AGENT",
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.usage.input_tokens": 100,
                    "gen_ai.usage.output_tokens": 50,
                },
            },
            {
                **raw_spans[2],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 60,
                    "gen_ai.usage.output_tokens": 20,
                },
            },
        ]

        builder = FlowBuilder(raw_spans, spans)
        builder.build()

        self.assertEqual(
            builder.statistics["outer"],
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "cache_read_input_tokens": 0,
                "cache_write_input_tokens": 0,
            },
        )

    def test_flow_builder_keeps_agent_reported_cache_and_backfills_other_fields(self):
        """Agent 只报缓存、未报输入输出时，缓存不被子树统计覆盖。"""
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "agent", "parent_span_id": "", "start_time": 100},
            {"trace_id": "trace-1", "span_id": "llm", "parent_span_id": "agent", "start_time": 110},
        ]
        spans = [
            {
                **raw_spans[0],
                "span_type": "AGENT",
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.usage.cache_read.input_tokens": 80,
                },
            },
            {
                **raw_spans[1],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 100,
                    "gen_ai.usage.output_tokens": 20,
                },
            },
        ]

        builder = FlowBuilder(raw_spans, spans)
        builder.build()

        self.assertEqual(
            builder.statistics["agent"],
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "cache_read_input_tokens": 80,
                "cache_write_input_tokens": 0,
            },
        )

    def test_flow_builder_keeps_descendant_cache_when_agent_reports_usage(self):
        """Agent 只报输入输出时，缺失的缓存字段仍由子树回填。"""
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "agent", "parent_span_id": "", "start_time": 100},
            {"trace_id": "trace-1", "span_id": "llm", "parent_span_id": "agent", "start_time": 110},
        ]
        spans = [
            {
                **raw_spans[0],
                "span_type": "AGENT",
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.usage.input_tokens": 100,
                    "gen_ai.usage.output_tokens": 20,
                },
            },
            {
                **raw_spans[1],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 60,
                    "gen_ai.usage.output_tokens": 20,
                    "gen_ai.usage.cache_read.input_tokens": 30,
                    "gen_ai.usage.cache_write.input_tokens": 5,
                },
            },
        ]

        builder = FlowBuilder(raw_spans, spans)
        flow = builder.build()

        self.assertEqual(
            builder.statistics["agent"],
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "cache_read_input_tokens": 30,
                "cache_write_input_tokens": 5,
            },
        )
        # 回填只补缺失字段，已上报的输入输出保持原值并写入节点属性
        self.assertEqual(flow[0]["attributes"]["gen_ai.usage.input_tokens"], 100)
        self.assertEqual(flow[0]["attributes"]["gen_ai.usage.cache_read.input_tokens"], 30)

    def test_flow_builder_keeps_explicit_zero_reported_by_agent(self):
        """Agent 显式上报 0 属有效值，不再用子树统计覆盖。"""
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "agent", "parent_span_id": "", "start_time": 100},
            {"trace_id": "trace-1", "span_id": "llm", "parent_span_id": "agent", "start_time": 110},
        ]
        spans = [
            {
                **raw_spans[0],
                "span_type": "AGENT",
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.usage.cache_read.input_tokens": 0,
                },
            },
            {
                **raw_spans[1],
                "span_type": "LLM",
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.cache_read.input_tokens": 30,
                },
            },
        ]

        builder = FlowBuilder(raw_spans, spans)
        builder.build()

        self.assertEqual(builder.statistics["agent"]["cache_read_input_tokens"], 0)

    def test_token_statistics_returns_all_agents_from_one_flow_query(self):
        resource = {"service.name": "agent-service"}
        status = {"code": 1, "message": ""}
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "",
                "span_name": "invoke_agent",
                "start_time": 100,
                "end_time": 200,
                "elapsed_time": 100,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.usage.input_tokens": 30,
                    "gen_ai.usage.output_tokens": 10,
                },
                "events": [],
            },
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "agent",
                "span_name": "chat demo-model",
                "start_time": 110,
                "end_time": 190,
                "elapsed_time": 80,
                "status": status,
                "resource": resource,
                "attributes": {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.usage.input_tokens": 20,
                    "gen_ai.usage.output_tokens": 5,
                    "gen_ai.usage.cache_read.input_tokens": 7,
                },
                "events": [],
            },
        ]
        application = mock.Mock()
        application.build_data_sources.return_value = [mock.sentinel.data_source]
        span_query = mock.Mock()
        span_query.query_by_group_ids.return_value = raw_spans
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
        ):
            result = TokenStatisticsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": "trace-1",
                }
            )

        # 统计与执行线出自同一次查询；Agent 自报输入输出，缺失的缓存字段由子树回填
        self.assertEqual(
            result,
            {
                "trace_id": "trace-1",
                "statistics": {
                    "agent": {
                        "input_tokens": 30,
                        "output_tokens": 10,
                        "total_tokens": 40,
                        "cache_read_input_tokens": 7,
                        "cache_write_input_tokens": 0,
                    }
                },
            },
        )
        span_query.query_by_group_ids.assert_called_once_with(group_field="trace_id", group_ids=["trace-1"])

    def test_session_returns_trace_summaries_without_loading_full_spans(self):
        group_field = "attributes.gen_ai.conversation.id"
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = [
            {"trace_id": "trace-1", "resource": {"service.name": "agent-service"}},
            {"trace_id": "trace-2", "resource": {"service.name": "agent-service"}},
            {"trace_id": "trace-1", "resource": {"service.name": "agent-service"}},
        ]
        spans = [
            {
                "trace_id": trace_id,
                "span_id": f"span-{index}",
                "parent_span_id": "external-parent",
                "span_name": "invoke_agent",
                "start_time": index * 100,
                "end_time": index * 100 + 50,
                "elapsed_time": 50,
                "status": {"code": 1},
                "resource": {"service.name": "agent-service"},
                "attributes": {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.conversation.id": "session-1",
                    "user.id": "user-1",
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "question"}]}],
                    "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}],
                    "gen_ai.usage.input_tokens": 999,
                },
            }
            for index, trace_id in enumerate(("trace-1", "trace-2"), 1)
        ]
        span_query.query_trace_preview.return_value = list(reversed(spans))
        # 错误来自未参与预览的 Span。
        span_query.query_trace_errors.return_value = [{"trace_id": "trace-2"}]
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        with (
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.FlowBuilder", side_effect=AssertionError("must not build session trees")),
            mock.patch(
                "apm_web.llm.resources.LLMMetricGroup.handle",
                side_effect=lambda cal_type: [
                    {
                        "trace_id": span["trace_id"],
                        "_result_": {
                            "input_tokens": 10,
                            "output_tokens": 3,
                            "cache_read_input_tokens": 2,
                            "cache_write_input_tokens": 1,
                        }[cal_type],
                    }
                    for span in spans
                ],
            ),
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "demo",
                    "group_field": group_field,
                    "group_id": "session-1",
                }
            )
        self.assertEqual(result["group_id"], "session-1")
        self.assertEqual(result["group_field"], group_field)
        self.assertEqual(
            {name: value for name, value in result.items() if name.endswith("_tokens")},
            {
                "input_tokens": 20,
                "output_tokens": 6,
                "total_tokens": 26,
                "cache_read_input_tokens": 4,
                "cache_write_input_tokens": 2,
            },
        )
        self.assertEqual((result["start_time"], result["end_time"], result["elapsed_time"]), (100, 250, 150))
        self.assertEqual([trace["trace_id"] for trace in result["traces"]], ["trace-1", "trace-2"])
        for index, trace in enumerate(result["traces"], 1):
            self.assertEqual(trace["flow"], [])
            self.assertEqual((trace["input"], trace["output"]), ("question", "answer"))
            self.assertEqual((trace["input_tokens"], trace["output_tokens"]), (10, 3))
            self.assertEqual(
                (trace["total_tokens"], trace["cache_read_input_tokens"], trace["cache_write_input_tokens"]), (13, 2, 1)
            )
            self.assertEqual(
                (trace["start_time"], trace["end_time"], trace["elapsed_time"]), (index * 100, index * 100 + 50, 50)
            )
            self.assertEqual((trace["conversation_id"], trace["user_id"]), ("session-1", "user-1"))
            self.assertEqual(trace["status"], "error" if index == 2 else "success")
        span_query.query_group_trace_list.assert_called_once_with(
            group_field=group_field,
            group_ids=["session-1"],
            possible_group_fields=resolve_query_fields(group_field),
            extra_fields=["resource.service.name"],
        )
        self.assertEqual(span_query.query_trace_preview.call_count, 2)
        span_query.query_trace_errors.assert_called_once_with(["trace-1", "trace-2"])
        span_query.query_by_group_ids.assert_not_called()
        span_query.iter_by_group_ids.assert_not_called()

    def test_session_queries_all_previews_per_product_without_batching(self):
        count = LLMQuery.GROUP_ID_BATCH_SIZE + 2
        records = [
            {"trace_id": f"trace-{index}", "resource.service.name": "legacy" if index == 1 else "standard"}
            for index in range(count)
        ]
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = records
        span_query.query_trace_preview.side_effect = lambda trace_ids, **kwargs: [
            {"trace_id": trace_id, "span_id": trace_id, "attributes": {}} for trace_id in reversed(trace_ids)
        ]
        span_query.query_trace_errors.return_value = []
        entity_set = mock.Mock(service_names=["standard", "legacy"])
        entity_set.get_system.side_effect = lambda service: {
            "is_support_llm": True,
            "product": "aidev" if service == "legacy" else "default",
        }
        metric_calls = []

        def tokens(group, cal_type):
            trace_ids = group.filter_dict["trace_id__eq"]
            metric_calls.append((group.product, tuple(trace_ids), cal_type))
            return [{"trace_id": trace_id, "_result_": 7 if group.product == "aidev" else 3} for trace_id in trace_ids]

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
            mock.patch("apm_web.llm.resources.adapt_spans", side_effect=lambda spans, entity: spans),
            mock.patch("apm_web.llm.resources.LLMMetricGroup.handle", autospec=True, side_effect=tokens),
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "demo",
                    "group_field": "attributes.gen_ai.conversation.id",
                    "group_id": "session-1",
                }
            )
        self.assertEqual([trace["trace_id"] for trace in result["traces"]], [record["trace_id"] for record in records])
        for index, trace in enumerate(result["traces"]):
            self.assertEqual(trace["flow"], [])
            self.assertEqual(trace["input_tokens"], 7 if index == 1 else 3)
        expected_trace_ids = {
            "default": tuple(record["trace_id"] for record in records if record["resource.service.name"] == "standard"),
            "aidev": ("trace-1",),
        }
        self.assertCountEqual(
            metric_calls,
            [
                (product, trace_ids, cal_type)
                for product, trace_ids in expected_trace_ids.items()
                for cal_type in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_write_input_tokens")
            ],
        )
        self.assertCountEqual(
            [tuple(call.args[0]) for call in span_query.query_trace_errors.call_args_list],
            list(expected_trace_ids.values()),
        )
        self.assertEqual(span_query.query_trace_preview.call_count, 4)
        for call in span_query.query_trace_preview.call_args_list:
            product = "aidev" if call.args[0] == ["trace-1"] else "default"
            self.assertEqual(tuple(call.args[0]), expected_trace_ids[product])
            if call.args[0] == ["trace-1"] and call.kwargs["sort"] == ["end_time desc"]:
                operations = [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}]
                self.assertEqual(
                    call.kwargs["extra_filter"],
                    operation_query("aidev", operations) & Q(span_name__neq=["agent.execution"]),
                )
        span_query.query_by_group_ids.assert_not_called()
        span_query.iter_by_group_ids.assert_not_called()

    def test_missing_session_does_not_query_previews_or_spans(self):
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = []
        topology = mock.Mock(service_names=["agent-service"])
        topology.get_system.return_value = {"is_support_llm": True, "product": "default"}
        with (
            mock.patch("apm_web.llm.resources.Application.objects.get"),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=topology) as entity_set,
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "demo",
                    "group_field": "attributes.gen_ai.conversation.id",
                    "group_id": "missing-session",
                }
            )
        self.assertEqual(result, {"traces": []})
        span_query.query_trace_preview.assert_not_called()
        span_query.query_trace_errors.assert_not_called()
        span_query.query_by_group_ids.assert_not_called()
        entity_set.assert_called_once_with(bk_biz_id=11, app_name="demo")

    def test_returns_empty_traces_when_group_does_not_exist(self):
        application = mock.Mock()
        application.build_data_sources.return_value = []
        span_query = mock.Mock()
        span_query.query_group_trace_list.return_value = []
        span_query.query_by_group_ids.return_value = []
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application),
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query),
            mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
        ):
            result = ListFlowsResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "group_field": "trace_id",
                    "group_id": "missing-trace",
                }
            )

        self.assertEqual(result, {"traces": []})
        span_query.query_group_trace_list.assert_not_called()
        span_query.query_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["missing-trace"],
        )


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
    "cache_read_input_tokens",
    "cache_write_input_tokens",
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
    query.GROUP_ID_BATCH_SIZE = 30
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

    def test_token_aggregation_supports_trace_dimension_and_filter(self):
        group = self._group("default", group_by=["trace_id"], filter_dict={"trace_id__eq": ["trace-1"]})
        group.query = make_query()
        group.query.query_field_aggregated_group.return_value = [{"trace_id": "trace-1", "_result_": 12}]
        for calculation_type in ("input_tokens", "output_tokens"):
            with self.subTest(calculation_type=calculation_type):
                records = group.handle(calculation_type)
                self.assertEqual(records, [{"trace_id": "trace-1", "_result_": 12, "_time_": 0}])
                self.assertEqual(
                    aggregate_call(group.query), ([f"attributes.gen_ai.usage.{calculation_type}"], "SUM", ["trace_id"])
                )
        self.assertEqual(group.query.query_field_aggregated_group.call_count, 2)
        self.assertEqual(group._filter_dict_to_q(), Q(trace_id__eq=["trace-1"]))
        self.assertEqual(layer_query(group.query), LLMMetricGroup.LAYER_QUERIES["model"]["default"])

    def test_langfuse_token_aggregation_supports_trace_dimension(self):
        group = self._group("langfuse", group_by=["trace_id"], filter_dict={"trace_id__eq": ["trace-1", "trace-2"]})
        group.query = make_query()
        group.query.query_field_values.return_value = [
            {
                "trace_id": "trace-1",
                group.LANGFUSE_USAGE_FIELD: '{"input": 2, "output": 4, "cache_read_input_tokens": 5}',
            },
            {"trace_id": "trace-1", group.LANGFUSE_USAGE_FIELD: '{"input": 3, "cache_creation_input_tokens": 1}'},
            {"trace_id": "trace-2", group.LANGFUSE_USAGE_FIELD: "invalid"},
        ]
        for calculation_type, expected in (("input_tokens", 11), ("output_tokens", 4)):
            with self.subTest(calculation_type=calculation_type):
                self.assertEqual(
                    group.handle(calculation_type),
                    [
                        {"trace_id": "trace-1", "_result_": expected, "_time_": 0},
                        {"trace_id": "trace-2", "_result_": 0, "_time_": 0},
                    ],
                )
        self.assertEqual(group.query.query_field_values.call_count, 2)
        self.assertEqual(fetched_fields(group.query), [group.LANGFUSE_USAGE_FIELD, "trace_id"])

    def test_langfuse_token_aggregation_batches_large_trace_lists(self):
        trace_ids = [f"trace-{index}" for index in range(31)]
        group = self._group("langfuse", group_by=["trace_id"], filter_dict={"trace_id__eq": trace_ids})
        group.query = make_query()
        group.query.query_field_values.side_effect = [
            [{"trace_id": "trace-0", group.LANGFUSE_USAGE_FIELD: '{"output": 2}'}],
            [{"trace_id": "trace-30", group.LANGFUSE_USAGE_FIELD: '{"output": 4}'}],
        ]
        self.assertEqual(
            group.handle("output_tokens"),
            [
                {"trace_id": "trace-0", "_result_": 2, "_time_": 0},
                {"trace_id": "trace-30", "_result_": 4, "_time_": 0},
            ],
        )
        self.assertEqual(group.query.query_field_values.call_count, 2)
        self.assertEqual(group.filter_dict, {"trace_id__eq": trace_ids})

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

    def test_bkaidev_reads_standard_and_legacy_token_fields_on_model_spans(self):
        """新旧两种埋点都参与模型层 Token 聚合。"""
        query = make_query(records=[{"_result_": 61083}])

        with patch_llm_metric_group(query, product="aidev"):
            for calculation_type, fields in (
                ("input_tokens", ["attributes.gen_ai.usage.input_tokens", "attributes.gen_ai.usage.prompt_tokens"]),
                (
                    "output_tokens",
                    ["attributes.gen_ai.usage.output_tokens", "attributes.gen_ai.usage.completion_tokens"],
                ),
                (
                    "total_tokens",
                    [
                        "attributes.gen_ai.usage.input_tokens",
                        "attributes.gen_ai.usage.prompt_tokens",
                        "attributes.gen_ai.usage.output_tokens",
                        "attributes.gen_ai.usage.completion_tokens",
                    ],
                ),
            ):
                with self.subTest(calculation_type=calculation_type):
                    CalculateByRangeResource().request(
                        {**LLM_METRIC_REQUEST, "cal_type": calculation_type, "group_by": []}
                    )
                    self.assertEqual(aggregate_call(query), (fields, "SUM", []))

        self.assertEqual(
            layer_query(query),
            Q(**{"attributes.gen_ai.operation.name": ["chat", "generate_content", "text_completion", "embeddings"]})
            | Q(span_name="chat_model.generate"),
        )

    def test_bkaidev_request_count_includes_standard_and_legacy_agents(self):
        query = make_query(records=[{"_result_": 2}])
        with patch_llm_metric_group(query, product="aidev"):
            result = CalculateByRangeResource().request(
                {**LLM_METRIC_REQUEST, "cal_type": "request_count", "group_by": []}
            )

        self.assertEqual(result["data"][0]["0s"], 2)
        self.assertEqual(aggregate_call(query), (["trace_id"], "DISTINCT", []))
        self.assertEqual(
            layer_query(query),
            Q(**{"attributes.gen_ai.operation.name": ["invoke_agent", "invoke_workflow"]})
            | Q(span_name="agent.execution"),
        )

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

    def test_cache_read_and_write_query_separate_product_fields(self):
        cases = {
            "default": {
                "cache_read_input_tokens": ["attributes.gen_ai.usage.cache_read.input_tokens"],
                "cache_write_input_tokens": ["attributes.gen_ai.usage.cache_write.input_tokens"],
            },
            "galileo": {
                "cache_read_input_tokens": [
                    "attributes.gen_ai.usage.cache_read.input_tokens",
                    "attributes.gen_ai.usage.cache_read_input_tokens",
                    "attributes.gen_ai.usage.cached.input_tokens",
                ],
                "cache_write_input_tokens": [
                    "attributes.gen_ai.usage.cache_creation.input_tokens",
                    "attributes.gen_ai.usage.cache_creation_input_tokens",
                ],
            },
        }
        for product, fields_by_type in cases.items():
            for cal_type, fields in fields_by_type.items():
                query = make_query(records=[{"_result_": 7}])
                with self.subTest(product=product, cal_type=cal_type), patch_llm_metric_group(query, product=product):
                    result = CalculateByRangeResource().request(
                        {**LLM_METRIC_REQUEST, "cal_type": cal_type, "group_by": []}
                    )
                self.assertEqual(result["data"][0]["0s"], 7)
                self.assertEqual(aggregate_call(query), (fields, "SUM", []))

    def test_langfuse_cache_read_and_write_are_aggregated_separately(self):
        for cal_type, expected in (("cache_read_input_tokens", 12), ("cache_write_input_tokens", 1672)):
            query = make_query()
            query.query_field_values.return_value = [
                {
                    "attributes.langfuse.observation.usage_details": (
                        '{"input": 5, "output": 38, "cache_read_input_tokens": 12, "cache_creation_input_tokens": 1672}'
                    )
                },
                {"attributes.langfuse.observation.usage_details": '{"input": 5, "output": 7}'},
            ]
            with self.subTest(cal_type=cal_type), patch_llm_metric_group(query, product="langfuse"):
                result = CalculateByRangeResource().request(
                    {**LLM_METRIC_REQUEST, "cal_type": cal_type, "group_by": []}
                )
            self.assertEqual(result["data"][0]["0s"], expected)
            query.query_field_aggregated_group.assert_not_called()

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
        for time_shift, seconds in [("1h", 3600), ("90m", 5400), ("3661s", 3661), ("1d", 86400)]:
            with self.subTest(time_shift=time_shift):
                query = make_query()
                start_time = LLM_METRIC_REQUEST["start_time"]
                end_time = start_time + seconds
                query.query_field_aggregated_group.side_effect = lambda queries, start, *args: (
                    [{"_result_": 100 if start == start_time else 80}]
                )

                with patch_llm_metric_group(query):
                    result = CalculateByRangeResource().request(
                        {
                            **LLM_METRIC_REQUEST,
                            "end_time": end_time,
                            "cal_type": "model_call_count",
                            "group_by": [],
                            "baseline": "0s",
                            "time_shifts": ["0s", time_shift],
                        }
                    )

                record = result["data"][0]
                self.assertEqual(set(record), {"dimensions", "0s", time_shift, "growth_rates"})
                self.assertEqual((record["0s"], record[time_shift]), (100, 80))
                self.assertEqual(record["growth_rates"]["0s"], 0)
                self.assertAlmostEqual(record["growth_rates"][time_shift], 25, delta=0.01)
                self.assertCountEqual(
                    [call.args[1:3] for call in query.query_field_aggregated_group.call_args_list],
                    [(start_time, end_time), (start_time - seconds, start_time)],
                )

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
