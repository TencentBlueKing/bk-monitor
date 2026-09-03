from unittest import TestCase, mock

from apm_web.llm.resources import (
    AGENT_CANDIDATE_QUERY,
    CalculateByRangeResource,
    ListSpansResource,
    ListTracesResource,
    MOCK_TIME_SERIES_MAX_POINTS,
    TimeSeriesResource,
)


class ListTracesResourceTestCase(TestCase):
    def test_agent_candidate_query_covers_supported_sources(self):
        candidate_fields = {
            condition.removeprefix("_exists_:attributes.") for condition in AGENT_CANDIDATE_QUERY.split(" OR ")
        }
        cases = {
            "agentlens": ({"gen_ai.span.kind": "LLM"}, True),
            "galileo": ({"gen_ai.operation.name": "chat"}, True),
            "bkaidev": ({"agent.info.id": 3129, "agent.info.name": "demo"}, True),
            "http": ({"http.method": "GET", "http.route": "/api/orders"}, False),
        }

        for source, (attributes, expected) in cases.items():
            with self.subTest(source=source):
                self.assertEqual(bool(candidate_fields.intersection(attributes)), expected)

    def test_request_exposes_supported_filters(self):
        fields = ListTracesResource.RequestSerializer().fields

        self.assertIn("keyword", fields)
        self.assertIn("service_name", fields)
        self.assertNotIn("filters", fields)

    def test_limit_max_value(self):
        request_data = {
            "bk_biz_id": 11,
            "app_name": "sand_local_dev",
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
    def convert_spans(raw_spans):
        return [
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
                "parent_span_id": span.get("parent_span_id", ""),
                "start_time": span.get("start_time", 0),
                "end_time": span.get("end_time", 0),
                "attributes": {
                    "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": span["input"]}]}],
                    "gen_ai.output.messages": [
                        {"role": "assistant", "parts": [{"type": "text", "content": span["output"]}]}
                    ],
                    "gen_ai.usage.input_tokens": span.get("input_tokens", 0),
                    "gen_ai.usage.output_tokens": span.get("output_tokens", 0),
                    "gen_ai.usage.cache_read.input_tokens": span.get("cache_read_input_tokens", 0),
                    "gen_ai.usage.cache_creation.input_tokens": span.get("cache_creation_input_tokens", 0),
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
                "input": "问一",
                "output": "答一",
                "start_time": 100,
                "end_time": 160,
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 2,
                "user_id": "user-1",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2",
                "parent_span_id": "",
                "input": "问二",
                "output": "处理中",
                "start_time": 200,
                "end_time": 280,
                "input_tokens": 12,
                "output_tokens": 5,
                "cache_read_input_tokens": 4,
                "cache_creation_input_tokens": 1,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-3",
                "parent_span_id": "span-2",
                "input": "问二（包含工具结果）",
                "output": "答二",
                "start_time": 250,
                "end_time": 280,
                "input_tokens": 8,
                "output_tokens": 3,
                "cache_read_input_tokens": 2,
                "cache_creation_input_tokens": 0,
                "user_id": "user-2",
            },
        ]
        span_query.query_by_group_ids.return_value = raw_spans

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application) as get_application,
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query) as get_query,
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

        self.assertEqual(
            result["items"],
            [
                {
                    "group_id": "trace-2",
                    "group_field": "trace_id",
                    "trace_id": "trace-2",
                    "input": "问二",
                    "output": "处理中",
                    "input_tokens": 20,
                    "output_tokens": 8,
                    "cache_read_input_tokens": 6,
                    "cache_creation_input_tokens": 1,
                    "start_time": 200,
                    "elapsed_time": 80,
                    "user_id": "user-2",
                },
                {
                    "group_id": "trace-1",
                    "group_field": "trace_id",
                    "trace_id": "trace-1",
                    "input": "问一",
                    "output": "答一",
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": 2,
                    "start_time": 100,
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
            filters=[
                {"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]},
                {"key": "keyword", "operator": "logic", "value": ["订单"]},
            ],
            query_string=AGENT_CANDIDATE_QUERY,
        )
        span_query.query_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-1"],
        )
        span_query.query_group_trace_list.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-1"],
        )

    def test_custom_group_keeps_trace_children(self):
        group_field = "attributes.session.id"
        span_query = mock.Mock(QUERY_MAX_LIMIT=10000)
        span_query.query_group_list.return_value = ["session-2", "session-1"]
        span_query.query_group_trace_list.return_value = [
            {group_field: "session-2", "trace_id": "trace-2"},
            {group_field: "session-2", "trace_id": "trace-3"},
            {group_field: "session-1", "trace_id": "trace-1"},
        ]
        application = mock.Mock()
        data_sources = [mock.sentinel.data_source]
        application.build_data_sources.return_value = data_sources
        raw_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "span-1",
                "parent_span_id": "",
                "attributes": {"session.id": "session-1"},
                "input": "问一",
                "output": "答一",
                "start_time": 300,
                "end_time": 330,
                "input_tokens": 5,
                "output_tokens": 2,
                "cache_read_input_tokens": 1,
                "cache_creation_input_tokens": 0,
                "user_id": "user-1",
            },
            {
                "trace_id": "trace-3",
                "span_id": "span-3",
                "parent_span_id": "",
                "attributes": {"session.id": "session-2"},
                "input": "问三",
                "output": "答三",
                "start_time": 200,
                "end_time": 280,
                "input_tokens": 20,
                "output_tokens": 8,
                "cache_read_input_tokens": 6,
                "cache_creation_input_tokens": 1,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2",
                "parent_span_id": "",
                "attributes": {"session.id": "session-2"},
                "input": "问二",
                "output": "答二",
                "start_time": 100,
                "end_time": 160,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "user_id": "user-2",
            },
            {
                "trace_id": "trace-2",
                "span_id": "span-2-llm",
                "parent_span_id": "span-2",
                "attributes": {},
                "input": "模型输入",
                "output": "模型输出",
                "start_time": 120,
                "end_time": 150,
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 2,
                "user_id": "",
            },
        ]
        span_query.query_by_group_ids.return_value = raw_spans

        with (
            mock.patch("apm_web.llm.resources.Application.objects.get", return_value=application) as get_application,
            mock.patch("apm_web.llm.resources.get_query", return_value=span_query) as get_query,
            mock.patch("apm_web.llm.resources.adapt_spans", side_effect=self.convert_spans),
        ):
            result = ListTracesResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "start_time": 1,
                    "end_time": 2,
                    "group_field": group_field,
                }
            )

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(
            result["items"][0],
            {
                "group_id": "session-2",
                "group_field": group_field,
                "input": "",
                "output": "",
                "input_tokens": 30,
                "output_tokens": 12,
                "cache_read_input_tokens": 9,
                "cache_creation_input_tokens": 3,
                "start_time": 100,
                "elapsed_time": 180,
                "user_id": "user-2",
                "childs": [
                    {
                        "group_id": "trace-2",
                        "group_field": "trace_id",
                        "trace_id": "trace-2",
                        "input": "问二",
                        "output": "答二",
                        "input_tokens": 10,
                        "output_tokens": 4,
                        "cache_read_input_tokens": 3,
                        "cache_creation_input_tokens": 2,
                        "start_time": 100,
                        "elapsed_time": 60,
                        "user_id": "user-2",
                    },
                    {
                        "group_id": "trace-3",
                        "group_field": "trace_id",
                        "trace_id": "trace-3",
                        "input": "问三",
                        "output": "答三",
                        "input_tokens": 20,
                        "output_tokens": 8,
                        "cache_read_input_tokens": 6,
                        "cache_creation_input_tokens": 1,
                        "start_time": 200,
                        "elapsed_time": 80,
                        "user_id": "user-2",
                    },
                ],
            },
        )
        span_query.query_group_list.assert_called_once_with(
            start_time=1,
            end_time=2,
            group_field=group_field,
            offset=0,
            limit=20,
            filters=[],
            query_string=AGENT_CANDIDATE_QUERY,
        )
        span_query.query_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-3", "trace-1"],
        )
        span_query.query_group_trace_list.assert_called_once_with(
            group_field=group_field,
            group_ids=["session-2", "session-1"],
        )
        get_application.assert_called_once_with(bk_biz_id=11, app_name="sand_local_dev")
        application.build_data_sources.assert_called_once_with()
        get_query.assert_called_once_with(data_sources)

    def test_trace_time_uses_raw_root_span(self):
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "root", "parent_span_id": "", "start_time": 100, "end_time": 300},
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "root",
                "start_time": 150,
                "end_time": 200,
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
            item = ListTracesResource._trace_item("trace-1", raw_spans)

        self.assertEqual(item["start_time"], 100)
        self.assertEqual(item["elapsed_time"], 200)

    def test_trace_preview_uses_last_user_and_assistant_on_logical_root(self):
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "http-root", "parent_span_id": "", "start_time": 100, "end_time": 300}
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "http-root",
                "parent_span_id": "",
                "attributes": {},
            },
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "http-root",
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
            item = ListTracesResource._trace_item("trace-1", raw_spans)

        self.assertEqual(item["input"], "最新问题")
        self.assertEqual(item["output"], "最终回答")

    def test_trace_preview_does_not_fallback_to_child_llm(self):
        raw_spans = [
            {"trace_id": "trace-1", "span_id": "agent", "parent_span_id": "", "start_time": 100, "end_time": 300}
        ]
        converted_spans = [
            {
                "trace_id": "trace-1",
                "span_id": "agent",
                "parent_span_id": "",
                "attributes": {"gen_ai.operation.name": "invoke_workflow"},
            },
            {
                "trace_id": "trace-1",
                "span_id": "llm",
                "parent_span_id": "agent",
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
            item = ListTracesResource._trace_item("trace-1", raw_spans)

        self.assertEqual(item["input"], "")
        self.assertEqual(item["output"], "")


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

        with mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response):
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

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list,
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
        adapt_spans.assert_called_once_with(response["data"])
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [{"key": "trace_id", "operator": "equal", "value": ["trace-1"]}],
                "limit": 10000,
                "exclude_field": ["bk_app_code"],
            }
        )


class TimeSeriesResourceTestCase(TestCase):
    def test_mock_accepts_metrics_required_by_overview_page(self):
        fields = TimeSeriesResource.RequestSerializer().fields

        self.assertEqual(
            set(fields["cal_type"].choices),
            {
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cache_tokens",
                "request_count",
                "model_call_count",
                "duration",
                "operation_count",
            },
        )

    def test_input_tokens_mock_returns_series_in_requested_time_range(self):
        request_data = {
            "bk_biz_id": 11,
            "app_name": "sand_local_dev",
            "service_name": "agent-service",
            "start_time": 1700000000,
            "end_time": 1700001800,
            "cal_type": "input_tokens",
            "group_by": [],
        }

        result = TimeSeriesResource().request(request_data)

        self.assertTrue(result["mock"])
        self.assertEqual(list(result), ["series", "mock"])
        self.assertEqual(len(result["series"]), 1)
        self.assertEqual(list(result["series"][0]), ["datapoints"])
        self.assertEqual(result["series"][0]["datapoints"][0][1], request_data["start_time"] * 1000)
        self.assertEqual(result["series"][0]["datapoints"][-1][1], request_data["end_time"] * 1000)
        self.assertEqual(result, TimeSeriesResource().request(request_data))

    def test_duration_mock_groups_by_model(self):
        result = TimeSeriesResource().request(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700003600,
                "cal_type": "duration",
                "group_by": ["gen_ai.response.model"],
            }
        )

        self.assertEqual(len(result["series"]), 3)
        self.assertEqual(
            [series["dimensions"]["gen_ai.response.model"] for series in result["series"]],
            ["hunyuan-turbo", "deepseek-r1", "qwen3-32b"],
        )
        self.assertEqual(
            [series["target"] for series in result["series"]],
            ["hunyuan-turbo", "deepseek-r1", "qwen3-32b"],
        )

    def test_operation_count_mock_groups_by_operation_name(self):
        result = TimeSeriesResource().request(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700003600,
                "cal_type": "operation_count",
                "group_by": ["gen_ai.operation.name"],
            }
        )

        self.assertEqual(len(result["series"]), 4)
        self.assertEqual(
            [series["dimensions"]["gen_ai.operation.name"] for series in result["series"]],
            ["invoke_agent", "chat", "execute_tool", "retrieval"],
        )
        self.assertEqual(
            [series["target"] for series in result["series"]],
            ["invoke_agent", "chat", "execute_tool", "retrieval"],
        )

    def test_each_series_limits_datapoints_for_large_time_range(self):
        request_data = {
            "bk_biz_id": 11,
            "app_name": "sand_local_dev",
            "start_time": 0,
            "end_time": 1_000_000_000_000,
            "cal_type": "operation_count",
            "group_by": ["gen_ai.operation.name"],
        }

        result = TimeSeriesResource().request(request_data)

        self.assertEqual(len(result["series"]), 4)
        for series in result["series"]:
            datapoints = series["datapoints"]
            self.assertLessEqual(len(datapoints), MOCK_TIME_SERIES_MAX_POINTS)
            self.assertEqual(datapoints[0][1], request_data["start_time"] * 1000)
            self.assertEqual(datapoints[-1][1], request_data["end_time"] * 1000)
            self.assertEqual(
                [datapoint[1] for datapoint in datapoints],
                sorted({datapoint[1] for datapoint in datapoints}),
            )

    def test_rejects_unsupported_group_by(self):
        serializer = TimeSeriesResource.RequestSerializer(
            data={
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700001800,
                "cal_type": "input_tokens",
                "group_by": ["user.id"],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("暂不支持", str(serializer.errors))

    def test_rejects_multiple_group_by_fields(self):
        serializer = TimeSeriesResource.RequestSerializer(
            data={
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700001800,
                "cal_type": "input_tokens",
                "group_by": ["gen_ai.response.model", "gen_ai.operation.name"],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("暂不支持多字段聚合", str(serializer.errors))


class CalculateByRangeResourceTestCase(TestCase):
    def test_input_tokens_mock_returns_calculate_by_range_shape(self):
        result = CalculateByRangeResource().request(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700001800,
                "cal_type": "input_tokens",
                "group_by": [],
            }
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(list(result), ["total", "data"])
        self.assertEqual(result["data"][0]["dimensions"], {})
        self.assertIn("0s", result["data"][0])
        self.assertNotIn("growth_rates", result["data"][0])

    def test_duration_mock_groups_by_model(self):
        result = CalculateByRangeResource().request(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700003600,
                "cal_type": "duration",
                "group_by": ["gen_ai.response.model"],
            }
        )

        self.assertEqual(result["total"], 3)
        self.assertEqual(
            [record["dimensions"]["gen_ai.response.model"] for record in result["data"]],
            ["hunyuan-turbo", "deepseek-r1", "qwen3-32b"],
        )
        for record in result["data"]:
            self.assertIn("0s", record)
            self.assertNotIn("1d", record)
            self.assertNotIn("growth_rates", record)

    def test_operation_count_mock_groups_by_operation_name(self):
        result = CalculateByRangeResource().request(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700003600,
                "cal_type": "operation_count",
                "group_by": ["gen_ai.operation.name"],
            }
        )

        self.assertEqual(result["total"], 4)
        self.assertEqual(
            [record["dimensions"]["gen_ai.operation.name"] for record in result["data"]],
            ["invoke_agent", "chat", "execute_tool", "retrieval"],
        )
        for record in result["data"]:
            self.assertIn("0s", record)
            self.assertNotIn("growth_rates", record)

    def test_rejects_unsupported_group_by(self):
        serializer = CalculateByRangeResource.RequestSerializer(
            data={
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "start_time": 1700000000,
                "end_time": 1700001800,
                "cal_type": "input_tokens",
                "group_by": ["user.id"],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("暂不支持", str(serializer.errors))
