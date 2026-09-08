from unittest import TestCase, mock

from django.db.models import Q

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.llm.constants import CONVERSATION_QUERY_FIELDS
from apm_web.llm.query import LLMQuery, get_span_field_value


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

    def test_query_group_buckets_builds_reference_query(self):
        query_builder = mock.Mock()
        query_builder.alias.return_value = query_builder
        query_builder.metric.return_value = query_builder
        query_builder.group_by.return_value = query_builder
        query_builder.order_by.return_value = query_builder
        queryset = mock.Mock()
        queryset.expression.return_value = queryset
        queryset.time_agg.return_value = queryset
        queryset.instant.return_value = queryset
        queryset.limit.return_value = queryset
        group_field = "attributes.gen_ai.session.id"
        standard_field = "attributes.gen_ai.conversation.id"
        filters = [{"key": "resource.service.name", "operator": "equal", "value": ["agent-service"]}]
        records = [{group_field: "conversation-1", "_result_": 2}]

        with (
            mock.patch.object(self.query, "build_queries", return_value=[query_builder]) as build_queries,
            mock.patch.object(self.query, "get_qs", return_value=queryset) as get_qs,
            mock.patch.object(self.query, "_add_query", return_value=records) as add_query,
        ):
            result = self.query._query_group_buckets(
                start_time=1,
                end_time=2,
                group_field=group_field,
                limit=20,
                filters=filters,
                query_string="_exists_:attributes.gen_ai.operation.name",
                exclude_fields=(standard_field,),
            )

        self.assertEqual(result, records)
        build_queries.assert_called_once_with(
            filters,
            "(_exists_:attributes.gen_ai.operation.name) AND "
            "(_exists_:attributes.gen_ai.session.id) AND "
            "(NOT _exists_:attributes.gen_ai.conversation.id)",
        )
        query_builder.alias.assert_called_once_with("a")
        query_builder.metric.assert_called_once_with(field="end_time", method="MAX", alias="a")
        query_builder.group_by.assert_called_once_with(group_field)
        query_builder.order_by.assert_called_once_with("_value desc", f"{group_field} asc")
        get_qs.assert_called_once_with(1, 2)
        queryset.expression.assert_called_once_with("a")
        queryset.time_agg.assert_called_once_with(False)
        queryset.instant.assert_called_once_with()
        queryset.limit.assert_called_once_with(20)
        add_query.assert_called_once_with(queryset, [query_builder])

    def test_query_group_aggregate_list_merges_candidate_fields_before_paging(self):
        standard_field = "attributes.gen_ai.conversation.id"
        alias_field = "attributes.gen_ai.session.id"
        with mock.patch.object(
            self.query,
            "_query_group_buckets",
            side_effect=[
                [
                    {standard_field: " ", "_result_": 200},
                    {standard_field: "conversation-1", "_result_": 100},
                    {standard_field: "shared", "_result_": 80},
                ],
                [
                    {"attributes": {"gen_ai.session.id": "shared"}, "_result_": 120},
                    {"attributes": {"gen_ai.session.id": "conversation-2"}, "_result_": 90},
                ],
            ],
        ) as query_group_buckets:
            group_ids = self.query.query_group_aggregate_list(
                start_time=1,
                end_time=2,
                group_fields=(standard_field, alias_field),
                offset=1,
                limit=2,
                filters=[],
            )

        self.assertEqual(group_ids, ["conversation-1", "conversation-2"])
        self.assertEqual(
            query_group_buckets.call_args_list,
            [
                mock.call(
                    start_time=1,
                    end_time=2,
                    group_field=standard_field,
                    limit=3,
                    filters=[],
                    query_string=None,
                    exclude_fields=(),
                ),
                mock.call(
                    start_time=1,
                    end_time=2,
                    group_field=alias_field,
                    limit=3,
                    filters=[],
                    query_string=None,
                    exclude_fields=(standard_field,),
                ),
            ],
        )

    def test_query_group_list_reads_normalized_record(self):
        group_field = "attributes.gen_ai.conversation.id"
        with mock.patch.object(
            self.query,
            "_query_list",
            return_value=[
                {"attributes": {"gen_ai.conversation.id": "conversation-2"}},
                {"attributes": {"gen_ai.conversation.id": "conversation-1"}},
            ],
        ):
            group_ids = self.query.query_group_list(
                start_time=1,
                end_time=2,
                group_field=group_field,
                offset=0,
                limit=20,
                filters=[],
            )

        self.assertEqual(group_ids, ["conversation-2", "conversation-1"])

    def test_get_span_field_value_supports_flat_and_normalized_records(self):
        field = "attributes.gen_ai.conversation.id"

        self.assertEqual(get_span_field_value({field: "flat"}, field), "flat")
        self.assertEqual(get_span_field_value({"attributes": {"gen_ai.conversation.id": "nested"}}, field), "nested")

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

    def test_query_group_trace_list(self):
        query_builder = mock.Mock()
        query_builder.filter.return_value = query_builder
        query_builder.distinct.return_value = query_builder
        query_builder.values.return_value = query_builder
        records = [
            {"attributes": {"session.id": "session-1"}, "trace_id": "trace-1"},
            {"attributes": {"session.id": "session-1"}, "trace_id": "trace-2"},
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

    def test_keyword_logic_filter(self):
        value = ["search-text"]

        result = self.query._build_filters([{"key": "keyword", "operator": "logic", "value": value}])

        expected = (
            Q(**{f"{OtlpKey.TRACE_ID}__eq": value})
            | Q(**{f"{OtlpKey.SPAN_ID}__eq": value})
            | Q(**{f"{OtlpKey.get_attributes_key('user.id')}__include": value})
        )
        conversation_fields = (
            "attributes.gen_ai.conversation.id",
            "attributes.gen_ai.session.id",
            "attributes.agent.session.session_code",
            "attributes.gen_ai.session_id",
        )
        self.assertEqual(CONVERSATION_QUERY_FIELDS, conversation_fields)
        for conversation_field in conversation_fields:
            expected |= Q(**{f"{conversation_field}__include": value})
        self.assertEqual(result, expected)
