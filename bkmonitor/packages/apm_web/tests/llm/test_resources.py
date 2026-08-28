from unittest import TestCase, mock

from apm_web.llm.resources import ListSpansResource, ListTracesResource


class ListTracesResourceTestCase(TestCase):
    @staticmethod
    def convert_spans(raw_spans):
        return [
            {
                "trace_id": span["trace_id"],
                "span_id": span["span_id"],
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
        proxy = mock.Mock(span_query=span_query)
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
            mock.patch("apm_web.llm.resources.QueryProxy", return_value=proxy) as query_proxy,
            mock.patch("apm_web.llm.resources.adapt_spans", side_effect=self.convert_spans),
        ):
            result = ListTracesResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "start_time": 1,
                    "end_time": 2,
                    "service_name": "demo-service",
                    "filters": [
                        {
                            "key": "keyword",
                            "operator": "logic",
                            "value": ["订单"],
                            "options": {"is_wildcard": False, "group_relation": "OR"},
                        }
                    ],
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
                    "output": "答二",
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
        query_proxy.assert_called_once_with(11, "sand_local_dev")
        span_query.query_group_list.assert_called_once_with(
            start_time=1,
            end_time=2,
            group_field="trace_id",
            offset=0,
            limit=20,
            filters=[
                {
                    "key": "keyword",
                    "operator": "logic",
                    "value": ["订单"],
                    "options": {"is_wildcard": False, "group_relation": "OR"},
                },
                {"key": "resource.service.name", "operator": "equal", "value": ["demo-service"]},
            ],
        )
        span_query.query_by_group_ids.assert_called_once_with(
            group_field="trace_id",
            group_ids=["trace-2", "trace-1"],
        )

    def test_custom_group_keeps_trace_children(self):
        group_field = "attributes.session.id"
        span_query = mock.Mock(QUERY_MAX_LIMIT=10000)
        span_query.query_group_list.return_value = ["session-2", "session-1"]
        proxy = mock.Mock(span_query=span_query)
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
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 2,
                "user_id": "user-2",
            },
        ]
        span_query.query_by_group_ids.return_value = raw_spans

        with (
            mock.patch("apm_web.llm.resources.QueryProxy", return_value=proxy),
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
        )
        span_query.query_by_group_ids.assert_called_once_with(
            group_field=group_field,
            group_ids=["session-2", "session-1"],
        )

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
