from unittest import TestCase, mock
from copy import deepcopy

from django.utils import tree

from django.db.models import Q

from bkmonitor.data_source import dict_to_q
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.llm.adapter.fields import AGENT_CANDIDATE_Q, SPAN_TYPES, operation_query
from apm_web.llm.query import LLMQuery


class LLMQueryTestCase(TestCase):
    def setUp(self):
        self.query = LLMQuery(
            [
                TraceDatasourceTarget.build(
                    bk_biz_id=11,
                    app_name="demo",
                    table_id="11_bkapm.trace_demo",
                    retention=7,
                )
            ]
        )

    def test_query_group_list(self):
        with mock.patch.object(
            self.query,
            "_query_list",
            return_value=[{"attributes.session.id": "session-2"}, {"attributes.session.id": "session-1"}],
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="attributes.session.id",
                offset=0,
                limit=20,
                filters=[],
            )

        self.assertEqual(group_ids, ["session-2", "session-1"])

    def test_query_group_list_with_nested_field(self):
        with mock.patch.object(
            self.query,
            "_query_list",
            return_value=[
                {
                    "attributes": {
                        "gen_ai": {
                            "conversation": {"id": "conversation-1"},
                        },
                    }
                }
            ],
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field="attributes.gen_ai.conversation.id",
                offset=0,
                limit=20,
                filters=[],
            )

        self.assertEqual(group_ids, ["conversation-1"])

    def test_query_group_list_applies_extra_filter(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        query_builder.order_by.return_value = query_builder

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=[{"trace_id": "trace-1"}]) as query_list,
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field=OtlpKey.TRACE_ID,
                offset=0,
                limit=20,
                filters=[],
                extra_filter=AGENT_CANDIDATE_Q,
            )

        self.assertEqual(group_ids, ["trace-1"])
        build_queries.assert_called_once_with([], None)
        query_builder.filter.assert_called_once_with(Q(trace_id__exists=[""], trace_id__neq=[""]) & AGENT_CANDIDATE_Q)
        query_builder.distinct.assert_called_once_with(OtlpKey.TRACE_ID)
        query_list.assert_called_once_with([query_builder], 1, 2, 0, 20)

    def test_group_pagination_excludes_empty_groups_before_collapse(self):
        for group_field in (
            "attributes.agent.session.session_code",
            "attributes.gen_ai.conversation.id",
            "attributes.session.id",
            "trace_id",
        ):
            with self.subTest(group_field=group_field):
                records = [{}, {group_field: None}, {group_field: ""}]
                records.extend({group_field: value} for value in ("group-1", "group-1", "group-2", "group-3"))

                def query_list(queries, start_time, end_time, offset, limit):
                    # 执行实际序列化后的条件，再模拟存储侧 collapse 和分页。
                    config = self.query._add_query(self.query.get_qs(None, None), queries).config
                    predicate = dict_to_q(config["query_configs"][0]["filter_dict"])
                    self.assertEqual(queries[0].query.distinct, group_field)
                    self.assertEqual(queries[0].query.order_by, ["end_time desc"])
                    collapsed = {}
                    for record in records:
                        if TracePreviewQueryTestCase.matches(record, predicate):
                            collapsed.setdefault(record.get(group_field), record)
                    return list(collapsed.values())[offset : offset + limit]

                with mock.patch.object(self.query, "_query_list", side_effect=query_list):
                    pages = [self.query.query_group_list(1, 2, group_field, offset, 2) for offset in (0, 2, 4)]
                self.assertEqual(pages, [["group-1", "group-2"], ["group-3"], []])

    def test_query_by_group_ids(self):
        query_builder = mock.Mock()
        query_builder.order_by.return_value = query_builder
        query_builder.filter.return_value = query_builder
        spans = [{"trace_id": "trace-1", "span_id": "span-1"}]

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=spans) as query_list,
        ):
            result = self.query.query_by_group_ids(
                group_field="attributes.session.id",
                group_ids=["session-1", "session-2"],
                start_time=1,
                end_time=2,
            )

        self.assertEqual(result, spans)
        build_queries.assert_called_once_with(time_field="start_time")
        query_builder.order_by.assert_called_once_with("start_time")
        query_builder.filter.assert_called_once_with(**{"attributes.session.id__eq": ["session-1", "session-2"]})
        query_list.assert_called_once_with([query_builder], 1, 2, 0, 10000)

    def test_query_by_group_ids_returns_empty_without_query(self):
        with mock.patch.object(self.query, "_query_list") as query_list:
            result = self.query.query_by_group_ids(group_field=OtlpKey.TRACE_ID, group_ids=[])

        self.assertEqual(result, [])
        query_list.assert_not_called()

    def test_query_by_group_ids_splits_large_id_list(self):
        group_ids = [f"trace-{index}" for index in range(self.query.GROUP_ID_BATCH_SIZE + 1)]
        builders: list[mock.Mock] = []

        def _build_queries(**kwargs):
            builder = mock.Mock()
            builder.order_by.return_value = builder

            def _filter(**filter_kwargs):
                builder.filtered_ids = filter_kwargs[f"{OtlpKey.TRACE_ID}__eq"]
                return builder

            builder.filter.side_effect = _filter
            builders.append(builder)
            return [builder]

        def _query_list(queries, start_time, end_time, offset, limit):
            return [{"trace_id": trace_id} for trace_id in queries[0].filtered_ids]

        with (
            mock.patch.object(self.query, "build_queries", side_effect=_build_queries) as build_queries,
            mock.patch.object(self.query, "_query_list", side_effect=_query_list) as query_list,
        ):
            result = self.query.query_by_group_ids(
                group_field=OtlpKey.TRACE_ID,
                group_ids=group_ids,
                start_time=1,
                end_time=2,
            )

        self.assertEqual([span["trace_id"] for span in result], group_ids)
        self.assertEqual(build_queries.call_count, 2)
        self.assertEqual(query_list.call_count, 2)
        self.assertCountEqual(
            [tuple(builder.filtered_ids) for builder in builders],
            [tuple(group_ids[: self.query.GROUP_ID_BATCH_SIZE]), tuple(group_ids[self.query.GROUP_ID_BATCH_SIZE :])],
        )
        for call in query_list.call_args_list:
            self.assertEqual(call.args[1:], (1, 2, 0, 10000))

    def test_iter_by_group_ids_yields_one_batch_per_chunk(self):
        group_ids = [f"trace-{index}" for index in range(self.query.GROUP_ID_BATCH_SIZE + 1)]

        def _build_queries(**kwargs):
            builder = mock.Mock()
            builder.order_by.return_value = builder

            def _filter(**filter_kwargs):
                builder.filtered_ids = filter_kwargs[f"{OtlpKey.TRACE_ID}__eq"]
                return builder

            builder.filter.side_effect = _filter
            return [builder]

        def _query_list(queries, start_time, end_time, offset, limit):
            return [{"trace_id": trace_id} for trace_id in queries[0].filtered_ids]

        with (
            mock.patch.object(self.query, "build_queries", side_effect=_build_queries),
            mock.patch.object(self.query, "_query_list", side_effect=_query_list),
        ):
            batches = list(
                self.query.iter_by_group_ids(
                    group_field=OtlpKey.TRACE_ID,
                    group_ids=group_ids,
                    start_time=1,
                    end_time=2,
                )
            )

        self.assertEqual(len(batches), 2)
        self.assertEqual([span["trace_id"] for span in batches[0]], group_ids[: self.query.GROUP_ID_BATCH_SIZE])
        self.assertEqual([span["trace_id"] for span in batches[1]], group_ids[self.query.GROUP_ID_BATCH_SIZE :])

    def test_query_group_trace_list(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        records = [
            {"attributes.session.id": "session-1", "trace_id": "trace-1"},
            {"attributes.session.id": "session-1", "trace_id": "trace-2"},
        ]

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=records) as query_list,
        ):
            result = self.query.query_group_trace_list(
                group_field="attributes.session.id",
                group_ids=["session-1"],
            )

        self.assertEqual(result, records)
        build_queries.assert_called_once_with()
        query_builder.filter.assert_called_once_with(**{"attributes.session.id__eq": ["session-1"]})
        query_builder.distinct.assert_called_once_with(OtlpKey.TRACE_ID)
        query_builder.values.assert_called_once_with("attributes.session.id", OtlpKey.TRACE_ID)
        query_list.assert_called_once_with([query_builder], None, None, 0, 10000)


class TracePreviewQueryTestCase(TestCase):
    setUp = LLMQueryTestCase.setUp

    def preview(self, trace_ids, product, direction):
        extra_filter = operation_query(product, [name for name, kind in SPAN_TYPES.items() if kind in {"AGENT", "LLM"}])
        sort = ["start_time asc"] if direction == "input" else ["end_time desc"]
        return self.query.query_trace_preview(trace_ids, extra_filter=extra_filter, sort=sort)

    @staticmethod
    def matches(record, predicate):
        if isinstance(predicate, tree.Node):
            values = [TracePreviewQueryTestCase.matches(record, item) for item in predicate.children]
            matched = any(values) if predicate.connector == "OR" else all(values)
            return not matched if predicate.negated else matched
        field, expected = predicate
        field, _, operator = field.partition("__")
        if field == "events.name":
            return any(event["name"] in expected for event in record.get("events", []))
        value = LLMQuery.get_field_value(record, field)
        if operator == "exists":
            return value is not None
        matched = value in expected if isinstance(expected, list) else value == expected
        return not matched if operator == "neq" else matched

    @staticmethod
    def span(index, **kwargs):
        return {
            "trace_id": "trace-1",
            "span_id": f"span-{index}",
            "parent_span_id": "root",
            "span_name": "invoke_agent",
            "start_time": index * 100,
            "end_time": index * 100 + 50,
            "elapsed_time": 50,
            "status": {"code": 1},
            "resource": {"service.name": "agent-service"},
            "attributes": {"gen_ai.operation.name": "invoke_agent", "irrelevant_large_field": "x" * 10000},
            **kwargs,
        }

    def execute(self, spans):
        def query_list(queries, start_time, end_time, offset, limit):
            self.assertEqual((start_time, end_time, offset), (None, None, 0))
            self.assertLessEqual(limit, self.query.QUERY_MAX_LIMIT)
            self.assertEqual(len(queries), 1)
            config = self.query._add_query(self.query.get_qs(None, None).offset(offset).limit(limit), queries).config
            self.assertTrue(config["query_configs"])
            query = queries[0].query
            self.assertEqual(query.distinct, "trace_id")
            # 使用实际下发的 UQ 条件，避免内存 Q 的取反语义掩盖序列化丢失。
            predicate = dict_to_q(config["query_configs"][0]["filter_dict"])
            records = [span for span in spans if self.matches(span, predicate)]
            if query.order_by:
                field, _, direction = query.order_by[0].partition(" ")
                records.sort(key=lambda record: record[field], reverse=direction == "desc")
            collapsed = {}
            for record in records:
                collapsed.setdefault(record["trace_id"], record)
            records = list(collapsed.values())[:limit]
            if not query.select:
                return deepcopy(records)
            return [
                {"trace_id": record["trace_id"], "status": {"code": record["status"]["code"]}} for record in records
            ]

        return query_list

    def test_preview_bounds_use_agent_and_llm_spans(self):
        from apm_web.llm.adapter import adapt_spans
        from apm_web.llm.builders.summary import TraceSummary

        spans = [self.span(index, attributes={"http.method": "GET"}) for index in range(1, 101)]
        for index, operation in ((1, "invoke_agent"), (50, "chat"), (75, "chat"), (90, "execute_tool")):
            spans[index]["attributes"]["gen_ai.operation.name"] = operation
            spans[index]["attributes"]["irrelevant_large_field"] = "x" * 10000
        spans[0]["parent_span_id"] = ""
        spans[1]["attributes"]["gen_ai.conversation.id"] = "session-1"
        spans[1]["attributes"]["gen_ai.input.messages"] = [
            {"role": "user", "parts": [{"type": "text", "content": "first"}]}
        ]
        spans[50]["attributes"]["gen_ai.input.messages"] = [
            {"role": "user", "parts": [{"type": "text", "content": "later"}]}
        ]
        spans[75]["attributes"]["gen_ai.output.messages"] = [
            {"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}
        ]
        spans[90]["attributes"]["gen_ai.tool.call.result"] = "tool output"
        spans[99]["status"]["code"] = 2
        spans[99]["attributes"] = {"http.method": "GET"}
        with mock.patch.object(self.query, "_query_list", side_effect=self.execute(spans)):
            samples = [
                *self.preview(["trace-1"], "default", "input"),
                *self.preview(["trace-1"], "default", "output"),
            ]
            errors = self.query.query_trace_errors(["trace-1"])
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples, [spans[1], spans[75]])
        self.assertEqual(errors, [{"trace_id": "trace-1", "status": {"code": 2}}])
        entity_set = mock.Mock(service_names=["agent-service"])
        entity_set.get_system.return_value = {"is_support_llm": True, "product": "default"}
        item = TraceSummary.build(
            "trace-1", samples, adapt_spans(samples, entity_set), {"input_tokens": 800}, has_error=True
        )
        self.assertEqual((item["input"], item["output"]), ("first", "answer"))
        self.assertEqual((item["start_time"], item["end_time"], item["status"]), (200, 7650, "error"))
        self.assertEqual(item["input_tokens"], 800)
        self.assertEqual(item["conversation_id"], "session-1")

    def test_empty_ids_do_not_query(self):
        with mock.patch.object(self.query, "_query_list") as query_list:
            self.assertEqual(self.preview([], "default", "input"), [])
        query_list.assert_not_called()

    def test_each_product_returns_complete_span_after_collapse(self):
        for product in ("default", "agentlens", "aidev", "galileo", "langfuse"):
            for direction in ("input", "output"):
                with self.subTest(product=product, direction=direction):
                    with mock.patch.object(self.query, "_query_list", return_value=[]) as query_list:
                        self.preview(["trace-1"], product, direction)
                    query_list.assert_called_once()
                    queries = query_list.call_args.args[0]
                    query = queries[0].query
                    self.assertEqual(query.distinct, "trace_id")
                    self.assertEqual(query.order_by, ["end_time desc" if direction == "output" else "start_time asc"])
                    self.assertFalse(query.select)
                    config = self.query._add_query(self.query.get_qs(None, None).limit(1), queries).config
                    self.assertFalse(config["query_configs"][0]["select"])
                    self.assertEqual(query_list.call_args.args[1:], (None, None, 0, 1))

    def test_operation_filter_translates_standard_values_for_each_product(self):
        cases = [
            ("default", "gen_ai.operation.name", ["chat", "execute_tool"], ["invoke_agent", "retrieval"]),
            ("galileo", "gen_ai.operation.name", ["chat", "execute_tool"], ["invoke_agent"]),
            ("agentlens", "gen_ai.span.kind", ["LLM", "TOOL"], ["AGENT"]),
            ("langfuse", "langfuse.observation.type", ["generation", "tool"], ["agent", "retriever"]),
        ]
        for product, field, included, excluded in cases:
            predicate = operation_query(product, ["chat", "execute_tool"])
            for value in included + excluded:
                with self.subTest(product=product, value=value):
                    self.assertEqual(
                        self.matches(self.span(1, attributes={field: value}), predicate), value in included
                    )
            self.assertTrue(self.matches(self.span(1, attributes={"gen_ai.operation.name": "chat"}), predicate))

    def test_aidev_operation_filter_supports_standard_and_legacy_spans(self):
        spans = [
            self.span(1, span_name="chat demo", attributes={"gen_ai.operation.name": "chat"}),
            self.span(2, span_name="agent demo", attributes={"gen_ai.operation.name": "invoke_agent"}),
            self.span(3, span_name="chat_model.generate", attributes={}),
            self.span(4, span_name="agent.execution", attributes={}),
            self.span(5, span_name="ChatModel.chat", attributes={"llm.request.type": "chat"}),
            self.span(6, span_name="tool.execution", attributes={}),
        ]
        cases = [
            (["chat"], ["span-1", "span-3"]),
            (["invoke_agent"], ["span-2", "span-4"]),
            (["chat", "invoke_agent"], ["span-1", "span-2", "span-3", "span-4"]),
            (["execute_tool"], []),
            ([], []),
        ]
        for operations, expected_ids in cases:
            with self.subTest(operations=operations):
                predicate = operation_query("aidev", operations)
                self.assertEqual([span["span_id"] for span in spans if self.matches(span, predicate)], expected_ids)

    def test_aidev_preview_includes_legacy_agent_and_model_without_request_type(self):
        spans = [
            self.span(1, span_name="agent.execution", attributes={}),
            self.span(2, span_name="chat_model.generate", attributes={}),
            self.span(3, span_name="ChatModel.chat", attributes={"llm.request.type": "chat"}),
        ]
        with mock.patch.object(self.query, "_query_list", side_effect=self.execute(spans)):
            self.assertEqual(self.preview(["trace-1"], "aidev", "input"), [spans[0]])
            self.assertEqual(self.preview(["trace-1"], "aidev", "output"), [spans[1]])

    def test_preview_does_not_require_message_fields(self):
        span = self.span(1)
        with mock.patch.object(self.query, "_query_list", side_effect=self.execute([span])):
            self.assertEqual(self.preview(["trace-1"], "default", "input"), [span])
            self.assertEqual(self.preview(["trace-1"], "default", "output"), [span])

    def test_aidev_output_preview_skips_later_ending_agent_execution(self):
        from apm_web.llm.resources import ListTracesResource

        for standard in (True, False):
            with self.subTest(standard=standard):
                wrapper = self.span(
                    1,
                    span_name="agent.execution",
                    end_time=1000,
                    attributes={"agent.session.input": "question"},
                )
                answer = self.span(
                    2,
                    span_name="invoke_agent demo" if standard else "chat_model.generate",
                    end_time=900,
                    attributes={"llm.output": "answer"},
                )
                if standard:
                    wrapper["attributes"]["gen_ai.conversation.id"] = "session-1"
                    answer["attributes"] = {
                        "gen_ai.operation.name": "invoke_agent",
                        "gen_ai.output.messages": [
                            {"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}
                        ],
                    }
                entity_set = mock.Mock(service_names=["agent-service"])
                entity_set.get_system.return_value = {"is_support_llm": True, "product": "aidev"}
                with (
                    mock.patch("apm_web.llm.resources.Application.objects.get"),
                    mock.patch("apm_web.llm.resources.EntitySet", return_value=entity_set),
                    mock.patch("apm_web.llm.resources.get_query", return_value=self.query),
                    mock.patch.object(self.query, "query_group_list", return_value=["trace-1"]),
                    mock.patch.object(self.query, "query_group_trace_list", return_value=[{"trace_id": "trace-1"}]),
                    mock.patch.object(self.query, "query_field_aggregated_group", return_value=[]),
                    mock.patch.object(self.query, "query_trace_errors", return_value=[]),
                    mock.patch.object(self.query, "_query_list", side_effect=self.execute([wrapper, answer])),
                ):
                    result = ListTracesResource().request(
                        {
                            "bk_biz_id": 11,
                            "app_name": "demo",
                            "service_name": "agent-service",
                            "start_time": 1,
                            "end_time": 2,
                        }
                    )
                self.assertEqual(result["items"][0]["input"], "question")
                self.assertEqual(result["items"][0]["output"], "answer")

    def test_collapsed_product_spans_can_be_converted_by_adapters(self):
        from apm_web.llm.adapter import adapt_spans
        from apm_web.llm.builders.summary import TraceSummary

        standard = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.input.messages": [{"role": "user", "parts": [{"type": "text", "content": "question"}]}],
            "gen_ai.output.messages": [{"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}],
        }
        cases = [
            ("default", "invoke_agent", standard, []),
            ("aidev", "invoke_agent", standard, []),
            (
                "aidev",
                "chat_model.generate",
                {"llm.request.type": "chat", "llm.input": "question", "llm.output": "answer"},
                [],
            ),
            (
                "agentlens",
                "invoke_agent",
                {"gen_ai.span.kind": "AGENT", "input.value": "question", "output.value": "answer"},
                [],
            ),
            (
                "langfuse",
                "invoke_agent",
                {
                    "langfuse.observation.type": "agent",
                    "langfuse.observation.input": "question",
                    "langfuse.observation.output": "answer",
                },
                [],
            ),
            (
                "galileo",
                "invoke_agent",
                {"gen_ai.operation.name": "invoke_agent"},
                [
                    {
                        "name": "gen_ai.invoke_agent_request",
                        "attributes": {"message.detail": "question", "debug": "large"},
                    },
                    {
                        "name": "gen_ai.invoke_agent_response",
                        "attributes": {"message.detail": "answer", "debug": "large"},
                    },
                ],
            ),
        ]
        for product, span_name, attributes, events in cases:
            with self.subTest(product=product, span_name=span_name):
                span = self.span(
                    1, span_name=span_name, attributes={**attributes, "large_debug": "x" * 10000}, events=events
                )
                entity_set = mock.Mock(service_names=["agent-service"])
                entity_set.get_system.return_value = {"is_support_llm": True, "product": product}
                with mock.patch.object(self.query, "_query_list", side_effect=self.execute([span])):
                    inputs = self.preview(["trace-1"], product, "input")
                    outputs = self.preview(["trace-1"], product, "output")
                self.assertEqual(inputs, [span])
                self.assertEqual(outputs, [span])
                self.assertEqual(TraceSummary._trace_previews(adapt_spans(inputs, entity_set))[0], "question", product)
                self.assertEqual(TraceSummary._trace_previews(adapt_spans(outputs, entity_set))[1], "answer", product)

    def test_error_query_only_returns_collapsed_trace_id_and_status(self):
        spans = [
            self.span(1),
            self.span(2, status={"code": 2}),
            self.span(3, status={"code": 2}),
            self.span(4, trace_id="trace-2"),
        ]
        with mock.patch.object(self.query, "_query_list", side_effect=self.execute(spans)) as query_list:
            errors = self.query.query_trace_errors(["trace-1", "trace-2"])
        self.assertEqual(errors, [{"trace_id": "trace-1", "status": {"code": 2}}])
        query_list.assert_called_once()
        self.assertEqual(query_list.call_args.args[0][0].query.select, ["trace_id", "status.code"])

    def test_multiple_tables_are_queried_together(self):
        source = TraceDatasourceTarget.build(
            bk_biz_id=11, app_name="demo", table_id="11_bkapm.trace_demo_second", retention=7
        )
        self.query = LLMQuery([*self.query.data_sources, source])
        for call in (
            lambda: self.preview(["trace-1"], "default", "output"),
            lambda: self.query.query_trace_errors(["trace-1"]),
        ):
            with mock.patch.object(self.query, "_query_list", return_value=[]) as query_list:
                call()
            query_list.assert_called_once()
            self.assertEqual(len(query_list.call_args.args[0]), 2)

    def test_query_group_trace_list_with_possible_group_fields(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        records = [{"trace_id": "trace-1"}, {"trace_id": "trace-2"}]
        group_fields = ("attributes.gen_ai.conversation.id", "attributes.session.id")

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "_query_list", return_value=records) as query_list,
        ):
            result = self.query.query_group_trace_list(
                group_field="attributes.gen_ai.conversation.id",
                group_ids=["session-1"],
                possible_group_fields=group_fields,
                extra_fields=["resource.service.name", OtlpKey.TRACE_ID],
            )

        self.assertEqual(result, records)
        build_queries.assert_called_once_with()
        query_builder.filter.assert_called_once_with(
            Q(**{"attributes.gen_ai.conversation.id__eq": ["session-1"]})
            | Q(**{"attributes.session.id__eq": ["session-1"]})
        )
        query_builder.distinct.assert_called_once_with(OtlpKey.TRACE_ID)
        query_builder.values.assert_called_once_with(
            "attributes.gen_ai.conversation.id", OtlpKey.TRACE_ID, "resource.service.name"
        )
        query_list.assert_called_once_with([query_builder], None, None, 0, 10000)
